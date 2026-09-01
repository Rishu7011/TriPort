"""
Audit Ledger Router — /api/v1/audit/* and /events/*

Events are stored in the in-memory hash chain only.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.audit_ledger.core.hash_chain import append_event, verify_chain, _IN_MEMORY_CHAIN
from backend.audit_ledger.schemas.ledger import (
    LedgerEventCreate,
    LedgerEventResponse,
    ChainVerificationResponse,
    LedgerHistoryResponse,
)

router = APIRouter(prefix="/events", tags=["ledger"])


@router.post("/", response_model=LedgerEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event_in: LedgerEventCreate):
    try:
        return await append_event(
            event_type=event_in.event_type,
            payload=event_in.payload,
            document_id=event_in.document_id,
            officer_id=event_in.officer_id,
            db=None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to append audit event: {exc}",
        )


@router.get("/verify", response_model=ChainVerificationResponse)
async def verify_ledger():
    return await verify_chain(db=None)


@router.get("/{document_id}", response_model=LedgerHistoryResponse)
async def get_document_events(document_id: str):
    events_out: list[LedgerEventResponse] = []

    for mem in _IN_MEMORY_CHAIN:
        if str(mem.get("document_id")) == document_id:
            events_out.append(
                LedgerEventResponse(
                    sequence_num=mem["sequence_num"],
                    event_type=mem["event_type"],
                    document_id=mem.get("document_id"),
                    officer_id=mem.get("officer_id"),
                    payload_hash=mem["payload_hash"],
                    prev_record_hash=mem["prev_record_hash"],
                    record_hash=mem["record_hash"],
                    created_at=mem.get("created_at"),
                )
            )

    return LedgerHistoryResponse(
        document_id=document_id,
        event_count=len(events_out),
        events=events_out,
    )
