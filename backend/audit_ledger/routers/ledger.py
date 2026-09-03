"""
Audit Ledger Router — /events/*

Events are persisted to Supabase via the hash-chained AuditLedgerEntry table.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.orchestrator.db.session import get_db
from backend.orchestrator.db.models import AuditLedgerEntry
from backend.audit_ledger.core.hash_chain import append_event, verify_chain
from backend.audit_ledger.schemas.ledger import (
    LedgerEventCreate,
    LedgerEventResponse,
    ChainVerificationResponse,
    LedgerHistoryResponse,
)

router = APIRouter(prefix="/events", tags=["ledger"])


@router.post("/", response_model=LedgerEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: LedgerEventCreate,
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/", response_model=list[LedgerEventResponse])
async def list_recent_events(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AuditLedgerEntry)
        .order_by(AuditLedgerEntry.sequence_num.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    return [
        LedgerEventResponse(
            id=str(row.id),
            sequence_num=row.sequence_num,
            event_type=row.event_type,
            document_id=str(row.scan_event_id) if row.scan_event_id else None,
            officer_id=str(row.officer_id) if row.officer_id else None,
            payload_hash=row.payload_hash,
            prev_record_hash=row.prev_record_hash,
            record_hash=row.record_hash,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/verify", response_model=ChainVerificationResponse)
async def verify_ledger(db: AsyncSession = Depends(get_db)):
    return await verify_chain(db=db)


@router.get("/{document_id}", response_model=LedgerHistoryResponse)
async def get_document_events(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        import uuid
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_id must be a valid UUID.",
        )

    stmt = (
        select(AuditLedgerEntry)
        .where(AuditLedgerEntry.scan_event_id == doc_uuid)
        .order_by(AuditLedgerEntry.sequence_num.asc())
    )
    res = await db.execute(stmt)
    rows = list(res.scalars().all())

    events_out = [
        LedgerEventResponse(
            id=str(row.id),
            sequence_num=row.sequence_num,
            event_type=row.event_type,
            document_id=str(row.scan_event_id) if row.scan_event_id else None,
            officer_id=str(row.officer_id) if row.officer_id else None,
            payload_hash=row.payload_hash,
            prev_record_hash=row.prev_record_hash,
            record_hash=row.record_hash,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return LedgerHistoryResponse(
        document_id=document_id,
        event_count=len(events_out),
        events=events_out,
    )
