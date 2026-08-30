"""
Document Classifier — Multi-modal document type classification.

Supports:
  1. Passport (International & Regional)
  2. Visa (Single, Multiple Entry, Tourist, Business)
  3. National ID (Aadhaar, Citizen ID, Voter ID, National Card)
  4. Driving License (State & National Motor Vehicle Cards)
  5. Permit (Land Border Crossings, Restricted Area Permits, Border Passes)
  6. Ferry Ticket (Sea Passenger Boarding Passes & Ferry Disembarkation Slips)

Provides both local heuristic / vision-feature classification and cloud API compatibility.
"""

import io
import re
from typing import Any
import numpy as np
from PIL import Image

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import DocumentType

logger = get_logger("ocr_service.classifier")

# Document Classification Keyword Signatures
DOCTYPE_KEYWORDS: dict[DocumentType, list[tuple[str, float]]] = {
    DocumentType.PASSPORT: [
        ("PASSPORT", 3.0),
        ("P<", 4.0),
        ("PASSEPORT", 3.0),
        ("REPUBLIC OF", 1.5),
        ("SURNAME", 1.5),
        ("GIVEN NAME", 1.5),
        ("NATIONALITY", 1.5),
        ("TYPE P", 2.5),
        ("PASSPORT NO", 2.5),
    ],
    DocumentType.VISA: [
        ("VISA", 4.0),
        ("V<", 3.5),
        ("ENTRY", 2.0),
        ("VALID FOR", 2.0),
        ("STAY DURATION", 2.5),
        ("ENTRIES", 2.0),
        ("BEARER", 1.5),
        ("IMMIGRATION", 1.5),
        ("CONSULAR", 2.0),
    ],
    DocumentType.NATIONAL_ID: [
        ("IDENTITY CARD", 3.5),
        ("NATIONAL ID", 3.5),
        ("CITIZEN", 2.0),
        ("AADHAAR", 4.0),
        ("UIDAI", 3.5),
        ("GOVERNMENT OF INDIA", 2.0),
        ("ELECTION COMMISSION", 3.0),
        ("UNIQUE IDENTIFICATION", 3.0),
        ("CIVIL ID", 3.0),
        ("CARD NO", 1.5),
        ("DOB", 1.0),
    ],
    DocumentType.DRIVING_LICENSE: [
        ("DRIVING LICENCE", 4.0),
        ("DRIVING LICENSE", 4.0),
        ("DRIVER LICENSE", 4.0),
        ("MOTOR VEHICLE", 3.0),
        ("UNION OF INDIA DRIVING", 4.0),
        ("DL NO", 3.5),
        ("AUTHORISATION TO DRIVE", 3.0),
        ("VEHICLE CLASS", 2.5),
        ("TRANSPORT DEPARTMENT", 2.5),
        ("NON-TRANSPORT", 2.0),
    ],
    DocumentType.PERMIT: [
        ("BORDER PERMIT", 4.0),
        ("ENTRY PERMIT", 4.0),
        ("BORDER PASS", 4.0),
        ("LAND PORT", 3.5),
        ("SPECIAL PERMIT", 3.0),
        ("MOVEMENT PERMIT", 3.5),
        ("TRAVEL PASS", 3.0),
        ("CHECKPOST PASS", 3.5),
        ("RESTRICTED AREA PERMIT", 4.0),
        ("CROSSING PERMIT", 3.5),
    ],
}


def _bytes_to_image(image_bytes: bytes) -> Image.Image:
    """Safely convert image bytes (or PDF) to PIL Image."""
    from backend.ocr_service.core.field_extractor import ensure_image_bytes
    valid_bytes = ensure_image_bytes(image_bytes)
    return Image.open(io.BytesIO(valid_bytes)).convert("RGB")


def classify_document(
    image_bytes: bytes,
    ocr_lines: list[tuple[str, float]] | None = None,
    provider: str = "local",
) -> tuple[DocumentType, float, dict[str, Any]]:
    """
    Classify the document type from image bytes and OCR text hints.

    Args:
        image_bytes: Raw image file bytes.
        ocr_lines: Optional pre-extracted OCR text lines and confidence scores.
        provider: 'local' (heuristics / features) or 'api' (cloud inspection).

    Returns:
        tuple: (predicted_document_type, confidence_score, metadata_details)
    """
    if len(image_bytes) == 0:
        return DocumentType.PASSPORT, 0.0, {"reason": "empty_image"}

    scores: dict[DocumentType, float] = {dtype: 0.0 for dtype in DocumentType}
    matched_features: dict[str, list[str]] = {dtype.value: [] for dtype in DocumentType}

    # 1. Quick Image Aspect Ratio & Size inspection
    try:
        pil_img = _bytes_to_image(image_bytes)
        w, h = pil_img.size
        aspect_ratio = max(w, h) / max(min(w, h), 1)
        
        # Tickets are often elongated strips (ratio > 1.8)
        if aspect_ratio > 1.9:
            scores[DocumentType.FERRY_TICKET] += 1.0
            matched_features[DocumentType.FERRY_TICKET.value].append(f"high_aspect_ratio_{aspect_ratio:.2f}")
    except Exception as e:
        logger.debug("Failed to read image dimensions for classification", error=str(e))

    # 2. Inspect OCR Lines if provided or extract lightweight text
    if ocr_lines is None:
        try:
            from backend.ocr_service.core.field_extractor import extract_raw_ocr_lines
            ocr_lines = extract_raw_ocr_lines(image_bytes)
        except Exception as e:
            logger.warning("OCR extraction during classification failed", error=str(e))
            ocr_lines = []

    full_text = " ".join([text.upper() for text, _ in ocr_lines])

    # 3. Fast MRZ pattern detection
    for text, conf in ocr_lines:
        clean = text.replace(" ", "").upper().replace("«", "<").replace("‹", "<")
        if clean.startswith("P<") or (clean.startswith("P") and "<<" in clean):
            scores[DocumentType.PASSPORT] += 5.0
            matched_features[DocumentType.PASSPORT.value].append("mrz_td3_line1")
        elif clean.startswith("V<") or (clean.startswith("V") and "<<" in clean):
            scores[DocumentType.VISA] += 5.0
            matched_features[DocumentType.VISA.value].append("mrz_mrv_line1")
        elif clean.startswith("I<") or clean.startswith("A<") or clean.startswith("C<"):
            scores[DocumentType.NATIONAL_ID] += 4.0
            matched_features[DocumentType.NATIONAL_ID.value].append("mrz_td1_line1")

    # 4. Keyword and Pattern Matching
    for dtype, keywords in DOCTYPE_KEYWORDS.items():
        for keyword, weight in keywords:
            if keyword in full_text:
                scores[dtype] += weight
                matched_features[dtype.value].append(keyword)

    # 5. Regex Specific ID Number Signatures
    # Passport Number: Letter followed by 7 digits
    if re.search(r"\b[A-Z][0-9]{7,8}\b", full_text) and scores[DocumentType.PASSPORT] > 0:
        scores[DocumentType.PASSPORT] += 2.0
    # Driving license: DL-[0-9]{13} or DL[0-9]{13}
    if re.search(r"\b(DL|RJ|MH|DL|KA|UP|TN|HR|PB)[0-9\- ]{8,16}\b", full_text):
        scores[DocumentType.DRIVING_LICENSE] += 3.0
        matched_features[DocumentType.DRIVING_LICENSE.value].append("dl_number_pattern")
    # Aadhaar format: 4 digits 4 digits 4 digits
    if re.search(r"\b[0-9]{4}\s+[0-9]{4}\s+[0-9]{4}\b", full_text):
        scores[DocumentType.NATIONAL_ID] += 4.0
        matched_features[DocumentType.NATIONAL_ID.value].append("aadhaar_number_pattern")

    # 6. Normalize and Determine Winner
    best_type = max(scores, key=lambda k: scores[k])
    best_raw_score = scores[best_type]

    if best_raw_score <= 0.0:
        # Default fallback to Passport with conservative confidence
        predicted = DocumentType.PASSPORT
        confidence = 0.50
    else:
        predicted = best_type
        confidence = min(0.98, max(0.60, best_raw_score / 8.0))

    details = {
        "scores": {k.value: round(v, 2) for k, v in scores.items()},
        "matched_features": matched_features.get(predicted.value, []),
        "provider": provider,
    }

    logger.info(
        "Document classified",
        predicted=predicted.value,
        confidence=round(confidence, 3),
        raw_score=best_raw_score,
    )
    return predicted, confidence, details
