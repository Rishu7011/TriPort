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
    Extract structured fields from image bytes using contextual OCR line analysis.
    """
    if raw_lines is None:
        raw_lines = extract_raw_ocr_lines(image_bytes)

    extracted: dict[str, ExtractedField] = {}

    # 1. Look for Passport / ID Number
    for i, (text, conf) in enumerate(raw_lines):
        if "passport_number" not in extracted:
            match = PATTERNS["passport_num"].search(text)
            if match:
                extracted["passport_number"] = ExtractedField(
                    field_name="passport_number",
                    field_value=match.group(0),
                    confidence=conf,
                    extraction_method=ExtractionMethod.OCR,
                )
            elif any(k in text.upper() for k in ["PASSPORT NO", "PASSPORT N", "पासपोर्ट", "DOC NO"]):
                # Check current or next line for 8-char token
                candidates = re.findall(r"\b[A-Z0-9]{8}\b", text.upper())
                if not candidates and i + 1 < len(raw_lines):
                    candidates = re.findall(r"\b[A-Z0-9]{8}\b", raw_lines[i + 1][0].upper())
                for cand in candidates:
                    if cand[0] == "2":
                        cand = "Z" + cand[1:]
                    elif cand[0] == "0":
                        cand = "O" + cand[1:]
                    if re.match(r"^[A-Z][0-9]{7,8}$", cand):
                        extracted["passport_number"] = ExtractedField(
                            field_name="passport_number",
                            field_value=cand,
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )
                        break

    # 2. Contextual Date Extraction (DOB vs Issue vs Expiry)
    found_labeled_dates: dict[str, tuple[str, float]] = {}
    unlabeled_dates: list[tuple[str, float]] = []

    for i, (text, conf) in enumerate(raw_lines):
        text_upper = text.upper()
        date_matches = list(PATTERNS["date"].finditer(text))
        
        # Check if date is on this line or the immediate next line
        dates_on_line = [m.group(0) for m in date_matches]
        next_line_date = None
        if i + 1 < len(raw_lines):
            next_m = PATTERNS["date"].search(raw_lines[i + 1][0])
            if next_m:
                next_line_date = (next_m.group(0), raw_lines[i + 1][1])

        target_date = (dates_on_line[0], conf) if dates_on_line else next_line_date

        if target_date:
            if any(k in text_upper for k in ["EXPIRY", "समाप्ति", "VALID UNTIL", "EXPIRATION"]):
                found_labeled_dates["date_of_expiry"] = target_date
            elif any(k in text_upper for k in ["BIRTH", "जन्म", "DOB", "NAISSANCE"]):
                found_labeled_dates["date_of_birth"] = target_date
            elif any(k in text_upper for k in ["ISSUE", "जारी"]):
                found_labeled_dates["date_of_issue"] = target_date
            elif dates_on_line:
                unlabeled_dates.append((dates_on_line[0], conf))

    # Apply labeled dates
    if "date_of_birth" in found_labeled_dates:
        d, c = found_labeled_dates["date_of_birth"]
        extracted["date_of_birth"] = ExtractedField(
            field_name="date_of_birth",
            field_value=d,
            confidence=c,
            extraction_method=ExtractionMethod.OCR,
        )
    if "date_of_expiry" in found_labeled_dates:
        d, c = found_labeled_dates["date_of_expiry"]
        extracted["date_of_expiry"] = ExtractedField(
            field_name="date_of_expiry",
            field_value=d,
            confidence=c,
            extraction_method=ExtractionMethod.OCR,
        )

    # Fallback to date sorting if labels weren't explicitly matched
    if ("date_of_birth" not in extracted or "date_of_expiry" not in extracted) and unlabeled_dates:
        # Sort dates chronologically if possible
        parsed_dates = []
        for d_str, c in unlabeled_dates:
            parts = re.split(r"[/-]", d_str)
            if len(parts) == 3:
                try:
                    # heuristic for YYYY at end vs beginning
                    yr = int(parts[2]) if len(parts[2]) == 4 else int(parts[0])
                    parsed_dates.append((yr, d_str, c))
                except ValueError:
                    pass
        
        parsed_dates.sort(key=lambda x: x[0])
        if parsed_dates:
            if "date_of_birth" not in extracted:
                extracted["date_of_birth"] = ExtractedField(
                    field_name="date_of_birth",
                    field_value=parsed_dates[0][1],
                    confidence=parsed_dates[0][2],
                    extraction_method=ExtractionMethod.OCR,
                )
            if "date_of_expiry" not in extracted and len(parsed_dates) > 1:
                # Latest date is expiry
                extracted["date_of_expiry"] = ExtractedField(
                    field_name="date_of_expiry",
                    field_value=parsed_dates[-1][1],
                    confidence=parsed_dates[-1][2],
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

    # 4. Search for Name / Given Name / Surname
    surname_val = ""
    given_val = ""
    for i, (text, conf) in enumerate(raw_lines):
        text_upper = text.upper()
        if "SURNAME" in text_upper or "उपनाम" in text_upper:
            # check inline or next line
            clean = re.sub(r"(SURNAME|उपनाम|/|:)", "", text, flags=re.IGNORECASE).strip()
            if clean and len(clean) > 1 and not re.search(r"^[A-Z0-9<]{9}", clean):
                surname_val = clean
            elif i + 1 < len(raw_lines):
                next_t = raw_lines[i + 1][0].strip()
                if next_t and not any(k in next_t.upper() for k in ["NAME", "GIVEN", "BIRTH", "DATE"]):
                    surname_val = next_t

        if "GIVEN NAME" in text_upper or "दिया गया नाम" in text_upper:
            clean = re.sub(r"(GIVEN NAME\(S\)|GIVEN NAME|दिया गया नाम|/|:|\(S\))", "", text, flags=re.IGNORECASE).strip()
            if clean and len(clean) > 1:
                given_val = clean
            elif i + 1 < len(raw_lines):
                next_t = raw_lines[i + 1][0].strip()
                if next_t and not any(k in next_t.upper() for k in ["BIRTH", "DATE", "SEX", "GENDER", "PLACE"]):
                    given_val = next_t

    if surname_val or given_val:
        full = f"{given_val} {surname_val}".strip() or surname_val or given_val
        extracted["name"] = ExtractedField(
            field_name="name",
            field_value=full,
            confidence=0.90,
            extraction_method=ExtractionMethod.OCR,
        )

    # 5. Look for Nationality
    for text, conf in raw_lines:
        text_upper = text.upper()
        if "INDIAN" in text_upper or "IND " in text_upper or "BHARATIYA" in text_upper:
            if "nationality" not in extracted:
                extracted["nationality"] = ExtractedField(
                    field_name="nationality",
                    field_value="INDIAN",
                    confidence=conf,
                    extraction_method=ExtractionMethod.OCR,
                )
                break

    return list(extracted.values())
