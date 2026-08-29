"""
Audit Ledger Router — /api/v1/audit/* and /events/*

Endpoints:
  - POST /events/           -> Append immutable event to hash chain
  - GET  /events/{doc_id}   -> Fetch complete hash chain history for document
  - GET  /events/verify     -> Cryptographically verify entire chain
"""

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.orchestrator.db.session import get_db
from backend.orchestrator.db.models import AuditLedgerEntry
from backend.audit_ledger.schemas.ledger import (
    LedgerEventCreate,
    LedgerEventResponse,
    ChainVerificationResponse,
    LedgerHistoryResponse,
)
from backend.audit_ledger.core.hash_chain import append_event, verify_chain, _IN_MEMORY_CHAIN

router = APIRouter(prefix="/events", tags=["ledger"])


@router.post("/", response_model=LedgerEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: LedgerEventCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Append an immutable event to the cryptographic audit ledger.
    Calculates SHA-256 payload hash and links to previous block record hash.
    """
    try:
        return await append_event(
            event_type=event_in.event_type,
            payload=event_in.payload,
            document_id=event_in.document_id,
            officer_id=event_in.officer_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to append audit event: {exc}",
        )


@router.get("/verify", response_model=ChainVerificationResponse)
async def verify_ledger(
    db: AsyncSession = Depends(get_db),
):
    """
    Cryptographically verify the integrity of every link in the audit ledger hash chain.
    """
    return await verify_chain(db=db)


@router.get("/{document_id}", response_model=LedgerHistoryResponse)
async def get_document_events(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all chained audit records associated with a specific document.
    """
    events_out: list[LedgerEventResponse] = []

    try:
        doc_uuid = uuid.UUID(document_id)
        stmt = (
            select(AuditLedgerEntry)
            .where(AuditLedgerEntry.document_id == doc_uuid)
            .order_by(AuditLedgerEntry.sequence_num.asc())
        )
        res = await db.execute(stmt)
        entries = res.scalars().all()

        for e in entries:
            events_out.append(
                LedgerEventResponse(
                    id=str(e.id),
                    sequence_num=e.sequence_num,
                    document_id=str(e.document_id) if e.document_id else None,
                    event_type=e.event_type,
                    payload_hash=e.payload_hash,
                    prev_record_hash=e.prev_record_hash,
                    record_hash=e.record_hash,
                    officer_id=str(e.officer_id) if e.officer_id else None,
                    created_at=e.created_at,
                )
            )
    except Exception:
        # Fallback to in-memory filter
        for mem in _IN_MEMORY_CHAIN:
            if mem.get("document_id") == document_id:
                events_out.append(
                    LedgerEventResponse(
                        id=mem["id"],
                        sequence_num=mem["sequence_num"],
                        document_id=mem["document_id"],
                        event_type=mem["event_type"],
                        payload_hash=mem["payload_hash"],
                        prev_record_hash=mem["prev_record_hash"],
                        record_hash=mem["record_hash"],
                        officer_id=mem["officer_id"],
                        created_at=mem["created_at"],
                    )
                )

    return LedgerHistoryResponse(
        document_id=document_id,
        total_events=len(events_out),
        events=events_out,
    )
