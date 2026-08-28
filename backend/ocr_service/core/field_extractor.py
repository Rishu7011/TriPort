"""
Field Extractor — Robust document OCR using EasyOCR.

Extracts text boxes, confidence scores, and maps key fields to document types.
"""

import io
import re
from typing import Any
import numpy as np
from PIL import Image

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)

logger = get_logger("ocr_service.field_extractor")

# Lazy-loaded EasyOCR reader
_ocr_reader: Any = None


def get_ocr_reader():
    """Singleton lazy-loader for EasyOCR reader."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            # Load English reader without GPU requirement by default for portability
            _ocr_reader = easyocr.Reader(["en"], gpu=False)
            logger.info("EasyOCR reader initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize EasyOCR engine", error=str(e))
            raise RuntimeError(f"OCR engine initialization error: {e}") from e
    return _ocr_reader


REQUIRED_FIELDS_BY_DOCTYPE: dict[DocumentType, list[str]] = {
    DocumentType.PASSPORT: [
        "name",
        "passport_number",
        "nationality",
        "date_of_birth",
        "date_of_expiry",
        "gender",
    ],
    DocumentType.VISA: [
        "visa_number",
        "visa_type",
        "passport_number",
        "entry_validity",
        "stay_duration",
    ],
    DocumentType.NATIONAL_ID: [
        "id_number",
        "name",
        "date_of_birth",
        "address",
    ],
    DocumentType.DRIVING_LICENSE: [
        "license_number",
        "name",
        "date_of_birth",
        "date_of_expiry",
        "vehicle_class",
    ],
    DocumentType.PERMIT: [
        "permit_number",
        "holder_name",
        "valid_until",
        "permit_type",
    ],
}

PATTERNS = {
    "date": re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2}|\d{2}\s+[A-Za-z]{3}\s+\d{4})\b"),
    "passport_num": re.compile(r"\b[A-Z][0-9]{7,8}\b"),
    "gender": re.compile(r"\b(SEX|GENDER)?\s*([MFX])\b", re.IGNORECASE),
    "nationality": re.compile(r"\b(NATIONALITY|CODE|COUNTRY)?\s*([A-Z]{3})\b", re.IGNORECASE),
}


def _bytes_to_numpy_image(image_bytes: bytes) -> np.ndarray:
    """Convert raw byte stream to RGB NumPy array."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(image)


def extract_raw_ocr_lines(image_bytes: bytes) -> list[tuple[str, float]]:
    """Extract raw text lines and confidences using EasyOCR."""
    img_array = _bytes_to_numpy_image(image_bytes)
    reader = get_ocr_reader()
    
    # reader.readtext() returns list of (bbox, text, prob)
    raw_results = reader.readtext(img_array)

    lines_with_conf: list[tuple[str, float]] = []
    for item in raw_results:
        text = str(item[1]).strip()
        prob = float(item[2])
        if text:
            lines_with_conf.append((text, prob))

    logger.info("OCR detection completed", lines_count=len(lines_with_conf))
    return lines_with_conf


def extract_fields(
    image_bytes: bytes,
    document_type: DocumentType,
    raw_lines: list[tuple[str, float]] | None = None,
) -> list[ExtractedField]:
    """
    Extract structured fields from image bytes.
    """
    if raw_lines is None:
        raw_lines = extract_raw_ocr_lines(image_bytes)

    extracted: dict[str, ExtractedField] = {}

    # 1. Look for Passport / ID Number
    for text, conf in raw_lines:
        if "passport_number" not in extracted:
            match = PATTERNS["passport_num"].search(text)
            if match:
                extracted["passport_number"] = ExtractedField(
                    field_name="passport_number",
                    field_value=match.group(0),
                    confidence=conf,
                    extraction_method=ExtractionMethod.OCR,
                )

    # 2. Look for Dates (DOB, Expiry)
    found_dates = []
    for text, conf in raw_lines:
        for match in PATTERNS["date"].finditer(text):
            found_dates.append((match.group(0), conf))

    if found_dates:
        if len(found_dates) >= 1 and "date_of_birth" not in extracted:
            extracted["date_of_birth"] = ExtractedField(
                field_name="date_of_birth",
                field_value=found_dates[0][0],
                confidence=found_dates[0][1],
                extraction_method=ExtractionMethod.OCR,
            )
        if len(found_dates) >= 2 and "date_of_expiry" not in extracted:
            extracted["date_of_expiry"] = ExtractedField(
                field_name="date_of_expiry",
                field_value=found_dates[1][0],
                confidence=found_dates[1][1],
                extraction_method=ExtractionMethod.OCR,
            )

    # 3. Look for Gender/Sex
    for text, conf in raw_lines:
        match = PATTERNS["gender"].search(text)
        if match and "gender" not in extracted:
            gender_val = match.group(2).upper()
            extracted["gender"] = ExtractedField(
                field_name="gender",
                field_value=gender_val,
                confidence=conf,
                extraction_method=ExtractionMethod.OCR,
            )

    # 4. Search for Name / other labeled fields
    for text, conf in raw_lines:
        if "name" not in extracted and any(kw in text.upper() for kw in ["GIVEN NAME", "SURNAME", "NAME"]):
            parts = re.split(r"[:\-\s]{2,}", text)
            val = parts[-1] if len(parts) > 1 else text
            extracted["name"] = ExtractedField(
                field_name="name",
                field_value=val,
                confidence=conf,
                extraction_method=ExtractionMethod.OCR,
            )

    return list(extracted.values())
