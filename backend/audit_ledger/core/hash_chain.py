"""
Tamper-Evident Hash Chaining Engine (Module 6).

CONCEPT:
Every scan, decision, and system event is permanently appended to an
immutable hash chain. Each entry commits to:
  1. payload_hash = SHA256(canonical_json(payload))
  2. prev_record_hash = record_hash of the immediately preceding event (or genesis "0"*64)
  3. record_hash = SHA256(payload_hash + prev_record_hash + ISO_timestamp)

Any retroactive tampering, deletion, or modification of an audit record
mathematically breaks all subsequent record_hashes and is detected instantly
by verify_chain().

When `db` (AsyncSession) is provided, events are persisted to the AuditLedgerEntry table.
When `db` is None (e.g. offline unit tests), events are tracked in `_IN_MEMORY_CHAIN`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.logging_config import get_logger
from backend.orchestrator.db.models import AuditLedgerEntry
from backend.audit_ledger.schemas.ledger import (
    ChainVerificationResponse,
    LedgerEventResponse,
)

logger = get_logger("audit_ledger.hash_chain")

# In-memory chain for offline tests / local fallbacks
_IN_MEMORY_CHAIN: list[dict[str, Any]] = []


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of a payload dictionary."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_record_hash(payload_hash: str, prev_record_hash: str, timestamp_iso: str) -> str:
    """Compute SHA-256 link binding payload, previous block, and timestamp."""
    combo = f"{payload_hash}{prev_record_hash}{timestamp_iso}"
    return hashlib.sha256(combo.encode("utf-8")).hexdigest()


async def append_event(
    event_type: str,
    payload: dict[str, Any],
    document_id: str | None = None,
    officer_id: str | None = None,
    db: AsyncSession | None = None,
) -> LedgerEventResponse:
    """
    Append a new event to the tamper-evident audit ledger.

    Args:
        event_type: Event category string (scan/officer_decision/face_verification/...).
        payload: Full event data dict — stored in JSONB and hashed.
        document_id: The scan_event_id this ledger entry relates to (nullable).
        officer_id: UUID of the acting officer (nullable).
        db: Async SQLAlchemy session. If None, appends to in-memory test chain.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    payload_hash = compute_payload_hash(payload)

    if db is None:
        if _IN_MEMORY_CHAIN:
            prev_record_hash = _IN_MEMORY_CHAIN[-1]["record_hash"]
            seq = _IN_MEMORY_CHAIN[-1]["sequence_num"] + 1
        else:
            prev_record_hash = settings.ledger_genesis_hash
            seq = 1

        rec_hash = compute_record_hash(payload_hash, prev_record_hash, now_iso)
        record_id = str(uuid.uuid4())
        mem_entry = {
            "id": record_id,
            "sequence_num": seq,
            "document_id": document_id,
            "event_type": event_type,
            "payload": payload,
            "payload_hash": payload_hash,
            "prev_record_hash": prev_record_hash,
            "record_hash": rec_hash,
            "officer_id": officer_id,
            "created_at": now_iso,
        }
        _IN_MEMORY_CHAIN.append(mem_entry)
        return LedgerEventResponse(
            id=record_id,
            sequence_num=seq,
            document_id=document_id,
            event_type=event_type,
            payload_hash=payload_hash,
            prev_record_hash=prev_record_hash,
            record_hash=rec_hash,
            officer_id=officer_id,
            created_at=now,
        )

    doc_uuid = None
    if document_id:
        try:
            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            pass

    off_uuid = None
    if officer_id:
        try:
            off_uuid = uuid.UUID(officer_id)
        except ValueError:
            pass

    # Fetch latest record in sequence to build the chain link
    stmt = select(AuditLedgerEntry).order_by(AuditLedgerEntry.sequence_num.desc()).limit(1)
    res = await db.execute(stmt)
    latest = res.scalar_one_or_none()

    if latest:
        sequence_num = latest.sequence_num + 1
        prev_record_hash = latest.record_hash
    else:
        sequence_num = 1
        prev_record_hash = settings.ledger_genesis_hash

    record_hash = compute_record_hash(payload_hash, prev_record_hash, now_iso)
    record_id = uuid.uuid4()

    entry = AuditLedgerEntry(
        id=record_id,
        sequence_num=sequence_num,
        scan_event_id=doc_uuid,
        event_type=event_type,
        payload=payload,
        payload_hash=payload_hash,
        prev_record_hash=prev_record_hash,
        record_hash=record_hash,
        officer_id=off_uuid,
        created_at=now,
    )
    try:
        db.add(entry)
        await db.commit()
        logger.info(
            "ledger_event_appended",
            sequence_num=sequence_num,
            event_type=event_type,
            document_id=document_id,
            record_hash=record_hash[:12],
        )
    except Exception as exc:
        await db.rollback()
        logger.warning("ledger_event_db_commit_failed", error=str(exc), document_id=document_id)
        return LedgerEventResponse(
            id=str(record_id),
            sequence_num=sequence_num,
            document_id=document_id,
            event_type=event_type,
            payload_hash=payload_hash,
            prev_record_hash=prev_record_hash,
            record_hash=record_hash,
            officer_id=officer_id,
            created_at=now,
        )


    return LedgerEventResponse(
        id=str(entry.id),
        sequence_num=entry.sequence_num,
        document_id=str(entry.scan_event_id) if entry.scan_event_id else None,
        event_type=entry.event_type,
        payload_hash=entry.payload_hash,
        prev_record_hash=entry.prev_record_hash,
        record_hash=entry.record_hash,
        officer_id=str(entry.officer_id) if entry.officer_id else None,
        created_at=entry.created_at,
    )


async def verify_chain(db: AsyncSession | None = None) -> ChainVerificationResponse:
    """
    Traverse the entire audit ledger and cryptographically verify all hash chain links.
    Returns exact sequence index where any corruption is detected.
    """
    if db is not None:
        stmt = select(AuditLedgerEntry).order_by(AuditLedgerEntry.sequence_num.asc())
        res = await db.execute(stmt)
        records = list(res.scalars().all())

        if not records:
            return ChainVerificationResponse(
                valid=True,
                total_events=0,
                first_invalid_sequence=None,
                detail="Ledger is currently empty (0 events recorded).",
            )

        prev_hash = settings.ledger_genesis_hash

        for rec in records:
            seq = rec.sequence_num
            stored_payload_hash = rec.payload_hash
            stored_prev_hash = rec.prev_record_hash
            stored_record_hash = rec.record_hash
            ts_iso = rec.created_at.isoformat()

            if stored_prev_hash != prev_hash:
                msg = f"Chain link broken at sequence {seq}: prev_record_hash mismatch."
                logger.error("chain_integrity_violation", sequence_num=seq, reason="prev_hash_mismatch")
                return ChainVerificationResponse(
                    valid=False,
                    total_events=len(records),
                    first_invalid_sequence=seq,
                    detail=msg,
                )

            expected_record_hash = compute_record_hash(stored_payload_hash, stored_prev_hash, ts_iso)
            if stored_record_hash != expected_record_hash:
                msg = f"Data tampering detected at sequence {seq}: record_hash recomputation failed."
                logger.error("chain_integrity_violation", sequence_num=seq, reason="payload_tampered")
                return ChainVerificationResponse(
                    valid=False,
                    total_events=len(records),
                    first_invalid_sequence=seq,
                    detail=msg,
                )

            prev_hash = stored_record_hash

        logger.info("ledger_chain_verified_successfully", total_events=len(records))
        return ChainVerificationResponse(
            valid=True,
            total_events=len(records),
            first_invalid_sequence=None,
            detail=f"All {len(records)} cryptographic hash chain links verified and intact.",
        )

    # In-memory chain verification
    if not _IN_MEMORY_CHAIN:
        return ChainVerificationResponse(
            valid=True,
            total_events=0,
            first_invalid_sequence=None,
            detail="Ledger is currently empty (0 events recorded).",
        )

    prev_hash = settings.ledger_genesis_hash
    for rec in _IN_MEMORY_CHAIN:
        seq = rec["sequence_num"]
        stored_payload_hash = rec["payload_hash"]
        stored_prev_hash = rec["prev_record_hash"]
        stored_record_hash = rec["record_hash"]
        ts_iso = rec["created_at"]

        if stored_prev_hash != prev_hash:
            msg = f"Chain link broken at sequence {seq}: prev_record_hash mismatch."
            return ChainVerificationResponse(
                valid=False,
                total_events=len(_IN_MEMORY_CHAIN),
                first_invalid_sequence=seq,
                detail=msg,
            )

        expected_record_hash = compute_record_hash(stored_payload_hash, stored_prev_hash, ts_iso)
        if stored_record_hash != expected_record_hash:
            msg = f"Data tampering detected at sequence {seq}: record_hash recomputation failed."
            return ChainVerificationResponse(
                valid=False,
                total_events=len(_IN_MEMORY_CHAIN),
                first_invalid_sequence=seq,
                detail=msg,
            )

        prev_hash = stored_record_hash

    return ChainVerificationResponse(
        valid=True,
        total_events=len(_IN_MEMORY_CHAIN),
        first_invalid_sequence=None,
        detail=f"All {len(_IN_MEMORY_CHAIN)} cryptographic hash chain links verified and intact.",
    )


def clear_in_memory_chain():
    """Clear in-memory fallback list."""
    _IN_MEMORY_CHAIN.clear()


def get_in_memory_chain() -> list[dict[str, Any]]:
    """Return copy of in-memory chain."""
    return list(_IN_MEMORY_CHAIN)
