"""
Orchestrator Documents & Audit Router — /api/v1/documents/* and /api/v1/audit/*

All endpoints now read from and write to Supabase via the async SQLAlchemy session.
In-memory scan store references replaced with DB-backed scan_store functions.
"""

import base64
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit_ledger.core.hash_chain import append_event
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import CheckpointType, DocumentType
from backend.orchestrator.auth.dependencies import require_roles
from backend.orchestrator.auth.security import UserTokenData
from backend.orchestrator.core.pipeline import run_pipeline
from backend.orchestrator.core import scan_store
from backend.orchestrator.core.service_clients import call_audit_ledger, call_face_service, call_risk_engine
from backend.orchestrator.db.session import get_db
from backend.orchestrator.db.models import (
    AuditLedgerEntry,
    FaceVerificationResult,
    OfficerDecision,
    ScanEvent,
)
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


async def _get_scan_or_404(db: AsyncSession, document_id: str) -> scan_store.ScanRecord:
    """Fetch a scan from DB or raise 404."""
    record = await scan_store.get_scan(db, document_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "document_not_found", "document_id": document_id},
        )
    return record


def _face_response(record: scan_store.ScanRecord) -> dict[str, Any]:
    face = record.pipeline.face
    doc_crop_url = record.doc_face_crop_data_url or record.doc_image_data_url
    if not face:
        return {
            "document_id": record.document_id,
            "has_face_record": False,
            "person_cluster_id": None,
            "doc_image_url": doc_crop_url,
            "raw_doc_image_url": record.doc_image_data_url,
            "live_image_url": record.live_image_data_url,
        }

    payload = face.model_dump()
    payload["document_id"] = record.document_id
    payload["has_face_record"] = bool(face.one_to_one or face.dedup)
    payload["person_cluster_id"] = (
        face.dedup.person_cluster_id if face.dedup else None
    )
    payload["doc_image_url"] = doc_crop_url
    payload["raw_doc_image_url"] = record.doc_image_data_url
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
    live_image: UploadFile | None = File(None, description="Optional live traveler face photo (alias)"),
    checkpoint_id: str | None = Form(None, description="Border checkpoint UUID"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
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

    effective_live_file = live_photo or live_image
    live_bytes: bytes | None = None
    if effective_live_file:
        try:
            live_bytes = await effective_live_file.read()
            if len(live_bytes) == 0:
                live_bytes = None
        except Exception as exc:
            logger.warning("live_photo_read_failed", error=str(exc))
            live_bytes = None

    # Resolve checkpoint: prefer form value, fall back to JWT claim
    effective_checkpoint_id = checkpoint_id or current_user.checkpoint_id

    pipeline_result: PipelineResult = await run_pipeline(
        image_bytes=image_bytes,
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider=provider,
        live_image_bytes=live_bytes,
        checkpoint_id=effective_checkpoint_id,
        db=db,
    )


    # Persist to Supabase (images → Storage, results → scan_events + child tables)
    await scan_store.save_scan(
        db,
        pipeline_result,
        document_type=document_type.value if hasattr(document_type, "value") else str(document_type),
        checkpoint_id=effective_checkpoint_id,
        image_bytes=image_bytes,
        live_image_bytes=live_bytes,
        inspection_status="standard_clearance",
        officer_id=current_user.user_id,
    )

    # Append to audit ledger
    await append_event(
        event_type="scan",
        payload={"document_type": str(document_type), "checkpoint_id": effective_checkpoint_id},
        document_id=pipeline_result.document_id,
        officer_id=current_user.user_id,
        db=db,
    )

    status_str = "degraded" if pipeline_result.degraded else "complete"
    return UploadResponse(
        document_id=pipeline_result.document_id,
        status=status_str,
        pipeline=pipeline_result,
    )


# ---------------------------------------------------------------------------
# 1b. Face Photo Crop (no DB needed — pure computation)
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
# 2. Get full pipeline result (DB-backed)
# ---------------------------------------------------------------------------
@router.get(
    "/documents/{document_id}/pipeline",
    response_model=UploadResponse,
    summary="Retrieve the full screening pipeline result for a document",
)
async def get_document_pipeline(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    record = await _get_scan_or_404(db, document_id)
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
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
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
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
    validation = record.pipeline.validation
    results = validation.rule_results if validation else []
    failed = [r.rule_name for r in results if not r.passed]
    return {
        "document_id": document_id,
        "document_type": record.document_type,
        "passed": len(failed) == 0,
        "failed_rules": failed,
        "rule_results": [
            {"rule_name": r.rule_name, "passed": r.passed, "detail": r.detail}
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
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
    tampering = record.pipeline.tampering
    checks = tampering.checks if tampering else []
    return {
        "document_id": document_id,
        "flagged": tampering.flagged if tampering else False,
        "tampering_score": tampering.tampering_score if tampering else 0.0,
        "checks": [
            {
                "check_type": (
                    c.check_type.value if hasattr(c.check_type, "value") else str(c.check_type)
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
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
    return _face_response(record)


# ---------------------------------------------------------------------------
# 3. Live face verification (DB-backed)
# ---------------------------------------------------------------------------
from backend.orchestrator.core.blacklist import check_blacklist
from backend.risk_engine.schemas.risk import (
    FaceSubScore,
    RiskScoreRequest,
    TamperingSubScore,
    ValidationSubScore,
)


@router.post(
    "/documents/{document_id}/verify-live-face",
    summary="Submit live camera photo and run biometric face verification against document",
)
async def verify_live_face(
    document_id: str,
    file: UploadFile = File(..., description="Live camera snapshot (JPEG/PNG)"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
    try:
        live_bytes = await file.read()
        if len(live_bytes) == 0:
            raise ValueError("Live photo is empty")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_live_image", "reason": str(exc)},
        ) from exc

    # Fetch document bytes from Supabase Storage if URL is available
    doc_bytes = b""
    doc_url = record.doc_image_data_url or ""
    if doc_url.startswith("http"):
        # Signed URL from Supabase Storage — fetch via httpx
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(doc_url)
                if resp.status_code == 200:
                    doc_bytes = resp.content
        except Exception as exc:
            logger.warning("Failed to fetch document image from Storage URL", error=str(exc))
    elif "," in doc_url:
        # Legacy base64 data URL fallback
        try:
            doc_bytes = base64.b64decode(doc_url.split(",", 1)[1])
        except Exception:
            doc_bytes = b""

    face_res = await call_face_service(
        doc_image_bytes=doc_bytes,
        live_image_bytes=live_bytes,
        current_doc_id=document_id,
    )

    # Upload live image to Supabase Storage
    from backend.orchestrator.storage import supabase_storage
    live_url = await supabase_storage.upload_live_capture_image(live_bytes, document_id)

    # Update scan_events with live image URL and new face result in pipeline_snapshot
    record.pipeline.face = face_res
    record.live_image_data_url = live_url

    # Persist face verification result row
    try:
        scan_id = uuid.UUID(document_id)
        one_to_one = face_res.one_to_one
        dedup = face_res.dedup
        liveness = face_res.liveness

        # Upsert face_verification_results
        from sqlalchemy import delete as sa_delete
        await db.execute(
            sa_delete(FaceVerificationResult).where(
                FaceVerificationResult.scan_event_id == scan_id
            )
        )
        fvr = FaceVerificationResult(
            scan_event_id=scan_id,
            one_to_one_matched=one_to_one.matched if one_to_one else None,
            match_score=one_to_one.match_score if one_to_one else None,
            cosine_similarity=one_to_one.cosine_similarity if one_to_one else None,
            dedup_has_duplicates=dedup.has_duplicates if dedup else None,
            dedup_hits=([h.model_dump() for h in dedup.hits] if dedup else None),
            liveness_is_live=liveness.is_live if liveness else None,
            liveness_score=liveness.liveness_score if liveness else None,
            bypassed=face_res.bypassed,
            bypassed_reason=face_res.bypassed_reason,
        )
        db.add(fvr)

        # Update scan_events.live_image_url and pipeline_snapshot
        event_row = await db.get(ScanEvent, scan_id)
        if event_row:
            event_row.live_image_url = live_url
            event_row.pipeline_snapshot = record.pipeline.model_dump(mode="json")
    except Exception as exc:
        logger.warning("Failed to persist face verification result", error=str(exc))

    # Re-evaluate composite risk score
    ext = record.pipeline.extraction
    tamp = record.pipeline.tampering
    val = record.pipeline.validation
    one_to_one = face_res.one_to_one
    dedup = face_res.dedup

    face_sub = FaceSubScore(
        cosine_similarity=one_to_one.cosine_similarity if one_to_one else None,
        matched=one_to_one.matched if one_to_one else None,
        has_duplicates=dedup.has_duplicates if dedup else False,
        dedup_hit_count=len(dedup.hits) if dedup else 0,
    )
    val_sub = ValidationSubScore(
        total_rules=len(val.rule_results) if val else 0,
        failed_rules=len(val.failed_rules) if val else 0,
        failed_rule_names=val.failed_rules if val else [],
        rule_details={r.rule_name: r.detail for r in (val.rule_results if val else []) if not r.passed},
    )
    tamp_sub = TamperingSubScore(
        overall_score=tamp.tampering_score if tamp else 0.0,
        flagged=tamp.flagged if tamp else False,
        flagged_checks=[
            (c.check_type.value if hasattr(c.check_type, "value") else str(c.check_type))
            for c in (tamp.checks if tamp else []) if c.flagged
        ],
        check_details={
            (c.check_type.value if hasattr(c.check_type, "value") else str(c.check_type)): c.detail
            for c in (tamp.checks if tamp else []) if c.flagged
        },
    )
    fields = ext.fields if ext else []
    bl_score = await check_blacklist(fields=fields, db=db)
    risk_req = RiskScoreRequest(
        document_id=document_id,
        checkpoint_type=getattr(record, "checkpoint_type", None),
        validation_sub=val_sub,
        tampering_sub=tamp_sub,
        face_sub=face_sub,
        blacklist_sub=bl_score,
        cross_checkpoint_sub=None,
    )
    updated_risk = await call_risk_engine(risk_req)
    record.pipeline.risk_score = updated_risk

    # Append to audit ledger
    await append_event(
        event_type="face_verification",
        payload={
            "matched": one_to_one.matched if one_to_one else False,
            "match_score": one_to_one.match_score if one_to_one else 0.0,
            "cluster_id": dedup.person_cluster_id if dedup else None,
            "checkpoint_id": current_user.checkpoint_id,
        },
        document_id=document_id,
        officer_id=current_user.user_id,
        db=db,
    )

    await db.commit()

    return {
        "document_id": document_id,
        "face": _face_response(record),
        "risk_score": {
            "score": updated_risk.score,
            "band": updated_risk.band.value,
            "reasons": updated_risk.reasons,
            "sub_scores": updated_risk.sub_scores.model_dump() if updated_risk.sub_scores else None,
        },
        "live_image_url": live_url,
        "doc_image_url": record.doc_face_crop_data_url or record.doc_image_data_url,
    }


@router.get(
    "/documents/{document_id}/risk-score",
    summary="Retrieve computed risk score, band, and reasons",
)
async def get_document_risk(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_scan_or_404(db, document_id)
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
# 7. Officer Decision Recording (DB-backed)
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
    db: AsyncSession = Depends(get_db),
) -> DecisionResponse:
    await _get_scan_or_404(db, document_id)

    acting_officer_id = body.officer_id or current_user.user_id

    # Insert officer_decisions row
    try:
        scan_id = uuid.UUID(document_id)
        officer_uuid = None
        try:
            officer_uuid = uuid.UUID(acting_officer_id) if acting_officer_id else None
        except ValueError:
            pass

        decision_row = OfficerDecision(
            scan_event_id=scan_id,
            officer_id=officer_uuid,
            decision=body.decision,
            notes=body.notes,
        )
        db.add(decision_row)

        # Also update inspection_status on scan_events for decision-driven status changes
        decision_to_status = {
            "approve": "approved",
            "reject": "rejected",
            "flag": "secondary_inspection",
            "escalate": "secondary_inspection",
        }
        new_status = decision_to_status.get(body.decision.lower())
        if new_status:
            await scan_store.update_inspection_status(db, document_id, new_status)

    except Exception as exc:
        logger.warning("Failed to persist officer decision row", error=str(exc))

    # Append to audit ledger
    ledger_payload = {
        "decision": body.decision,
        "notes": body.notes,
        "officer_id": acting_officer_id,
    }
    ledger_entry = await append_event(
        event_type="officer_decision",
        payload=ledger_payload,
        document_id=document_id,
        officer_id=acting_officer_id,
        db=db,
    )

    logger.info(
        "officer_decision_recorded",
        document_id=document_id,
        officer_id=acting_officer_id,
        decision=body.decision,
        sequence_num=ledger_entry.sequence_num,
    )

    return DecisionResponse(
        document_id=document_id,
        decision=body.decision,
        recorded=True,
        ledger_sequence=ledger_entry.sequence_num,
    )


# ---------------------------------------------------------------------------
# 8. Document Audit Ledger Trail (DB-backed)
# ---------------------------------------------------------------------------
@router.get(
    "/audit/{document_id}",
    summary="Retrieve full hash-chained event trail for a document investigation",
)
async def get_document_audit_trail(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(AUDIT_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    # Verify document exists first (may raise 404)
    await _get_scan_or_404(db, document_id)

    from sqlalchemy import select
    try:
        scan_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    stmt = (
        select(AuditLedgerEntry)
        .where(AuditLedgerEntry.scan_event_id == scan_id)
        .order_by(AuditLedgerEntry.sequence_num.asc())
    )
    entries = (await db.execute(stmt)).scalars().all()

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
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# 9. Cross-Checkpoint Cluster History (DB-backed)
# ---------------------------------------------------------------------------
@router.get(
    "/clusters/{person_cluster_id}",
    summary="Retrieve full cross-checkpoint history and multi-identity flags for a person cluster",
)
async def get_cluster_history_endpoint(
    person_cluster_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    from backend.cross_checkpoint_service.core.face_graph import get_cluster_history

    try:
        history = await get_cluster_history(person_cluster_id, db=db)
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
# 10. Secondary Inspection Queue (DB-backed)
# ---------------------------------------------------------------------------
@router.get(
    "/documents/secondary-queue",
    summary="List all documents routed to the Secondary Inspection Queue",
)
async def get_secondary_inspection_queue(
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    queue_items = []
    for record in await scan_store.list_secondary_queue(db):
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
