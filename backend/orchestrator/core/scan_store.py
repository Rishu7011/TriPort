"""
Scan Store — persistent database-backed replacement for the old in-memory store.

All functions are now async and accept an AsyncSession from SQLAlchemy.
The in-memory dicts and threading.Lock have been removed entirely.
Data lives in Supabase (scan_events + child tables + object storage).

Function signatures preserved where possible so call-sites require minimal changes.
Image data_urls are replaced by Supabase Storage URLs.

Blacklist/watchlist functions redirect to watchlist_entries CRUD (see below).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.orchestrator.db.models import (
    ExtractedField,
    FaceVerificationResult,
    RiskResult,
    ScanEvent,
    TamperingResult,
    WatchlistEntry,
)
from backend.orchestrator.schemas.pipeline import PipelineResult
from backend.orchestrator.storage import supabase_storage
from backend.logging_config import get_logger

logger = get_logger("orchestrator.scan_store")

# In-memory LRU cache for active document crops (avoids remote Storage re-downloads in Stage 2)
_RECENT_DOC_CROPS: dict[str, bytes] = {}
_RECENT_SCAN_RECORDS: dict[str, Any] = {}
_MAX_CACHE_SIZE = 256


def set_cached_doc_crop(document_id: str, crop_bytes: bytes | None) -> None:
    if not crop_bytes:
        return
    if len(_RECENT_DOC_CROPS) >= _MAX_CACHE_SIZE:
        oldest_key = next(iter(_RECENT_DOC_CROPS))
        _RECENT_DOC_CROPS.pop(oldest_key, None)
    _RECENT_DOC_CROPS[str(document_id)] = crop_bytes


def get_cached_doc_crop(document_id: str) -> bytes | None:
    return _RECENT_DOC_CROPS.get(str(document_id))


def set_cached_scan(document_id: str, record: Any) -> None:
    if len(_RECENT_SCAN_RECORDS) >= _MAX_CACHE_SIZE:
        oldest_key = next(iter(_RECENT_SCAN_RECORDS))
        _RECENT_SCAN_RECORDS.pop(oldest_key, None)
    _RECENT_SCAN_RECORDS[str(document_id)] = record


def get_cached_scan(document_id: str) -> Any | None:
    return _RECENT_SCAN_RECORDS.get(str(document_id))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# ScanRecord — thin view model reconstructed from DB rows
# ---------------------------------------------------------------------------

@dataclass
class ScanRecord:
    """
    View model returned by store functions.
    Mirrors the old in-memory dataclass API so call-sites change minimally.
    Images are now Supabase Storage URLs (or None), never base64 data URLs.
    """
    document_id: str
    document_type: str
    checkpoint_id: str | None
    uploaded_at: str
    pipeline: PipelineResult
    doc_image_data_url: str | None = None      # actually a Storage URL now (name kept for compat)
    doc_face_crop_data_url: str | None = None  # actually a Storage URL now
    live_image_data_url: str | None = None     # actually a Storage URL now
    inspection_status: str = "standard_clearance"


@dataclass
class BlacklistEntryRecord:
    """View model for a watchlist_entries row."""
    id: str
    document_number: str | None
    full_name: str | None
    date_of_birth: str | None
    nationality: str | None
    severity: str
    reason: str | None
    created_at: str


# ---------------------------------------------------------------------------
# Internal helper — reconstruct ScanRecord from a ScanEvent ORM row
# ---------------------------------------------------------------------------

def _normalize_storage_url(url: str | None) -> str | None:
    if not url:
        return None
    if ".supabase.co/object/sign/" in url:
        return url.replace(".supabase.co/object/sign/", ".supabase.co/storage/v1/object/sign/")
    return url


def _scan_event_to_record(row: ScanEvent) -> ScanRecord:
    """Reconstruct a ScanRecord view model from a loaded ScanEvent row."""
    pipeline: PipelineResult | None = None
    snapshot = row.__dict__.get("pipeline_snapshot")
    if snapshot:
        try:
            pipeline = PipelineResult.model_validate(snapshot)
        except Exception:
            pipeline = None

    if pipeline is None:
        # Minimal fallback — when snapshot is deferred or unparsed
        pipeline = PipelineResult(document_id=str(row.id))

    return ScanRecord(
        document_id=str(row.id),
        document_type=row.document_type,
        checkpoint_id=str(row.checkpoint_id) if row.checkpoint_id else None,
        uploaded_at=row.uploaded_at.isoformat() if row.uploaded_at else _utc_now_iso(),
        pipeline=pipeline,
        doc_image_data_url=_normalize_storage_url(row.doc_image_url),
        doc_face_crop_data_url=_normalize_storage_url(row.doc_face_crop_url),
        live_image_data_url=_normalize_storage_url(row.live_image_url),
        inspection_status=row.inspection_status,
    )



# ---------------------------------------------------------------------------
# save_scan
# ---------------------------------------------------------------------------

async def save_scan(
    db: AsyncSession,
    pipeline: PipelineResult,
    *,
    document_type: str,
    checkpoint_id: str | None,
    image_bytes: bytes,
    doc_face_crop_bytes: bytes | None = None,
    live_image_bytes: bytes | None = None,
    inspection_status: str = "standard_clearance",
    officer_id: str | None = None,
) -> ScanRecord:
    """
    Persist a completed screening run to Supabase.

    Steps:
    1. Extract face crop if not provided.
    2. Upload document image + face crop + live image to Supabase Storage.
    3. Insert/upsert scan_events row with pipeline snapshot.
    4. Insert/upsert extracted_fields EAV rows.
    5. Insert/upsert child table rows (tampering, risk, face).
    6. Return a ScanRecord view model.
    """
    doc_id = pipeline.document_id

    # ── 1. Extract face crop if not provided ────────────────────────────────
    if doc_face_crop_bytes is None:
        try:
            from backend.face_service.core.embedding import extract_face_crop_bytes
            c_bytes, found = extract_face_crop_bytes(image_bytes)
            if found and c_bytes:
                doc_face_crop_bytes = c_bytes
        except Exception:
            pass

    set_cached_doc_crop(doc_id, doc_face_crop_bytes or image_bytes)

    # ── 2. Immediate Lightweight Data URLs for instant client display (0ms remote storage wait) ──
    import base64
    import io
    from PIL import Image

    def _to_preview_data_url(raw_b: bytes | None, max_dim: int = 1000) -> str | None:
        if not raw_b:
            return None
        try:
            with Image.open(io.BytesIO(raw_b)) as im:
                im = im.convert("RGB")
                w, h = im.size
                if max(w, h) > max_dim:
                    scale = max_dim / float(max(w, h))
                    im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=85)
                return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
        except Exception:
            return f"data:image/jpeg;base64,{base64.b64encode(raw_b[:500000]).decode('ascii')}"

    immediate_doc_url = _to_preview_data_url(image_bytes, max_dim=1000)
    immediate_crop_url = _to_preview_data_url(doc_face_crop_bytes, max_dim=600)
    immediate_live_url = _to_preview_data_url(live_image_bytes, max_dim=800)

    # ── 3. Resolve UUID for scan_event_id and checkpoint_id ─────────────────
    try:
        scan_id = uuid.UUID(doc_id)
    except ValueError:
        scan_id = uuid.uuid4()
        logger.warning("save_scan_invalid_uuid", original=doc_id, assigned=str(scan_id))

    cp_uuid = None
    if checkpoint_id:
        try:
            cp_uuid = uuid.UUID(checkpoint_id)
        except ValueError:
            pass  # checkpoint_id is "CP-DEL-T3" legacy string — ignore, FK will be NULL

    # ── 4. Launch remote Supabase Storage upload asynchronously in background ─
    async def _safe_upload_doc():
        try:
            return await supabase_storage.upload_document_image(image_bytes, doc_id)
        except Exception as exc:
            logger.warning("storage_upload_doc_failed", doc_id=doc_id, error=str(exc))
            return None

    async def _safe_upload_crop():
        if not doc_face_crop_bytes:
            return None
        try:
            return await supabase_storage.upload_face_crop_image(doc_face_crop_bytes, doc_id)
        except Exception as exc:
            logger.warning("storage_upload_crop_failed", doc_id=doc_id, error=str(exc))
            return None

    async def _safe_upload_live():
        if not live_image_bytes:
            return None
        try:
            return await supabase_storage.upload_live_capture_image(live_image_bytes, doc_id)
        except Exception as exc:
            logger.warning("storage_upload_live_failed", doc_id=doc_id, error=str(exc))
            return None

    async def _background_storage_upload(target_scan_id: uuid.UUID):
        try:
            d_url, c_url, l_url = await asyncio.gather(
                _safe_upload_doc(),
                _safe_upload_crop(),
                _safe_upload_live(),
            )
            await asyncio.sleep(0.5)
            from backend.orchestrator.db.session import get_session_factory
            factory = await get_session_factory()
            async with factory() as bg_db:
                ev = await bg_db.get(ScanEvent, target_scan_id)
                if ev:
                    if d_url:
                        ev.doc_image_url = d_url
                    if c_url:
                        ev.doc_face_crop_url = c_url
                    if l_url:
                        ev.live_image_url = l_url
                    await bg_db.commit()
            cached_rec = get_cached_scan(str(target_scan_id))
            if cached_rec:
                if d_url:
                    cached_rec.doc_image_data_url = _normalize_storage_url(d_url)
                if c_url:
                    cached_rec.doc_face_crop_data_url = _normalize_storage_url(c_url)
                if l_url:
                    cached_rec.live_image_data_url = _normalize_storage_url(l_url)
            logger.info("background_storage_upload_persisted", scan_id=str(target_scan_id))
        except Exception as exc:
            logger.warning("background_storage_upload_failed", scan_id=str(target_scan_id), error=str(exc))

    asyncio.create_task(_background_storage_upload(scan_id))

    officer_uuid = None
    if officer_id:
        try:
            officer_uuid = uuid.UUID(officer_id)
        except ValueError:
            pass

    pipeline_dict = pipeline.model_dump(mode="json")
    # Strip any heavy base64 strings from snapshot to keep DB row under 5KB
    if "tampering" in pipeline_dict and isinstance(pipeline_dict["tampering"], dict):
        pipeline_dict["tampering"].pop("ela_heatmap_base64", None)

    # ── 4. Upsert scan_events ────────────────────────────────────────────────
    existing = await db.get(ScanEvent, scan_id)
    if existing is None:
        event = ScanEvent(
            id=scan_id,
            checkpoint_id=cp_uuid,
            officer_id=officer_uuid,
            document_type=document_type,
            inspection_status=inspection_status,
            doc_image_url=None,
            doc_face_crop_url=None,
            live_image_url=None,
            pipeline_snapshot=pipeline_dict,
            degraded=getattr(pipeline, "degraded", False),
        )
        db.add(event)
    else:
        existing.pipeline_snapshot = pipeline_dict
        existing.inspection_status = inspection_status
        existing.degraded = getattr(pipeline, "degraded", False)

    # ── 5. Upsert extracted_fields EAV rows ─────────────────────────────────
    from sqlalchemy import delete as sa_delete
    if existing is not None:
        await db.execute(
            sa_delete(ExtractedField).where(ExtractedField.scan_event_id == scan_id)
        )

    if pipeline.extraction and pipeline.extraction.fields:
        for f in pipeline.extraction.fields:
            src = "ocr"
            f_source = getattr(f, "source", None)
            f_method = getattr(f, "extraction_method", None)
            if f_source is not None:
                src = f_source.value if hasattr(f_source, "value") else str(f_source)
            elif f_method is not None:
                src = f_method.value if hasattr(f_method, "value") else str(f_method)

            db.add(ExtractedField(
                scan_event_id=scan_id,
                field_name=f.field_name,
                field_value=str(f.field_value) if f.field_value is not None else None,
                confidence=float(f.confidence) if f.confidence is not None else None,
                source=src,
            ))
    elif hasattr(pipeline, "extracted_fields") and isinstance(pipeline.extracted_fields, dict):
        for field_name, field_data in pipeline.extracted_fields.items():
            if isinstance(field_data, dict):
                value = field_data.get("value") or field_data.get("text")
                confidence = field_data.get("confidence")
                source = field_data.get("source") or field_data.get("extraction_method") or "ocr"
                if hasattr(source, "value"):
                    source = source.value
            else:
                value = str(field_data) if field_data is not None else None
                confidence = None
                source = "ocr"
            db.add(ExtractedField(
                scan_event_id=scan_id,
                field_name=field_name,
                field_value=str(value) if value is not None else None,
                confidence=float(confidence) if confidence is not None else None,
                source=str(source),
            ))

    # ── 6. Upsert tampering_results ─────────────────────────────────────────
    tamper = getattr(pipeline, "tampering", None)
    if tamper is not None:
        if existing is not None:
            await db.execute(
                sa_delete(TamperingResult).where(TamperingResult.scan_event_id == scan_id)
            )
        tamper_dict = tamper.model_dump(mode="json") if hasattr(tamper, "model_dump") else dict(tamper)
        checks_raw = tamper_dict.get("checks") or tamper_dict.get("results") or []
        db.add(TamperingResult(
            scan_event_id=scan_id,
            flagged=tamper_dict.get("flagged", False),
            composite_score=tamper_dict.get("composite_score") or tamper_dict.get("score") or tamper_dict.get("tampering_score"),
            checks=checks_raw,
            ela_heatmap_url=None,
        ))

    # ── 7. Upsert face_verification_results ──────────────────────────────────
    face = getattr(pipeline, "face", None)
    if face is not None and (face.one_to_one or face.dedup or face.bypassed):
        if existing is not None:
            await db.execute(
                sa_delete(FaceVerificationResult).where(FaceVerificationResult.scan_event_id == scan_id)
            )
        one_to_one = face.one_to_one
        dedup = face.dedup
        liveness = face.liveness
        db.add(FaceVerificationResult(
            scan_event_id=scan_id,
            one_to_one_matched=one_to_one.matched if one_to_one else None,
            match_score=one_to_one.match_score if one_to_one else None,
            cosine_similarity=one_to_one.cosine_similarity if one_to_one else None,
            dedup_has_duplicates=dedup.has_duplicates if dedup else None,
            dedup_hits=([h.model_dump() for h in dedup.hits] if dedup else None),
            liveness_is_live=liveness.is_live if liveness else None,
            liveness_score=liveness.liveness_score if liveness else None,
            bypassed=face.bypassed,
            bypassed_reason=face.bypassed_reason,
        ))

    # ── 8. Upsert risk_results ───────────────────────────────────────────────
    risk = getattr(pipeline, "risk_score", None)
    if risk is not None:
        if existing is not None:
            await db.execute(
                sa_delete(RiskResult).where(RiskResult.scan_event_id == scan_id)
            )
        risk_dict = risk.model_dump(mode="json") if hasattr(risk, "model_dump") else dict(risk)
        band_val = risk_dict.get("band")
        if hasattr(band_val, "value"):
            band_val = band_val.value
        db.add(RiskResult(
            scan_event_id=scan_id,
            score=risk_dict.get("score"),
            band=str(band_val) if band_val else None,
            reasons=risk_dict.get("reasons") or [],
            sub_scores=risk_dict.get("sub_scores"),
        ))

    await db.commit()

    record = ScanRecord(
        document_id=str(scan_id),
        document_type=document_type,
        checkpoint_id=str(cp_uuid) if cp_uuid else None,
        uploaded_at=_utc_now_iso(),
        pipeline=pipeline,
        doc_image_data_url=immediate_doc_url,
        doc_face_crop_data_url=immediate_crop_url,
        live_image_data_url=immediate_live_url,
        inspection_status=inspection_status,
    )
    set_cached_scan(str(scan_id), record)
    return record


# ---------------------------------------------------------------------------
# get_scan
# ---------------------------------------------------------------------------

async def get_scan(db: AsyncSession, document_id: str) -> ScanRecord | None:
    """Fetch a scan by document_id. Checks fast in-memory cache first."""
    cached = get_cached_scan(document_id)
    if cached is not None:
        return cached

    try:
        scan_id = uuid.UUID(document_id)
    except ValueError:
        return None

    row = await db.get(ScanEvent, scan_id)
    if row is None:
        return None
    rec = _scan_event_to_record(row)
    set_cached_scan(document_id, rec)
    return rec


# ---------------------------------------------------------------------------
# list_recent_scans
# ---------------------------------------------------------------------------

async def list_recent_scans(db: AsyncSession, limit: int = 20) -> list[ScanRecord]:
    """Fetch the most recent scans ordered by upload time descending."""
    from sqlalchemy.orm import defer
    stmt = (
        select(ScanEvent)
        .options(defer(ScanEvent.pipeline_snapshot))
        .order_by(ScanEvent.uploaded_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_scan_event_to_record(r) for r in rows]


# ---------------------------------------------------------------------------
# list_high_risk_scans
# ---------------------------------------------------------------------------

async def list_high_risk_scans(db: AsyncSession, limit: int = 20) -> list[ScanRecord]:
    """Fetch scans with risk band high or critical."""
    from sqlalchemy.orm import defer
    stmt = (
        select(ScanEvent)
        .options(defer(ScanEvent.pipeline_snapshot))
        .join(RiskResult, RiskResult.scan_event_id == ScanEvent.id, isouter=True)
        .where(RiskResult.band.in_(["high", "critical"]))
        .order_by(RiskResult.score.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_scan_event_to_record(r) for r in rows]


# ---------------------------------------------------------------------------
# list_secondary_queue
# ---------------------------------------------------------------------------

async def list_secondary_queue(db: AsyncSession, limit: int = 50) -> list[ScanRecord]:
    """Fetch scans in secondary inspection or high/critical risk."""
    from sqlalchemy.orm import defer
    stmt = (
        select(ScanEvent)
        .options(defer(ScanEvent.pipeline_snapshot))
        .join(RiskResult, RiskResult.scan_event_id == ScanEvent.id, isouter=True)
        .where(
            (ScanEvent.inspection_status == "secondary_inspection")
            | (RiskResult.band.in_(["high", "critical"]))
        )
        .order_by(ScanEvent.uploaded_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_scan_event_to_record(r) for r in rows]


# ---------------------------------------------------------------------------
# update_inspection_status
# ---------------------------------------------------------------------------

async def update_inspection_status(
    db: AsyncSession, document_id: str, status: str
) -> bool:
    """Update the inspection_status on a scan_event. Returns True on success."""
    try:
        scan_id = uuid.UUID(document_id)
    except ValueError:
        return False

    result = await db.execute(
        update(ScanEvent)
        .where(ScanEvent.id == scan_id)
        .values(inspection_status=status)
    )
    await db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# summary_stats
# ---------------------------------------------------------------------------

async def summary_stats(db: AsyncSession) -> dict[str, Any]:
    """Aggregate statistics across all scans."""
    from sqlalchemy import case, literal

    total_result = await db.execute(select(func.count()).select_from(ScanEvent))
    total_scans = total_result.scalar() or 0

    # Risk band distribution
    band_stmt = (
        select(RiskResult.band, func.count().label("cnt"))
        .group_by(RiskResult.band)
    )
    band_rows = (await db.execute(band_stmt)).all()
    risk_distribution: dict[str, int] = {r.band or "unknown": r.cnt for r in band_rows}

    critical_count = risk_distribution.get("critical", 0)
    high_count = risk_distribution.get("high", 0)

    # Checkpoint type distribution
    from backend.orchestrator.db.models import Checkpoint
    cp_stmt = (
        select(Checkpoint.checkpoint_type, func.count().label("cnt"))
        .join(ScanEvent, ScanEvent.checkpoint_id == Checkpoint.id)
        .group_by(Checkpoint.checkpoint_type)
    )
    cp_rows = (await db.execute(cp_stmt)).all()
    checkpoint_distribution = {r.checkpoint_type: r.cnt for r in cp_rows}

    return {
        "total_scans": total_scans,
        "risk_distribution": risk_distribution,
        "checkpoint_distribution": checkpoint_distribution,
        "flagged_today": critical_count + high_count,
        "critical_count": critical_count,
        "high_count": high_count,
    }


# ---------------------------------------------------------------------------
# Watchlist / Blacklist CRUD  (redirects to watchlist_entries table)
# ---------------------------------------------------------------------------

def _wl_row_to_record(row: WatchlistEntry) -> BlacklistEntryRecord:
    return BlacklistEntryRecord(
        id=str(row.id),
        document_number=row.document_number,
        full_name=row.full_name,
        date_of_birth=row.date_of_birth,
        nationality=row.nationality,
        severity=row.severity,
        reason=row.reason,
        created_at=row.created_at.isoformat() if row.created_at else _utc_now_iso(),
    )


async def list_blacklist(db: AsyncSession, limit: int = 100) -> list[BlacklistEntryRecord]:
    """Return active watchlist entries, most recently added first."""
    stmt = (
        select(WatchlistEntry)
        .where(WatchlistEntry.is_active.is_(True))
        .order_by(WatchlistEntry.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_wl_row_to_record(r) for r in rows]


async def add_blacklist_entry(
    db: AsyncSession,
    *,
    document_number: str | None,
    full_name: str | None,
    date_of_birth: str | None,
    nationality: str | None,
    severity: str,
    reason: str | None,
    source: str = "national",
    created_by: str | None = None,
) -> BlacklistEntryRecord:
    """
    Add a new watchlist entry.
    document_number and full_name are normalised (UPPERCASE+STRIP) by the
    SQLAlchemy event listener on WatchlistEntry before_insert.
    """
    created_by_uuid = None
    if created_by:
        try:
            created_by_uuid = uuid.UUID(created_by)
        except ValueError:
            pass

    entry = WatchlistEntry(
        id=uuid.uuid4(),
        source=source,
        document_number=document_number,
        full_name=full_name,
        date_of_birth=date_of_birth,
        nationality=nationality,
        severity=severity,
        reason=reason,
        is_active=True,
        created_by=created_by_uuid,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _wl_row_to_record(entry)


async def remove_blacklist_entry(db: AsyncSession, entry_id: str) -> bool:
    """Soft-delete a watchlist entry (sets is_active = False)."""
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError:
        return False

    result = await db.execute(
        update(WatchlistEntry)
        .where(WatchlistEntry.id == entry_uuid)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount > 0
