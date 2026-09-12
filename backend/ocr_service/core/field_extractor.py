"""
Field Extractor — Robust Multi-Modal Document OCR using EasyOCR.

Extracts text boxes, confidence scores, and maps structured fields for:
  1. Passport
  2. Visa
  3. National ID (Aadhaar, Citizen Card, Voter ID)
  4. Driving License
  5. Permit (Land Border Crossings & Transit Passes)
  6. Ferry Ticket (Sea Passenger Crossings)

Phase 9 — Global Multi-Language Passport OCR:
  - EasyOCR loads English + Devanagari (hi/ne) + Bengali (bn) + Latin diacritics (de, fr, es)
  - Multilingual field anchors: Hindi (उपनाम, दिया गया नाम), Bengali (পদবি, প্রদত্ত নাম), German (NACHNAME, VORNAMEN)
  - ExtractedField.native_value stores original script; field_value is ICAO-normalized ASCII
  - Script detection via transliteration.detect_script() across all OCR lines
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
from backend.ocr_service.core.transliteration import (
    normalize_icao_transliteration,
    normalize_regional_numerals,
    detect_script,
    detect_languages_in_text,
    normalize_country_code,
)

logger = get_logger("ocr_service.field_extractor")

# Singleton OCR engine state
_ocr_engine_type: str | None = None  # "easyocr"
_ocr_reader: Any = None

# Phase 9: EasyOCR language configuration
# Local engine runs ["en"] (fully cached offline with Latin character support).
# Multi-script multilingual documents (Hindi, Bengali, Arabic, Cyrillic, Thai, etc.)
# are extracted with high fidelity by Layer 2 (Gemini Vision LLM fallback).
_EASYOCR_LANGUAGES: list[str] = ["en"]


def get_ocr_reader() -> tuple[str, Any]:
    """
    Singleton lazy-loader for EasyOCR engine.
    Uses local offline English model (compatible with Latin text/MRZ).
    Complex multilingual/non-Latin documents are routed to Layer 2 (Gemini Vision).
    """
    global _ocr_reader, _ocr_engine_type
    if _ocr_reader is None:
        import easyocr
        import torch
        use_gpu = torch.cuda.is_available()
        _ocr_reader = easyocr.Reader(_EASYOCR_LANGUAGES, gpu=use_gpu)
        _ocr_engine_type = "easyocr"
        logger.info(
            "EasyOCR engine initialized successfully",
            gpu=use_gpu,
            languages=_EASYOCR_LANGUAGES,
        )

    return _ocr_engine_type, _ocr_reader


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
        "issuing_authority",
        "validity_period",
    ],
    DocumentType.DRIVING_LICENSE: [
        "license_number",
        "name",
        "date_of_birth",
        "date_of_expiry",
        "vehicle_class",
        "issuing_authority",
    ],
    DocumentType.PERMIT: [
        "permit_number",
        "name",
        "permit_type",
        "valid_until",
        "issuing_authority",
    ],
    DocumentType.PAN_CARD: [
        "pan_number",
        "name",
        "father_name",
        "date_of_birth",
        "issuing_authority",
    ],
    DocumentType.VOTER_ID: [
        "voter_id_number",
        "name",
        "father_name",
        "date_of_birth",
        "gender",
        "issuing_authority",
    ],
}

PATTERNS = {
    "date": re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4}[/\-.\s]\d{1,2}[/\-.]\d{1,2}|\d{1,2}[\s/\-.]?[A-Za-z]{3}[\s/\-.]?\d{2,4})\b"),
    "date_devanagari": re.compile(r"[\u0966-\u096F]{1,2}[/\-][\u0966-\u096F]{1,2}[/\-][\u0966-\u096F]{4}"),
    "passport_num": re.compile(r"\b[A-Z]{1,2}[0-9]{7,8}\b"),
    "gender": re.compile(r"\b(SEX|GENDER|\u0932\u093f\u0902\u0917)?\s*([MFX])\b", re.IGNORECASE),
    "nationality": re.compile(r"\b(NATIONALITY|CODE|COUNTRY|\u0930\u093e\u0937\u094d\u091f\u094d\u0930\u0940\u092f\u0924\u093e)?\s*([A-Z]{3})\b", re.IGNORECASE),
    "aadhaar": re.compile(r"\b\d{4}\s+\d{4}\s+\d{4}\b"),
    "dl_num": re.compile(r"\b([A-Z]{2}[- /]?[0-9]{1,2}[ -/:]?[0-9]{4,11}(?:[ -/:][0-9]{4,7})?|[A-Z]{2}[0-9A-Z/-]{10,20})\b", re.IGNORECASE),
    "permit_num": re.compile(r"\b(?:PER|BP|LPAI|RAP)[- /]?[0-9A-Z]{6,12}\b|\b(?:IN|NP|BT|BD)[-/][0-9A-Z/-]{4,16}\b", re.IGNORECASE),
    "ticket_num": re.compile(r"\b(TKT|FERRY|BRD|SEA)[- /]?[0-9A-Z]{6,12}\b", re.IGNORECASE),
    "pan_num": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE),
    "voter_id_num": re.compile(r"\b[A-Z]{3}[-/]?[0-9]{7}\b", re.IGNORECASE),
}

# Phase 9: Multilingual field anchor keywords
# Grouped by field name with English + Hindi + Bengali + German labels
_FIELD_ANCHORS: dict[str, list[str]] = {
    "surname": [
        # English
        "SURNAME", "LAST NAME",
        # Hindi (Devanagari)
        "\u0909\u092a\u0928\u093e\u092e",         # उपनाम
        # Bengali
        "\u09aa\u09a6\u09ac\u09bf",               # পদবি
        "\u09ac\u0982\u09b6\u0997\u09a4 \u09a8\u09be\u09ae",  # বংশগত নাম (Bengali surname in BD passport)
        # Nepali
        "\u0925\u0930",                            # थर
        # German
        "NACHNAME", "FAMILIENNAME",
        # French
        "NOM DE FAMILLE", "NOM",
    ],
    "given_names": [
        # English
        "GIVEN NAMES", "GIVEN NAME", "FIRST NAME", "FORENAMES",
        # Hindi (Devanagari)
        "\u0926\u093f\u092f\u093e \u0917\u092f\u093e \u0928\u093e\u092e",  # दिया गया नाम
        "\u0928\u093e\u092e",                     # नाम
        # Bengali
        "\u09aa\u09cd\u09b0\u09a6\u09a4\u09cd\u09a4 \u09a8\u09be\u09ae",   # প্রদত্ত নাম
        # German
        "VORNAMEN", "VORNAME",
        # French
        "PRÉNOMS", "PRENOMS",
    ],
    "nationality": [
        # English
        "NATIONALITY",
        # Hindi
        "\u0930\u093e\u0937\u094d\u091f\u094d\u0930\u0940\u092f\u0924\u093e",  # राष्ट्रीयता
        # Bengali
        "\u099c\u09be\u09a4\u09c0\u09af\u09bc\u09a4\u09be",                    # জাতীয়তা
        # German
        "STAATSANGEHÖRIGKEIT", "STAATSANGEHOERIGKEIT",
        # French
        "NATIONALITÉ", "NATIONALITE",
    ],
    "date_of_birth": [
        # English
        "BIRTH", "DOB", "DATE OF BIRTH",
        # Hindi
        "\u091c\u0928\u094d\u092e",  # जन्म
        "\u091c\u0928\u094d\u092e \u0924\u093f\u0925\u093f",  # जन्म तिथि
        # Bengali
        "\u099c\u09a8\u09cd\u09ae",  # জন্ম
        # German
        "GEBURTSDATUM", "GEBOREN",
        # French
        "NAISSANCE", "DATE DE NAISSANCE",
    ],
    "date_of_expiry": [
        # English
        "EXPIRY", "VALID UNTIL", "EXPIRATION", "VALID TILL", "VALID UPTO",
        # Hindi
        "\u0938\u092e\u093e\u092a\u094d\u0924\u093f",  # समाप्ति
        # German
        "ABLAUFDATUM", "GÜLTIG BIS", "GUELTIG BIS",
        # French
        "DATE D'EXPIRATION", "EXPIRE LE",
    ],
    "date_of_issue": [
        # English
        "ISSUE", "DATE OF ISSUE", "ISSUED ON",
        # Hindi
        "\u091c\u093e\u0930\u0940",  # जारी
        # German
        "AUSSTELLUNGSDATUM",
        # French
        "DATE DE DÉLIVRANCE",
    ],
}


def ensure_image_bytes(raw_bytes: bytes) -> bytes:
    """If input is a PDF byte stream (%PDF), render the first page to JPEG bytes."""
    if b"%PDF" in raw_bytes[:1024]:
        try:
            import pymupdf
            pdf_doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
            if len(pdf_doc) > 0:
                first_page = pdf_doc.load_page(0)
                pix = first_page.get_pixmap(dpi=300)
                logger.info("Rendered PDF page 1 to JPEG image for OCR extraction")
                return pix.tobytes("jpeg")
        except Exception as e:
            logger.warning("Failed to render PDF page to image", error=str(e))
            raise ValueError("Failed to process uploaded PDF file. Please ensure it is a valid PDF scan.") from e
    return raw_bytes


def _bytes_to_numpy_image(image_bytes: bytes, max_dim: int = 1200) -> np.ndarray:
    """Convert raw byte stream (or PDF) to RGB NumPy array with smart downscaling for fast inference."""
    valid_bytes = ensure_image_bytes(image_bytes)
    image = Image.open(io.BytesIO(valid_bytes)).convert("RGB")
    
    # Scale down oversized phone camera images to 1200px max dimension for fast CRAFT inference
    w, h = image.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_w, new_h = int(w * scale), int(h * scale)
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        
    return np.array(image)


def extract_raw_ocr_lines(image_bytes: bytes) -> list[tuple[str, float]]:
    """Extract raw text lines and confidences exclusively using EasyOCR."""
    valid_bytes = ensure_image_bytes(image_bytes)
    img_array = _bytes_to_numpy_image(valid_bytes)
    engine_type, reader = get_ocr_reader()

    lines_with_conf: list[tuple[str, float]] = []

    import torch
    with torch.inference_mode():
        raw_results = reader.readtext(
            img_array,
            batch_size=4,
            paragraph=False,
            canvas_size=1200,
            mag_ratio=1.0,
        )
    for item in raw_results:
        if item and len(item) >= 3:
            text = str(item[1]).strip()
            prob = float(item[2])
            if text:
                lines_with_conf.append((text, prob))

    logger.info("OCR detection completed", engine=engine_type, lines_count=len(lines_with_conf))
    return lines_with_conf


def extract_fields(
    image_bytes: bytes,
    document_type: DocumentType,
    raw_lines: list[tuple[str, float]] | None = None,
) -> list[ExtractedField]:
    """
    Extract structured fields from image bytes using contextual OCR line analysis
    tailored to the document type.
    """
    if raw_lines is None:
        raw_lines = extract_raw_ocr_lines(image_bytes)

    extracted: dict[str, ExtractedField] = {}
    full_text_upper = " ".join([t.upper() for t, _ in raw_lines])

    # -----------------------------------------------------------------------
    # 1. Document-Specific ID Numbers
    # -----------------------------------------------------------------------
    if document_type in [DocumentType.PASSPORT, DocumentType.VISA]:
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
                elif any(k in text.upper() for k in ["PASSPORT NO", "PASSPORT N", "DOC NO"]):
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

    if document_type == DocumentType.VISA:
        # Visa Number
        for text, conf in raw_lines:
            if "visa_number" not in extracted:
                if any(k in text.upper() for k in ["VISA NO", "VISA NUMBER", "V NO", "CONTROL NO"]):
                    nums = re.findall(r"\b[A-Z0-9]{8,12}\b", text.upper())
                    if nums:
                        extracted["visa_number"] = ExtractedField(
                            field_name="visa_number",
                            field_value=nums[0],
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )
        # Visa Type
        for text, conf in raw_lines:
            text_u = text.upper()
            if "visa_type" not in extracted:
                for vtype in ["TOURIST", "BUSINESS", "TRANSIT", "EMPLOYMENT", "STUDENT", "DIPLOMATIC", "OFFICIAL"]:
                    if vtype in text_u:
                        extracted["visa_type"] = ExtractedField(
                            field_name="visa_type",
                            field_value=vtype,
                            confidence=0.90,
                            extraction_method=ExtractionMethod.OCR,
                        )
                        break
        # Stay Duration
        for text, conf in raw_lines:
            text_u = text.upper()
            if "stay_duration" not in extracted:
                m_stay = re.search(r"\b(\d{1,3}\s+(DAYS|MONTHS|YEARS))\b", text_u)
                if m_stay:
                    extracted["stay_duration"] = ExtractedField(
                        field_name="stay_duration",
                        field_value=m_stay.group(1),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )

    elif document_type == DocumentType.NATIONAL_ID:
        for i, (text, conf) in enumerate(raw_lines):
            if "id_number" not in extracted:
                # Aadhaar check
                m_aadhaar = PATTERNS["aadhaar"].search(text)
                if m_aadhaar:
                    extracted["id_number"] = ExtractedField(
                        field_name="id_number",
                        field_value=m_aadhaar.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
                # General ID number
                elif any(k in text.upper() for k in ["ID NO", "IDENTITY NO", "CARD NO", "CITIZEN NO", "UID"]):
                    candidates = re.findall(r"\b[A-Z0-9\-]{8,16}\b", text.upper())
                    numeric_cands = [c for c in candidates if any(ch.isdigit() for ch in c)]
                    if numeric_cands:
                        extracted["id_number"] = ExtractedField(
                            field_name="id_number",
                            field_value=numeric_cands[0],
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )
        if "issuing_authority" not in extracted:
            for text, conf in raw_lines:
                if any(k in text.upper() for k in ["GOVERNMENT", "UIDAI", "ELECTION COMMISSION", "MINISTRY OF HOME"]):
                    extracted["issuing_authority"] = ExtractedField(
                        field_name="issuing_authority",
                        field_value="Government of India / National Authority",
                        confidence=0.88,
                        extraction_method=ExtractionMethod.OCR,
                    )
                    break

    elif document_type == DocumentType.DRIVING_LICENSE:
        # 1. License Number
        for i, (text, conf) in enumerate(raw_lines):
            if "license_number" not in extracted:
                text_clean = text.strip()
                # Multi-line match: Box 1 is state/RTO code (e.g. DL9, DL09, MH02), Box 2 is year+serial (e.g. 20220000839)
                if re.fullmatch(r"[A-Z]{2}[0-9]{1,2}", text_clean, re.IGNORECASE):
                    if i + 1 < len(raw_lines):
                        next_t = raw_lines[i + 1][0].strip()
                        if re.fullmatch(r"[0-9]{10,15}", next_t):
                            extracted["license_number"] = ExtractedField(
                                field_name="license_number",
                                field_value=f"{text_clean.upper()}-{next_t}",
                                confidence=conf,
                                extraction_method=ExtractionMethod.OCR,
                            )
                            break
                # Single-line regex match
                m_dl = PATTERNS["dl_num"].search(text_clean.replace(" ", ""))
                if m_dl:
                    extracted["license_number"] = ExtractedField(
                        field_name="license_number",
                        field_value=m_dl.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
                    break

        # 2. Vehicle Class
        for text, conf in raw_lines:
            text_u = text.upper()
            if "vehicle_class" not in extracted:
                for vclass in ["LMV", "MCWG", "HMV", "3W-NT", "NON-TRANS", "TRANS", "NT", "TR"]:
                    if re.search(rf"\b{re.escape(vclass)}\b", text_u):
                        extracted["vehicle_class"] = ExtractedField(
                            field_name="vehicle_class",
                            field_value=vclass,
                            confidence=0.90,
                            extraction_method=ExtractionMethod.OCR,
                        )
                        break

        # 3. Issuing Authority
        for text, conf in raw_lines:
            if "issuing_authority" not in extracted:
                if any(k in text.upper() for k in ["TRANSPORT DEPARTMENT", "ISSUED BY", "LICENSING AUTHORITY", "RTO"]):
                    clean_auth = re.sub(r"(?:Issued\s*by\s*:?|Licensing\s*Authority\s*:?)", "", text, flags=re.IGNORECASE).strip()
                    extracted["issuing_authority"] = ExtractedField(
                        field_name="issuing_authority",
                        field_value=clean_auth or text.strip(),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
                    break

    elif document_type == DocumentType.PERMIT:
        for text, conf in raw_lines:
            text_u = text.upper().strip()

            # 1. Permit Number
            if "permit_number" not in extracted:
                m_label = re.search(r"(?:PERMIT\s*(?:NO|NUMBER|#)?[:.\s]+)([A-Z0-9/\-]{5,25})", text_u)
                if m_label:
                    extracted["permit_number"] = ExtractedField(
                        field_name="permit_number",
                        field_value=m_label.group(1).strip(),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
                else:
                    m_per = PATTERNS["permit_num"].search(text)
                    if m_per:
                        extracted["permit_number"] = ExtractedField(
                            field_name="permit_number",
                            field_value=m_per.group(0),
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )

            # 2. Permit Type
            if "permit_type" not in extracted:
                m_ptype = re.search(r"(?:PERMIT\s*TYPE[:.\s]+)(.+)", text, re.IGNORECASE)
                if m_ptype:
                    val = m_ptype.group(1).strip()
                    if len(val) >= 2:
                        extracted["permit_type"] = ExtractedField(
                            field_name="permit_type",
                            field_value=val,
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )
                else:
                    for ptype in ["BORDER PASS", "ENTRY PERMIT", "RESTRICTED AREA PERMIT", "LAND TRANSIT PASS", "CROSS-BORDER TRANSIT", "TRANSIT PERMIT"]:
                        if ptype in text_u:
                            extracted["permit_type"] = ExtractedField(
                                field_name="permit_type",
                                field_value=ptype.title(),
                                confidence=0.90,
                                extraction_method=ExtractionMethod.OCR,
                            )
                            break

            # 3. Issuing Authority
            if "issuing_authority" not in extracted:
                m_auth = re.search(r"(?:ISSUING\s*AUTHORITY[:.\s]+)(.+)", text, re.IGNORECASE)
                if m_auth:
                    val = m_auth.group(1).strip()
                    if len(val) >= 2:
                        extracted["issuing_authority"] = ExtractedField(
                            field_name="issuing_authority",
                            field_value=val,
                            confidence=conf,
                            extraction_method=ExtractionMethod.OCR,
                        )

            # 4. Valid Until
            if "valid_until" not in extracted:
                m_val = re.search(r"(?:VALID\s*(?:UNTIL|TO|THRU)[:.\s]+)([0-9A-Za-z\-/ ]+)", text, re.IGNORECASE)
                if m_val:
                    val = m_val.group(1).strip()
                    extracted["valid_until"] = ExtractedField(
                        field_name="valid_until",
                        field_value=val,
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )

    elif document_type == DocumentType.FERRY_TICKET:
        for text, conf in raw_lines:
            if "ticket_number" not in extracted:
                m_tkt = PATTERNS["ticket_num"].search(text)
                if m_tkt:
                    extracted["ticket_number"] = ExtractedField(
                        field_name="ticket_number",
                        field_value=m_tkt.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        # Route
        for text, conf in raw_lines:
            text_u = text.upper()
            if "route" not in extracted:
                if any(sym in text_u for sym in [" - ", " TO ", " -> ", "⇄", "->"]):
                    extracted["route"] = ExtractedField(
                        field_name="route",
                        field_value=text.strip(),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        # Vessel name
        for text, conf in raw_lines:
            text_u = text.upper()
            if "vessel_name" not in extracted:
                if any(k in text_u for k in ["VESSEL", "FERRY", "CRUISE", "SHIP", "MV ", "SS "]):
                    extracted["vessel_name"] = ExtractedField(
                        field_name="vessel_name",
                        field_value=text.strip(),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )

    elif document_type == DocumentType.PAN_CARD:
        for text, conf in raw_lines:
            if "pan_number" not in extracted:
                m_pan = PATTERNS["pan_num"].search(text)
                if m_pan:
                    extracted["pan_number"] = ExtractedField(
                        field_name="pan_number",
                        field_value=m_pan.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        extracted["issuing_authority"] = ExtractedField(
            field_name="issuing_authority",
            field_value="Income Tax Department, Govt. of India",
            confidence=0.95,
            extraction_method=ExtractionMethod.OCR,
        )

    elif document_type == DocumentType.VOTER_ID:
        for text, conf in raw_lines:
            if "voter_id_number" not in extracted:
                m_vid = PATTERNS["voter_id_num"].search(text)
                if m_vid:
                    extracted["voter_id_number"] = ExtractedField(
                        field_name="voter_id_number",
                        field_value=m_vid.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        extracted["issuing_authority"] = ExtractedField(
            field_name="issuing_authority",
            field_value="Election Commission of India",
            confidence=0.95,
            extraction_method=ExtractionMethod.OCR,
        )

    # -----------------------------------------------------------------------
    # 2. Contextual Date Extraction (DOB vs Issue vs Expiry / Travel Date)
    # -----------------------------------------------------------------------
    found_labeled_dates: dict[str, tuple[str, float]] = {}
    unlabeled_dates: list[tuple[str, float]] = []
    used_next_line_indices: set[int] = set()

    for i, (text, conf) in enumerate(raw_lines):
        if i in used_next_line_indices:
            continue
        text_upper = text.upper()
        date_matches = list(PATTERNS["date"].finditer(text))
        
        dates_on_line = [m.group(0) for m in date_matches]
        next_line_date = None
        if i + 1 < len(raw_lines) and (i + 1) not in used_next_line_indices:
            next_m = PATTERNS["date"].search(raw_lines[i + 1][0])
            if next_m:
                next_line_date = (next_m.group(0), raw_lines[i + 1][1])

        target_date = (dates_on_line[0], conf) if dates_on_line else next_line_date

        if target_date:
            label_matched = False
            if any(k in text_upper for k in ["EXPIRY", "समाप्ति", "VALID UNTIL", "EXPIRATION", "VALID TILL", "VALID UPTO"]):
                found_labeled_dates["date_of_expiry"] = target_date
                label_matched = True
            elif any(k in text_upper for k in ["BIRTH", "जन्म", "DOB", "NAISSANCE"]):
                found_labeled_dates["date_of_birth"] = target_date
                label_matched = True
            elif any(k in text_upper for k in ["TRAVEL DATE", "JOURNEY DATE", "SAILING DATE", "DEPARTURE DATE"]):
                found_labeled_dates["travel_date"] = target_date
                label_matched = True
            elif any(k in text_upper for k in ["ENTRY VALIDITY", "VALIDITY"]):
                found_labeled_dates["entry_validity"] = target_date
                label_matched = True
            elif any(k in text_upper for k in ["ISSUE", "जारी"]):
                found_labeled_dates["date_of_issue"] = target_date
                label_matched = True
            elif dates_on_line:
                unlabeled_dates.append((dates_on_line[0], conf))

            if label_matched and not dates_on_line and next_line_date:
                used_next_line_indices.add(i + 1)

    # Apply labeled dates
    for field_key in ["date_of_birth", "date_of_expiry", "travel_date", "entry_validity", "valid_until"]:
        target_k = "date_of_expiry" if field_key == "valid_until" and "date_of_expiry" in found_labeled_dates else field_key
        if target_k in found_labeled_dates:
            d, c = found_labeled_dates[target_k]
            extracted[field_key] = ExtractedField(
                field_name=field_key,
                field_value=d,
                confidence=c,
                extraction_method=ExtractionMethod.OCR,
            )

    # Fallback to date sorting if labels weren't matched
    labeled_values = {v[0] for v in found_labeled_dates.values()}
    unlabeled_dates = [ud for ud in unlabeled_dates if ud[0] not in labeled_values]

    if ("date_of_birth" not in extracted or "date_of_expiry" not in extracted) and unlabeled_dates:
        parsed_dates = []
        for d_str, c in unlabeled_dates:
            parts = re.split(r"[/-]", d_str)
            if len(parts) == 3:
                try:
                    yr = int(parts[2]) if len(parts[2]) == 4 else int(parts[0])
                    parsed_dates.append((yr, d_str, c))
                except ValueError:
                    pass
        
        parsed_dates.sort(key=lambda x: x[0])
        if parsed_dates:
            if "date_of_birth" not in extracted and document_type != DocumentType.FERRY_TICKET:
                extracted["date_of_birth"] = ExtractedField(
                    field_name="date_of_birth",
                    field_value=parsed_dates[0][1],
                    confidence=parsed_dates[0][2],
                    extraction_method=ExtractionMethod.OCR,
                )
            if "date_of_expiry" not in extracted and len(parsed_dates) > 1 and document_type in [DocumentType.PASSPORT, DocumentType.DRIVING_LICENSE, DocumentType.PERMIT]:
                extracted["date_of_expiry"] = ExtractedField(
                    field_name="date_of_expiry",
                    field_value=parsed_dates[-1][1],
                    confidence=parsed_dates[-1][2],
                    extraction_method=ExtractionMethod.OCR,
                )
            if "travel_date" not in extracted and document_type == DocumentType.FERRY_TICKET:
                extracted["travel_date"] = ExtractedField(
                    field_name="travel_date",
                    field_value=parsed_dates[0][1],
                    confidence=parsed_dates[0][2],
                    extraction_method=ExtractionMethod.OCR,
                )

    # -----------------------------------------------------------------------
    # 3. Look for Gender/Sex
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # 4. Search for Name / Passenger Name / Holder Name (Phase 9: multilingual)
    # -----------------------------------------------------------------------
    surname_val = ""
    given_val = ""
    surname_native = ""
    given_native = ""

    # Build flat lists for anchor-based lookup using _FIELD_ANCHORS
    surname_anchors_upper = [a.upper() for a in _FIELD_ANCHORS.get("surname", [])]
    givenname_anchors_upper = [a.upper() for a in _FIELD_ANCHORS.get("given_names", [])]
    label_keywords = {
        "NAME", "SURNAME", "SURNAMES", "GIVEN", "GIVEN NAMES", "GIVEN NAME",
        "FIRST NAME", "FORENAMES", "LAST NAME", "NACHNAME", "FAMILIENNAME",
        "VORNAMEN", "VORNAME", "NOM", "NOMS", "PRENOMS", "PRÉNOMS",
        "STAATSANGEHÖRIGKEIT", "STAATSANGEHORIGKEIT", "NATIONALITY",
        "GEBURTSDATUM", "DATE OF BIRTH", "PASS-NR", "PASSPORT NO",
        "उपनाम", "दिया गया नाम", "नाम", "पदবি", "প্রদত্ত নাম",
    }

    for i, (text, conf) in enumerate(raw_lines):
        text_upper = text.upper()

        # Match surname anchors (multilingual)
        surname_matched = any(anchor in text_upper for anchor in surname_anchors_upper)
        if surname_matched:
            clean = re.sub(
                r"(SURNAME|LAST NAME|NACHNAME|FAMILIENNAME|NOM DE FAMILLE|\bNOM\b|\u0909\u092a\u0928\u093e\u092e|\u09aa\u09a6\u09ac\u09bf|\u0925\u0930|/|:|\bNAME\b)",
                "", text, flags=re.IGNORECASE
            ).strip()
            if clean and len(clean) > 1 and clean.upper() not in label_keywords and not re.search(r"^[A-Z0-9<]{9}", clean):
                surname_native = clean
                surname_val = normalize_icao_transliteration(clean)
            elif i + 1 < len(raw_lines):
                next_t = raw_lines[i + 1][0].strip()
                if next_t and next_t.upper() not in label_keywords and not any(k in next_t.upper() for k in ["NAME", "GIVEN", "BIRTH", "DATE"]):
                    surname_native = next_t
                    surname_val = normalize_icao_transliteration(next_t)

        # Match given name anchors (multilingual)
        givenname_matched = any(anchor in text_upper for anchor in givenname_anchors_upper)
        if givenname_matched:
            clean = re.sub(
                r"(GIVEN NAME\(S\)|GIVEN NAMES|GIVEN NAME|FIRST NAME|FORENAMES|VORNAMEN|VORNAME|PRÉNOMS|PRENOMS|\u0926\u093f\u092f\u093e \u0917\u092f\u093e \u0928\u093e\u092e|\u0928\u093e\u092e|\u09aa\u09cd\u09b0\u09a6\u09a4\u09cd\u09a4 \u09a8\u09be\u09ae|/|:|\(S\)|\bNAMES\b|\bNAME\b)",
                "", text, flags=re.IGNORECASE
            ).strip()
            if clean and len(clean) > 1 and clean.upper() not in label_keywords:
                given_native = clean
                given_val = normalize_icao_transliteration(clean)
            elif i + 1 < len(raw_lines):
                next_t = raw_lines[i + 1][0].strip()
                if next_t and next_t.upper() not in label_keywords and not any(k in next_t.upper() for k in ["BIRTH", "DATE", "SEX", "GENDER", "PLACE"]):
                    given_native = next_t
                    given_val = normalize_icao_transliteration(next_t)

        is_relational_name = any(r in text_upper for r in [
            "FATHER", "MOTHER", "SPOUSE", "HUSBAND", "GUARDIAN",
            "W/O", "D/O", "S/O", "C/O",
            "\u092a\u093f\u0924\u093e", "\u092a\u0924\u093f",  # Hindi: पिता, पति
        ])
        if any(k in text_upper for k in [
            "ELECTOR'S NAME", "ELECTORS NAME", "ELECTOR NAME",
            "\u092e\u0924\u0926\u093e\u0924\u093e \u0915\u093e \u0928\u093e\u092e",  # मतदाता का नाम
            "PASSENGER NAME", "HOLDER NAME", "NAME:", "NAME;", "NAME "
        ]) and not is_relational_name and document_type != DocumentType.PASSPORT:
            clean_name = re.sub(
                r"(ELECTOR'S NAME|ELECTORS NAME|ELECTOR NAME|\u092e\u0924\u0926\u093e\u0924\u093e \u0915\u093e \u0928\u093e\u092e|PASSENGER NAME|HOLDER NAME|NAME[:;\s]+|\bNAME\b)",
                "", text, flags=re.IGNORECASE
            ).strip()
            if clean_name and len(clean_name) > 2:
                given_native = clean_name
                given_val = normalize_icao_transliteration(clean_name)
            elif i + 1 < len(raw_lines):
                given_native = raw_lines[i + 1][0].strip()
                given_val = normalize_icao_transliteration(given_native)

        if is_relational_name and "father_name" not in extracted:
            clean_rel = re.sub(
                r"(FATHER'S NAME|FATHERS NAME|FATHER NAME|HUSBAND'S NAME|HUSBANDS NAME|SPOUSE NAME|\u092a\u093f\u0924\u093e \u0915\u093e \u0928\u093e\u092e|\u092a\u0924\u093f \u0915\u093e \u0928\u093e\u092e|W/O|D/O|S/O|C/O|:)",
                "", text, flags=re.IGNORECASE
            ).strip()
            native_rel = clean_rel
            icao_rel = normalize_icao_transliteration(clean_rel)
            if icao_rel and len(icao_rel) > 2:
                extracted["father_name"] = ExtractedField(
                    field_name="father_name",
                    field_value=icao_rel,
                    native_value=native_rel if native_rel != icao_rel else None,
                    transliterated_value=icao_rel if native_rel != icao_rel else None,
                    confidence=0.88,
                    extraction_method=ExtractionMethod.OCR,
                )
            elif i + 1 < len(raw_lines):
                next_rel = raw_lines[i + 1][0].strip()
                if next_rel and not any(k in next_rel.upper() for k in ["BIRTH", "DATE", "SEX", "GENDER", "EPIC"]):
                    icao_next = normalize_icao_transliteration(next_rel)
                    extracted["father_name"] = ExtractedField(
                        field_name="father_name",
                        field_value=icao_next,
                        native_value=next_rel if next_rel != icao_next else None,
                        transliterated_value=icao_next if next_rel != icao_next else None,
                        confidence=0.85,
                        extraction_method=ExtractionMethod.OCR,
                    )

    if surname_val or given_val:
        full_native = f"{given_native} {surname_native}".strip() or surname_native or given_native
        full_icao = f"{given_val} {surname_val}".strip() or surname_val or given_val
        # Detect language of the name
        name_lang: str | None = None
        name_script = detect_script(full_native)
        if name_script not in ("latin", "unknown"):
            langs = detect_languages_in_text(full_native)
            name_lang = langs[0] if langs else None
        extracted["name"] = ExtractedField(
            field_name="name",
            field_value=full_icao,
            native_value=full_native if full_native != full_icao else None,
            transliterated_value=full_icao if full_native != full_icao else None,
            language=name_lang,
            confidence=0.90,
            extraction_method=ExtractionMethod.OCR,
        )

    # -----------------------------------------------------------------------
    # 5. Look for Nationality (Phase 9: multilingual expansion)
    # -----------------------------------------------------------------------
    nat_anchors = _FIELD_ANCHORS.get("nationality", [])
    nat_anchors_upper = [a.upper() for a in nat_anchors]
    known_nationality_keywords = [
        # English
        "INDIAN", "IND", "BHARAT", "BHARATIYA",
        "NEPALI", "NEPALESE",
        "BHUTANESE",
        "BANGLADESHI",
        "SRI LANKAN", "SRILANKA",
        "MYANMAR", "BURMESE",
        # German
        "DEUTSCH", "DEUTSCHLAND",
        # French
        "FRANCAIS", "FRANÇAIS",
        # Gulf
        "EMIRATI", "SAUDI",
        # Common
        "PAKISTANI", "CHINESE", "RUSSIAN", "BRITISH", "AMERICAN",
    ]
    for text, conf in raw_lines:
        text_upper = text.upper()
        if "nationality" not in extracted:
            if any(kw in text_upper for kw in known_nationality_keywords):
                # Find the matched keyword and normalize to country code
                found_kw = next(
                    (kw for kw in known_nationality_keywords if kw in text_upper), None
                )
                nat_val = normalize_country_code(found_kw) if found_kw else "IND"
                native_nat = found_kw or text.strip()
                extracted["nationality"] = ExtractedField(
                    field_name="nationality",
                    field_value=nat_val,
                    native_value=native_nat if native_nat != nat_val else None,
                    confidence=conf,
                    extraction_method=ExtractionMethod.OCR,
                )
                break

    return list(extracted.values())


# ---------------------------------------------------------------------------
# Phase 9: Multilingual passport metadata detection
# ---------------------------------------------------------------------------
def detect_multilingual_ocr_metadata(
    raw_lines: list[tuple[str, float]],
) -> tuple[list[str], str | None, bool]:
    """
    Analyse all OCR text lines and return multilingual metadata for ExtractionResponse.

    Returns:
        detected_languages : list of ISO 639-1 codes (e.g. ['hi', 'en'] or ['de', 'en'])
        primary_script     : dominant non-Latin script name (e.g. 'devanagari', 'arabic')
        is_multilingual    : True when non-Latin script characters are present alongside Latin
    """
    full_text = " ".join(t for t, _ in raw_lines)
    script = detect_script(full_text)

    has_latin = bool(re.search(r"[A-Za-z]", full_text))
    is_multilingual = (script not in ("latin", "unknown")) and has_latin

    langs = detect_languages_in_text(full_text)
    if has_latin and "en" not in langs:
        langs = langs + ["en"]

    primary_script: str | None = None if script in ("latin", "unknown") else script

    return (langs, primary_script, is_multilingual)
