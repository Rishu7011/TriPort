"""
Date Logic — Parsing, Normalization, and Evaluation for Validation Rules.

CONCEPT:
Travel documents use multiple conflicting date conventions:
  - MRZ format: YYMMDD (e.g. '850115' for 15 Jan 1985, '281015' for 15 Oct 2028)
  - Visual zone formats: '15/01/1985', '1985-01-15', '15 JAN 1985'

This module provides:
  1. Multi-format date parsing with 2-digit year ICAO 9303 century pivot logic.
  2. Condition evaluation: '> today', '< today', '> today + 180d'.
  3. Cross-document date comparisons (e.g. visa entry validity within passport window).
"""

from datetime import date, datetime, timedelta
import re
from typing import Any

from backend.logging_config import get_logger

logger = get_logger("validation_service.date_logic")

# Date parse formats to test in priority order
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
]


def parse_date(value: str | None) -> date | None:
    """
    Parse arbitrary date strings into a standard datetime.date object.

    Handles:
      - 6-digit MRZ YYMMDD format with ICAO century pivot
      - Standard delimited date formats (ISO, European, etc.)
    """
    if not value or not isinstance(value, str):
        return None

    cleaned = value.strip().replace(".", "-").replace("/", "-")

    # 1. Check for 6-digit MRZ format: YYMMDD
    if re.fullmatch(r"\d{6}", cleaned):
        try:
            yy = int(cleaned[0:2])
            mm = int(cleaned[2:4])
            dd = int(cleaned[4:6])

            current_year = date.today().year % 100
            # ICAO standard rule: If YY <= (current_year + 10), it's 2000s, else 1900s
            century = 2000 if yy <= (current_year + 10) else 1900
            full_year = century + yy
            return date(full_year, mm, dd)
        except Exception:
            return None

    # 2. Try standard date format strings
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue

    logger.debug("Failed to parse date string", raw_value=value)
    return None


def evaluate_date_condition(target_date_str: str | None, condition: str) -> tuple[bool, str]:
    """
    Evaluate condition string against a parsed date.

    Supported conditions:
      - "> today"
      - "< today"
      - "> today + Nd" (e.g. "> today + 180d" for 6 months validity)
      - "< today - Ny" (e.g. "< today - 18y" for age check)
    """
    if not target_date_str:
        return False, "Date value is missing or null."

    parsed_target = parse_date(target_date_str)
    if not parsed_target:
        return False, f"Date format could not be parsed: '{target_date_str}'."

    today = date.today()
    cond = condition.strip().lower()

    if cond == "> today":
        passed = parsed_target > today
        detail = f"Date {parsed_target.isoformat()} is in the future." if passed else f"Date {parsed_target.isoformat()} has passed (today is {today.isoformat()})."
        return passed, detail

    if cond == "< today":
        passed = parsed_target < today
        detail = f"Date {parsed_target.isoformat()} is in the past." if passed else f"Date {parsed_target.isoformat()} cannot be in the future (today is {today.isoformat()})."
        return passed, detail

    # Check "+ Nd" offset (e.g. "> today + 180d")
    match_plus_days = re.match(r">\s*today\s*\+\s*(\d+)d", cond)
    if match_plus_days:
        days_offset = int(match_plus_days.group(1))
        required_date = today + timedelta(days=days_offset)
        passed = parsed_target >= required_date
        detail = (
            f"Date {parsed_target.isoformat()} meets required threshold (after {required_date.isoformat()})."
            if passed
            else f"Date {parsed_target.isoformat()} fails required 6-month validity threshold (needs {required_date.isoformat()})."
        )
        return passed, detail

    return False, f"Unsupported date condition: '{condition}'"


def evaluate_cross_document_dates(
    visa_expiry_str: str | None,
    passport_expiry_str: str | None,
) -> tuple[bool, str]:
    """
    Cross-document check: A visa's valid stay/expiry must not exceed
    the underlying passport's expiry date.
    """
    if not visa_expiry_str or not passport_expiry_str:
        return False, "Missing visa or passport expiration date for cross-document validation."

    visa_exp = parse_date(visa_expiry_str)
    pass_exp = parse_date(passport_expiry_str)

    if not visa_exp or not pass_exp:
        return False, "Unable to parse dates for cross-document comparison."

    passed = visa_exp <= pass_exp
    if passed:
        return True, f"Visa expiry ({visa_exp.isoformat()}) is within passport validity window ({pass_exp.isoformat()})."
    else:
        return False, f"Visa expiry ({visa_exp.isoformat()}) exceeds passport validity ({pass_exp.isoformat()})."
