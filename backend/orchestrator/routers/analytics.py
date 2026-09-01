"""
Analytics & Command Dashboard Router — /api/v1/analytics/*

Aggregate statistics and feeds are derived from the in-memory scan store.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.audit_ledger.core.hash_chain import verify_chain
from backend.logging_config import get_logger
from backend.orchestrator.auth.dependencies import require_roles
from backend.orchestrator.auth.security import UserTokenData
from backend.orchestrator.core.scan_store import (
    add_blacklist_entry,
    list_blacklist,
    list_high_risk_scans,
    list_recent_scans,
    remove_blacklist_entry,
    summary_stats,
)

logger = get_logger("orchestrator.analytics")

router = APIRouter(prefix="/api/v1/analytics", tags=["Command Dashboard & Analytics"])

STANDARD_ROLES = ["officer", "supervisor", "admin"]
ADMIN_ROLES = ["admin"]


class SummaryStats(BaseModel):
    total_scans: int
    risk_distribution: dict[str, int]
    checkpoint_distribution: dict[str, int]
    flagged_today: int
    critical_count: int
    high_count: int


class RecentScan(BaseModel):
    document_id: str
    document_type: str
    checkpoint_id: str | None
    uploaded_at: str | None
    risk_score: float | None
    risk_band: str | None
    reasons: list[str]


class BlacklistEntryOut(BaseModel):
    id: str
    document_number: str | None
    full_name: str | None
    date_of_birth: str | None
    nationality: str | None
    severity: str
    reason: str | None
    created_at: str | None


class BlacklistEntryIn(BaseModel):
    document_number: str | None = None
    full_name: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    severity: str = "watch"
    reason: str | None = None


def _to_recent_scan(record) -> RecentScan:
    risk = record.pipeline.risk_score
    return RecentScan(
        document_id=record.document_id,
        document_type=record.document_type,
        checkpoint_id=record.checkpoint_id,
        uploaded_at=record.uploaded_at,
        risk_score=risk.score if risk else None,
        risk_band=risk.band.value if risk else None,
        reasons=risk.reasons if risk else [],
    )


@router.get("/summary", response_model=SummaryStats)
async def get_summary_stats(
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    return SummaryStats(**summary_stats())


@router.get("/scans/recent", response_model=list[RecentScan])
async def get_recent_scans(
    limit: int = 20,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    return [_to_recent_scan(record) for record in list_recent_scans(limit)]


@router.get("/scans/high-risk", response_model=list[RecentScan])
async def get_high_risk_scans(
    limit: int = 20,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    return [_to_recent_scan(record) for record in list_high_risk_scans(limit)]


@router.get("/audit/chain-status")
async def get_chain_integrity_status(
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    return await verify_chain(db=None)


@router.get("/blacklist", response_model=list[BlacklistEntryOut])
async def list_blacklist_entries(
    limit: int = 100,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    return [
        BlacklistEntryOut(
            id=entry.id,
            document_number=entry.document_number,
            full_name=entry.full_name,
            date_of_birth=entry.date_of_birth,
            nationality=entry.nationality,
            severity=entry.severity,
            reason=entry.reason,
            created_at=entry.created_at,
        )
        for entry in list_blacklist(limit)
    ]


@router.post("/blacklist", response_model=BlacklistEntryOut, status_code=status.HTTP_201_CREATED)
async def add_blacklist_entry_route(
    entry: BlacklistEntryIn,
    current_user: UserTokenData = Depends(require_roles(ADMIN_ROLES)),
):
    if not entry.document_number and not entry.full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of document_number or full_name must be provided.",
        )

    created = add_blacklist_entry(
        document_number=entry.document_number,
        full_name=entry.full_name,
        date_of_birth=entry.date_of_birth,
        nationality=entry.nationality,
        severity=entry.severity,
        reason=entry.reason,
    )

    logger.info("Blacklist entry added", entry_id=created.id, by=current_user.user_id)
    return BlacklistEntryOut(
        id=created.id,
        document_number=created.document_number,
        full_name=created.full_name,
        date_of_birth=created.date_of_birth,
        nationality=created.nationality,
        severity=created.severity,
        reason=created.reason,
        created_at=created.created_at,
    )


@router.delete("/blacklist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_blacklist_entry_route(
    entry_id: str,
    current_user: UserTokenData = Depends(require_roles(ADMIN_ROLES)),
):
    try:
        uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid entry ID format")

    if not remove_blacklist_entry(entry_id):
        raise HTTPException(status_code=404, detail="Blacklist entry not found")

    logger.info("Blacklist entry removed", entry_id=entry_id, by=current_user.user_id)
