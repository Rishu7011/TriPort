"""
LangGraph Orchestration Pipeline for BorderGuard-AI (Phase 7).

Architecture:
  - Directed Acyclic Graph (DAG) state machine using LangGraph StateGraph.
  - Parallel Fan-Out of initial visual & biometric workloads (OCR, Tampering, Face).
  - Conditional Edge 1: LLM Vision Fallback when OCR confidence is degraded.
  - Parallel Dependent Stage: YAML Rules Validation, Watchlist Cross-Check, Cross-Checkpoint Graph.
  - Synthesis & Risk Scoring Node.
  - Conditional Edge 2: Automated Routing between Standard Clearance vs Secondary Inspection Queue.
  - Append-Only Tamper-Evident Audit Logging & PostgreSQL Persistence.
"""

import asyncio
import time
import uuid
from typing import Annotated, Any, TypedDict
from langgraph.graph import StateGraph, START, END
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    CheckpointType,
    DocumentType,
    ExtractionResponse,
    MRZResult,
    ExtractionMethod,
)
from backend.validation_service.schemas.validation import ValidationResponse
from backend.tampering_service.schemas.tampering import TamperingResponse
from backend.face_service.schemas.face import FullFaceVerificationResponse
from backend.cross_checkpoint_service.schemas.cross_checkpoint import (
    ClusterAnalysisResponse,
    ClusterDocument,
)
from backend.risk_engine.schemas.risk import (
    BlacklistSubScore,
    CrossCheckpointSubScore,
    FaceSubScore,
    RiskBand,
    RiskScoreRequest,
    RiskScoreResponse,
    TamperingSubScore,
    ValidationSubScore,
)
from backend.orchestrator.core.blacklist import check_blacklist
from backend.orchestrator.core.service_clients import (
    call_audit_ledger,
    call_cross_checkpoint_service,
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

logger = get_logger("orchestrator.langgraph_pipeline")


def merge_degraded(left: list[str] | None, right: list[str] | None) -> list[str]:
    """LangGraph state reducer for merging degraded module lists from parallel nodes."""
    res = list(left or [])
    for item in (right or []):
        if item not in res:
            res.append(item)
    return res


# ---------------------------------------------------------------------------
# 1. Pipeline Typed State
# ---------------------------------------------------------------------------
class ScreeningState(TypedDict, total=False):
    """Global execution state passed between LangGraph nodes."""
    document_id: str
    image_bytes: bytes
    live_image_bytes: bytes | None
    document_type: DocumentType
    checkpoint_type: CheckpointType
    border_checkpoint_id: str | None
    provider: str
    image_object_key: str | None
    db: Any | None  # AsyncSession

    # Microservice outputs
    extraction: ExtractionResponse | None
    validation: ValidationResponse | None
    tampering: TamperingResponse | None
    face: FullFaceVerificationResponse | None
    blacklist: BlacklistSubScore | None
    cross_checkpoint: ClusterAnalysisResponse | None
    risk_score: RiskScoreResponse | None

    # Node individual availability flags (prevents parallel overwrite collisions)
    ocr_available: bool
    ocr_error: str | None
    tampering_available: bool
    tampering_error: str | None
    face_available: bool
    face_error: str | None
    validation_available: bool
    validation_error: str | None
    cross_checkpoint_available: bool
    cross_checkpoint_error: str | None
    risk_engine_available: bool
    risk_engine_error: str | None

    # Routing & status
    inspection_status: str  # "standard_clearance" | "secondary_inspection"
    inspection_reasons: list[str]
    degraded_modules: Annotated[list[str], merge_degraded]
    start_time: float


def _safe_uuid(val: Any) -> uuid.UUID | None:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# 2. Graph Nodes
# ---------------------------------------------------------------------------

async def minio_storage_node(state: ScreeningState) -> dict:
    """Store the image when object storage is available and create the document row."""
    doc_id = state["document_id"]
    try:
        image_key = await upload_document_image(state["image_bytes"], doc_id)
        db = state.get("db")
        if db is not None:
            doc_uuid = _safe_uuid(doc_id)
            doc_record = await db.get(Document, doc_uuid) if doc_uuid else None
            if doc_record is None:
                doc_record = Document(
                    id=doc_uuid,
                    document_type=state["document_type"].value,
                    image_object_key=image_key,
                    checkpoint_id=_safe_uuid(state.get("border_checkpoint_id")),
                )
                db.add(doc_record)
            else:
                doc_record.document_type = state["document_type"].value
                doc_record.image_object_key = image_key
                doc_record.checkpoint_id = _safe_uuid(state.get("border_checkpoint_id"))
            await db.flush()
        return {"image_object_key": image_key}
    except Exception as exc:
        logger.warning("MinIO / DB init warning in node", error=str(exc))
        return {"image_object_key": None}


async def ocr_extraction_node(state: ScreeningState) -> dict:
    """Extract text & MRZ from document image."""
    try:
        res = await call_ocr_service(
            image_bytes=state["image_bytes"],
            document_type=state["document_type"],
            checkpoint_type=state["checkpoint_type"],
            provider=state["provider"],
        )
        return {
            "extraction": res,
            "ocr_available": True,
            "ocr_error": None,
        }
    except Exception as exc:
        logger.error("OCR node execution failed", error=str(exc))
        fallback_res = ExtractionResponse(
            document_type=state["document_type"],
            checkpoint_type=state["checkpoint_type"],
            provider_used=state["provider"],
            extraction_method="ocr",
            fields=[],
            mrz=MRZResult(mrz_present=False, checksum_valid=None, checksum_failures=[], mrz_fields={}),
            warnings=[f"OCR failed: {exc}"],
        )
        return {
            "extraction": fallback_res,
            "ocr_available": False,
            "ocr_error": str(exc),
            "degraded_modules": ["OCR"],
        }


async def llm_vision_fallback_node(state: ScreeningState) -> dict:
    """Invoked conditionally if OCR extracted fields have low confidence."""
    ext = state.get("extraction")
    if not ext:
        return {}
    logger.info("Executing LLM Vision Fallback conditional branch")
    try:
        from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
        _, llm_fields = extract_fields_with_llm(state["image_bytes"], state["document_type"])
        if llm_fields:
            current_fields = {f.field_name: f for f in ext.fields}
            for f in llm_fields:
                current_fields[f.field_name] = f
            ext.fields = list(current_fields.values())
            ext.extraction_method = ExtractionMethod.LLM
            ext.warnings.append("LLM vision fallback applied due to low OCR confidence")
    except Exception as exc:
        logger.warning("LLM vision fallback node error", error=str(exc))
    return {"extraction": ext}


async def tampering_detection_node(state: ScreeningState) -> dict:
    """Run 5-layer forensic analysis (ELA, metadata, boundary, stamp dHash)."""
    try:
        res = await call_tampering_service(state["image_bytes"])
        return {
            "tampering": res,
            "tampering_available": True,
            "tampering_error": None,
        }
    except Exception as exc:
        logger.error("Tampering node execution failed", error=str(exc))
        fallback = TamperingResponse(
            flagged=False,
            tampering_score=0.0,
            checks=[],
            warnings=[f"Tampering check unavailable: {exc}"],
        )
        return {
            "tampering": fallback,
            "tampering_available": False,
            "tampering_error": str(exc),
            "degraded_modules": ["Tampering"],
        }


async def face_verification_node(state: ScreeningState) -> dict:
    """Execute 1:1 face verification and 1:N deduplication."""
    try:
        res = await call_face_service(
            doc_image_bytes=state["image_bytes"],
            live_image_bytes=state.get("live_image_bytes"),
            current_doc_id=state["document_id"],
        )
        return {
            "face": res,
            "face_available": True,
            "face_error": None,
        }
    except Exception as exc:
        logger.error("Face verification node failed", error=str(exc))
        fallback = FullFaceVerificationResponse(document_id=state["document_id"])
        return {
            "face": fallback,
            "face_available": False,
            "face_error": str(exc),
            "degraded_modules": ["FaceVerification"],
        }


async def validation_rules_node(state: ScreeningState) -> dict:
    """Evaluate business rules against extracted fields."""
    ext = state.get("extraction")
    fields = ext.fields if ext else []
    try:
        res = await call_validation_service(
            document_type=state["document_type"],
            fields=fields,
        )
        return {
            "validation": res,
            "validation_available": True,
            "validation_error": None,
        }
    except Exception as exc:
        logger.error("Validation node execution failed", error=str(exc))
        fallback = ValidationResponse(
            document_type=state["document_type"],
            passed=False,
            failed_rules=["validation_service_unavailable"],
            rule_results=[],
        )
        return {
            "validation": fallback,
            "validation_available": False,
            "validation_error": str(exc),
            "degraded_modules": ["Validation"],
        }


async def blacklist_check_node(state: ScreeningState) -> dict:
    """Cross-check extracted fields against national & Interpol watchlists."""
    ext = state.get("extraction")
    fields = ext.fields if ext else []
    bl_score = await check_blacklist(fields=fields, db=state.get("db"))
    return {"blacklist": bl_score}


async def cross_checkpoint_node(state: ScreeningState) -> dict:
    """Analyze multi-identity anomalies across checkpoints for the person's face cluster."""
    face = state.get("face")
    dedup = face.dedup if face else None

    if not dedup or not dedup.person_cluster_id:
        return {
            "cross_checkpoint": None,
            "cross_checkpoint_available": True,
            "cross_checkpoint_error": None,
        }

    try:
        ext = state.get("extraction")
        field_lookup = {
            f.field_name.lower(): f.field_value
            for f in (ext.fields if ext else [])
            if f.field_value
        }
        name_val = field_lookup.get("name") or field_lookup.get("full_name") or field_lookup.get("surname")
        doc_no = field_lookup.get("document_number") or field_lookup.get("doc_number") or field_lookup.get("passport_number")
        nat_val = field_lookup.get("nationality") or field_lookup.get("country")
        dob_val = field_lookup.get("date_of_birth") or field_lookup.get("dob")

        curr_doc = ClusterDocument(
            document_id=state["document_id"],
            checkpoint_type=state["checkpoint_type"].value,
            checkpoint_id=state.get("border_checkpoint_id"),
            uploaded_at=None,
            document_type=state["document_type"].value,
            name=name_val,
            document_number=doc_no,
            nationality=nat_val,
            date_of_birth=dob_val,
        )

        res = await call_cross_checkpoint_service(
            person_cluster_id=dedup.person_cluster_id,
            current_doc=curr_doc,
            current_risk_band="low",
        )
        return {
            "cross_checkpoint": res,
            "cross_checkpoint_available": True,
            "cross_checkpoint_error": None,
        }
    except Exception as exc:
        logger.error("Cross-checkpoint node execution failed", error=str(exc))
        return {
            "cross_checkpoint": None,
            "cross_checkpoint_available": False,
            "cross_checkpoint_error": str(exc),
            "degraded_modules": ["CrossCheckpoint"],
        }


async def risk_engine_node(state: ScreeningState) -> dict:
    """Combine all signals into a weighted risk score and plain-language explanation."""
    val = state.get("validation")
    val_sub = ValidationSubScore(
        total_rules=len(val.rule_results) if val else 0,
        failed_rules=len(val.failed_rules) if val else 0,
        failed_rule_names=val.failed_rules if val else [],
        rule_details={r.rule_name: r.detail for r in (val.rule_results if val else []) if not r.passed},
    )

    tamp = state.get("tampering")
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

    face = state.get("face")
    one_to_one = face.one_to_one if face else None
    dedup = face.dedup if face else None
    face_sub = FaceSubScore(
        cosine_similarity=one_to_one.cosine_similarity if one_to_one else None,
        matched=one_to_one.matched if one_to_one else None,
        has_duplicates=dedup.has_duplicates if dedup else False,
        dedup_hit_count=len(dedup.hits) if dedup else 0,
    )

    cc = state.get("cross_checkpoint")
    if cc:
        flag_names = [f.flag_type.value for f in cc.flags]
        flag_details = [f.detail for f in cc.flags]
        cc_sub = CrossCheckpointSubScore(
            cross_checkpoint_risk=cc.cross_checkpoint_risk,
            flags=flag_names,
            flag_details=flag_details,
            repeat_offender_hit=cc.repeat_offender_hit,
            prior_critical_or_high_count=cc.prior_critical_or_high_count,
        )
    else:
        cc_sub = CrossCheckpointSubScore()

    degraded_list = state.get("degraded_modules", [])
    score_req = RiskScoreRequest(
        document_id=state["document_id"],
        validation=val_sub,
        tampering=tamp_sub,
        face=face_sub,
        blacklist=state.get("blacklist") or BlacklistSubScore(),
        cross_checkpoint=cc_sub,
        degraded_modules=degraded_list,
    )

    try:
        risk_res = await call_risk_engine(score_req)
        return {
            "risk_score": risk_res,
            "risk_engine_available": True,
            "risk_engine_error": None,
        }
    except Exception as exc:
        logger.error("Risk engine node failed, using fallback", error=str(exc))
        from backend.risk_engine.core.scoring import build_risk_response
        risk_res = build_risk_response(score_req)
        return {
            "risk_score": risk_res,
            "risk_engine_available": False,
            "risk_engine_error": str(exc),
        }


async def secondary_inspection_node(state: ScreeningState) -> dict:
    """Conditional Node: Routes high-threat documents to secondary inspection queue."""
    risk = state.get("risk_score")
    reasons = risk.reasons if risk else ["Elevated risk threshold exceeded"]
    logger.warning("Routing document to Secondary Inspection Queue", doc_id=state["document_id"], band=risk.band.value if risk else None)
    return {
        "inspection_status": "secondary_inspection",
        "inspection_reasons": reasons,
    }


async def standard_clearance_node(state: ScreeningState) -> dict:
    """Conditional Node: Marks clean scans for standard officer review."""
    logger.info("Document cleared for standard processing", doc_id=state["document_id"])
    return {
        "inspection_status": "standard_clearance",
        "inspection_reasons": ["Standard verification passed"],
    }


async def audit_ledger_node(state: ScreeningState) -> dict:
    """Append immutable event to the hash-chained audit ledger."""
    risk = state.get("risk_score")
    val = state.get("validation")
    tamp = state.get("tampering")
    cc = state.get("cross_checkpoint")

    ledger_payload = {
        "document_type": state["document_type"].value,
        "risk_score": risk.score if risk else None,
        "risk_band": risk.band.value if risk else None,
        "inspection_status": state.get("inspection_status", "standard_clearance"),
        "reasons": risk.reasons if risk else [],
        "tampering_flagged": tamp.flagged if tamp else False,
        "validation_passed": val.passed if val else False,
        "cross_checkpoint_flags": [f.flag_type.value for f in cc.flags] if cc else [],
        "repeat_offender": cc.repeat_offender_hit if cc else False,
    }

    try:
        await call_audit_ledger(
            event_type="scan",
            document_id=state["document_id"],
            payload=ledger_payload,
        )
    except Exception as exc:
        logger.debug("Audit ledger logging in node skipped", error=str(exc))
    return {}


async def db_persistence_node(state: ScreeningState) -> dict:
    """Commit all relational results to PostgreSQL."""
    db: AsyncSession = state.get("db")
    doc_uuid = _safe_uuid(state["document_id"])

    if db is not None and doc_uuid:
        try:
            # A client retry may execute a scan again with the same document ID.
            # Replace derived records atomically rather than violating their
            # document-scoped unique constraints.
            for model in (
                ExtractedFieldModel,
                ValidationResultModel,
                TamperingResultModel,
                FaceEmbeddingModel,
                RiskScoreModel,
            ):
                await db.execute(delete(model).where(model.document_id == doc_uuid))

            ext = state.get("extraction")
            if ext and ext.fields:
                for f in ext.fields:
                    db.add(
                        ExtractedFieldModel(
                            document_id=doc_uuid,
                            field_name=f.field_name,
                            field_value=f.field_value,
                            confidence=f.confidence,
                        )
                    )

            val = state.get("validation")
            if val and val.rule_results:
                for r in val.rule_results:
                    db.add(
                        ValidationResultModel(
                            document_id=doc_uuid,
                            rule_name=r.rule_name,
                            passed=r.passed,
                            detail=r.detail,
                        )
                    )

            tamp = state.get("tampering")
            if tamp and tamp.checks:
                for c in tamp.checks:
                    check_type = (
                        c.check_type.value
                        if hasattr(c.check_type, "value")
                        else str(c.check_type)
                    )
                    detail_payload: dict[str, Any] = {
                        "detail": c.detail,
                        **c.metadata,
                    }
                    if check_type == "ela" and tamp.ela_heatmap_base64:
                        detail_payload["ela_heatmap_base64"] = tamp.ela_heatmap_base64
                    db.add(
                        TamperingResultModel(
                            document_id=doc_uuid,
                            check_type=check_type,
                            score=c.score,
                            flagged=c.flagged,
                            detail=detail_payload,
                        )
                    )

            face = state.get("face")
            dedup = face.dedup if face else None
            if dedup and dedup.person_cluster_id:
                cluster_uuid = _safe_uuid(dedup.person_cluster_id)
                db.add(
                    FaceEmbeddingModel(
                        document_id=doc_uuid,
                        embedding=None,
                        person_cluster_id=cluster_uuid,
                    )
                )

            risk = state.get("risk_score")
            if risk:
                db.add(
                    RiskScoreModel(
                        document_id=doc_uuid,
                        score=risk.score,
                        band=risk.band.value,
                        reasons=risk.reasons,
                    )
                )

            await db.commit()
            logger.info("Persisted all LangGraph entities to PostgreSQL", document_id=str(doc_uuid))
        except Exception as exc:
            logger.error("DB persistence node error", error=str(exc))
            await db.rollback()

    return {}


# ---------------------------------------------------------------------------
# 3. Conditional Routers (Edges)
# ---------------------------------------------------------------------------

def check_ocr_quality(state: ScreeningState) -> str:
    """
    Conditional Edge: Route to LLM Vision Fallback if OCR confidence is low
    or fields are missing on complex document formats.
    """
    ext = state.get("extraction")
    if not ext:
        return "fallback"

    doc_type = state.get("document_type", DocumentType.PASSPORT)
    fields = ext.fields or []

    # Check 1: No fields extracted and no MRZ
    if not fields and (not ext.mrz or not ext.mrz.mrz_present):
        return "fallback"

    # Check 2: Complex formats (Driving License, Permit) with < 2 fields
    if doc_type in [DocumentType.DRIVING_LICENSE, DocumentType.PERMIT] and len(fields) < 2:
        return "fallback"

    # Check 3: Low average confidence (< 0.60)
    confidences = [f.confidence for f in fields if f.confidence is not None]
    if confidences and (sum(confidences) / len(confidences)) < 0.60:
        return "fallback"

    return "continue"


def route_by_threat_level(state: ScreeningState) -> str:
    """
    Conditional Edge: Route to Secondary Inspection Queue if risk band is High/Critical,
    or a Blacklist/Watchlist hit occurred, or repeat offender was flagged.
    """
    risk = state.get("risk_score")
    bl = state.get("blacklist")
    cc = state.get("cross_checkpoint")

    if risk and hasattr(risk, "band") and risk.band in [RiskBand.HIGH, RiskBand.CRITICAL]:
        return "secondary"

    if bl and getattr(bl, "hit", False):
        return "secondary"

    if cc and getattr(cc, "repeat_offender_hit", False):
        return "secondary"

    return "clearance"


# ---------------------------------------------------------------------------
# 4. StateGraph Builder & Compilation
# ---------------------------------------------------------------------------

def build_screening_graph():
    """Construct and compile the full LangGraph screening state machine."""
    workflow = StateGraph(ScreeningState)

    # Register Nodes
    workflow.add_node("minio_storage", minio_storage_node)
    workflow.add_node("ocr_extraction", ocr_extraction_node)
    workflow.add_node("llm_vision_fallback", llm_vision_fallback_node)
    workflow.add_node("tampering_detection", tampering_detection_node)
    workflow.add_node("face_verification", face_verification_node)
    workflow.add_node("validation_rules", validation_rules_node)
    workflow.add_node("blacklist_check", blacklist_check_node)
    workflow.add_node("cross_checkpoint", cross_checkpoint_node)
    workflow.add_node("risk_engine", risk_engine_node)
    workflow.add_node("secondary_inspection", secondary_inspection_node)
    workflow.add_node("standard_clearance", standard_clearance_node)
    workflow.add_node("audit_ledger", audit_ledger_node)
    workflow.add_node("db_persistence", db_persistence_node)

    # ── Initial Parallel Fan-Out ──────────────────────────────────────────────
    workflow.add_edge(START, "minio_storage")
    workflow.add_edge(START, "ocr_extraction")
    workflow.add_edge(START, "tampering_detection")
    workflow.add_edge(START, "face_verification")

    # ── Conditional Edge 1: OCR Quality / LLM Fallback ───────────────────────
    workflow.add_conditional_edges(
        "ocr_extraction",
        check_ocr_quality,
        {
            "fallback": "llm_vision_fallback",
            "continue": "validation_rules",
        },
    )
    workflow.add_edge("llm_vision_fallback", "validation_rules")
    workflow.add_edge("ocr_extraction", "blacklist_check")
    workflow.add_edge("face_verification", "cross_checkpoint")

    # ── Aggregation / Fan-In to Risk Engine ───────────────────────────────────
    # A list source is a LangGraph fan-in: risk scoring must wait for every
    # independent branch and run exactly once. Separate edges here would
    # schedule the node once per completed branch, duplicating audit and DB work.
    workflow.add_edge(
        [
            "validation_rules",
            "tampering_detection",
            "blacklist_check",
            "cross_checkpoint",
            "minio_storage",
        ],
        "risk_engine",
    )

    # ── Conditional Edge 2: Risk Threat Level Escalation ─────────────────────
    workflow.add_conditional_edges(
        "risk_engine",
        route_by_threat_level,
        {
            "secondary": "secondary_inspection",
            "clearance": "standard_clearance",
        },
    )

    # ── Audit & Final Persistence ─────────────────────────────────────────────
    workflow.add_edge("secondary_inspection", "audit_ledger")
    workflow.add_edge("standard_clearance", "audit_ledger")
    workflow.add_edge("audit_ledger", "db_persistence")
    workflow.add_edge("db_persistence", END)

    return workflow.compile()


_COMPILED_SCREENING_GRAPH = build_screening_graph()


# ---------------------------------------------------------------------------
# 5. Public Execution API
# ---------------------------------------------------------------------------

async def run_langgraph_pipeline(
    image_bytes: bytes,
    document_type: DocumentType = DocumentType.PASSPORT,
    checkpoint_type: CheckpointType = CheckpointType.AIRPORT,
    provider: str = "local",
    live_image_bytes: bytes | None = None,
    document_id: str | None = None,
    checkpoint_id: str | None = None,
    db: AsyncSession | None = None,
) -> PipelineResult:
    """
    Execute the document screening pipeline using the LangGraph StateGraph engine.
    """
    doc_uuid = _safe_uuid(document_id) or uuid.uuid4()
    doc_id_str = str(doc_uuid)

    initial_state: ScreeningState = {
        "document_id": doc_id_str,
        "image_bytes": image_bytes,
        "live_image_bytes": live_image_bytes,
        "document_type": document_type,
        "checkpoint_type": checkpoint_type,
        "border_checkpoint_id": checkpoint_id,
        "provider": provider,
        "image_object_key": None,
        "db": db,
        "extraction": None,
        "validation": None,
        "tampering": None,
        "face": None,
        "blacklist": None,
        "cross_checkpoint": None,
        "risk_score": None,
        "ocr_available": True,
        "tampering_available": True,
        "face_available": True,
        "validation_available": True,
        "cross_checkpoint_available": True,
        "risk_engine_available": True,
        "inspection_status": "standard_clearance",
        "inspection_reasons": [],
        "degraded_modules": [],
        "start_time": time.perf_counter(),
    }

    logger.info("langgraph_pipeline_started", document_id=doc_id_str, doc_type=document_type.value)

    # Execute state graph
    final_state = await _COMPILED_SCREENING_GRAPH.ainvoke(initial_state)

    total_duration = int((time.perf_counter() - initial_state["start_time"]) * 1000)
    risk = final_state.get("risk_score")

    statuses = PipelineServiceStatuses(
        ocr=ServiceStatus(
            available=final_state.get("ocr_available", True),
            error=final_state.get("ocr_error"),
        ),
        tampering=ServiceStatus(
            available=final_state.get("tampering_available", True),
            error=final_state.get("tampering_error"),
        ),
        face=ServiceStatus(
            available=final_state.get("face_available", True),
            error=final_state.get("face_error"),
        ),
        validation=ServiceStatus(
            available=final_state.get("validation_available", True),
            error=final_state.get("validation_error"),
        ),
        cross_checkpoint=ServiceStatus(
            available=final_state.get("cross_checkpoint_available", True),
            error=final_state.get("cross_checkpoint_error"),
        ),
        risk_engine=ServiceStatus(
            available=final_state.get("risk_engine_available", True),
            error=final_state.get("risk_engine_error"),
        ),
    )

    logger.info(
        "langgraph_pipeline_completed",
        document_id=doc_id_str,
        score=risk.score if risk else None,
        band=risk.band.value if risk else None,
        status=final_state.get("inspection_status"),
        duration_ms=total_duration,
    )

    return PipelineResult(
        document_id=doc_id_str,
        degraded=len(final_state.get("degraded_modules", [])) > 0,
        service_statuses=statuses,
        extraction=final_state.get("extraction"),
        validation=final_state.get("validation"),
        tampering=final_state.get("tampering"),
        face=final_state.get("face"),
        cross_checkpoint=final_state.get("cross_checkpoint"),
        risk_score=final_state.get("risk_score"),
    )
