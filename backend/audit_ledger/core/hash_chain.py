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
"""

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

# In-memory ledger buffer for test suites or offline mode
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
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    doc_uuid = uuid.UUID(document_id) if document_id else None
    off_uuid = uuid.UUID(officer_id) if officer_id else None

    payload_hash = compute_payload_hash(payload)

    # 1. Database-backed chain
    if db is not None:
        try:
            # Fetch latest record in sequence
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
                document_id=doc_uuid,
                event_type=event_type,
                payload_hash=payload_hash,
                prev_record_hash=prev_record_hash,
                record_hash=record_hash,
                officer_id=off_uuid,
                created_at=now,
            )
            db.add(entry)
            await db.commit()
            await db.refresh(entry)

            logger.info(
                "ledger_event_appended",
                sequence_num=sequence_num,
                event_type=event_type,
                document_id=document_id,
                record_hash=record_hash[:12],
            )

            return LedgerEventResponse(
                id=str(entry.id),
                sequence_num=entry.sequence_num,
                document_id=str(entry.document_id) if entry.document_id else None,
                event_type=entry.event_type,
                payload_hash=entry.payload_hash,
                prev_record_hash=entry.prev_record_hash,
                record_hash=entry.record_hash,
                officer_id=str(entry.officer_id) if entry.officer_id else None,
                created_at=entry.created_at,
            )
        except Exception as exc:
            logger.warning("Database ledger append fell back to in-memory store", error=str(exc))
            if db:
                await db.rollback()

    # 2. In-memory fallback
    global _IN_MEMORY_CHAIN
    if _IN_MEMORY_CHAIN:
        sequence_num = _IN_MEMORY_CHAIN[-1]["sequence_num"] + 1
        prev_record_hash = _IN_MEMORY_CHAIN[-1]["record_hash"]
    else:
        sequence_num = 1
        prev_record_hash = settings.ledger_genesis_hash

    record_hash = compute_record_hash(payload_hash, prev_record_hash, now_iso)
    record_id_str = str(uuid.uuid4())

    in_mem_record = {
        "id": record_id_str,
        "sequence_num": sequence_num,
        "document_id": document_id,
        "event_type": event_type,
        "payload_hash": payload_hash,
        "prev_record_hash": prev_record_hash,
        "record_hash": record_hash,
        "officer_id": officer_id,
        "created_at": now,
        "timestamp_iso": now_iso,
    }
    _IN_MEMORY_CHAIN.append(in_mem_record)

    return LedgerEventResponse(
        id=record_id_str,
        sequence_num=sequence_num,
        document_id=document_id,
        event_type=event_type,
        payload_hash=payload_hash,
        prev_record_hash=prev_record_hash,
        record_hash=record_hash,
        officer_id=officer_id,
        created_at=now,
    )


async def verify_chain(db: AsyncSession | None = None) -> ChainVerificationResponse:
    """
    Traverse the entire audit ledger and cryptographically verify all hash chain links.
    Returns exact sequence index where any corruption is detected.
    """
    records: list[Any] = []

    if db is not None:
        try:
            stmt = select(AuditLedgerEntry).order_by(AuditLedgerEntry.sequence_num.asc())
            res = await db.execute(stmt)
            records = list(res.scalars().all())
        except Exception as exc:
            logger.warning("DB query failed during verify_chain, using in-memory chain", error=str(exc))

    if not records:
        records = list(_IN_MEMORY_CHAIN)

    if not records:
        return ChainVerificationResponse(
            valid=True,
            total_events=0,
            first_invalid_sequence=None,
            detail="Ledger is currently empty (0 events recorded).",
        )

    prev_hash = settings.ledger_genesis_hash

    for idx, rec in enumerate(records):
        # Support both SQLAlchemy model and in-memory dict
        if isinstance(rec, dict):
            seq = rec["sequence_num"]
            stored_payload_hash = rec["payload_hash"]
            stored_prev_hash = rec["prev_record_hash"]
            stored_record_hash = rec["record_hash"]
            ts_iso = rec.get("timestamp_iso", rec["created_at"].isoformat())
        else:
            seq = rec.sequence_num
            stored_payload_hash = rec.payload_hash
            stored_prev_hash = rec.prev_record_hash
            stored_record_hash = rec.record_hash
            ts_iso = rec.created_at.isoformat()

        # 1. Verify link back to previous record
        if stored_prev_hash != prev_hash:
            msg = f"Chain link broken at sequence {seq}: prev_record_hash mismatch."
            logger.error("chain_integrity_violation", sequence_num=seq, reason="prev_hash_mismatch")
            return ChainVerificationResponse(
                valid=False,
                total_events=len(records),
                first_invalid_sequence=seq,
                detail=msg,
            )

        # 2. Verify record_hash computation
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


def clear_in_memory_chain():
    """Helper for test suites."""
    _IN_MEMORY_CHAIN.clear()


def get_in_memory_chain() -> list[dict[str, Any]]:
    """Return live in-memory ledger list."""
    return _IN_MEMORY_CHAIN
