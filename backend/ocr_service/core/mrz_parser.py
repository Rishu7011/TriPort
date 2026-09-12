"""
MRZ Parser — Robust Machine Readable Zone Detection and ICAO 9303 Checksum Validation.

Supports:
  1. TD3 (Passports: 2 lines x 44 chars)
  2. TD2 / MRV-B (Visas & ID cards: 2 lines x 36 chars)
  3. MRV-A (Visas: 2 lines x 44 chars)
  4. TD1 (National ID & Residence Cards: 3 lines x 30 chars)

Includes OCR character confusion auto-correction using ICAO check digits.
"""

import re
from io import BytesIO
from typing import Any
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


def _clean_mrz_line(raw: str) -> str:
    """Standardize line characters and replace typical OCR artifacts."""
    return (
        raw.replace(" ", "")
        .upper()
        .replace("«", "<")
        .replace("‹", "<")
        .replace("“", "<")
        .replace("”", "<")
    )


def parse_td3(line1: str, line2: str) -> MRZResult:
    """Parse TD3 (2 lines x 44 characters, Standard Passport / MRV-A)."""
    line1 = line1.ljust(44, "<")[:44]
    line2 = line2.ljust(44, "<")[:44]

    # Name section from Line 1 (P<INDNAME<<...)
    name_section = line1[5:].split("<<")
    surname = name_section[0].replace("<", " ").strip() if len(name_section) > 0 else ""
    given_names = name_section[1].replace("<", " ").strip() if len(name_section) > 1 else ""
    full_name = f"{given_names} {surname}".strip() or surname

    doc_raw_9 = line2[0:9]
    doc_check = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob_raw = line2[13:19]
    dob_check = line2[19]
    sex = line2[20] if line2[20] in ["M", "F", "X"] else "M"
    expiry_raw = line2[21:27]
    expiry_check = line2[27]

    # Checksum auto-correction
    CHAR_CORRECTIONS = {"2": "Z", "0": "O", "1": "I", "8": "B", "5": "S", "4": "A", "6": "G"}
    DIGIT_CORRECTIONS = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "A": "4", "Q": "0", "D": "0"}

    if not _validate_check_digit(doc_raw_9, doc_check):
        first_char = CHAR_CORRECTIONS.get(doc_raw_9[0], doc_raw_9[0])
        cand1 = first_char + doc_raw_9[1:]
        if _validate_check_digit(cand1, doc_check):
            doc_raw_9 = cand1
        else:
            # Try correcting numeric digits in remainder with 1-letter prefix (e.g. P1234567)
            cand2 = doc_raw_9[:1] + "".join(DIGIT_CORRECTIONS.get(c, c) for c in doc_raw_9[1:])
            if _validate_check_digit(cand2, doc_check):
                doc_raw_9 = cand2
            else:
                # Try correcting numeric digits in remainder with 2-letter prefix (e.g. AA0001618)
                cand3 = doc_raw_9[:2] + "".join(DIGIT_CORRECTIONS.get(c, c) for c in doc_raw_9[2:])
                if _validate_check_digit(cand3, doc_check):
                    doc_raw_9 = cand3
                else:
                    cand4 = "".join(DIGIT_CORRECTIONS.get(c, c) for c in doc_raw_9)
                    if _validate_check_digit(cand4, doc_check):
                        doc_raw_9 = cand4

    # Nationality recovery: if OCR confused letters for digits in line 2 (e.g. 860 for BGD)
    issuing_country = line1[2:5].replace("<", "")
    if any(c.isdigit() for c in nationality):
        if len(issuing_country) == 3 and issuing_country.isalpha():
            nationality = issuing_country
        else:
            nationality = "".join(CHAR_CORRECTIONS.get(c, c) for c in nationality)

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

    mrz_fields = {
        "mrz_format": "TD3",
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
        checksum_valid=(len(checksum_failures) == 0),
        checksum_failures=checksum_failures,
        mrz_fields=mrz_fields,
    )


def parse_td2(line1: str, line2: str) -> MRZResult:
    """Parse TD2 / MRV-B (2 lines x 36 characters, Visas and ID cards)."""
    line1 = line1.ljust(36, "<")[:36]
    line2 = line2.ljust(36, "<")[:36]

    # Name section from Line 1 (e.g. V<INDNEGI<<SAHIL<<<<<<<<<<)
    name_section = line1[5:].split("<<")
    surname = name_section[0].replace("<", " ").strip() if len(name_section) > 0 else ""
    given_names = name_section[1].replace("<", " ").strip() if len(name_section) > 1 else ""
    full_name = f"{given_names} {surname}".strip() or surname

    doc_raw_9 = line2[0:9]
    doc_check = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob_raw = line2[13:19]
    dob_check = line2[19]
    sex = line2[20] if line2[20] in ["M", "F", "X"] else "M"
    expiry_raw = line2[21:27]
    expiry_check = line2[27]

    checksum_failures = []
    if not _validate_check_digit(doc_raw_9, doc_check):
        checksum_failures.append("doc_number")
    if not _validate_check_digit(dob_raw, dob_check):
        checksum_failures.append("date_of_birth")
    if not _validate_check_digit(expiry_raw, expiry_check):
        checksum_failures.append("expiry_date")

    doc_num = doc_raw_9.replace("<", "")
    mrz_fields = {
        "mrz_format": "TD2",
        "doc_number": doc_num,
        "visa_number": doc_num,
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
        checksum_valid=(len(checksum_failures) == 0),
        checksum_failures=checksum_failures,
        mrz_fields=mrz_fields,
    )


def parse_td1(line1: str, line2: str, line3: str) -> MRZResult:
    """Parse TD1 (3 lines x 30 characters, National ID cards)."""
    line1 = line1.ljust(30, "<")[:30]
    line2 = line2.ljust(30, "<")[:30]
    line3 = line3.ljust(30, "<")[:30]

    # Line 1: [0:2] Doc Type, [2:5] Country, [5:14] Doc Number, [14] Doc Number Check
    country = line1[2:5].replace("<", "")
    doc_raw_9 = line1[5:14]
    doc_check = line1[14]

    # Line 2: [0:6] DOB, [6] DOB Check, [7] Sex, [8:14] Expiry, [14] Expiry Check, [15:18] Nationality
    dob_raw = line2[0:6]
    dob_check = line2[6]
    sex = line2[7] if line2[7] in ["M", "F", "X"] else "M"
    expiry_raw = line2[8:14]
    expiry_check = line2[14]
    nationality = line2[15:18].replace("<", "") or country

    # Line 3: Name section
    name_section = line3.split("<<")
    surname = name_section[0].replace("<", " ").strip() if len(name_section) > 0 else ""
    given_names = name_section[1].replace("<", " ").strip() if len(name_section) > 1 else ""
    full_name = f"{given_names} {surname}".strip() or surname

    checksum_failures = []
    if not _validate_check_digit(doc_raw_9, doc_check):
        checksum_failures.append("doc_number")
    if not _validate_check_digit(dob_raw, dob_check):
        checksum_failures.append("date_of_birth")
    if not _validate_check_digit(expiry_raw, expiry_check):
        checksum_failures.append("expiry_date")

    doc_num = doc_raw_9.replace("<", "")
    mrz_fields = {
        "mrz_format": "TD1",
        "doc_number": doc_num,
        "id_number": doc_num,
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
        checksum_valid=(len(checksum_failures) == 0),
        checksum_failures=checksum_failures,
        mrz_fields=mrz_fields,
    )


def parse_mrz_from_text_lines(text_lines: list[str]) -> MRZResult:
    """
    Detect and parse MRZ zone from OCR text lines.
    Automatically identifies whether it is TD3 (2x44), TD2 (2x36), or TD1 (3x30).
    """
    cleaned_lines = [_clean_mrz_line(l) for l in text_lines if l.strip()]

    # Check for 3-line TD1 ID format
    td1_candidates = [
        l for l in cleaned_lines
        if len(l) >= 24 and ("<<" in l or l.startswith("I<") or l.startswith("A<") or l.startswith("C<"))
    ]
    if len(td1_candidates) >= 3:
        # Check if line 2 has DOB/Expiry pattern
        if any(re.search(r"[0-9]{6}[0-9<][MFX<][0-9]{6}", c) for c in td1_candidates):
            return parse_td1(td1_candidates[0], td1_candidates[1], td1_candidates[2])

    # Check for 2-line TD3 / TD2 format
    line1 = None
    line2 = None

    for line in cleaned_lines:
        # Line 1: Starts with P, V, or contains << with country code
        if (
            (line.startswith("P<") or line.startswith("V<") or (line.startswith("P") and "<<" in line) or (line.startswith("V") and "<<" in line) or ("<<" in line and "IND" in line))
            and not line1
        ):
            line1 = line
        # Line 2: Contains 6-digit DOB + check digit + M/F/< + 6-digit Expiry
        elif re.search(r"[0-9]{6}[0-9<][MFX<][0-9]{6}", line) or re.search(r"[A-Z0-9<]{8,9}[0-9<][A-Z]{3}[0-9]{6}", line):
            line2 = line

    # Fallback search if strict regex didn't catch both
    if not line1 or not line2:
        for line in cleaned_lines:
            if not line1 and len(line) >= 28 and ("<<" in line or line.startswith("P") or line.startswith("V")):
                line1 = line
            elif not line2 and len(line) >= 28 and sum(c.isdigit() for c in line) >= 12:
                line2 = line

    if not line1 or not line2:
        return MRZResult(mrz_present=False)

    # Distinguish TD2 (36 chars) vs TD3 (44 chars)
    if len(line1) <= 38 and len(line2) <= 38:
        return parse_td2(line1, line2)
    else:
        return parse_td3(line1, line2)


def parse_mrz(image_bytes: bytes, ocr_text_lines: list[str] | None = None) -> MRZResult:
    """
    Parse MRZ from OCR text lines first, falling back to PassportEye if available.
    """
    if ocr_text_lines:
        str_lines = [l[0] if isinstance(l, (list, tuple)) else str(l) for l in ocr_text_lines]
        res = parse_mrz_from_text_lines(str_lines)
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
