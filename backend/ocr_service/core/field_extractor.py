"""
Field Extractor — Robust Multi-Modal Document OCR using EasyOCR.

Extracts text boxes, confidence scores, and maps structured fields for:
  1. Passport
  2. Visa
  3. National ID (Aadhaar, Citizen Card, Voter ID)
  4. Driving License
  5. Permit (Land Border Crossings & Transit Passes)
  6. Ferry Ticket (Sea Passenger Crossings)
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

# Singleton OCR engine state
_ocr_engine_type: str | None = None  # "paddleocr", "easyocr", or None
_ocr_reader: Any = None


def get_ocr_reader() -> tuple[str, Any]:
    """
    Singleton lazy-loader for local OCR engines.
    Tries PyTesseract first (lightest, 15MB RAM, rock solid C++ binary), then PaddleOCR, then EasyOCR.
    """
    global _ocr_reader, _ocr_engine_type
    if _ocr_reader is None:
        # 1. Try PyTesseract first (lightweight, stable, zero SIGSEGV)
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _ocr_reader = pytesseract
            _ocr_engine_type = "tesseract"
            logger.info("Tesseract OCR engine initialized successfully")
            return _ocr_engine_type, _ocr_reader
        except Exception as e:
            logger.debug("PyTesseract engine check skipped", error=str(e))

        # 2. Try PaddleOCR second
        try:
            import paddle
            if hasattr(paddle, "base") and hasattr(paddle.base, "libpaddle"):
                if not hasattr(paddle.base.libpaddle.AnalysisConfig, "set_optimization_level"):
                    setattr(paddle.base.libpaddle.AnalysisConfig, "set_optimization_level", lambda self, *args, **kwargs: None)
        except Exception as patch_exc:
            logger.debug("Paddle AnalysisConfig patch check skipped", error=str(patch_exc))

        try:
            from paddleocr import PaddleOCR
            _ocr_reader = PaddleOCR(use_angle_cls=False, lang="en")
            _ocr_engine_type = "paddleocr"
            logger.info("PaddleOCR engine initialized successfully")
            return _ocr_engine_type, _ocr_reader
        except ImportError:
            logger.debug("PaddleOCR package not installed; checking EasyOCR")
        except Exception as e:
            logger.warning("Failed to initialize PaddleOCR engine", error=str(e))

        # 3. Try EasyOCR third
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(["en"], gpu=False)
            _ocr_engine_type = "easyocr"
            logger.info("EasyOCR engine initialized successfully")
            return _ocr_engine_type, _ocr_reader
        except ImportError:
            logger.debug("EasyOCR package not installed; running in Cloud Mode")
            raise RuntimeError("No local OCR engine installed (PyTesseract, PaddleOCR or EasyOCR)")
        except Exception as e:
            logger.warning("Failed to initialize EasyOCR engine", error=str(e))
            raise RuntimeError(f"OCR engine initialization error: {e}") from e

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
    "date": re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[\s/-]?[A-Za-z]{3}[\s/-]?\d{2,4})\b"),
    "passport_num": re.compile(r"\b[A-Z][0-9]{7,8}\b"),
    "gender": re.compile(r"\b(SEX|GENDER)?\s*([MFX])\b", re.IGNORECASE),
    "nationality": re.compile(r"\b(NATIONALITY|CODE|COUNTRY)?\s*([A-Z]{3})\b", re.IGNORECASE),
    "aadhaar": re.compile(r"\b\d{4}\s+\d{4}\s+\d{4}\b"),
    "dl_num": re.compile(r"\b(DL[- /]?[0-9A-Z/-]{8,18}|[A-Z]{2}[0-9]{2}[ -/:]?[0-9]{4,11}(?:[ -/:][0-9]{4,7})?)\b", re.IGNORECASE),
    "permit_num": re.compile(r"\b(PER|BP|LPAI|RAP)[- /]?[0-9A-Z]{6,12}\b", re.IGNORECASE),
    "ticket_num": re.compile(r"\b(TKT|FERRY|BRD|SEA)[- /]?[0-9A-Z]{6,12}\b", re.IGNORECASE),
    "pan_num": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE),
    "voter_id_num": re.compile(r"\b[A-Z]{3}[-/]?[0-9]{7}\b", re.IGNORECASE),
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


def _bytes_to_numpy_image(image_bytes: bytes, max_dim: int = 1600) -> np.ndarray:
    """Convert raw byte stream (or PDF) to RGB NumPy array with smart downscaling for fast inference."""
    valid_bytes = ensure_image_bytes(image_bytes)
    image = Image.open(io.BytesIO(valid_bytes)).convert("RGB")
    
    # Scale down oversized phone camera images to 1600px max dimension for 2x-3x faster CRAFT/Paddle OCR
    w, h = image.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_w, new_h = int(w * scale), int(h * scale)
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        
    return np.array(image)


def extract_raw_ocr_lines(image_bytes: bytes) -> list[tuple[str, float]]:
    """Extract raw text lines and confidences using PyTesseract, PaddleOCR or EasyOCR."""
    valid_bytes = ensure_image_bytes(image_bytes)
    img_array = _bytes_to_numpy_image(valid_bytes)
    engine_type, reader = get_ocr_reader()

    lines_with_conf: list[tuple[str, float]] = []

    if engine_type == "tesseract":
        import pytesseract
        pil_img = Image.fromarray(img_array)
        data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
        lines_dict: dict[tuple[int, int], list[tuple[str, float]]] = {}
        n_boxes = len(data.get("text", []))
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            conf_val = float(data["conf"][i])
            if text and conf_val > 0:
                line_num = data["line_num"][i]
                block_num = data["block_num"][i]
                key = (block_num, line_num)
                if key not in lines_dict:
                    lines_dict[key] = []
                lines_dict[key].append((text, conf_val / 100.0))
        for key in sorted(lines_dict.keys()):
            line_texts = [t for t, _ in lines_dict[key]]
            confs = [c for _, c in lines_dict[key]]
            avg_conf = sum(confs) / len(confs)
            lines_with_conf.append((" ".join(line_texts), round(avg_conf, 2)))
    elif engine_type == "paddleocr":
        raw_results = reader.ocr(img_array, cls=True)
        if raw_results and raw_results[0]:
            for line in raw_results[0]:
                if line and len(line) >= 2 and line[1]:
                    text = str(line[1][0]).strip()
                    prob = float(line[1][1])
                    if text:
                        lines_with_conf.append((text, prob))
    elif engine_type == "easyocr":
        import torch
        with torch.inference_mode():
            raw_results = reader.readtext(img_array, batch_size=4, paragraph=False)
        for item in raw_results:
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
        for text, conf in raw_lines:
            if "license_number" not in extracted:
                m_dl = PATTERNS["dl_num"].search(text)
                if m_dl:
                    extracted["license_number"] = ExtractedField(
                        field_name="license_number",
                        field_value=m_dl.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        # Vehicle class
        for text, conf in raw_lines:
            text_u = text.upper()
            if "vehicle_class" not in extracted:
                for vclass in ["LMV", "MCWG", "HMV", "TRANS", "NON-TRANS", "3W-NT"]:
                    if vclass in text_u:
                        extracted["vehicle_class"] = ExtractedField(
                            field_name="vehicle_class",
                            field_value=vclass,
                            confidence=0.90,
                            extraction_method=ExtractionMethod.OCR,
                        )
                        break

    elif document_type == DocumentType.PERMIT:
        for text, conf in raw_lines:
            if "permit_number" not in extracted:
                m_per = PATTERNS["permit_num"].search(text)
                if m_per:
                    extracted["permit_number"] = ExtractedField(
                        field_name="permit_number",
                        field_value=m_per.group(0),
                        confidence=conf,
                        extraction_method=ExtractionMethod.OCR,
                    )
        # Permit Type
        for text, conf in raw_lines:
            text_u = text.upper()
            if "permit_type" not in extracted:
                for ptype in ["BORDER PASS", "ENTRY PERMIT", "RESTRICTED AREA PERMIT", "LAND TRANSIT PASS"]:
                    if ptype in text_u:
                        extracted["permit_type"] = ExtractedField(
                            field_name="permit_type",
                            field_value=ptype,
                            confidence=0.90,
                            extraction_method=ExtractionMethod.OCR,
                        )
                        break

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
    # 4. Search for Name / Passenger Name / Holder Name
    # -----------------------------------------------------------------------
    surname_val = ""
    given_val = ""
    for i, (text, conf) in enumerate(raw_lines):
        text_upper = text.upper()
        if "SURNAME" in text_upper or "उपनाम" in text_upper:
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

        is_relational_name = any(r in text_upper for r in ["FATHER", "MOTHER", "SPOUSE", "HUSBAND", "GUARDIAN", "W/O", "D/O", "S/O", "C/O"])
        if any(k in text_upper for k in ["PASSENGER NAME", "HOLDER NAME", "NAME:"]) and not is_relational_name:
            clean_name = re.sub(r"(PASSENGER NAME|HOLDER NAME|NAME:|\bNAME\b|:)", "", text, flags=re.IGNORECASE).strip()
            if clean_name and len(clean_name) > 2:
                given_val = clean_name
            elif i + 1 < len(raw_lines):
                given_val = raw_lines[i + 1][0].strip()

    if surname_val or given_val:
        full = f"{given_val} {surname_val}".strip() or surname_val or given_val
        extracted["name"] = ExtractedField(
            field_name="name",
            field_value=full,
            confidence=0.90,
            extraction_method=ExtractionMethod.OCR,
        )

    # -----------------------------------------------------------------------
    # 5. Look for Nationality
    # -----------------------------------------------------------------------
    for text, conf in raw_lines:
        text_upper = text.upper()
        if any(k in text_upper for k in ["INDIAN", "IND ", "BHARATIYA", "NEPALI", "BHUTANESE", "BANGLADESHI", "SRI LANKAN", "MYANMAR"]):
            if "nationality" not in extracted:
                nat_val = "INDIAN"
                for nat_check in ["NEPALI", "BHUTANESE", "BANGLADESHI", "SRI LANKAN", "MYANMAR"]:
                    if nat_check in text_upper:
                        nat_val = nat_check
                        break
                extracted["nationality"] = ExtractedField(
                    field_name="nationality",
                    field_value=nat_val,
                    confidence=conf,
                    extraction_method=ExtractionMethod.OCR,
                )
                break

    return list(extracted.values())
