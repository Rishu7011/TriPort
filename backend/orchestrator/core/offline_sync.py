"""
Orchestrator Offline Sync Mechanism (Module 7).

Features:
  - Local SQLite buffer (WAL mode) for all checkpoint types during connectivity blackouts.
  - is_online() — fast DNS/TCP connectivity probe to Supabase host.
  - Periodic background asyncio task pushing queued screening events to central PostgreSQL.
  - Retry tracking: records failing 5+ times are skipped to avoid infinite loops.
  - Tracks 'mode: offline' in all audit metadata generated during disconnects.
"""

import asyncio
import json
import socket
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.logging_config import get_logger

logger = get_logger("orchestrator.offline_sync")

# SQLite lives next to the backend data directory — survives restarts
DEFAULT_OFFLINE_DB = Path(__file__).resolve().parents[2] / "data" / "orchestrator_offline.db"

# How often the background loop tries to flush the queue (seconds)
SYNC_INTERVAL_SECONDS = 30

# Max retry attempts before a record is permanently skipped
MAX_RETRY_COUNT = 5


# ---------------------------------------------------------------------------
# Connectivity Probe
# ---------------------------------------------------------------------------

def _extract_supabase_host() -> str:
    """Extract the hostname from DATABASE_URL for connectivity probing."""
    try:
        from backend.config import settings
        url = settings.database_url
        # e.g. postgresql+psycopg://user:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
        host_part = url.split("@")[-1].split("/")[0]
        host = host_part.split(":")[0]
        return host
    except Exception:
        return "aws-0-ap-south-1.pooler.supabase.com"


def is_online(timeout: float = 3.0) -> bool:
    """
    Fast TCP connectivity probe — returns True if Supabase host is reachable.
    Uses socket.getaddrinfo (DNS) which is fast and has no side effects.
    """
    host = _extract_supabase_host()
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo(host, 443)
        return True
    except (socket.gaierror, OSError):
        return False


# ---------------------------------------------------------------------------
# SQLite Offline Queue
# ---------------------------------------------------------------------------

class OrchestratorOfflineStore:
    """Thread-safe SQLite queue for offline screening events."""

    def __init__(self, db_path: Path = DEFAULT_OFFLINE_DB):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pending_screenings (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT    NOT NULL UNIQUE,
                        checkpoint_type TEXT,
                        payload     JSON    NOT NULL,
                        created_at  TEXT    NOT NULL,
                        synced      INTEGER DEFAULT 0,
                        retry_count INTEGER DEFAULT 0,
                        last_error  TEXT
                    );
                    """
                )
                # Add columns to existing DBs (safe no-op if already present)
                for col_sql in [
                    "ALTER TABLE pending_screenings ADD COLUMN retry_count INTEGER DEFAULT 0",
                    "ALTER TABLE pending_screenings ADD COLUMN last_error TEXT",
                    "ALTER TABLE pending_screenings ADD COLUMN live_image_url TEXT",
                    "ALTER TABLE pending_screenings ADD COLUMN inspection_status TEXT",
                ]:
                    try:
                        conn.execute(col_sql)
                    except sqlite3.OperationalError:
                        pass  # Column already exists
                conn.commit()

    def record_offline_screening(
        self,
        document_id: str,
        checkpoint_type: str,
        result_payload: dict[str, Any],
    ) -> None:
        """Buffer a pipeline screening result locally when central Postgres is unreachable."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pending_screenings
                    (document_id, checkpoint_type, payload, created_at, synced, retry_count)
                    VALUES (?, ?, ?, ?, 0, 0)
                    """,
                    (document_id, checkpoint_type, json.dumps(result_payload), now_iso),
                )
                conn.commit()
        logger.info(
            "offline_scan_queued_to_sqlite",
            document_id=document_id,
            checkpoint_type=checkpoint_type,
            db_path=str(self.db_path),
        )

    def get_pending_screenings(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve unsynced screening records that haven't exceeded max retries."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    """
                    SELECT id, document_id, checkpoint_type, payload, created_at, retry_count
                    FROM pending_screenings
                    WHERE synced = 0 AND retry_count < ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (MAX_RETRY_COUNT, limit),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "document_id": r[1],
                        "checkpoint_type": r[2],
                        "payload": json.loads(r[3]),
                        "created_at": r[4],
                        "retry_count": r[5],
                    }
                    for r in rows
                ]

    def mark_synced(self, record_ids: list[int]) -> None:
        """Delete successfully synced records from SQLite (purge-after-sync)."""
        if not record_ids:
            return
        placeholders = ",".join("?" * len(record_ids))
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    f"DELETE FROM pending_screenings WHERE id IN ({placeholders})",
                    record_ids,
                )
                conn.commit()
        logger.info("offline_screenings_purged_from_sqlite", count=len(record_ids))

    def increment_retry(self, record_id: int, error: str) -> None:
        """Increment retry count and store last error for a failed sync attempt."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "UPDATE pending_screenings SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                    (error[:500], record_id),
                )
                conn.commit()

    def pending_count(self) -> int:
        """Return total number of unsynced, non-exhausted records."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM pending_screenings WHERE synced = 0 AND retry_count < ?",
                    (MAX_RETRY_COUNT,),
                )
                return cursor.fetchone()[0]

    def get_offline_record(self, document_id: str) -> "dict[str, Any] | None":
        """Retrieve the stored payload dict for a given document_id from SQLite."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT payload FROM pending_screenings WHERE document_id = ? LIMIT 1",
                    (document_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                try:
                    return json.loads(row[0])
                except Exception:
                    return None

    def update_offline_screening_stage2(
        self,
        document_id: str,
        stage2_payload: "dict[str, Any]",
        live_image_url: "str | None",
        inspection_status: str,
    ) -> None:
        """
        Merge Stage 2 biometric/risk results into the existing offline record.
        Overwrites payload, live_image_url, and inspection_status columns.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Merge with existing payload so Stage 1 data is preserved
                cursor = conn.execute(
                    "SELECT payload FROM pending_screenings WHERE document_id = ? LIMIT 1",
                    (document_id,),
                )
                row = cursor.fetchone()
                merged: dict[str, Any] = {}
                if row:
                    try:
                        merged = json.loads(row[0])
                    except Exception:
                        merged = {}
                merged.update(stage2_payload)
                merged["inspection_status"] = inspection_status
                merged["live_image_url"] = live_image_url
                conn.execute(
                    """
                    UPDATE pending_screenings
                    SET payload = ?, live_image_url = ?, inspection_status = ?
                    WHERE document_id = ?
                    """,
                    (json.dumps(merged), live_image_url, inspection_status, document_id),
                )
                conn.commit()
        logger.info(
            "offline_stage2_updated",
            document_id=document_id,
            inspection_status=inspection_status,
        )

    def record_offline_decision(
        self,
        document_id: str,
        decision: str,
        notes: "str | None" = None,
    ) -> None:
        """
        Record an officer decision into the offline pending_screenings row.
        Updates inspection_status based on decision and stores decision/notes
        in the payload dict for later sync.
        """
        decision_to_status = {
            "approve": "approved",
            "reject": "rejected",
            "flag": "secondary_inspection",
            "escalate": "secondary_inspection",
        }
        new_status = decision_to_status.get(decision.lower(), decision)
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT payload FROM pending_screenings WHERE document_id = ? LIMIT 1",
                    (document_id,),
                )
                row = cursor.fetchone()
                payload: dict[str, Any] = {}
                if row:
                    try:
                        payload = json.loads(row[0])
                    except Exception:
                        payload = {}
                payload["officer_decision"] = decision
                payload["officer_notes"] = notes
                payload["inspection_status"] = new_status
                conn.execute(
                    """
                    UPDATE pending_screenings
                    SET payload = ?, inspection_status = ?
                    WHERE document_id = ?
                    """,
                    (json.dumps(payload), new_status, document_id),
                )
                conn.commit()
        logger.info(
            "offline_decision_recorded",
            document_id=document_id,
            decision=decision,
            new_status=new_status,
        )


# ---------------------------------------------------------------------------
# Module-Level Singleton
# ---------------------------------------------------------------------------

_store = OrchestratorOfflineStore()


def get_offline_store() -> OrchestratorOfflineStore:
    return _store


# ---------------------------------------------------------------------------
# Sync Worker — Flushes SQLite Queue → Supabase PostgreSQL
# ---------------------------------------------------------------------------


async def _upload_data_url_to_storage(data_url: str | None, scan_id: str, label: str) -> str | None:
    """
    Decode a base64 data: URL and upload it to the appropriate Supabase Storage bucket.
    Returns the signed/public URL on success, or None on failure.
    """
    if not data_url or not str(data_url).startswith("data:"):
        return data_url  # Already a real URL or empty

    import base64
    from backend.orchestrator.storage.supabase_storage import (
        upload_document_image, upload_face_crop_image, upload_live_capture_image,
    )

    try:
        # Strip header: "data:image/jpeg;base64,<data>"
        header, b64_data = data_url.split(",", 1)
        img_bytes = base64.b64decode(b64_data)

        if label == "doc_image":
            return await upload_document_image(img_bytes, scan_id)
        elif label == "face_crop":
            return await upload_face_crop_image(img_bytes, scan_id)
        elif label == "live_capture":
            return await upload_live_capture_image(img_bytes, scan_id)
    except Exception as exc:
        logger.warning(
            "offline_sync_image_upload_failed",
            label=label,
            scan_id=scan_id,
            error=str(exc)[:200],
        )
    return None


async def sync_offline_screenings_to_postgres() -> int:
    """
    Flush buffered SQLite screenings to central PostgreSQL (Supabase).
    Returns the number of records successfully synced.
    Called by the background loop every SYNC_INTERVAL_SECONDS.
    """
    store = get_offline_store()
    pending = store.get_pending_screenings()
    if not pending:
        return 0

    logger.info("offline_sync_attempt_started", pending_count=len(pending))

    # Lazily import to avoid circular imports
    from backend.orchestrator.db.session import get_session_factory
    from backend.orchestrator.db.models import ScanEvent
    from backend.orchestrator.schemas.pipeline import PipelineResult

    synced_ids: list[int] = []

    try:
        factory = await get_session_factory()
    except Exception as exc:
        logger.warning("offline_sync_db_unavailable", error=str(exc)[:200])
        return 0

    for item in pending:
        doc_id = item["document_id"]
        record_id = item["id"]
        payload = item["payload"]
        checkpoint_type = item.get("checkpoint_type", "airport")

        try:
            async with factory() as db:
                import uuid as _uuid
                from sqlalchemy import delete as _sa_delete

                # Check if already exists (idempotent upsert)
                try:
                    scan_uuid = _uuid.UUID(doc_id)
                except ValueError:
                    scan_uuid = _uuid.uuid4()

                from backend.orchestrator.db.models import (
                    ExtractedField, FaceVerificationResult,
                    OfficerDecision, RiskResult, TamperingResult,
                )

                existing = await db.get(ScanEvent, scan_uuid)

                # ── Upload buffered base64 images to Supabase Storage ──────
                doc_image_url = await _upload_data_url_to_storage(
                    payload.get("doc_image_data_url"), doc_id, "doc_image"
                )
                face_crop_url = await _upload_data_url_to_storage(
                    payload.get("doc_face_crop_data_url"), doc_id, "face_crop"
                )
                live_image_url = await _upload_data_url_to_storage(
                    payload.get("live_image_data_url") or payload.get("live_image_url"),
                    doc_id, "live_capture"
                )

                if existing is None:
                    event = ScanEvent(
                        id=scan_uuid,
                        checkpoint_id=None,
                        officer_id=None,
                        document_type=payload.get("document_type", "passport"),
                        inspection_status=payload.get("inspection_status", "standard_clearance"),
                        doc_image_url=doc_image_url,
                        doc_face_crop_url=face_crop_url,
                        live_image_url=live_image_url,
                        pipeline_snapshot=payload,
                        degraded=payload.get("degraded", False),
                    )
                    db.add(event)
                else:
                    existing.pipeline_snapshot = payload
                    existing.inspection_status = payload.get("inspection_status", existing.inspection_status)
                    # Backfill image URLs if they were missing on the initial upsert
                    if doc_image_url and not existing.doc_image_url:
                        existing.doc_image_url = doc_image_url
                    if face_crop_url and not existing.doc_face_crop_url:
                        existing.doc_face_crop_url = face_crop_url
                    if live_image_url and not existing.live_image_url:
                        existing.live_image_url = live_image_url

                # ── Sync extracted_fields ──────────────────────────────────
                await db.execute(_sa_delete(ExtractedField).where(ExtractedField.scan_event_id == scan_uuid))
                extraction = payload.get("extraction") or {}
                for f in extraction.get("fields") or []:
                    src = f.get("source") or f.get("extraction_method") or "ocr"
                    if hasattr(src, "value"):
                        src = src.value
                    db.add(ExtractedField(
                        scan_event_id=scan_uuid,
                        field_name=f.get("field_name", ""),
                        field_value=str(f.get("field_value")) if f.get("field_value") is not None else None,
                        confidence=float(f.get("confidence")) if f.get("confidence") is not None else None,
                        source=str(src),
                    ))

                # ── Sync tampering_results ─────────────────────────────────
                tampering = payload.get("tampering") or {}
                if tampering:
                    await db.execute(_sa_delete(TamperingResult).where(TamperingResult.scan_event_id == scan_uuid))
                    db.add(TamperingResult(
                        scan_event_id=scan_uuid,
                        flagged=tampering.get("flagged", False),
                        composite_score=tampering.get("composite_score") or tampering.get("tampering_score"),
                        checks=tampering.get("checks") or tampering.get("results") or [],
                        ela_heatmap_url=None,
                    ))

                # ── Sync face_verification_results ─────────────────────────
                face = payload.get("face") or {}
                if face:
                    await db.execute(_sa_delete(FaceVerificationResult).where(FaceVerificationResult.scan_event_id == scan_uuid))
                    oto = face.get("one_to_one") or {}
                    dedup = face.get("dedup") or {}
                    liveness = face.get("liveness") or {}
                    db.add(FaceVerificationResult(
                        scan_event_id=scan_uuid,
                        one_to_one_matched=oto.get("matched"),
                        match_score=oto.get("match_score"),
                        cosine_similarity=oto.get("cosine_similarity"),
                        dedup_has_duplicates=dedup.get("has_duplicates"),
                        dedup_hits=dedup.get("hits") or [],
                        liveness_is_live=liveness.get("is_live"),
                        liveness_score=liveness.get("liveness_score"),
                        bypassed=face.get("bypassed", False),
                        bypassed_reason=face.get("bypassed_reason"),
                    ))

                # ── Sync risk_results ──────────────────────────────────────
                risk = payload.get("risk_score") or {}
                if risk:
                    await db.execute(_sa_delete(RiskResult).where(RiskResult.scan_event_id == scan_uuid))
                    band = risk.get("band")
                    if hasattr(band, "value"):
                        band = band.value
                    db.add(RiskResult(
                        scan_event_id=scan_uuid,
                        score=risk.get("score"),
                        band=str(band) if band else None,
                        reasons=risk.get("reasons") or [],
                        sub_scores=risk.get("sub_scores"),
                    ))

                # ── Sync officer_decisions ─────────────────────────────────
                decision_str = payload.get("officer_decision")
                if decision_str:
                    db.add(OfficerDecision(
                        scan_event_id=scan_uuid,
                        officer_id=None,
                        decision=decision_str,
                        notes=payload.get("officer_notes"),
                    ))

                await db.commit()
                synced_ids.append(record_id)
                logger.info("offline_record_synced", document_id=doc_id)

        except Exception as exc:
            error_str = str(exc)
            logger.warning(
                "offline_sync_record_failed",
                document_id=doc_id,
                retry_count=item["retry_count"],
                error=error_str[:300],
            )
            store.increment_retry(record_id, error_str)

    if synced_ids:
        store.mark_synced(synced_ids)

    return len(synced_ids)


# ---------------------------------------------------------------------------
# Background Loop — starts once on server startup via main.py lifespan
# ---------------------------------------------------------------------------

_sync_task: asyncio.Task | None = None


async def _sync_loop() -> None:
    """Asyncio background task: wakes every SYNC_INTERVAL_SECONDS and flushes queue."""
    logger.info(
        "offline_sync_background_loop_started",
        interval_seconds=SYNC_INTERVAL_SECONDS,
    )
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        store = get_offline_store()
        count = store.pending_count()
        if count == 0:
            continue  # Nothing to do — skip probe entirely

        if not is_online():
            logger.debug("offline_sync_skipped_no_connectivity", pending=count)
            continue

        try:
            synced = await sync_offline_screenings_to_postgres()
            if synced > 0:
                logger.info(
                    "offline_sync_batch_completed",
                    synced=synced,
                    remaining=store.pending_count(),
                )
        except Exception as exc:
            logger.warning("offline_sync_loop_iteration_error", error=str(exc)[:300])


def start_sync_background_loop() -> None:
    """
    Spawn the background sync asyncio task.
    Safe to call multiple times — only one task is created.
    Must be called from within a running asyncio event loop (e.g. FastAPI lifespan).
    """
    global _sync_task
    if _sync_task is not None and not _sync_task.done():
        return  # Already running
    _sync_task = asyncio.create_task(_sync_loop(), name="offline_sync_loop")
    logger.info("offline_sync_task_spawned")
