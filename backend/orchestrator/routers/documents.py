"""
Orchestrator Documents & Audit Router — /api/v1/documents/* and /api/v1/audit/*

All endpoints now read from and write to Supabase via the async SQLAlchemy session.
In-memory scan store references replaced with DB-backed scan_store functions.
"""

import asyncio
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
from backend.orchestrator.core.pipeline import run_stage1_pipeline, run_stage2_pipeline
from backend.orchestrator.core import scan_store
from backend.orchestrator.db.session import get_db, get_db_optional
from backend.orchestrator.db.models import (
    AuditLedgerEntry,
    FaceVerificationResult,
    OfficerDecision,
    RiskResult,
    ScanEvent,
)
from backend.orchestrator.schemas.pipeline import (
    DecisionRequest,
    DecisionResponse,
    UploadResponse,
)

logger = get_logger("orchestrator.router")

router = APIRouter(prefix="/api/v1", tags=["Documents & Screening"])

STANDARD_ROLES = ["officer", "supervisor", "admin"]
AUDIT_ROLES = ["supervisor", "auditor", "admin"]


async def _bg_append_event(
    event_type: str,
    payload: dict,
    document_id: str | None,
    officer_id: str | None,
) -> None:
    """Commit audit ledger entry asynchronously in background so HTTP response returns instantly."""
    try:
        from backend.orchestrator.db.session import get_session_factory
        factory = await get_session_factory()
        async with factory() as session:
            await append_event(
                event_type=event_type,
                payload=payload,
                document_id=document_id,
                officer_id=officer_id,
                db=session,
            )
    except Exception as exc:
        logger.warning("background_append_event_failed", event_type=event_type, error=str(exc))


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


async def _get_scan_or_404(db: "AsyncSession | None", document_id: str) -> scan_store.ScanRecord:
    """Fetch a scan from DB/cache/SQLite or raise 404."""
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
# 1. Document Upload & Stage 1 Screening Pipeline
# ---------------------------------------------------------------------------
@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload document and execute Stage 1 screening pipeline (OCR, Tampering, Validation)",
)
async def upload_and_screen_document(
    file: UploadFile = File(..., description="Document scan image (JPEG/PNG)"),
    document_type: DocumentType = Form(default=DocumentType.PASSPORT),
    checkpoint_type: CheckpointType = Form(default=CheckpointType.AIRPORT),
    provider: str = Form(default="local"),
    live_photo: UploadFile | None = File(None, description="Optional live traveler face photo (legacy parameter)"),
    live_image: UploadFile | None = File(None, description="Optional live traveler face photo alias (legacy parameter)"),
    checkpoint_id: str | None = Form(None, description="Border checkpoint UUID"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: AsyncSession | None = Depends(get_db_optional),
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

    effective_checkpoint_id = checkpoint_id or current_user.checkpoint_id

    # Extract face crop in parallel with Stage 1 execution (0 added latency)
    import asyncio
    from backend.face_service.core.embedding import extract_face_crop_bytes

    crop_task = asyncio.to_thread(extract_face_crop_bytes, image_bytes)
    stage1_task = run_stage1_pipeline(
        image_bytes=image_bytes,
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider=provider,
        checkpoint_id=effective_checkpoint_id,
        db=db,
    )

    (crop_bytes, face_found), (pipeline_result, meta) = await asyncio.gather(crop_task, stage1_task)
    doc_crop = crop_bytes if (face_found and crop_bytes) else None

    # Persist Stage 1 result to Supabase with status "pending_biometric"
    record = await scan_store.save_scan(
        db,
        pipeline_result,
        document_type=document_type.value if hasattr(document_type, "value") else str(document_type),
        checkpoint_id=effective_checkpoint_id,
        image_bytes=image_bytes,
        doc_face_crop_bytes=doc_crop,
        live_image_bytes=None,
        inspection_status="pending_biometric",
        officer_id=current_user.user_id,
    )

    # Append Stage 1 audit ledger event in background
    asyncio.create_task(
        _bg_append_event(
            event_type="document_screened",
            payload={
                "document_type": str(document_type),
                "checkpoint_id": effective_checkpoint_id,
                "duration_ms": meta.get("duration_ms"),
                "tampering_score": pipeline_result.tampering.tampering_score if pipeline_result.tampering else None,
                "validation_passed": pipeline_result.validation.passed if pipeline_result.validation else None,
            },
            document_id=pipeline_result.document_id,
            officer_id=current_user.user_id,
        )
    )

    status_str = "pending_biometric" if not pipeline_result.degraded else "degraded"
    return UploadResponse(
        document_id=pipeline_result.document_id,
        status=status_str,
        pipeline=pipeline_result,
        doc_image_url=record.doc_image_data_url,
        doc_face_crop_url=record.doc_face_crop_data_url,
        live_image_url=record.live_image_data_url,
        inspection_status=record.inspection_status,
    )


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
    db: "AsyncSession | None" = Depends(get_db_optional),
) -> UploadResponse:
    record = await _get_scan_or_404(db, document_id)
    return UploadResponse(
        document_id=record.document_id,
        status=record.inspection_status or ("degraded" if record.pipeline.degraded else "complete"),
        pipeline=record.pipeline,
        doc_image_url=record.doc_image_data_url,
        doc_face_crop_url=record.doc_face_crop_data_url,
        live_image_url=record.live_image_data_url,
        inspection_status=record.inspection_status,
    )


@router.get(
    "/documents/{document_id}/extraction",
    summary="Retrieve OCR extracted fields and MRZ status for a document",
)
async def get_document_extraction(
    document_id: str,
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: "AsyncSession | None" = Depends(get_db_optional),
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
    db: "AsyncSession | None" = Depends(get_db_optional),
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
    db: "AsyncSession | None" = Depends(get_db_optional),
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
    db: "AsyncSession | None" = Depends(get_db_optional),
):
    record = await _get_scan_or_404(db, document_id)
    return _face_response(record)


# ---------------------------------------------------------------------------
# 3. Stage 2 Biometric Verification & Risk Scoring Pipeline (DB-backed)
# ---------------------------------------------------------------------------
@router.post(
    "/documents/{document_id}/verify-live-face",
    summary="Submit live camera photo and run Stage 2 biometric face verification + risk scoring against document",
)
async def verify_live_face(
    document_id: str,
    file: UploadFile = File(..., description="Live camera snapshot (JPEG/PNG)"),
    current_user: UserTokenData = Depends(require_roles(STANDARD_ROLES)),
    db: "AsyncSession | None" = Depends(get_db_optional),
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

    # Fetch document / face crop bytes from in-memory cache or Supabase Storage signed URL
    doc_bytes = scan_store.get_cached_doc_crop(document_id) or b""
    if not doc_bytes:
        doc_url = record.doc_face_crop_data_url or record.doc_image_data_url or ""
        if doc_url.startswith("http"):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(doc_url)
                    if resp.status_code == 200:
                        doc_bytes = resp.content
            except Exception as exc:
                logger.warning("Failed to fetch document image from Storage URL", error=str(exc))
        elif "," in doc_url:
            try:
                doc_bytes = base64.b64decode(doc_url.split(",", 1)[1])
            except Exception:
                doc_bytes = b""

    # Execute Stage 2 LangGraph StateGraph pipeline
    doc_type_enum = DocumentType.PASSPORT
    try:
        doc_type_enum = DocumentType(record.document_type)
    except Exception:
        pass

    stage2_result, meta = await run_stage2_pipeline(
        doc_image_bytes=doc_bytes,
        live_image_bytes=live_bytes,
        document_id=document_id,
        stage1_result=record.pipeline,
        document_type=doc_type_enum,
        checkpoint_id=record.checkpoint_id or current_user.checkpoint_id,
        db=db,
    )

    # Upload live image to Supabase Storage — fall back to data URL if offline
    from backend.orchestrator.storage import supabase_storage
    live_url: str | None = None
    try:
        live_url = await supabase_storage.upload_live_capture_image(live_bytes, document_id)
    except Exception as exc:
        logger.warning("live_image_upload_failed_using_data_url", error=str(exc))
    if not live_url:
        live_url = f"data:image/jpeg;base64,{base64.b64encode(live_bytes).decode('ascii')}"

    # Update record view model and status
    record.pipeline = stage2_result
    record.live_image_data_url = live_url
    record.inspection_status = meta.get("inspection_status", "standard_clearance")

    # Persist Stage 2 child tables and scan_event update
    if db is not None:
        # ── ONLINE: write to Supabase ────────────────────────────────────────
        try:
            scan_id = uuid.UUID(document_id)
            from sqlalchemy import delete as sa_delete

            # Upsert face_verification_results
            face_res = stage2_result.face
            if face_res:
                await db.execute(
                    sa_delete(FaceVerificationResult).where(
                        FaceVerificationResult.scan_event_id == scan_id
                    )
                )
                one_to_one = face_res.one_to_one
                dedup = face_res.dedup
                liveness = face_res.liveness
                db.add(FaceVerificationResult(
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
                ))

            # Upsert risk_results
            risk_res = stage2_result.risk_score
            if risk_res:
                await db.execute(
                    sa_delete(RiskResult).where(RiskResult.scan_event_id == scan_id)
                )
                db.add(RiskResult(
                    scan_event_id=scan_id,
                    score=risk_res.score,
                    band=risk_res.band.value if hasattr(risk_res.band, "value") else str(risk_res.band),
                    reasons=risk_res.reasons,
                    sub_scores=risk_res.sub_scores.model_dump() if risk_res.sub_scores else None,
                ))

            # Update scan_events
            event_row = await db.get(ScanEvent, scan_id)
            if event_row:
                event_row.live_image_url = live_url
                event_row.inspection_status = record.inspection_status
                event_row.pipeline_snapshot = record.pipeline.model_dump(mode="json")

            await db.commit()
        except Exception as exc:
            logger.warning("Failed to persist Stage 2 DB updates", error=str(exc))
    else:
        # ── OFFLINE: merge into SQLite pending_screenings ────────────────────
        from backend.orchestrator.core.offline_sync import get_offline_store
        try:
            stage2_dict = stage2_result.model_dump(mode="json")
            get_offline_store().update_offline_screening_stage2(
                document_id=document_id,
                stage2_payload={
                    **stage2_dict,
                    "live_image_data_url": live_url,
                },
                live_image_url=live_url,
                inspection_status=record.inspection_status,
            )
        except Exception as exc:
            logger.warning("Failed to persist Stage 2 offline update", error=str(exc))

    # Update in-memory cache with final record
    scan_store.set_cached_scan(document_id, record)

    # Append distinct Stage 2 event to audit ledger
    one_to_one = stage2_result.face.one_to_one if stage2_result.face else None
    dedup = stage2_result.face.dedup if stage2_result.face else None
    risk = stage2_result.risk_score

    # Append distinct Stage 2 event to audit ledger in background
    asyncio.create_task(
        _bg_append_event(
            event_type="biometric_verified",
            payload={
                "matched": one_to_one.matched if one_to_one else False,
                "match_score": one_to_one.match_score if one_to_one else 0.0,
                "cluster_id": dedup.person_cluster_id if dedup else None,
                "risk_score": risk.score if risk else None,
                "risk_band": risk.band.value if risk else None,
                "inspection_status": record.inspection_status,
                "duration_ms": meta.get("duration_ms"),
                "checkpoint_id": current_user.checkpoint_id,
            },
            document_id=document_id,
            officer_id=current_user.user_id,
        )
    )

    return {
        "document_id": document_id,
        "face": _face_response(record),
        "risk_score": {
            "score": risk.score if risk else 0.0,
            "band": risk.band.value if risk else "low",
            "reasons": risk.reasons if risk else [],
            "sub_scores": risk.sub_scores.model_dump() if (risk and risk.sub_scores) else None,
        },
        "cross_checkpoint": stage2_result.cross_checkpoint.model_dump() if stage2_result.cross_checkpoint else None,
        "inspection_status": record.inspection_status,
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
    db: "AsyncSession | None" = Depends(get_db_optional),
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
    db: "AsyncSession | None" = Depends(get_db_optional),
) -> DecisionResponse:
    await _get_scan_or_404(db, document_id)

    acting_officer_id = body.officer_id or current_user.user_id

    if db is not None:
        # ── ONLINE: persist decision row and update scan_events ──────────────
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
    else:
        # ── OFFLINE: record decision in SQLite ───────────────────────────────
        from backend.orchestrator.core.offline_sync import get_offline_store
        try:
            get_offline_store().record_offline_decision(
                document_id=document_id,
                decision=body.decision,
                notes=body.notes,
            )
        except Exception as exc:
            logger.warning("Failed to record offline officer decision", error=str(exc))

    # Update in-memory cached record status
    cached = scan_store.get_cached_scan(document_id)
    if cached:
        decision_to_status_map = {
            "approve": "approved",
            "reject": "rejected",
            "flag": "secondary_inspection",
            "escalate": "secondary_inspection",
        }
        new_status = decision_to_status_map.get(body.decision.lower())
        if new_status:
            cached.inspection_status = new_status

    # Append to audit ledger (best-effort — uses its own session factory)
    ledger_payload = {
        "decision": body.decision,
        "notes": body.notes,
        "officer_id": acting_officer_id,
    }
    sequence_num = 0
    try:
        ledger_entry = await append_event(
            event_type="officer_decision",
            payload=ledger_payload,
            document_id=document_id,
            officer_id=acting_officer_id,
            db=db,
        )
        sequence_num = ledger_entry.sequence_num
    except Exception as exc:
        logger.warning("audit_ledger_append_failed_offline", error=str(exc))

    logger.info(
        "officer_decision_recorded",
        document_id=document_id,
        officer_id=acting_officer_id,
        decision=body.decision,
        sequence_num=sequence_num,
    )

    return DecisionResponse(
        document_id=document_id,
        decision=body.decision,
        recorded=True,
        ledger_sequence=sequence_num,
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
    db: "AsyncSession | None" = Depends(get_db_optional),
):
    if db is None:
        return {"queue": [], "count": 0, "offline": True}
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
