"""
Document Classifier — Multi-modal document type classification.

Supports:
  1. Passport (International & Regional)
  2. Visa (Single, Multiple Entry, Tourist, Business)
  3. National ID (Aadhaar, Citizen ID, National Card)
  4. Driving License (State & National Motor Vehicle Cards)
  5. Permit (Land Border Crossings, Restricted Area Permits, Border Passes)
  6. Ferry Ticket (Sea Passenger Boarding Passes & Ferry Disembarkation Slips)
  7. PAN Card (Indian Permanent Account Number Card)
  8. Voter ID (Elector Identity Card / EPIC Card)

Provides both local heuristic / vision-feature classification and cloud API compatibility.
"""

import io
import re
from typing import Any
from PIL import Image

from backend.config import settings
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import DocumentType

logger = get_logger("ocr_service.classifier")

# Document Classification Keyword Signatures
DOCTYPE_KEYWORDS: dict[DocumentType, list[tuple[str, float]]] = {
    DocumentType.PASSPORT: [
        ("PASSPORT", 4.0),
        ("P<", 5.0),
        ("PASSEPORT", 4.0),
        ("REPUBLIC OF", 2.0),
        ("SURNAME", 1.5),
        ("GIVEN NAME", 1.5),
        ("NATIONALITY", 1.5),
        ("TYPE P", 3.0),
        ("PASSPORT NO", 3.5),
    ],
    DocumentType.VISA: [
        ("VISA", 4.0),
        ("V<", 4.0),
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
        ("AADHAAR", 5.0),
        ("AADHAR", 5.0),
        ("ADHAAR", 5.0),
        ("UIDAI", 5.0),
        ("UNIQUE IDENTIFICATION", 4.0),
        ("GOVERNMENT OF INDIA", 3.0),
        ("CIVIL ID", 3.5),
        ("CARD NO", 1.5),
        ("YEAR OF BIRTH", 3.0),
        ("MALE", 1.5),
        ("FEMALE", 1.5),
        ("DOB", 1.0),
    ],
    DocumentType.DRIVING_LICENSE: [
        ("DRIVING LICENCE", 5.0),
        ("DRIVING LICENSE", 5.0),
        ("DRIVER LICENSE", 5.0),
        ("MOTOR VEHICLE", 4.0),
        ("UNION OF INDIA DRIVING", 5.0),
        ("DL NO", 4.0),
        ("AUTHORISATION TO DRIVE", 4.0),
        ("VEHICLE CLASS", 3.5),
        ("TRANSPORT DEPARTMENT", 3.5),
        ("NON-TRANSPORT", 3.0),
        ("FORM 7", 3.5),
        ("LICENCE NO", 4.0),
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
    DocumentType.FERRY_TICKET: [
        ("FERRY TICKET", 5.0),
        ("FERRY", 4.0),
        ("BOARDING PASS", 4.0),
        ("CRUISE", 3.5),
        ("SEAPORT", 3.5),
        ("VESSEL", 3.5),
        ("DISEMBARKATION", 4.0),
        ("DEPARTURE", 2.5),
        ("ARRIVAL", 2.5),
        ("SEAT NO", 3.0),
    ],
    DocumentType.PAN_CARD: [
        ("INCOME TAX DEPARTMENT", 5.0),
        ("PERMANENT ACCOUNT NUMBER", 5.0),
        ("PAN CARD", 5.0),
        ("PERMANENT ACCOUNT", 4.0),
        ("GOVT OF INDIA", 3.0),
        ("GOVT. OF INDIA", 3.0),
        ("GOVERNMENT OF INDIA", 2.5),
        ("FATHER'S NAME", 3.5),
        ("FATHERS NAME", 3.5),
        ("आयकर विभाग", 5.0),
    ],
    DocumentType.VOTER_ID: [
        ("ELECTION COMMISSION OF INDIA", 5.0),
        ("ELECTOR IDENTITY CARD", 5.0),
        ("ELECTORAL REGISTRATION OFFICER", 4.0),
        ("VOTER ID", 5.0),
        ("EPIC NO", 5.0),
        ("EPIC NUMBER", 5.0),
        ("ELECTION COMMISSION", 4.0),
        ("ELECTOR'S NAME", 4.0),
        ("ELECTORS NAME", 4.0),
        ("भारत निर्वाचन आयोग", 5.0),
        ("मतदाता पहचान पत्र", 5.0),
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

    # If provider is 'api' or if Gemini Vision API key is configured and ocr_lines is empty/low quality,
    # attempt Cloud Vision API classification
    if provider == "api" and settings.llm_api_key:
        try:
            from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
            resolved_type, llm_fields = extract_fields_with_llm(image_bytes, document_type=None)
            if resolved_type:
                logger.info("Classified document via Cloud Vision API", predicted=resolved_type.value)
                return resolved_type, 0.95, {
                    "scores": {resolved_type.value: 1.0},
                    "matched_features": ["cloud_vision_api_multimodal"],
                    "provider": "api",
                }
        except Exception as e:
            logger.warning("Cloud Vision API classification failed, falling back to local engine", error=str(e))

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
    # Passport Number: Letter followed by 7-8 digits
    if re.search(r"\b[A-Z][0-9]{7,8}\b", full_text) and any(k in full_text for k in ["PASSPORT", "P<", "NATIONALITY"]):
        scores[DocumentType.PASSPORT] += 2.0

    # Driving license: DL-[0-9]{13} or state prefixes (MH, DL, HR, KA, UP, RJ, TN)
    if re.search(r"\b(DL|RJ|MH|KA|UP|TN|HR|PB)[0-9\- ]{8,16}\b", full_text) or "DRIVING" in full_text:
        scores[DocumentType.DRIVING_LICENSE] += 4.0
        matched_features[DocumentType.DRIVING_LICENSE.value].append("dl_number_pattern")

    # Aadhaar format: 12 digits (4 4 4) or 16 digit VID
    if re.search(r"\b[0-9]{4}\s+[0-9]{4}\s+[0-9]{4}\b", full_text) or re.search(r"\b[0-9]{12}\b", full_text):
        scores[DocumentType.NATIONAL_ID] += 5.0
        matched_features[DocumentType.NATIONAL_ID.value].append("aadhaar_number_pattern")

    # PAN Number: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
    if re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", full_text):
        scores[DocumentType.PAN_CARD] += 5.0
        matched_features[DocumentType.PAN_CARD.value].append("pan_number_pattern")

    # Voter ID / EPIC Number: 3 letters, 7 digits (e.g. ABC1234567)
    if re.search(r"\b[A-Z]{3}[0-9]{7}\b", full_text) or "ELECTION COMMISSION" in full_text:
        scores[DocumentType.VOTER_ID] += 5.0
        matched_features[DocumentType.VOTER_ID.value].append("voter_id_number_pattern")

    # 6. Normalize and Determine Winner
    best_type = max(scores, key=lambda k: scores[k])
    best_raw_score = scores[best_type]

    # If local score is low / zero and Gemini Vision API key is available, use LLM classification
    if best_raw_score <= 1.0 and settings.llm_api_key:
        try:
            from backend.ocr_service.core.llm_fallback import extract_fields_with_llm
            resolved_type, llm_fields = extract_fields_with_llm(image_bytes, document_type=None)
            if resolved_type:
                logger.info("Classified document via LLM fallback (low local score)", predicted=resolved_type.value)
                return resolved_type, 0.90, {
                    "scores": {resolved_type.value: 1.0},
                    "matched_features": ["llm_vision_auto_classified"],
                    "provider": provider,
                }
        except Exception as e:
            logger.warning("LLM classification attempt failed", error=str(e))

    if best_raw_score <= 0.0:
        # Default fallback to National ID / Passport depending on pattern
        predicted = DocumentType.NATIONAL_ID if re.search(r"\d{4}", full_text) else DocumentType.PASSPORT
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
