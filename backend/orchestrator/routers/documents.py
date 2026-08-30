"""
Orchestrator Documents & Audit Router — /api/v1/documents/* and /api/v1/audit/*

Endpoints implemented (plan.md §7):
  - POST /api/v1/documents/upload
  - GET  /api/v1/documents/{id}/extraction
  - GET  /api/v1/documents/{id}/validation
  - GET  /api/v1/documents/{id}/tampering
  - GET  /api/v1/documents/{id}/face-verification
  - GET  /api/v1/documents/{id}/risk-score
  - POST /api/v1/documents/{id}/decision
  - GET  /api/v1/audit/{document_id}
"""

import base64
import io
import uuid
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import CheckpointType, DocumentType
from backend.orchestrator.auth.dependencies import require_roles
from backend.orchestrator.auth.security import UserTokenData
from backend.orchestrator.core.pipeline import run_pipeline
from backend.orchestrator.core.service_clients import call_audit_ledger
from backend.orchestrator.db.models import (
    AuditLedgerEntry,
    Document,
    ExtractedField,
    FaceEmbedding,
    RiskScore,
    TamperingResult,
    ValidationResult,
)
from backend.orchestrator.db.session import get_db
from backend.orchestrator.schemas.pipeline import (
    DecisionRequest,
    DecisionResponse,
    DocumentNotFoundError,
    PipelineResult,
    UploadResponse,
)
from backend.orchestrator.storage.minio_client import get_document_image_url

logger = get_logger("orchestrator.router")

router = APIRouter(prefix="/api/v1", tags=["Documents & Screening"])

STANDARD_ROLES = ["officer", "supervisor", "admin"]
AUDIT_ROLES = ["supervisor", "admin"]


# ---------------------------------------------------------------------------
# Helper: verify document existence
# ---------------------------------------------------------------------------
async def _get_document_or_404(document_id: str, db: AsyncSession) -> Document:
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "document_not_found", "document_id": document_id},
        )

    stmt = select(Document).where(Document.id == doc_uuid)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "document_not_found", "document_id": document_id},
        )
    return doc


# ---------------------------------------------------------------------------
# 1. Document Upload & Screening Pipeline
# ---------------------------------------------------------------------------
@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload document and execute complete screening pipeline",
)
async def upload_and_screen_document(
    file: UploadFile = File(..., description="Document scan image (JPEG/PNG)"),
    document_type: DocumentType = Form(default=DocumentType.PASSPORT),
    checkpoint_type: CheckpointType = Form(default=CheckpointType.AIRPORT),
    provider: str = Form(default="local"),
    live_photo: UploadFile | None = File(None, description="Optional live traveler face photo"),
    checkpoint_id: str | None = Form(None, description="Border checkpoint UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> UploadResponse:
    """
    Ingest a document scan, run all AI modules + risk scoring + audit logging,
    and return the complete screening report.
    """
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Uploaded document image is empty")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_image", "reason": str(exc)},
        ) from exc

    live_bytes: bytes | None = None
    if live_photo:
        try:
            live_bytes = await live_photo.read()
            if len(live_bytes) == 0:
                live_bytes = None
        except Exception:
            live_bytes = None

    pipeline_result: PipelineResult = await run_pipeline(
        image_bytes=image_bytes,
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider=provider,
        live_image_bytes=live_bytes,
        checkpoint_id=checkpoint_id or current_user.checkpoint_id,
        db=db,
    )

    status_str = "degraded" if pipeline_result.degraded else "complete"

    return UploadResponse(
        document_id=pipeline_result.document_id,
        status=status_str,
        pipeline=pipeline_result,
    )


# ---------------------------------------------------------------------------
# 1b. Face Photo Crop — Extract passport holder photo from document image
# ---------------------------------------------------------------------------
@router.post(
    "/documents/face-crop",
    summary="Extract and return the face photo from a passport image as base64",
)
async def extract_face_crop(
    file: UploadFile = File(..., description="Passport or ID document image"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> JSONResponse:
    """
    Use MTCNN face detection to locate and crop the holder photo from a
    document scan. Returns the crop as a base64-encoded JPEG data URL so
    the frontend can display the ID photo directly without canvas tricks.
    """
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Empty file")
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_image", "reason": str(exc)}) from exc

    try:
        from backend.face_service.core.embedding import extract_face_crop_bytes
        crop_bytes, face_detected = extract_face_crop_bytes(image_bytes)
    except Exception:
        # Fallback: try calling embedding directly without the crop helper
        face_detected = False
        crop_bytes = None

    if not face_detected or not crop_bytes:
        return JSONResponse({"face_detected": False, "face_crop_base64": None})

    b64 = base64.b64encode(crop_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"
    return JSONResponse({"face_detected": True, "face_crop_base64": data_url})


# ---------------------------------------------------------------------------
# 2. Document Extraction Details

# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/extraction",
    summary="Retrieve OCR extracted fields and MRZ status for a document",
)
async def get_document_extraction(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    doc = await _get_document_or_404(document_id, db)
    stmt = select(ExtractedField).where(ExtractedField.document_id == doc.id)
    res = await db.execute(stmt)
    fields = res.scalars().all()

    return {
        "document_id": document_id,
        "document_type": doc.document_type,
        "uploaded_at": doc.uploaded_at,
        "fields": [
            {
                "field_name": f.field_name,
                "field_value": f.field_value,
                "confidence": f.confidence,
            }
            for f in fields
        ],
        "image_url": get_document_image_url(doc.image_object_key),
    }


# ---------------------------------------------------------------------------
# 3. Document Validation Details
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/validation",
    summary="Retrieve business rules validation results",
)
async def get_document_validation(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    doc = await _get_document_or_404(document_id, db)
    stmt = select(ValidationResult).where(ValidationResult.document_id == doc.id)
    res = await db.execute(stmt)
    results = res.scalars().all()

    failed = [r.rule_name for r in results if not r.passed]
    passed = len(failed) == 0

    return {
        "document_id": document_id,
        "passed": passed,
        "failed_rules": failed,
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "passed": r.passed,
                "detail": r.detail,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# 4. Document Tampering Details
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/tampering",
    summary="Retrieve forensic tampering and ELA results",
)
async def get_document_tampering(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    doc = await _get_document_or_404(document_id, db)
    stmt = select(TamperingResult).where(TamperingResult.document_id == doc.id)
    res = await db.execute(stmt)
    checks = res.scalars().all()

    flagged = any(c.flagged for c in checks)

    return {
        "document_id": document_id,
        "flagged": flagged,
        "checks": [
            {
                "check_type": c.check_type,
                "score": c.score,
                "flagged": c.flagged,
                "detail": c.detail,
            }
            for c in checks
        ],
        "image_url": get_document_image_url(doc.image_object_key),
    }


# ---------------------------------------------------------------------------
# 5. Face Verification Details
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/face-verification",
    summary="Retrieve biometric match score and deduplication clusters",
)
async def get_document_face(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    doc = await _get_document_or_404(document_id, db)
    stmt = select(FaceEmbedding).where(FaceEmbedding.document_id == doc.id)
    res = await db.execute(stmt)
    face_row = res.scalar_one_or_none()

    return {
        "document_id": document_id,
        "has_face_record": face_row is not None,
        "person_cluster_id": str(face_row.person_cluster_id) if (face_row and face_row.person_cluster_id) else None,
    }


# ---------------------------------------------------------------------------
# 6. Risk Score Details
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/risk-score",
    summary="Retrieve computed risk score, band, and reasons",
)
async def get_document_risk(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    doc = await _get_document_or_404(document_id, db)
    stmt = select(RiskScore).where(RiskScore.document_id == doc.id)
    res = await db.execute(stmt)
    risk_row = res.scalar_one_or_none()

    if not risk_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "risk_score_not_found", "document_id": document_id},
        )

    return {
        "document_id": document_id,
        "score": risk_row.score,
        "band": risk_row.band,
        "reasons": risk_row.reasons,
        "computed_at": risk_row.computed_at,
    }


# ---------------------------------------------------------------------------
# 7. Officer Decision Recording
# ---------------------------------------------------------------------------
@router.post(
    "/documents/{document_id}/decision",
    response_model=DecisionResponse,
    summary="Record officer verdict (approve / flag / reject) into audit ledger",
)
async def record_officer_decision(
    document_id: str,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> DecisionResponse:
    """Record an officer's final decision for a document scan."""
    doc = await _get_document_or_404(document_id, db)

    # Append to tamper-evident audit ledger
    ledger_payload = {
        "decision": body.decision,
        "notes": body.notes,
        "officer_id": body.officer_id or current_user.user_id,
    }
    ledger_res = await call_audit_ledger(
        event_type="officer_decision",
        document_id=str(doc.id),
        payload=ledger_payload,
        officer_id=body.officer_id or current_user.user_id,
    )

    seq_num = ledger_res.get("sequence_num") if ledger_res else None

    logger.info(
        "officer_decision_recorded",
        document_id=document_id,
        officer_id=body.officer_id or current_user.user_id,
        decision=body.decision,
        sequence_num=seq_num,
    )

    return DecisionResponse(
        document_id=document_id,
        decision=body.decision,
        recorded=True,
        ledger_sequence=seq_num,
    )


# ---------------------------------------------------------------------------
# 8. Document Audit Ledger Trail
# ---------------------------------------------------------------------------
@router.get(
    "/audit/{document_id}",
    summary="Retrieve full hash-chained event trail for a document investigation",
)
async def get_document_audit_trail(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserTokenData = Depends(require_roles(AUDIT_ROLES)),
):
    """Fetch complete immutable audit history for a document."""
    doc = await _get_document_or_404(document_id, db)

    stmt = (
        select(AuditLedgerEntry)
        .where(AuditLedgerEntry.document_id == doc.id)
        .order_by(AuditLedgerEntry.sequence_num.asc())
    )
    res = await db.execute(stmt)
    entries = res.scalars().all()

    return {
        "document_id": document_id,
        "event_count": len(entries),
        "events": [
            {
                "sequence_num": e.sequence_num,
                "event_type": e.event_type,
                "payload_hash": e.payload_hash,
                "prev_record_hash": e.prev_record_hash,
                "record_hash": e.record_hash,
                "officer_id": str(e.officer_id) if e.officer_id else None,
                "created_at": e.created_at,
            }
            for e in entries
        ],
    }
