"""
Orchestration Pipeline — End-to-end execution of the document screening workflow.

SEQUENTIAL PIPELINE STEPS:
  1. Save raw image scan to MinIO object storage.
  2. Create Document record in PostgreSQL.
  3. Extract text & MRZ check digits via OCR Service (Module 1).
  4. Run YAML Business Rules validation via Validation Service (Module 2).
  5. Perform multi-layer forensic tampering checks via Tampering Service (Module 3).
  6. Execute Biometric 1:1 match & 1:N deduplication via Face Service (Module 4).
  7. Check watchlist / blacklist repository.
  8. Compute explainable weighted risk score & band via Risk Engine (Module 5).
  9. Append immutable event to the Audit Ledger (Module 6).
 10. Persist all relational results to PostgreSQL.
"""

import time
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import DocumentType, ExtractionResponse
from backend.validation_service.schemas.validation import ValidationResponse
from backend.tampering_service.schemas.tampering import TamperingResponse
from backend.face_service.schemas.face import FullFaceVerificationResponse
from backend.risk_engine.schemas.risk import (
    BlacklistSubScore,
    FaceSubScore,
    RiskScoreRequest,
    RiskScoreResponse,
    TamperingSubScore,
    ValidationSubScore,
)
from backend.orchestrator.core.blacklist import check_blacklist
from backend.orchestrator.core.service_clients import (
    call_audit_ledger,
    call_face_service,
    call_ocr_service,
    call_risk_engine,
    call_tampering_service,
    call_validation_service,
)
from backend.orchestrator.db.models import (
    Document,
    ExtractedField as ExtractedFieldModel,
    FaceEmbedding as FaceEmbeddingModel,
    RiskScore as RiskScoreModel,
    TamperingResult as TamperingResultModel,
    ValidationResult as ValidationResultModel,
)
from backend.orchestrator.schemas.pipeline import (
    PipelineResult,
    PipelineServiceStatuses,
    ServiceStatus,
)
from backend.orchestrator.storage.minio_client import upload_document_image

logger = get_logger("orchestrator.pipeline")


async def run_pipeline(
    image_bytes: bytes,
    document_type: DocumentType = DocumentType.PASSPORT,
    live_image_bytes: bytes | None = None,
    document_id: str | None = None,
    checkpoint_id: str | None = None,
    db: AsyncSession | None = None,
) -> PipelineResult:
    """
    Execute the full end-to-end document screening pipeline.
    """
    pipeline_start = time.perf_counter()
    doc_uuid = uuid.UUID(document_id) if document_id else uuid.uuid4()
    doc_id_str = str(doc_uuid)

    logger.info(
        "pipeline_started",
        document_id=doc_id_str,
        document_type=document_type.value,
        has_live_photo=bool(live_image_bytes),
    )

    statuses = PipelineServiceStatuses()
    degraded_modules: list[str] = []

    # ── 1. MinIO Upload ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    image_object_key = await upload_document_image(image_bytes, doc_id_str)
    duration_minio = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="minio_upload", document_id=doc_id_str, duration_ms=duration_minio)

    # ── 2. Create DB Record ──────────────────────────────────────────────────
    doc_record: Document | None = None
    if db is not None:
        try:
            doc_record = Document(
                id=doc_uuid,
                document_type=document_type.value,
                image_object_key=image_object_key,
                checkpoint_id=uuid.UUID(checkpoint_id) if checkpoint_id else None,
            )
            db.add(doc_record)
            await db.flush()
        except Exception as exc:
            logger.warning("Failed to initialize document DB row", error=str(exc))

    # ── 3. OCR Service (Module 1) ────────────────────────────────────────────
    t0 = time.perf_counter()
    extraction_res: ExtractionResponse | None = None
    try:
        extraction_res = await call_ocr_service(image_bytes, document_type)
        statuses.ocr = ServiceStatus(available=True)
    except Exception as exc:
        logger.error("OCR stage failed", error=str(exc), document_id=doc_id_str)
        statuses.ocr = ServiceStatus(available=False, error=str(exc))
        degraded_modules.append("OCR")
        extraction_res = ExtractionResponse(
            document_type=document_type,
            extraction_method="ocr",
            fields=[],
            mrz={"mrz_present": False, "checksum_valid": None, "checksum_failures": [], "mrz_fields": {}},
            warnings=[f"OCR failed: {exc}"],
        )

    duration_ocr = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="ocr_extraction", document_id=doc_id_str, duration_ms=duration_ocr)

    # ── 4. Validation Service (Module 2) ─────────────────────────────────────
    t0 = time.perf_counter()
    validation_res: ValidationResponse | None = None
    try:
        validation_res = await call_validation_service(
            document_type=document_type,
            fields=extraction_res.fields if extraction_res else [],
        )
        statuses.validation = ServiceStatus(available=True)
    except Exception as exc:
        logger.error("Validation stage failed", error=str(exc), document_id=doc_id_str)
        statuses.validation = ServiceStatus(available=False, error=str(exc))
        degraded_modules.append("Validation")
        validation_res = ValidationResponse(
            document_type=document_type,
            passed=False,
            failed_rules=["validation_service_unavailable"],
            rule_results=[],
        )

    duration_val = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="document_validation", document_id=doc_id_str, duration_ms=duration_val)

    # ── 5. Tampering Service (Module 3) ──────────────────────────────────────
    t0 = time.perf_counter()
    tampering_res: TamperingResponse | None = None
    try:
        tampering_res = await call_tampering_service(image_bytes)
        statuses.tampering = ServiceStatus(available=True)
    except Exception as exc:
        logger.error("Tampering detection failed", error=str(exc), document_id=doc_id_str)
        statuses.tampering = ServiceStatus(available=False, error=str(exc))
        degraded_modules.append("Tampering")
        tampering_res = TamperingResponse(
            flagged=False,
            tampering_score=0.0,
            checks=[],
            warnings=[f"Tampering check unavailable: {exc}"],
        )

    duration_tamp = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="tampering_detection", document_id=doc_id_str, duration_ms=duration_tamp)

    # ── 6. Face Verification (Module 4) ──────────────────────────────────────
    t0 = time.perf_counter()
    face_res: FullFaceVerificationResponse | None = None
    try:
        face_res = await call_face_service(
            doc_image_bytes=image_bytes,
            live_image_bytes=live_image_bytes,
            current_doc_id=doc_id_str,
        )
        statuses.face = ServiceStatus(available=True)
    except Exception as exc:
        logger.error("Face verification failed", error=str(exc), document_id=doc_id_str)
        statuses.face = ServiceStatus(available=False, error=str(exc))
        degraded_modules.append("FaceVerification")
        face_res = FullFaceVerificationResponse(document_id=doc_id_str)

    duration_face = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="face_verification", document_id=doc_id_str, duration_ms=duration_face)

    # ── 7. Watchlist / Blacklist Check ───────────────────────────────────────
    blacklist_sub_score = await check_blacklist(
        fields=extraction_res.fields if extraction_res else [],
        db=db,
    )

    # ── 8. Risk Scoring Engine (Module 5) ────────────────────────────────────
    t0 = time.perf_counter()

    # Assemble sub-scores
    val_sub = ValidationSubScore(
        total_rules=len(validation_res.rule_results) if validation_res else 0,
        failed_rules=len(validation_res.failed_rules) if validation_res else 0,
        failed_rule_names=validation_res.failed_rules if validation_res else [],
        rule_details={
            r.rule_name: r.detail
            for r in (validation_res.rule_results if validation_res else [])
            if not r.passed
        },
    )

    tamp_sub = TamperingSubScore(
        overall_score=tampering_res.tampering_score if tampering_res else 0.0,
        flagged=tampering_res.flagged if tampering_res else False,
        flagged_checks=[c.check_type.value for c in (tampering_res.checks if tampering_res else []) if c.flagged],
        check_details={
            c.check_type.value: c.detail
            for c in (tampering_res.checks if tampering_res else [])
            if c.flagged
        },
    )

    one_to_one = face_res.one_to_one if face_res else None
    dedup = face_res.dedup if face_res else None
    face_sub = FaceSubScore(
        cosine_similarity=one_to_one.cosine_similarity if one_to_one else None,
        matched=one_to_one.matched if one_to_one else None,
        has_duplicates=dedup.has_duplicates if dedup else False,
        dedup_hit_count=len(dedup.hits) if dedup else 0,
    )

    score_req = RiskScoreRequest(
        document_id=doc_id_str,
        validation=val_sub,
        tampering=tamp_sub,
        face=face_sub,
        blacklist=blacklist_sub_score,
        degraded_modules=degraded_modules,
    )

    risk_res: RiskScoreResponse | None = None
    try:
        risk_res = await call_risk_engine(score_req)
        statuses.risk_engine = ServiceStatus(available=True)
    except Exception as exc:
        logger.error("Risk scoring engine failed", error=str(exc), document_id=doc_id_str)
        statuses.risk_engine = ServiceStatus(available=False, error=str(exc))
        from backend.risk_engine.core.scoring import build_risk_response
        risk_res = build_risk_response(score_req)

    duration_risk = int((time.perf_counter() - t0) * 1000)
    logger.info("stage_complete", stage="risk_scoring", document_id=doc_id_str, duration_ms=duration_risk)

    # ── 9. Audit Ledger Event (Module 6) ─────────────────────────────────────
    t0 = time.perf_counter()
    ledger_payload = {
        "document_type": document_type.value,
        "risk_score": risk_res.score if risk_res else None,
        "risk_band": risk_res.band.value if risk_res else None,
        "reasons": risk_res.reasons if risk_res else [],
        "tampering_flagged": tampering_res.flagged if tampering_res else False,
        "validation_passed": validation_res.passed if validation_res else False,
    }
    await call_audit_ledger(
        event_type="scan",
        document_id=doc_id_str,
        payload=ledger_payload,
    )

    # ── 10. Persist All Relations in Postgres ────────────────────────────────
    if db is not None and doc_record is not None:
        try:
            # 1. Extracted fields
            if extraction_res and extraction_res.fields:
                for f in extraction_res.fields:
                    db.add(
                        ExtractedFieldModel(
                            document_id=doc_uuid,
                            field_name=f.field_name,
                            field_value=f.field_value,
                            confidence=f.confidence,
                        )
                    )

            # 2. Validation results
            if validation_res and validation_res.rule_results:
                for r in validation_res.rule_results:
                    db.add(
                        ValidationResultModel(
                            document_id=doc_uuid,
                            rule_name=r.rule_name,
                            passed=r.passed,
                            detail=r.detail,
                        )
                    )

            # 3. Tampering results
            if tampering_res and tampering_res.checks:
                for c in tampering_res.checks:
                    db.add(
                        TamperingResultModel(
                            document_id=doc_uuid,
                            check_type=c.check_type.value,
                            score=c.score,
                            flagged=c.flagged,
                            detail={"text": c.detail, **c.metadata},
                        )
                    )

            # 4. Face Embedding / Clustering
            if dedup and dedup.person_cluster_id:
                try:
                    cluster_uuid = uuid.UUID(dedup.person_cluster_id) if dedup.person_cluster_id else None
                except ValueError:
                    cluster_uuid = None
                db.add(
                    FaceEmbeddingModel(
                        document_id=doc_uuid,
                        embedding=None,  # Can store vector if pgvector active
                        person_cluster_id=cluster_uuid,
                    )
                )

            # 5. Risk score
            if risk_res:
                db.add(
                    RiskScoreModel(
                        document_id=doc_uuid,
                        score=risk_res.score,
                        band=risk_res.band.value,
                        reasons=risk_res.reasons,
                    )
                )

            await db.commit()
            logger.info("Persisted full pipeline results to PostgreSQL", document_id=doc_id_str)
        except Exception as exc:
            logger.error("DB persistence failed during pipeline run", error=str(exc), document_id=doc_id_str)
            await db.rollback()

    total_duration = int((time.perf_counter() - pipeline_start) * 1000)
    logger.info(
        "pipeline_completed",
        document_id=doc_id_str,
        score=risk_res.score if risk_res else None,
        band=risk_res.band.value if risk_res else None,
        degraded=len(degraded_modules) > 0,
        total_duration_ms=total_duration,
    )

    return PipelineResult(
        document_id=doc_id_str,
        degraded=len(degraded_modules) > 0,
        service_statuses=statuses,
        extraction=extraction_res,
        validation=validation_res,
        tampering=tampering_res,
        face=face_res,
        risk_score=risk_res,
    )
