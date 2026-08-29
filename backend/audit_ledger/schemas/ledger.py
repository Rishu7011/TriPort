"""
Pydantic Schemas for the Audit Ledger Service (Module 6).

Covers:
  - Event creation payload
  - Chained ledger event record
  - Cryptographic chain verification report
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class LedgerEventCreate(BaseModel):
    """Event creation payload sent by orchestrator or officer actions."""
    document_id: str | None = Field(None, description="UUID of the associated document")
    event_type: str = Field(..., description="Event type: scan | officer_decision | sync | chain_verify")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload dictionary to be hashed")
    officer_id: str | None = Field(None, description="UUID of officer initiating action")


class LedgerEventResponse(BaseModel):
    """Immutable hash-chained ledger record."""
    id: str
    sequence_num: int = Field(..., description="Monotonically increasing sequence index")
    document_id: str | None = None
    event_type: str
    payload_hash: str = Field(..., description="SHA-256 of canonical payload JSON")
    prev_record_hash: str = Field(..., description="SHA-256 hash of the previous record")
    record_hash: str = Field(..., description="SHA-256(payload_hash + prev_record_hash + timestamp)")
    officer_id: str | None = None
    created_at: datetime


class ChainVerificationResponse(BaseModel):
    """Report from walking and validating the complete cryptographic hash chain."""
    valid: bool = Field(..., description="True if 100% of chain links are mathematically valid")
    total_events: int = Field(..., description="Total number of events validated")
    first_invalid_sequence: int | None = Field(None, description="Sequence number where corruption was detected")
    detail: str = Field(..., description="Explainable validation status message")
    verified_at: datetime = Field(default_factory=datetime.utcnow)


class LedgerHistoryResponse(BaseModel):
    """List of all ledger events for a document investigation."""
    document_id: str
    total_events: int
    events: list[LedgerEventResponse]
