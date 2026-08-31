"""
Typed Async HTTP Service Clients for Downstream Microservices.

Features:
- Configurable timeout (default 5.0s) & retry-once policy.
- Typed Pydantic request/response parsing.
- Direct core fallback: If services are running in unified monorepo or during
  tests without separate Uvicorn ports open, seamlessly invokes internal core logic.
"""

import httpx
from typing import Any

from backend.config import settings
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    CheckpointType,
    DocumentType,
    ExtractedField,
    ExtractionResponse,
    MRZResult,
    ExtractionMethod,
)
from backend.validation_service.schemas.validation import (
    ValidationRequest,
    ValidationResponse,
)
from backend.tampering_service.schemas.tampering import (
    TamperingCheckResult,
    TamperingCheckType,
    TamperingResponse,
)
from backend.face_service.schemas.face import (
    FullFaceVerificationResponse,
    OneToOneVerifyResponse,
    DedupSearchResponse,
)
from backend.risk_engine.schemas.risk import (
    RiskScoreRequest,
    RiskScoreResponse,
)

logger = get_logger("orchestrator.service_clients")

CLIENT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


# ---------------------------------------------------------------------------
# 1. OCR Service Client
# ---------------------------------------------------------------------------
async def call_ocr_service(
    image_bytes: bytes,
    document_type: DocumentType | None = None,
    checkpoint_type: CheckpointType = CheckpointType.AIRPORT,
    provider: str = "local",
) -> ExtractionResponse:
    """Invoke OCR extraction via HTTP or fallback to core pipeline."""
    url = f"{settings.ocr_service_url}/api/v1/ocr/extract"
    files = {"file": ("document.jpg", image_bytes, "image/jpeg")}
    data = {
        "checkpoint_type": checkpoint_type.value,
        "provider": provider,
    }
    if document_type:
        data["document_type"] = document_type.value

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url, files=files, data=data)
                if res.status_code == 200:
                    return ExtractionResponse.model_validate(res.json())
        except Exception as exc:
            logger.debug("OCR HTTP call failed, retrying or falling back", attempt=attempt, error=str(exc))

    # In-process direct fallback
    logger.info("Executing OCR via internal core pipeline", document_type=document_type.value if document_type else "auto")
    from backend.ocr_service.core.classifier import classify_document
    from backend.ocr_service.core.field_extractor import extract_fields, extract_raw_ocr_lines
    from backend.ocr_service.core.mrz_parser import parse_mrz
    from backend.ocr_service.core.llm_fallback import extract_fields_with_llm

    extracted_dict: dict[str, ExtractedField] = {}
    warnings: list[str] = []
    primary_method = ExtractionMethod.OCR

    raw_ocr_lines: list[tuple[str, float]] = []
    try:
        raw_ocr_lines = extract_raw_ocr_lines(image_bytes)
    except Exception as e:
        logger.warning("OCR engine internal call warning", error=str(e))

    if not document_type:
        document_type, _, _ = classify_document(image_bytes, ocr_lines=raw_ocr_lines, provider=provider)

    text_lines = [t for t, _ in raw_ocr_lines]
    mrz_res: MRZResult = parse_mrz(image_bytes, ocr_text_lines=text_lines)

    if mrz_res.mrz_present:
        primary_method = ExtractionMethod.MRZ
        for k, v in mrz_res.mrz_fields.items():
            if v and k != "mrz_format":
                extracted_dict[k] = ExtractedField(
                    field_name=k,
                    field_value=v,
                    confidence=1.0 if mrz_res.checksum_valid else 0.7,
                    extraction_method=ExtractionMethod.MRZ,
                )
        if not mrz_res.checksum_valid:
            warnings.append(f"MRZ checksum verification failed on: {', '.join(mrz_res.checksum_failures)}")

    ocr_fields = extract_fields(image_bytes, document_type, raw_lines=raw_ocr_lines)
    for f in ocr_fields:
        if f.field_name not in extracted_dict:
            extracted_dict[f.field_name] = f

    if (not extracted_dict and not mrz_res.mrz_present) or (
        document_type in [DocumentType.DRIVING_LICENSE, DocumentType.PERMIT, DocumentType.FERRY_TICKET]
        and len(extracted_dict) < 2
    ):
        _, llm_fields = extract_fields_with_llm(image_bytes, document_type)
        if llm_fields:
            primary_method = ExtractionMethod.LLM
            for f in llm_fields:
                extracted_dict[f.field_name] = f


    return ExtractionResponse(
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider_used=provider,
        extraction_method=primary_method,
        fields=list(extracted_dict.values()),
        mrz=mrz_res,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# 2. Validation Service Client
# ---------------------------------------------------------------------------
async def call_validation_service(
    document_type: DocumentType,
    fields: list[ExtractedField],
    related_document_fields: list[ExtractedField] | None = None,
) -> ValidationResponse:
    """Invoke Document Validation via HTTP or fallback to core engine."""
    url = f"{settings.validation_service_url}/api/v1/validation/validate"
    req_payload = ValidationRequest(
        document_type=document_type,
        fields=fields,
        related_document_fields=related_document_fields,
    ).model_dump(mode="json")

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url, json=req_payload)
                if res.status_code == 200:
                    return ValidationResponse.model_validate(res.json())
        except Exception as exc:
            logger.debug("Validation HTTP call failed, retrying or falling back", attempt=attempt, error=str(exc))

    # In-process direct fallback
    logger.info("Executing Validation via internal core engine", document_type=document_type.value)
    from backend.validation_service.core.rules_engine import validate_document
    return validate_document(
        document_type=document_type,
        fields=fields,
        related_document_fields=related_document_fields,
    )


# ---------------------------------------------------------------------------
# 3. Tampering Service Client
# ---------------------------------------------------------------------------
async def call_tampering_service(image_bytes: bytes) -> TamperingResponse:
    """Invoke Tampering Detection via HTTP or fallback to core forensics."""
    url = f"{settings.tampering_service_url}/api/v1/tampering/detect"
    files = {"file": ("document.jpg", image_bytes, "image/jpeg")}

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url, files=files)
                if res.status_code == 200:
                    return TamperingResponse.model_validate(res.json())
        except Exception as exc:
            logger.debug("Tampering HTTP call failed, retrying or falling back", attempt=attempt, error=str(exc))

    # In-process direct fallback
    logger.info("Executing Tampering analysis via internal core forensics")
    from backend.tampering_service.core.ela import compute_ela, ela_to_base64
    from backend.tampering_service.core.metadata_forensics import analyze_metadata
    from backend.tampering_service.core.boundary_analysis import analyze_photo_boundaries
    from backend.tampering_service.core.stamp_matcher import verify_stamps

    checks: list[TamperingCheckResult] = []

    ela_score, ela_flagged, heatmap_bytes, ela_detail = compute_ela(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.ELA,
            score=round(ela_score, 3),
            flagged=ela_flagged,
            detail=ela_detail,
            metadata={"quality": 90},
        )
    )
    heatmap_b64 = ela_to_base64(heatmap_bytes) if heatmap_bytes else None

    meta_score, meta_flagged, flags, raw_meta, meta_detail = analyze_metadata(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.METADATA,
            score=round(meta_score, 3),
            flagged=meta_flagged,
            detail=meta_detail,
            metadata={"detected_flags": flags, "tag_count": len(raw_meta)},
        )
    )

    bnd_score, bnd_flagged, bnd_detail, bnd_meta = analyze_photo_boundaries(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.BOUNDARY,
            score=round(bnd_score, 3),
            flagged=bnd_flagged,
            detail=bnd_detail,
            metadata=bnd_meta,
        )
    )

    stamp_score, stamp_flagged, _, _, stamp_detail, stamp_meta = verify_stamps(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.STAMP_MATCH,
            score=round(stamp_score, 3),
            flagged=stamp_flagged,
            detail=stamp_detail,
            metadata=stamp_meta,
        )
    )

    weighted_score = (
        0.35 * ela_score
        + 0.30 * meta_score
        + 0.25 * bnd_score
        + 0.10 * stamp_score
    )
    max_score = max(ela_score, meta_score, bnd_score, stamp_score)
    overall_tampering_score = max(0.0, min(1.0, float(0.6 * max_score + 0.4 * weighted_score)))
    flagged = any(c.flagged for c in checks) or (overall_tampering_score >= 0.45)

    return TamperingResponse(
        flagged=flagged,
        tampering_score=round(overall_tampering_score, 3),
        checks=checks,
        ela_heatmap_base64=heatmap_b64,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# 4. Face Verification Client
# ---------------------------------------------------------------------------
async def call_face_service(
    doc_image_bytes: bytes,
    live_image_bytes: bytes | None = None,
    current_doc_id: str | None = None,
) -> FullFaceVerificationResponse:
    """Invoke Face verification (1:1 and 1:N) via HTTP or fallback to core."""
    one_to_one_res: OneToOneVerifyResponse | None = None
    dedup_res: DedupSearchResponse | None = None

    # 1. Check 1:1 if live photo provided
    if live_image_bytes:
        url_verify = f"{settings.face_service_url}/api/v1/face/verify"
        files = {
            "doc_photo": ("doc.jpg", doc_image_bytes, "image/jpeg"),
            "live_photo": ("live.jpg", live_image_bytes, "image/jpeg"),
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                    res = await client.post(url_verify, files=files)
                    if res.status_code == 200:
                        one_to_one_res = OneToOneVerifyResponse.model_validate(res.json())
                        break
            except Exception:
                pass

        if one_to_one_res is None:
            from backend.face_service.core.one_to_one import verify_one_to_one
            matched, score, sim, detail = verify_one_to_one(doc_image_bytes, live_image_bytes)
            one_to_one_res = OneToOneVerifyResponse(
                matched=matched,
                match_score=score,
                cosine_similarity=sim,
                threshold=0.60,
                detail=detail,
            )

    # 2. Check 1:N deduplication
    url_dedup = f"{settings.face_service_url}/api/v1/face/dedup"
    files_dedup = {"file": ("doc.jpg", doc_image_bytes, "image/jpeg")}
    data_dedup = {"current_doc_id": current_doc_id} if current_doc_id else {}

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url_dedup, files=files_dedup, data=data_dedup)
                if res.status_code == 200:
                    dedup_res = DedupSearchResponse.model_validate(res.json())
                    break
        except Exception:
            pass

    if dedup_res is None:
        from backend.face_service.core.embedding import extract_face_embedding
        from backend.face_service.core.dedup_search import search_duplicates

        ok, emb, _, msg = extract_face_embedding(doc_image_bytes)
        if ok and emb:
            has_dups, hits, cluster_id, detail = await search_duplicates(
                embedding=emb,
                current_doc_id=current_doc_id,
            )
            dedup_res = DedupSearchResponse(
                has_duplicates=has_dups,
                hits=hits,
                person_cluster_id=cluster_id,
                detail=detail,
            )
        else:
            dedup_res = DedupSearchResponse(
                has_duplicates=False,
                hits=[],
                person_cluster_id="",
                detail=f"Face embedding extraction skipped: {msg}",
            )

    return FullFaceVerificationResponse(
        document_id=current_doc_id,
        one_to_one=one_to_one_res,
        dedup=dedup_res,
    )


# ---------------------------------------------------------------------------
# 5. Risk Engine Client
# ---------------------------------------------------------------------------
async def call_risk_engine(request: RiskScoreRequest) -> RiskScoreResponse:
    """Invoke Risk Engine via HTTP or fallback to internal scoring logic."""
    url = f"{settings.risk_engine_url}/score/"
    payload = request.model_dump(mode="json")

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return RiskScoreResponse.model_validate(res.json())
        except Exception as exc:
            logger.debug("Risk Engine HTTP call failed, retrying or falling back", attempt=attempt, error=str(exc))

    logger.info("Executing Risk Engine via internal scoring core", document_id=request.document_id)
    from backend.risk_engine.core.scoring import build_risk_response
    return build_risk_response(request)


# ---------------------------------------------------------------------------
# 6. Cross-Checkpoint Service Client (Module 5)
# ---------------------------------------------------------------------------
async def call_cross_checkpoint_service(
    person_cluster_id: str,
    current_doc: Any | None = None,
    current_risk_band: str | None = "low",
) -> Any:
    """Invoke Cross-Checkpoint analysis via HTTP or fallback to internal graph engine."""
    from backend.cross_checkpoint_service.schemas.cross_checkpoint import (
        ClusterAnalysisRequest,
        ClusterAnalysisResponse,
        ClusterDocument,
    )
    from backend.cross_checkpoint_service.core.face_graph import analyze_cluster

    url = f"{settings.cross_checkpoint_service_url}/api/v1/clusters/analyze"
    req = ClusterAnalysisRequest(
        person_cluster_id=person_cluster_id,
        current_document_id=current_doc.document_id if current_doc else None,
        current_checkpoint_type=current_doc.checkpoint_type if current_doc else None,
        current_checkpoint_id=current_doc.checkpoint_id if current_doc else None,
        current_timestamp=current_doc.uploaded_at if current_doc else None,
        current_name=current_doc.name if current_doc else None,
        current_document_number=current_doc.document_number if current_doc else None,
        current_nationality=current_doc.nationality if current_doc else None,
        current_date_of_birth=current_doc.date_of_birth if current_doc else None,
        current_risk_score=current_doc.risk_score if current_doc else None,
        current_risk_band=current_risk_band,
    )

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
                res = await client.post(url, json=req.model_dump(mode="json"))
                if res.status_code == 200:
                    return ClusterAnalysisResponse.model_validate(res.json())
        except Exception as exc:
            logger.debug("Cross-checkpoint HTTP call failed, retrying or falling back", attempt=attempt, error=str(exc))

    logger.info("Executing Cross-Checkpoint analysis via internal core engine", cluster_id=person_cluster_id)
    return await analyze_cluster(
        person_cluster_id=person_cluster_id,
        current_doc=current_doc,
        current_risk_band=current_risk_band,
    )


# ---------------------------------------------------------------------------
# 7. Audit Ledger Client
# ---------------------------------------------------------------------------
async def call_audit_ledger(
    event_type: str,
    document_id: str,
    payload: dict[str, Any],
    officer_id: str | None = None,
) -> dict[str, Any] | None:
    """Append event to the tamper-evident audit ledger (safe call; never raises)."""
    url = f"{settings.audit_ledger_url}/events/"
    data = {
        "event_type": event_type,
        "document_id": document_id,
        "payload": payload,
        "officer_id": officer_id,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            res = await client.post(url, json=data)
            if res.status_code in [200, 201]:
                return res.json()
    except Exception as exc:
        logger.debug("Audit ledger append event skipped or pending Phase 4", error=str(exc))
    return None

