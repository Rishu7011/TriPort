"""
LangGraph Orchestration Pipeline for BorderGuard-AI (Phase 7).

Architecture:
  - Directed Acyclic Graph (DAG) state machine using LangGraph StateGraph.
  - Parallel Fan-Out of initial visual & biometric workloads (OCR, Tampering, Face).
  - Conditional Edge 1: LLM Vision Fallback when OCR confidence is degraded.
  - Parallel Dependent Stage: YAML Rules Validation, Watchlist Cross-Check, Cross-Checkpoint Graph.
  - Synthesis & Risk Scoring Node.
  - Conditional Edge 2: Automated Routing between Standard Clearance vs Secondary Inspection Queue.
  - Append-Only Tamper-Evident Audit Logging (in-memory ledger).
"""

import asyncio
import time
import uuid
from typing import Annotated, Any, TypedDict
from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    CheckpointType,
    DocumentType,
    ExtractionResponse,
    MRZResult,
    ExtractionMethod,
)
from backend.validation_service.schemas.validation import (
    ValidationResponse,
    RuleResult,
)
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
from backend.orchestrator.core.scan_store import save_scan
from backend.orchestrator.core.service_clients import (
    call_audit_ledger,
    call_cross_checkpoint_service,
    call_face_service,
    call_ocr_service,
    call_risk_engine,
    call_tampering_service,
    call_validation_service,
)
from backend.orchestrator.schemas.pipeline import (
    PipelineResult,
    PipelineServiceStatuses,
    ServiceStatus,
)

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
    db: Any | None

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

async def buffer_images_node(state: ScreeningState) -> dict:
    """Keep images in pipeline state only — no external storage."""
    return {}


async def ocr_extraction_node(state: ScreeningState) -> dict:
    """Extract text & MRZ from document image."""
    try:
        res = await call_ocr_service(
            image_bytes=state["image_bytes"],
            document_type=state["document_type"],
            checkpoint_type=state["checkpoint_type"],
            provider=state["provider"],
        )
        is_empty = not res.fields and not res.mrz.mrz_present
        return {
            "extraction": res,
            "ocr_available": True,
            "ocr_error": "Zero fields extracted from document scan" if is_empty else None,
            "degraded_modules": ["OCR_EXTRACTION_EMPTY"] if is_empty else [],
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
    """Invoked conditionally if OCR extracted fields have low confidence or are missing."""
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

    # If both OCR and LLM fallback failed to extract any fields, surface a clear extraction failure
    if not fields and (not ext or not ext.mrz or not ext.mrz.mrz_present):
        logger.warning(
            "Validation skipped — zero fields extracted from document image",
            document_type=state["document_type"].value,
        )
        empty_val = ValidationResponse(
            document_type=state["document_type"],
            passed=False,
            failed_rules=["document_unreadable_no_fields_extracted"],
            rule_results=[
                RuleResult(
                    rule_name="document_unreadable_no_fields_extracted",
                    passed=False,
                    detail="No text or MRZ fields could be extracted from the document image (OCR and LLM vision extraction both returned zero fields). The document may be blurry, unreadable, or missing credentials.",
                )
            ],
        )
        return {
            "validation": empty_val,
            "validation_available": True,
            "validation_error": "No fields extracted for validation",
            "degraded_modules": ["OCR_EXTRACTION_EMPTY"],
        }

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
    db = state.get("db")
    bl_score = await check_blacklist(fields=fields, db=db)
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


# ---------------------------------------------------------------------------
# 3. Conditional Routers (Edges)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 3. Conditional Routers (Edges) & Gating Nodes
# ---------------------------------------------------------------------------

def check_document_integrity(state: ScreeningState) -> str:
    """
    Conditional Gate: If a live traveler photo is provided, always route to biometric
    face verification (AWS Rekognition / ArcFace) so the officer receives the 1:1 facial comparison.
    Only bypass biometrics when NO live photo is captured AND document integrity is flagged.
    """
    if state.get("live_image_bytes") is not None:
        return "clean"

    ext = state.get("extraction")
    tamp = state.get("tampering")
    val = state.get("validation")
    bl = state.get("blacklist")

    # 1. Forensic Tampering flagged
    if tamp and (tamp.flagged or tamp.tampering_score >= 0.40):
        return "flagged"

    # 2. MRZ Checksum failed
    if ext and ext.mrz and ext.mrz.checksum_valid is False:
        return "flagged"

    # 3. Validation business rules failed (e.g. expired document, insufficient validity)
    if val and (not val.passed or len(val.failed_rules) > 0):
        return "flagged"

    # 4. Blacklist hit
    if bl and getattr(bl, "hit", False):
        return "flagged"

    return "clean"



async def document_gate_node(state: ScreeningState) -> dict:
    """
    Document Forensics Gate:
    If no live photo was captured AND document integrity flagged anomalies,
    mark biometrics as bypassed and route directly to Human Officer Verification.
    If a live photo IS provided, always allow face verification to run so the
    officer has the full biometric comparison.
    """
    has_live_photo = state.get("live_image_bytes") is not None
    integrity = check_document_integrity(state)

    if integrity == "flagged" and not has_live_photo:
        reasons = []
        tamp = state.get("tampering")
        if tamp and (tamp.flagged or tamp.tampering_score >= 0.40):
            reasons.append("Forensic tampering anomaly detected (ELA/metadata/boundary)")
        ext = state.get("extraction")
        if ext and ext.mrz and ext.mrz.checksum_valid is False:
            reasons.append("MRZ check digit checksum failure")
        val = state.get("validation")
        if val and (not val.passed or len(val.failed_rules) > 0):
            reasons.append(f"Validation rules failed: {', '.join(val.failed_rules)}")
        bl = state.get("blacklist")
        if bl and getattr(bl, "hit", False):
            reasons.append("Watchlist / Blacklist match")

        reason_str = "; ".join(reasons) or "Document integrity failed"
        bypassed_face = FullFaceVerificationResponse(
            document_id=state["document_id"],
            bypassed=True,
            bypassed_reason=f"Biometric scan bypassed: {reason_str}. Directly routed to human officer verification.",
        )
        logger.warning(
            "Document integrity gate flagged anomalies — bypassing biometric scan (no live capture provided)",
            doc_id=state["document_id"],
            reasons=reasons,
        )
        return {"face": bypassed_face}

    return {}



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
    or a Blacklist/Watchlist hit occurred, or repeat offender was flagged, or document failed gate.
    """
    face = state.get("face")
    if face and face.bypassed:
        return "secondary"

    tamp = state.get("tampering")
    if tamp and (tamp.flagged or tamp.tampering_score >= 0.40):
        return "secondary"

    ext = state.get("extraction")
    if ext and ext.mrz and ext.mrz.checksum_valid is False:
        return "secondary"

    val = state.get("validation")
    if val and (not val.passed or len(val.failed_rules) > 0):
        return "secondary"

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
# 4. StateGraph Builders & Compilation (Stage 1, Stage 2, and Unified)
# ---------------------------------------------------------------------------

def build_stage1_graph():
    """
    Stage 1 StateGraph: Document Forensics & Ingestion Pipeline.
    Runs parallel OCR extraction (+ conditional LLM fallback), 5-layer forensic
    tampering analysis, YAML validation rules, and Watchlist cross-checks.
    Target execution time: ~5-8 seconds.
    """
    workflow = StateGraph(ScreeningState)

    workflow.add_node("buffer_images", buffer_images_node)
    workflow.add_node("ocr_extraction", ocr_extraction_node)
    workflow.add_node("llm_vision_fallback", llm_vision_fallback_node)
    workflow.add_node("tampering_detection", tampering_detection_node)
    workflow.add_node("validation_rules", validation_rules_node)
    workflow.add_node("blacklist_check", blacklist_check_node)

    # Initial Fan-Out
    workflow.add_edge(START, "buffer_images")
    workflow.add_edge(START, "ocr_extraction")
    workflow.add_edge(START, "tampering_detection")

    # OCR Quality conditional routing
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

    # Fan-in to END
    workflow.add_edge("buffer_images", END)
    workflow.add_edge("tampering_detection", END)
    workflow.add_edge("validation_rules", END)
    workflow.add_edge("blacklist_check", END)

    return workflow.compile()


def build_stage2_graph():
    """
    Stage 2 StateGraph: Biometric Verification & Risk Scoring Pipeline.
    Orchestrates AWS Rekognition (CompareFaces) / local ArcFace, Cross-Checkpoint
    identity clustering, weighted composite risk synthesis, threat routing,
    and SHA-256 hash-chained audit logging.
    """
    workflow = StateGraph(ScreeningState)

    workflow.add_node("face_verification", face_verification_node)
    workflow.add_node("cross_checkpoint", cross_checkpoint_node)
    workflow.add_node("risk_engine", risk_engine_node)
    workflow.add_node("secondary_inspection", secondary_inspection_node)
    workflow.add_node("standard_clearance", standard_clearance_node)
    workflow.add_node("audit_ledger", audit_ledger_node)

    workflow.add_edge(START, "face_verification")
    workflow.add_edge("face_verification", "cross_checkpoint")
    workflow.add_edge("cross_checkpoint", "risk_engine")

    workflow.add_conditional_edges(
        "risk_engine",
        route_by_threat_level,
        {
            "secondary": "secondary_inspection",
            "clearance": "standard_clearance",
        },
    )

    workflow.add_edge("secondary_inspection", "audit_ledger")
    workflow.add_edge("standard_clearance", "audit_ledger")
    workflow.add_edge("audit_ledger", END)

    return workflow.compile()


def build_screening_graph():
    """Construct and compile the full unified LangGraph screening state machine."""
    workflow = StateGraph(ScreeningState)

    # Register Nodes
    workflow.add_node("buffer_images", buffer_images_node)
    workflow.add_node("ocr_extraction", ocr_extraction_node)
    workflow.add_node("llm_vision_fallback", llm_vision_fallback_node)
    workflow.add_node("tampering_detection", tampering_detection_node)
    workflow.add_node("validation_rules", validation_rules_node)
    workflow.add_node("blacklist_check", blacklist_check_node)
    workflow.add_node("document_gate", document_gate_node)
    workflow.add_node("face_verification", face_verification_node)
    workflow.add_node("cross_checkpoint", cross_checkpoint_node)
    workflow.add_node("risk_engine", risk_engine_node)
    workflow.add_node("secondary_inspection", secondary_inspection_node)
    workflow.add_node("standard_clearance", standard_clearance_node)
    workflow.add_node("audit_ledger", audit_ledger_node)

    # ── Stage 1: Initial Document Forensics Fan-Out ──────────────────────────
    workflow.add_edge(START, "buffer_images")
    workflow.add_edge(START, "ocr_extraction")
    workflow.add_edge(START, "tampering_detection")

    # ── Stage 1b: OCR Quality / LLM Fallback & Rule Checks ───────────────────
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

    # ── Stage 2: Fan-In to Document Integrity Gate ───────────────────────────
    workflow.add_edge(
        [
            "validation_rules",
            "tampering_detection",
            "blacklist_check",
            "buffer_images",
        ],
        "document_gate",
    )

    # ── Stage 2b: Conditional Gate ➔ Biometrics vs Direct Human Verification ──
    workflow.add_conditional_edges(
        "document_gate",
        check_document_integrity,
        {
            "clean": "face_verification",
            "flagged": "risk_engine",
        },
    )

    # ── Stage 3: Biometric Verification & Person Clustering (Clean Documents Only)
    workflow.add_edge("face_verification", "cross_checkpoint")
    workflow.add_edge("cross_checkpoint", "risk_engine")

    # ── Stage 4: Risk Scoring & Threat Routing ────────────────────────────────
    workflow.add_conditional_edges(
        "risk_engine",
        route_by_threat_level,
        {
            "secondary": "secondary_inspection",
            "clearance": "standard_clearance",
        },
    )

    # ── Stage 5: Immutable SHA-256 Audit Trail ───────────────────────────────
    workflow.add_edge("secondary_inspection", "audit_ledger")
    workflow.add_edge("standard_clearance", "audit_ledger")
    workflow.add_edge("audit_ledger", END)

    return workflow.compile()


_COMPILED_STAGE1_GRAPH = build_stage1_graph()
_COMPILED_STAGE2_GRAPH = build_stage2_graph()
_COMPILED_SCREENING_GRAPH = build_screening_graph()


# ---------------------------------------------------------------------------
# 5. Public Execution APIs
# ---------------------------------------------------------------------------

async def run_stage1_pipeline(
    image_bytes: bytes,
    document_type: DocumentType = DocumentType.PASSPORT,
    checkpoint_type: CheckpointType = CheckpointType.AIRPORT,
    provider: str = "local",
    document_id: str | None = None,
    checkpoint_id: str | None = None,
    db: AsyncSession | None = None,
) -> tuple[PipelineResult, dict[str, Any]]:
    """
    Execute Stage 1: Document Forensics (OCR + Tampering + Rules + Watchlist).
    Runs in parallel without waiting on biometrics or live camera capture.
    Returns (PipelineResult, meta_dict).
    """
    doc_uuid = _safe_uuid(document_id) or uuid.uuid4()
    doc_id_str = str(doc_uuid)
    start_t = time.perf_counter()

    logger.info(
        "stage1_pipeline_started",
        document_id=doc_id_str,
        doc_type=document_type.value if hasattr(document_type, "value") else str(document_type),
        checkpoint_type=checkpoint_type.value if hasattr(checkpoint_type, "value") else str(checkpoint_type),
    )

    initial_state: ScreeningState = {
        "document_id": doc_id_str,
        "image_bytes": image_bytes,
        "live_image_bytes": None,
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
        "inspection_status": "pending_biometric",
        "inspection_reasons": [],
        "degraded_modules": [],
        "start_time": start_t,
    }

    final_state = await _COMPILED_STAGE1_GRAPH.ainvoke(initial_state)
    duration_ms = int((time.perf_counter() - start_t) * 1000)

    statuses = PipelineServiceStatuses(
        ocr=ServiceStatus(
            available=final_state.get("ocr_available", True),
            error=final_state.get("ocr_error"),
        ),
        tampering=ServiceStatus(
            available=final_state.get("tampering_available", True),
            error=final_state.get("tampering_error"),
        ),
        face=ServiceStatus(available=True),
        validation=ServiceStatus(
            available=final_state.get("validation_available", True),
            error=final_state.get("validation_error"),
        ),
        cross_checkpoint=ServiceStatus(available=True),
        risk_engine=ServiceStatus(available=True),
    )

    result = PipelineResult(
        document_id=doc_id_str,
        degraded=len(final_state.get("degraded_modules", [])) > 0,
        service_statuses=statuses,
        extraction=final_state.get("extraction"),
        validation=final_state.get("validation"),
        tampering=final_state.get("tampering"),
        face=None,
        cross_checkpoint=None,
        risk_score=None,
    )

    logger.info(
        "stage1_pipeline_completed",
        document_id=doc_id_str,
        duration_ms=duration_ms,
        degraded=result.degraded,
        tampering_score=result.tampering.tampering_score if result.tampering else None,
        validation_passed=result.validation.passed if result.validation else None,
    )

    meta = {
        "duration_ms": duration_ms,
        "blacklist": final_state.get("blacklist"),
        "inspection_status": "pending_biometric",
    }
    return result, meta


async def run_stage2_pipeline(
    doc_image_bytes: bytes,
    live_image_bytes: bytes,
    document_id: str,
    stage1_result: PipelineResult,
    document_type: DocumentType = DocumentType.PASSPORT,
    checkpoint_type: CheckpointType = CheckpointType.AIRPORT,
    checkpoint_id: str | None = None,
    blacklist_sub: BlacklistSubScore | None = None,
    provider: str = "local",
    db: AsyncSession | None = None,
) -> tuple[PipelineResult, dict[str, Any]]:
    """
    Execute Stage 2: Biometric Verification, Cross-Checkpoint, and Risk Engine Synthesis.
    Triggered when officer captures live photo.
    Returns (PipelineResult, meta_dict).
    """
    doc_uuid = _safe_uuid(document_id) or uuid.uuid4()
    doc_id_str = str(doc_uuid)
    start_t = time.perf_counter()

    logger.info(
        "stage2_pipeline_started",
        document_id=doc_id_str,
        doc_type=document_type.value if hasattr(document_type, "value") else str(document_type),
        checkpoint_id=checkpoint_id,
    )

    state: ScreeningState = {
        "document_id": doc_id_str,
        "image_bytes": doc_image_bytes,
        "live_image_bytes": live_image_bytes,
        "document_type": document_type,
        "checkpoint_type": checkpoint_type,
        "border_checkpoint_id": checkpoint_id,
        "provider": provider,
        "image_object_key": None,
        "db": db,
        "extraction": stage1_result.extraction,
        "validation": stage1_result.validation,
        "tampering": stage1_result.tampering,
        "face": None,
        "blacklist": blacklist_sub or BlacklistSubScore(),
        "cross_checkpoint": None,
        "risk_score": None,
        "ocr_available": stage1_result.service_statuses.ocr.available,
        "tampering_available": stage1_result.service_statuses.tampering.available,
        "face_available": True,
        "validation_available": stage1_result.service_statuses.validation.available,
        "cross_checkpoint_available": True,
        "risk_engine_available": True,
        "inspection_status": "standard_clearance",
        "inspection_reasons": [],
        "degraded_modules": ["degraded"] if stage1_result.degraded else [],
        "start_time": start_t,
    }

    final_state = await _COMPILED_STAGE2_GRAPH.ainvoke(state)
    duration_ms = int((time.perf_counter() - start_t) * 1000)

    risk = final_state.get("risk_score")
    inspection_status = final_state.get("inspection_status", "standard_clearance")

    statuses = PipelineServiceStatuses(
        ocr=stage1_result.service_statuses.ocr,
        tampering=stage1_result.service_statuses.tampering,
        face=ServiceStatus(
            available=final_state.get("face_available", True),
            error=final_state.get("face_error"),
        ),
        validation=stage1_result.service_statuses.validation,
        cross_checkpoint=ServiceStatus(
            available=final_state.get("cross_checkpoint_available", True),
            error=final_state.get("cross_checkpoint_error"),
        ),
        risk_engine=ServiceStatus(
            available=final_state.get("risk_engine_available", True),
            error=final_state.get("risk_engine_error"),
        ),
    )

    result = PipelineResult(
        document_id=doc_id_str,
        degraded=len(final_state.get("degraded_modules", [])) > 0,
        service_statuses=statuses,
        extraction=stage1_result.extraction,
        validation=stage1_result.validation,
        tampering=stage1_result.tampering,
        face=final_state.get("face"),
        cross_checkpoint=final_state.get("cross_checkpoint"),
        risk_score=final_state.get("risk_score"),
    )

    logger.info(
        "stage2_pipeline_completed",
        document_id=doc_id_str,
        duration_ms=duration_ms,
        score=risk.score if risk else None,
        band=risk.band.value if risk else None,
        inspection_status=inspection_status,
    )

    meta = {
        "duration_ms": duration_ms,
        "inspection_status": inspection_status,
        "inspection_reasons": final_state.get("inspection_reasons", []),
    }
    return result, meta


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
    For end-to-end / testing execution when live photo is available upfront or offline.
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

    result = PipelineResult(
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

    return result
