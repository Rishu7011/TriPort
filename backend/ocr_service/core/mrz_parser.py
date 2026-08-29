"""
MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.

Works seamlessly with OCR text output and PassportEye.
"""

import re
from io import BytesIO
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import MRZResult

logger = get_logger("ocr_service.mrz_parser")

# ---------------------------------------------------------------------------
# ICAO 9303 checksum weights — the repeating [7, 3, 1] pattern
# ---------------------------------------------------------------------------
_WEIGHTS = [7, 3, 1]

_CHAR_VALUES: dict[str, int] = {
    "<": 0,
    **{str(d): d for d in range(10)},
    **{chr(ord("A") + i): 10 + i for i in range(26)},
}


def _compute_check_digit(field: str) -> int:
    """Compute ICAO 9303 check digit using repeating weights [7, 3, 1]."""
    total = 0
    for i, char in enumerate(field.upper()):
        value = _CHAR_VALUES.get(char, 0)
        total += value * _WEIGHTS[i % 3]
    return total % 10


def _validate_check_digit(field: str, check_char: str) -> bool:
    """Return True if the computed check digit matches the expected one."""
    try:
        expected = int(check_char)
    except (ValueError, TypeError):
        return False
    return _compute_check_digit(field) == expected


# TD3 (Standard Passport) Regex patterns for Line 1 and Line 2
TD3_LINE1_REGEX = re.compile(r"P[A-Z<][A-Z]{3}([A-Z0-9<]{39})")
TD3_LINE2_REGEX = re.compile(r"([A-Z0-9<]{9})([0-9])([A-Z]{3})([0-9]{6})([0-9])([MFX<])([0-9]{6})([0-9])([A-Z0-9<]{14})([0-9<])([0-9<])")


def _mrz_date_to_dmy(yymmdd: str, is_expiry: bool = False) -> str:
    """Convert YYMMDD string to DD/MM/YYYY."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return yymmdd
    yy = int(yymmdd[0:2])
    mm = yymmdd[2:4]
    dd = yymmdd[4:6]
    if is_expiry:
        year = 2000 + yy if yy < 75 else 1900 + yy
    else:
        year = 2000 + yy if yy <= 26 else 1900 + yy
    return f"{dd}/{mm}/{year}"


def parse_mrz_from_text_lines(text_lines: list[str]) -> MRZResult:
    """
    Directly parse MRZ lines from extracted OCR text lines.
    Detects TD3 Line 1 (P<...) and Line 2 (Passport number + DOB + Expiry).
    """
    cleaned_lines = [
        line.replace(" ", "").upper().replace("«", "<").replace("‹", "<")
        for line in text_lines
        if line.strip()
    ]

    line1 = None
    line2 = None

    for line in cleaned_lines:
        # Line 1: Starts with P followed by < or 3-letter country code, or contains << and P
        if (line.startswith("P<") or (line.startswith("P") and "<<" in line) or ("<<" in line and "IND" in line)) and not line1:
            line1 = line
        # Line 2: Contains 6-digit DOB + check digit + M/F/< + 6-digit Expiry
        elif re.search(r"[0-9]{6}[0-9<][MFX<][0-9]{6}", line) or re.search(r"[A-Z0-9<]{8,9}[0-9<][A-Z]{3}[0-9]{6}", line):
            line2 = line

    # Fallback search if not matched by regex
    if not line1 or not line2:
        for line in cleaned_lines:
            if not line1 and len(line) >= 28 and ("<<" in line or line.startswith("P")):
                line1 = line
            elif not line2 and len(line) >= 28 and sum(c.isdigit() for c in line) >= 12:
                line2 = line

    if not line1 or not line2:
        return MRZResult(mrz_present=False)

    # Pad lines to 44 characters with '<' if slightly truncated
    line1 = line1.ljust(44, "<")[:44]
    line2 = line2.ljust(44, "<")[:44]

    logger.info("Found MRZ lines in text", line1=line1, line2=line2)

    # Extract names from Line 1 (e.g. P<INDNEGI<<SAHIL<<<<<<<<<<<<...)
    # Country code is at [2:5]
    name_section = line1[5:].split("<<")
    surname = name_section[0].replace("<", " ").strip() if len(name_section) > 0 else ""
    given_names = name_section[1].replace("<", " ").strip() if len(name_section) > 1 else ""
    full_name = f"{given_names} {surname}".strip() or surname

    # Parse Line 2 positions:
    # [0:9]   Document Number (e.g. Z6720715<)
    # [9]     Check digit for doc number (e.g. 3)
    # [10:13] Nationality (e.g. IND)
    # [13:19] Date of Birth (YYMMDD)
    # [19]    Check digit for DOB
    # [20]    Sex (M/F/<)
    # [21:27] Expiry Date (YYMMDD)
    # [27]    Check digit for Expiry
    # Checksum verification & OCR Character Confusion Auto-Correction
    doc_raw_9 = line2[0:9]
    doc_check = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob_raw = line2[13:19]
    dob_check = line2[19]
    sex = line2[20] if line2[20] in ["M", "F"] else "M"
    expiry_raw = line2[21:27]
    expiry_check = line2[27]

    # Auto-correct common OCR letter/number confusion in doc_number using checksum verification
    # e.g., '2' at position 0 misread for 'Z', '0' for 'O', '8' for 'B', '5' for 'S'
    CHAR_CORRECTIONS = {"2": "Z", "0": "O", "1": "I", "8": "B", "5": "S", "4": "A"}
    if not _validate_check_digit(doc_raw_9, doc_check):
        # Try correcting first character to letter
        first_char = doc_raw_9[0]
        if first_char in CHAR_CORRECTIONS:
            corrected_9 = CHAR_CORRECTIONS[first_char] + doc_raw_9[1:]
            if _validate_check_digit(corrected_9, doc_check):
                logger.info("OCR error corrected in doc_number using ICAO check digit", original=doc_raw_9, corrected=corrected_9)
                doc_raw_9 = corrected_9

    # Auto-correct common OCR digit confusion in dates
    DIGIT_CORRECTIONS = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "A": "4"}
    if not _validate_check_digit(dob_raw, dob_check):
        corrected_dob = "".join(DIGIT_CORRECTIONS.get(c, c) for c in dob_raw)
        if _validate_check_digit(corrected_dob, dob_check):
            dob_raw = corrected_dob

    if not _validate_check_digit(expiry_raw, expiry_check):
        corrected_exp = "".join(DIGIT_CORRECTIONS.get(c, c) for c in expiry_raw)
        if _validate_check_digit(corrected_exp, expiry_check):
            expiry_raw = corrected_exp

    doc_num = doc_raw_9.replace("<", "")

    checksum_failures = []
    if not _validate_check_digit(doc_raw_9, doc_check):
        checksum_failures.append("doc_number")
    if not _validate_check_digit(dob_raw, dob_check):
        checksum_failures.append("date_of_birth")
    if not _validate_check_digit(expiry_raw, expiry_check):
        checksum_failures.append("expiry_date")

    checksum_valid = len(checksum_failures) == 0

    mrz_fields = {
        "doc_number": doc_num,
        "passport_number": doc_num,
        "surname": surname,
        "given_names": given_names,
        "name": full_name,
        "nationality": nationality,
        "date_of_birth": _mrz_date_to_dmy(dob_raw, is_expiry=False),
        "raw_dob": dob_raw,
        "sex": sex,
        "gender": sex,
        "date_of_expiry": _mrz_date_to_dmy(expiry_raw, is_expiry=True),
        "raw_expiry": expiry_raw,
    }

    return MRZResult(
        mrz_present=True,
        checksum_valid=checksum_valid,
        checksum_failures=checksum_failures,
        mrz_fields=mrz_fields,
    )


def parse_mrz(image_bytes: bytes, ocr_text_lines: list[str] | None = None) -> MRZResult:
    """
    Parse MRZ from OCR text lines first, falling back to PassportEye if available.
    """
    if ocr_text_lines:
        res = parse_mrz_from_text_lines(ocr_text_lines)
        if res.mrz_present:
            return res

    # Try PassportEye if installed and available
    try:
        import passporteye
        mrz = passporteye.read_mrz(BytesIO(image_bytes), save_roi=False)
        if mrz:
            raw = mrz.to_dict()
            if raw and raw.get("raw_text"):
                lines = raw.get("raw_text", "").split("\n")
                return parse_mrz_from_text_lines(lines)
    except Exception as exc:
        logger.debug("PassportEye fallback attempt skipped", error=str(exc))

    return MRZResult(mrz_present=False)
