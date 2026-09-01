"""
Extraction Router — FastAPI endpoints for TriPort OCR, Classification & Batch Extraction.

Endpoints:
  1. POST /api/v1/ocr/classify — Classifies document type from image scan.
  2. POST /api/v1/ocr/extract — Extracts structured fields + MRZ check digits.
  3. POST /api/v1/ocr/extract/batch — Processes bulk passenger arrival queues (bus/ferry).
"""

from typing import List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.logging_config import get_logger
from backend.ocr_service.core.batch import process_batch_queue
from backend.ocr_service.core.classifier import classify_document
from backend.ocr_service.core.field_extractor import (
    extract_fields,
    extract_raw_ocr_lines,
)
from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
from backend.ocr_service.core.mrz_parser import parse_mrz
from backend.ocr_service.schemas.extraction import (
    BatchExtractionResponse,
    CheckpointType,
    ClassificationResult,
    DocumentType,
    ExtractedField,
    ExtractionError,
    ExtractionMethod,
    ExtractionResponse,
    MRZResult,
)

logger = get_logger("ocr_service.router")

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR Extraction"])


@router.post(
    "/classify",
    response_model=ClassificationResult,
    summary="Classify document type from uploaded image",
)
async def classify_document_type(
    file: UploadFile = File(..., description="Document scan image file (JPEG, PNG, WEBP)"),
    provider: str = Form(default="local", description="Provider flag: 'local' or 'api'"),
) -> ClassificationResult:
    """Classify an identity document into passport, visa, national_id, driving_license, permit, or ferry_ticket."""
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Empty image file uploaded")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "classification_failed", "reason": "Failed to read image byte stream"},
        ) from e

    doc_type, conf, details = classify_document(image_bytes, provider=provider)
    return ClassificationResult(
        document_type=doc_type,
        confidence=conf,
        scores=details.get("scores", {}),
        matched_features=details.get("matched_features", []),
        provider=provider,
    )


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={
        422: {"model": ExtractionError, "description": "Unprocessable / Unreadable Image"},
    },
    summary="Extract text & MRZ from a single document scan",
)
async def extract_document(
    file: UploadFile = File(..., description="Document scan image file (JPEG or PNG)"),
    document_type: Optional[DocumentType] = Form(
        default=None,
        description="Optional document type hint. If omitted, automatic classification runs.",
    ),
    checkpoint_type: CheckpointType = Form(
        default=CheckpointType.AIRPORT,
        description="Checkpoint type: airport, land_border, or sea",
    ),
    provider: str = Form(
        default="local",
        description="Execution mode: 'local' (offline-capable) or 'api'",
    ),
) -> ExtractionResponse:
    """
    Extract structured fields, MRZ verification, and check digits from an uploaded document image.
    """
    logger.info(
        "Received extraction request",
        filename=file.filename,
        content_type=file.content_type,
        checkpoint_type=checkpoint_type.value,
        document_type=document_type.value if document_type else "auto",
        provider=provider,
    )

    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Empty image file uploaded")
    except Exception as e:
        logger.error("Failed to read uploaded image bytes", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "extraction_failed", "reason": "Failed to read image byte stream"},
        ) from e

    warnings: list[str] = []
    extracted_fields: dict[str, ExtractedField] = {}
    primary_method = ExtractionMethod.OCR

    explicit_document_type = document_type is not None

    # 1. Pure Cloud API Mode (Google Gemini Vision API)
    if provider == "api":
        logger.info(
            "Executing Cloud Vision API extraction",
            document_type=document_type.value if explicit_document_type else "auto",
            provider="api",
        )
        resolved_doc_type, llm_fields = extract_fields_with_llm(
            image_bytes=image_bytes,
            document_type=document_type if explicit_document_type else None,
            mime_type=file.content_type or "image/jpeg",
        )
        if llm_fields:
            for f in llm_fields:
                extracted_fields[f.field_name] = f
            return ExtractionResponse(
                document_type=resolved_doc_type,
                checkpoint_type=checkpoint_type,
                provider_used="api",
                extraction_method=ExtractionMethod.LLM,
                fields=list(extracted_fields.values()),
                mrz=MRZResult(mrz_present=False, mrz_format=None, mrz_fields={}, checksum_valid=None, checksum_failures=[]),
                warnings=["Extracted via Gemini Vision API (gemini-3.5-flash-lite)"],
            )
        else:
            warnings.append("Cloud API extraction returned empty, falling back to local engine.")

    # 2. Local OCR Engine Execution
    raw_ocr_lines: list[tuple[str, float]] = []
    try:
        raw_ocr_lines = extract_raw_ocr_lines(image_bytes)
    except RuntimeError as exc:
        logger.debug("Local OCR engine not installed, defaulting to Cloud Vision API", reason=str(exc))
    except Exception as exc:
        logger.warning("Local OCR engine failed on image", error=str(exc))

    text_only_lines = [text for text, _ in raw_ocr_lines]

    # 3. If document_type not explicitly provided, auto-classify
    if not explicit_document_type:
        classified_type, class_conf, _ = classify_document(
            image_bytes,
            ocr_lines=raw_ocr_lines,
            provider=provider,
        )
        document_type = classified_type
        if class_conf < 0.70:
            warnings.append(f"Auto-classified document type as {document_type.value} with confidence {class_conf:.2f}")

    # 4. Parse MRZ (from OCR text lines)
    mrz_res: MRZResult = parse_mrz(image_bytes, ocr_text_lines=text_only_lines)

    if mrz_res.mrz_present:
        primary_method = ExtractionMethod.MRZ
        for key, val in mrz_res.mrz_fields.items():
            if val and key != "mrz_format":
                extracted_fields[key] = ExtractedField(
                    field_name=key,
                    field_value=val,
                    confidence=1.0 if mrz_res.checksum_valid else 0.7,
                    extraction_method=ExtractionMethod.MRZ,
                )
        if not mrz_res.checksum_valid:
            warnings.append(f"MRZ checksum verification failed on: {', '.join(mrz_res.checksum_failures)}")

    # 5. Extract visual zone fields
    ocr_fields = extract_fields(image_bytes, document_type, raw_lines=raw_ocr_lines)
    for field in ocr_fields:
        if field.field_name not in extracted_fields:
            extracted_fields[field.field_name] = field

    # 6. Fallback to Vision LLM if no text/MRZ extracted or if non-standard layout.
    # Also trigger for NATIONAL_ID (e.g. Aadhaar) when sparse: EasyOCR reliably extracts
    # dates but misses the name because Aadhaar doesn't use "GIVEN NAME"/"SURNAME" labels.
    _sparse_non_mrz = (
        document_type in [
            DocumentType.DRIVING_LICENSE,
            DocumentType.PERMIT,
            DocumentType.FERRY_TICKET,
            DocumentType.NATIONAL_ID,
            DocumentType.PAN_CARD,
            DocumentType.VOTER_ID,
        ]
        and len(extracted_fields) < 3
    )
    if (not extracted_fields and not mrz_res.mrz_present) or _sparse_non_mrz:
        logger.info("Triggering LLM fallback", document_type=document_type.value if document_type else "auto")
        llm_detected_type, llm_fields = extract_fields_with_llm(
            image_bytes=image_bytes,
            document_type=document_type if explicit_document_type else None,
            mime_type=file.content_type or "image/jpeg",
        )
        if llm_fields:
            if not explicit_document_type and llm_detected_type:
                document_type = llm_detected_type
            if not extracted_fields:
                primary_method = ExtractionMethod.LLM
            for f in llm_fields:
                # Additive merge: LLM fills gaps; don't overwrite MRZ/OCR fields
                if f.field_name not in extracted_fields:
                    extracted_fields[f.field_name] = f

    if not extracted_fields and not mrz_res.mrz_present:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "extraction_failed",
                "reason": "Unable to detect text or MRZ data in the provided document image.",
            },
        )

    return ExtractionResponse(
        document_type=document_type,
        checkpoint_type=checkpoint_type,
        provider_used=provider,
        extraction_method=primary_method,
        fields=list(extracted_fields.values()),
        mrz=mrz_res,
        warnings=warnings,
    )


@router.post(
    "/extract/batch",
    response_model=BatchExtractionResponse,
    summary="Process bulk document queue for bus / ferry arrivals",
)
async def extract_documents_batch(
    files: List[UploadFile] = File(..., description="List of document scan images"),
    checkpoint_type: CheckpointType = Form(
        default=CheckpointType.LAND_BORDER,
        description="Checkpoint type: airport, land_border, or sea",
    ),
    provider: str = Form(
        default="local",
        description="Execution mode: 'local' or 'api'",
    ),
) -> BatchExtractionResponse:
    """
    Concurrent batch processing for bulk passenger queues (e.g. 50 bus passengers or 100 ferry passengers).
    """
    logger.info("Received batch extraction queue", count=len(files), checkpoint=checkpoint_type.value)
    
    items = []
    for file in files:
        b = await file.read()
        items.append((b, file.filename, None))

    res = await process_batch_queue(
        items=items,
        checkpoint_type=checkpoint_type,
        provider=provider,
    )
    return res
