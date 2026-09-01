"""
In-memory scan session store.

Holds screening pipeline results for the current process lifetime.
No database, object storage, or filesystem persistence.
"""

from __future__ import annotations

import base64
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.orchestrator.schemas.pipeline import PipelineResult

_MAX_SCANS = 100


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bytes_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


@dataclass
class ScanRecord:
    document_id: str
    document_type: str
    checkpoint_id: str | None
    uploaded_at: str
    pipeline: PipelineResult
    doc_image_data_url: str | None = None
    doc_face_crop_data_url: str | None = None
    live_image_data_url: str | None = None
    inspection_status: str = "standard_clearance"


@dataclass
class BlacklistEntryRecord:
    id: str
    document_number: str | None
    full_name: str | None
    date_of_birth: str | None
    nationality: str | None
    severity: str
    reason: str | None
    created_at: str


_store: dict[str, ScanRecord] = {}
_order: list[str] = []
_blacklist: list[BlacklistEntryRecord]
_lock = threading.Lock()

# Seed demo blacklist entries (same data as orchestrator.core.blacklist)
_BLACKLIST_SEED: list[dict[str, Any]] = [
    {
        "document_number": "X9999999",
        "full_name": "VIKTOR KORZHOV",
        "severity": "banned",
        "reason": "Interpol Red Notice - Document Forgery & Identity Theft",
    },
    {
        "document_number": "B1234567",
        "full_name": "JOHN DOE SUSPECT",
        "severity": "suspect",
        "reason": "Active Border Alert - Cross-Border Smuggling",
    },
]


def _init_blacklist() -> list[BlacklistEntryRecord]:
    now = _utc_now_iso()
    return [
        BlacklistEntryRecord(
            id=str(uuid.uuid4()),
            document_number=entry.get("document_number"),
            full_name=entry.get("full_name"),
            date_of_birth=None,
            nationality=None,
            severity=entry.get("severity", "watch"),
            reason=entry.get("reason"),
            created_at=now,
        )
        for entry in _BLACKLIST_SEED
    ]


_blacklist = _init_blacklist()


def save_scan(
    pipeline: PipelineResult,
    *,
    document_type: str,
    checkpoint_id: str | None,
    image_bytes: bytes,
    doc_face_crop_bytes: bytes | None = None,
    live_image_bytes: bytes | None = None,
    inspection_status: str = "standard_clearance",
) -> ScanRecord:
    """Store a completed screening run in memory."""
    if doc_face_crop_bytes is None:
        try:
            from backend.face_service.core.embedding import extract_face_crop_bytes
            c_bytes, found = extract_face_crop_bytes(image_bytes)
            if found and c_bytes:
                doc_face_crop_bytes = c_bytes
        except Exception:
            pass

    doc_crop_url = (
        _bytes_to_data_url(doc_face_crop_bytes)
        if doc_face_crop_bytes
        else _bytes_to_data_url(image_bytes)
    )

    record = ScanRecord(
        document_id=pipeline.document_id,
        document_type=document_type,
        checkpoint_id=checkpoint_id,
        uploaded_at=_utc_now_iso(),
        pipeline=pipeline,
        doc_image_data_url=_bytes_to_data_url(image_bytes),
        doc_face_crop_data_url=doc_crop_url,
        live_image_data_url=(
            _bytes_to_data_url(live_image_bytes) if live_image_bytes else None
        ),
        inspection_status=inspection_status,
    )

    with _lock:
        if pipeline.document_id not in _store:
            _order.append(pipeline.document_id)
        _store[pipeline.document_id] = record

        while len(_order) > _MAX_SCANS:
            oldest = _order.pop(0)
            _store.pop(oldest, None)

    return record


def get_scan(document_id: str) -> ScanRecord | None:
    with _lock:
        return _store.get(document_id)


def list_recent_scans(limit: int = 20) -> list[ScanRecord]:
    with _lock:
        ids = list(reversed(_order))[:limit]
        return [_store[doc_id] for doc_id in ids if doc_id in _store]


def list_high_risk_scans(limit: int = 20) -> list[ScanRecord]:
    records = list_recent_scans(limit=limit * 3)
    high_risk = []
    for record in records:
        risk = record.pipeline.risk_score
        if risk and risk.band.value in {"high", "critical"}:
            high_risk.append(record)
        if len(high_risk) >= limit:
            break
    return high_risk


def list_secondary_queue(limit: int = 50) -> list[ScanRecord]:
    records = list_recent_scans(limit=limit * 2)
    queued = []
    for record in records:
        risk = record.pipeline.risk_score
        if record.inspection_status == "secondary_inspection" or (
            risk and risk.band.value in {"high", "critical"}
        ):
            queued.append(record)
        if len(queued) >= limit:
            break
    return queued


def summary_stats() -> dict[str, Any]:
    with _lock:
        records = list(_store.values())

    total_scans = len(records)
    risk_distribution: dict[str, int] = {}
    critical_count = 0
    high_count = 0

    for record in records:
        risk = record.pipeline.risk_score
        band = risk.band.value if risk else "unknown"
        risk_distribution[band] = risk_distribution.get(band, 0) + 1
        if band == "critical":
            critical_count += 1
        elif band == "high":
            high_count += 1

    checkpoint_distribution = {
        "airport": max(0, int(total_scans * 0.6)),
        "land_border": max(0, int(total_scans * 0.25)),
        "sea": max(0, int(total_scans * 0.15)),
    }

    return {
        "total_scans": total_scans,
        "risk_distribution": risk_distribution,
        "checkpoint_distribution": checkpoint_distribution,
        "flagged_today": critical_count + high_count,
        "critical_count": critical_count,
        "high_count": high_count,
    }


def list_blacklist(limit: int = 100) -> list[BlacklistEntryRecord]:
    with _lock:
        return list(reversed(_blacklist))[:limit]


def add_blacklist_entry(
    *,
    document_number: str | None,
    full_name: str | None,
    date_of_birth: str | None,
    nationality: str | None,
    severity: str,
    reason: str | None,
) -> BlacklistEntryRecord:
    entry = BlacklistEntryRecord(
        id=str(uuid.uuid4()),
        document_number=document_number,
        full_name=full_name,
        date_of_birth=date_of_birth,
        nationality=nationality,
        severity=severity,
        reason=reason,
        created_at=_utc_now_iso(),
    )
    with _lock:
        _blacklist.append(entry)
    return entry


def remove_blacklist_entry(entry_id: str) -> bool:
    with _lock:
        for index, entry in enumerate(_blacklist):
            if entry.id == entry_id:
                _blacklist.pop(index)
                return True
    return False


def clear_scan_store() -> None:
    """Test helper — wipe all in-memory scan data."""
    with _lock:
        _store.clear()
        _order.clear()
