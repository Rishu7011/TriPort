"""
Extraction Router — FastAPI endpoint for document OCR extraction.

FLOW:
  1. Receives uploaded document image via multipart/form-data.
  2. Runs EasyOCR to extract all text lines & confidence scores.
  3. Detects and parses MRZ lines (`P<IND...`, `U5691319...`) & calculates ICAO check digits.
  4. Maps visual text fields (dates, names, numbers).
  5. Triggers LLM fallback if document is unstructured (driving license, permit) or unreadable.
  6. Returns structured ExtractionResponse.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.logging_config import get_logger
from backend.ocr_service.core.field_extractor import (
    extract_fields,
    extract_raw_ocr_lines,
)
from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
from backend.ocr_service.core.mrz_parser import parse_mrz
from backend.ocr_service.schemas.extraction import (
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
    "/extract",
    response_model=ExtractionResponse,
    responses={
        422: {"model": ExtractionError, "description": "Unprocessable / Unreadable Image"},
    },
    summary="Extract text & MRZ from a document scan",
)
async def extract_document(
    file: UploadFile = File(..., description="Document scan image file (JPEG or PNG)"),
    document_type: DocumentType = Form(
        default=DocumentType.PASSPORT,
        description="Type of document (passport, visa, national_id, driving_license, permit)",
    ),
) -> ExtractionResponse:
    """
    Extract structured fields and MRZ check digits from an uploaded document image.
    """
    logger.info(
        "Received extraction request",
        filename=file.filename,
        content_type=file.content_type,
        document_type=document_type.value,
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

    # 1. Run OCR to get text lines
    raw_ocr_lines: list[tuple[str, float]] = []
    try:
        raw_ocr_lines = extract_raw_ocr_lines(image_bytes)
    except Exception as exc:
        logger.warning("OCR engine failed on image", error=str(exc))

    text_only_lines = [text for text, _ in raw_ocr_lines]

    # 2. Parse MRZ (from OCR text lines)
    mrz_res: MRZResult = parse_mrz(image_bytes, ocr_text_lines=text_only_lines)

    if mrz_res.mrz_present:
        primary_method = ExtractionMethod.MRZ
        for key, val in mrz_res.mrz_fields.items():
            if val:
                extracted_fields[key] = ExtractedField(
                    field_name=key,
                    field_value=val,
                    confidence=1.0 if mrz_res.checksum_valid else 0.7,
                    extraction_method=ExtractionMethod.MRZ,
                )
        if not mrz_res.checksum_valid:
            warnings.append(f"MRZ checksum verification failed on: {', '.join(mrz_res.checksum_failures)}")

    # 3. Extract visual zone fields
    ocr_fields = extract_fields(image_bytes, document_type, raw_lines=raw_ocr_lines)
    for field in ocr_fields:
        if field.field_name not in extracted_fields:
            extracted_fields[field.field_name] = field

    # 4. Fallback to Vision LLM if no text/MRZ extracted or if driving license
    if (not extracted_fields and not mrz_res.mrz_present) or (
        document_type in [DocumentType.DRIVING_LICENSE, DocumentType.PERMIT]
    ):
        logger.info("Triggering LLM fallback", document_type=document_type.value)
        llm_fields = extract_fields_with_llm(
            image_bytes=image_bytes,
            document_type=document_type,
            mime_type=file.content_type or "image/jpeg",
        )
        if llm_fields:
            primary_method = ExtractionMethod.LLM
            for f in llm_fields:
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
        extraction_method=primary_method,
        fields=list(extracted_fields.values()),
        mrz=mrz_res,
        warnings=warnings,
    )
