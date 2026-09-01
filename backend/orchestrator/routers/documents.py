"""
Orchestrator Documents & Audit Router — /api/v1/documents/* and /api/v1/audit/*

Screening results are held in the in-memory scan store for the current process.
No database or object storage is used.
"""

import base64
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from backend.audit_ledger.core.hash_chain import _IN_MEMORY_CHAIN
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import CheckpointType, DocumentType
from backend.orchestrator.auth.dependencies import require_roles
from backend.orchestrator.auth.security import UserTokenData
from backend.orchestrator.core.pipeline import run_pipeline
from backend.orchestrator.core.scan_store import ScanRecord, get_scan
from backend.orchestrator.core.service_clients import call_audit_ledger
from backend.orchestrator.schemas.pipeline import (
    DecisionRequest,
    DecisionResponse,
    PipelineResult,
    UploadResponse,
)

logger = get_logger("orchestrator.router")

router = APIRouter(prefix="/api/v1", tags=["Documents & Screening"])

STANDARD_ROLES = ["officer", "supervisor", "admin"]
AUDIT_ROLES = ["supervisor", "auditor", "admin"]


def _normalize_tampering_detail(raw: Any) -> Any:
    if raw is None:
        return "No detail provided."
    if isinstance(raw, (str, int, float, bool)):
        return raw if isinstance(raw, str) else str(raw)
    if isinstance(raw, dict):
        nested = raw.get("detail")
        if isinstance(nested, str):
            return nested
    return raw


def _get_scan_or_404(document_id: str) -> ScanRecord:
    record = get_scan(document_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "document_not_found", "document_id": document_id},
        )
    return record


def _face_response(record: ScanRecord) -> dict[str, Any]:
    face = record.pipeline.face
    if not face:
        return {
            "document_id": record.document_id,
            "has_face_record": False,
            "person_cluster_id": None,
        }

    payload = face.model_dump()
    payload["document_id"] = record.document_id
    payload["has_face_record"] = bool(face.one_to_one or face.dedup)
    payload["person_cluster_id"] = (
        face.dedup.person_cluster_id if face.dedup else None
    )
    payload["doc_image_url"] = record.doc_image_data_url
    payload["live_image_url"] = record.live_image_data_url
    return payload


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
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> UploadResponse:
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
    )

    status_str = "degraded" if pipeline_result.degraded else "complete"

    return UploadResponse(
        document_id=pipeline_result.document_id,
        status=status_str,
        pipeline=pipeline_result,
    )


# ---------------------------------------------------------------------------
# 1b. Face Photo Crop
# ---------------------------------------------------------------------------
@router.post(
    "/documents/face-crop",
    summary="Extract and return the face photo from a passport image as base64",
)
async def extract_face_crop(
    file: UploadFile = File(..., description="Passport or ID document image"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> JSONResponse:
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Empty file")
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_image", "reason": str(exc)},
        ) from exc

    try:
        from backend.face_service.core.embedding import extract_face_crop_bytes

        crop_bytes, face_detected = extract_face_crop_bytes(image_bytes)
    except Exception:
        face_detected = False
        crop_bytes = None

    if not face_detected or not crop_bytes:
        return JSONResponse({"face_detected": False, "face_crop_base64": None})

    b64 = base64.b64encode(crop_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"
    return JSONResponse({"face_detected": True, "face_crop_base64": data_url})


# ---------------------------------------------------------------------------
# 2–6. Screening result endpoints (in-memory)
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/pipeline",
    response_model=UploadResponse,
    summary="Retrieve the full screening pipeline result for a document",
)
async def get_document_pipeline(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> UploadResponse:
    record = _get_scan_or_404(document_id)
    return UploadResponse(
        document_id=record.document_id,
        status="degraded" if record.pipeline.degraded else "complete",
        pipeline=record.pipeline,
    )


@router.get(
    "/documents/{document_id}/extraction",
    summary="Retrieve OCR extracted fields and MRZ status for a document",
)
async def get_document_extraction(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    record = _get_scan_or_404(document_id)
    extraction = record.pipeline.extraction
    fields = extraction.fields if extraction else []

    return {
        "document_id": document_id,
        "document_type": record.document_type,
        "uploaded_at": record.uploaded_at,
        "fields": [
            {
                "field_name": f.field_name,
                "field_value": f.field_value,
                "confidence": f.confidence,
            }
            for f in fields
        ],
        "mrz": extraction.mrz.model_dump() if extraction and extraction.mrz else None,
        "image_url": record.doc_image_data_url,
    }


@router.get(
    "/documents/{document_id}/validation",
    summary="Retrieve business rules validation results",
)
async def get_document_validation(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    record = _get_scan_or_404(document_id)
    validation = record.pipeline.validation
    results = validation.rule_results if validation else []

    failed = [r.rule_name for r in results if not r.passed]
    return {
        "document_id": document_id,
        "document_type": record.document_type,
        "passed": len(failed) == 0,
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


@router.get(
    "/documents/{document_id}/tampering",
    summary="Retrieve forensic tampering and ELA results",
)
async def get_document_tampering(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    record = _get_scan_or_404(document_id)
    tampering = record.pipeline.tampering
    checks = tampering.checks if tampering else []

    return {
        "document_id": document_id,
        "flagged": tampering.flagged if tampering else False,
        "tampering_score": tampering.tampering_score if tampering else 0.0,
        "checks": [
            {
                "check_type": (
                    c.check_type.value
                    if hasattr(c.check_type, "value")
                    else str(c.check_type)
                ),
                "score": c.score,
                "flagged": c.flagged,
                "detail": _normalize_tampering_detail(c.detail),
            }
            for c in checks
        ],
        "ela_heatmap_base64": tampering.ela_heatmap_base64 if tampering else None,
        "image_url": record.doc_image_data_url,
    }


@router.get(
    "/documents/{document_id}/face-verification",
    summary="Retrieve biometric match score and deduplication clusters",
)
async def get_document_face(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    record = _get_scan_or_404(document_id)
    return _face_response(record)


@router.get(
    "/documents/{document_id}/risk-score",
    summary="Retrieve computed risk score, band, and reasons",
)
async def get_document_risk(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    record = _get_scan_or_404(document_id)
    risk = record.pipeline.risk_score
    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "risk_score_not_found", "document_id": document_id},
        )

    return {
        "document_id": document_id,
        "score": risk.score,
        "band": risk.band.value,
        "reasons": risk.reasons,
        "sub_scores": risk.sub_scores.model_dump() if risk.sub_scores else None,
        "computed_at": record.uploaded_at,
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
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
) -> DecisionResponse:
    _get_scan_or_404(document_id)

    ledger_payload = {
        "decision": body.decision,
        "notes": body.notes,
        "officer_id": body.officer_id or current_user.user_id,
    }
    ledger_res = await call_audit_ledger(
        event_type="officer_decision",
        document_id=document_id,
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
    current_user: UserTokenData = Depends(require_roles(AUDIT_ROLES)),
):
    _get_scan_or_404(document_id)

    entries = [
        event
        for event in _IN_MEMORY_CHAIN
        if str(event.get("document_id")) == document_id
    ]

    return {
        "document_id": document_id,
        "event_count": len(entries),
        "events": [
            {
                "sequence_num": e.get("sequence_num"),
                "event_type": e.get("event_type"),
                "payload_hash": e.get("payload_hash"),
                "prev_record_hash": e.get("prev_record_hash"),
                "record_hash": e.get("record_hash"),
                "officer_id": e.get("officer_id"),
                "created_at": e.get("created_at"),
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# 9. Cross-Checkpoint Cluster History
# ---------------------------------------------------------------------------
@router.get(
    "/clusters/{person_cluster_id}",
    summary="Retrieve full cross-checkpoint history and multi-identity flags for a person cluster",
)
async def get_cluster_history_endpoint(
    person_cluster_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    from backend.cross_checkpoint_service.core.face_graph import get_cluster_history

    try:
        history = await get_cluster_history(person_cluster_id, db=None)
        return history
    except Exception as exc:
        logger.error(
            "Failed to query cluster history in orchestrator",
            cluster_id=person_cluster_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cluster history: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# 10. Secondary Inspection Queue
# ---------------------------------------------------------------------------
@router.get(
    "/documents/secondary-queue",
    summary="List all documents routed to the Secondary Inspection Queue",
)
async def get_secondary_inspection_queue(
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
):
    from backend.orchestrator.core.scan_store import list_secondary_queue

    queue_items = []
    for record in list_secondary_queue():
        risk = record.pipeline.risk_score
        queue_items.append(
            {
                "document_id": record.document_id,
                "document_type": record.document_type,
                "uploaded_at": record.uploaded_at,
                "risk_score": risk.score if risk else None,
                "risk_band": risk.band.value if risk else None,
                "reasons": risk.reasons if risk else [],
                "status": "secondary_inspection",
            }
        )

    return {"queue": queue_items, "count": len(queue_items)}
