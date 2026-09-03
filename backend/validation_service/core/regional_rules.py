"""
Regional Document Rules Engine — Country-Specific Format Validation.

CONCEPT:
Land-border checkpoints (Nepal, Bhutan, Bangladesh, Myanmar) process far more
neighboring-country national ID cards and regional travel documents than
international passports. These documents have unique number formats that the
generic passport/visa rules engine cannot handle.

This module:
  1. Maps ISO-3166-1 alpha-2 (and alpha-3) nationality codes to their
     country-specific YAML rule file in validation_service/rules/regional/.
  2. Reuses the generic YAML rule interpreter pattern from rules_engine.py.
  3. Applies regional rules per document type in addition to the base
     document-type rules.
  4. Gracefully returns an empty-pass result for countries without a
     dedicated regional rule file (rules are additive, not mandatory).

Supported countries:
  NP   — Nepal       (citizenship certificate + MRP passport)
  BT   — Bhutan      (CID + passport)
  BD   — Bangladesh  (NID 10/13/17-digit + MRP passport)
  MM   — Myanmar     (NRC + passport)
  IND  — India       (Passport + Voter ID/EPIC + PAN Card + Aadhaar)
"""

from pathlib import Path
import re
from typing import Any
import yaml

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import DocumentType, ExtractedField
from backend.validation_service.core.date_logic import evaluate_date_condition
from backend.validation_service.schemas.validation import (
    RuleResult,
    ValidationResponse,
)

logger = get_logger("validation_service.regional_rules")

REGIONAL_RULES_DIR = Path(__file__).resolve().parent.parent / "rules" / "regional"

# ---------------------------------------------------------------------------
# Nationality normalization — accept both alpha-2 and alpha-3 codes
# ---------------------------------------------------------------------------

# Map of alpha-3 → alpha-2 / standard regional file stems
_ALPHA3_TO_ALPHA2: dict[str, str] = {
    "NPL": "NP",   # Nepal
    "BTN": "BT",   # Bhutan
    "BGD": "BD",   # Bangladesh
    "MMR": "MM",   # Myanmar
    "IND": "IND",  # India (maps to IND.yaml)
}


def _normalise_nationality(nationality: str) -> str:
    """
    Normalise any nationality code to standard country code.

    Accepts:
      - 2-letter alpha-2 codes ('NP', 'BD', 'IN', ...)
      - 3-letter alpha-3 ICAO codes ('NPL', 'BGD', 'IND', ...)
    """
    code = nationality.upper().strip()
    if code in ("IN", "IND"):
        return "IND"
    if len(code) == 3 and code in _ALPHA3_TO_ALPHA2:
        return _ALPHA3_TO_ALPHA2[code]
    return code[:2]   # Truncate alpha-3 to alpha-2 as fallback


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def _load_regional_rules(
    country_code: str,
    document_type: DocumentType | str | None = None,
) -> list[dict[str, Any]]:
    """
    Load country-specific YAML rules from rules/regional/<COUNTRY_CODE>.yaml.
    Generically filters by document_type when provided.

    Hot-reload: re-read on every call (same guarantee as rules_engine.py).
    Returns empty list (not an error) if no regional file exists for the country.
    """
    norm_code = _normalise_nationality(country_code)
    file_path = REGIONAL_RULES_DIR / f"{norm_code.upper()}.yaml"

    if not file_path.exists() and norm_code.upper() == "IND":
        file_path = REGIONAL_RULES_DIR / "IN.yaml"
    elif not file_path.exists() and norm_code.upper() == "IN":
        file_path = REGIONAL_RULES_DIR / "IND.yaml"

    if not file_path.exists():
        logger.info(
            "No regional rule file for country — skipping",
            country_code=country_code,
        )
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_rules: Any = yaml.safe_load(f) or []

        doc_type_str: str | None = None
        if document_type:
            doc_type_str = (
                document_type.value
                if hasattr(document_type, "value")
                else str(document_type).lower()
            )

        selected_rules: list[dict[str, Any]] = []

        if isinstance(raw_rules, dict):
            # Dict-based grouping: {"passport": [...], "voter_id": [...]}
            if doc_type_str and doc_type_str in raw_rules:
                selected_rules.extend(raw_rules[doc_type_str])
            selected_rules.extend(raw_rules.get("common", []))
            selected_rules.extend(raw_rules.get("all", []))
        elif isinstance(raw_rules, list):
            # List-based rules: filter by document_type if present
            for rule in raw_rules:
                rule_doc_type = rule.get("document_type")
                if rule_doc_type:
                    if doc_type_str and rule_doc_type.lower() == doc_type_str:
                        selected_rules.append(rule)
                else:
                    # General country rule (e.g. dob_in_past) without specific doctype
                    selected_rules.append(rule)

        logger.info(
            "Loaded regional rules",
            country_code=country_code,
            document_type=doc_type_str,
            count=len(selected_rules),
        )
        return selected_rules

    except Exception as e:
        logger.error(
            "Failed to parse regional YAML rule file",
            country_code=country_code,
            error=str(e),
        )
        return []


# ---------------------------------------------------------------------------
# Core regional validation entry point
# ---------------------------------------------------------------------------

def apply_regional_rules(
    nationality: str,
    document_type: DocumentType,
    fields: list[ExtractedField],
) -> ValidationResponse:
    """
    Apply country-specific format rules for a given nationality and document type.

    Args:
        nationality:    ISO alpha-2 or alpha-3 nationality code from the document.
        document_type:  Classified document type.
        fields:         Extracted document fields.

    Returns:
        ValidationResponse using the regional rule set.
        If no regional rules exist for the country, returns passed=True with
        an informational note — absence of country rules is not a failure.
    """
    country_code = _normalise_nationality(nationality)

    logger.info(
        "Applying regional validation rules",
        nationality=nationality,
        normalised_code=country_code,
        document_type=document_type.value,
        field_count=len(fields),
    )

    regional_rules = _load_regional_rules(country_code, document_type)

    if not regional_rules:
        # No country-specific rules — return a pass with informational detail
        return ValidationResponse(
            document_type=document_type,
            passed=True,
            failed_rules=[],
            rule_results=[
                RuleResult(
                    rule_name="regional_rules_not_configured",
                    passed=True,
                    detail=(
                        f"Regional format rules are not configured for nationality code "
                        f"'{country_code}'. Standard document-type rules apply."
                    ),
                    severity="low",
                )
            ],
        )

    # Delegate to the generic YAML rule interpreter pattern
    from backend.validation_service.core.rules_engine import _build_field_map

    field_map = _build_field_map(fields)
    results: list[RuleResult] = []
    failed_rule_names: list[str] = []

    for rule in regional_rules:
        rule_name: str = rule.get("rule_name", "unnamed_rule")
        rule_type: str | None = rule.get("rule_type")
        target_field: str = rule.get("field", "").lower()
        error_msg: str = rule.get("error_message", "Regional validation rule failed.")
        severity: str = rule.get("severity", "medium")
        field_value = field_map.get(target_field)

        if rule_type == "date_check":
            # If target field is missing from document, check if optional/general
            if not field_value:
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=False,
                        detail=f"Missing field '{target_field}' for date check.",
                        severity=severity,
                    )
                )
                failed_rule_names.append(rule_name)
                continue

            condition: str = rule.get("condition", "> today")
            passed, detail = evaluate_date_condition(field_value, condition)
            if not passed and error_msg:
                detail = f"{error_msg} ({detail})"
            results.append(
                RuleResult(
                    rule_name=rule_name,
                    passed=passed,
                    detail=detail,
                    severity=severity,
                )
            )
            if not passed:
                failed_rule_names.append(rule_name)

        elif rule_type == "regex_format":
            pattern: str = rule.get("pattern", "")
            if not field_value:
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=False,
                        detail=f"Missing field '{target_field}' for regional format check.",
                        severity=severity,
                    )
                )
                failed_rule_names.append(rule_name)
            else:
                regex_match = re.match(pattern, field_value.strip()) is not None
                detail = (
                    f"Field '{target_field}' ('{field_value}') matches "
                    f"country-specific format for '{country_code}'."
                    if regex_match
                    else f"{error_msg} (Value: '{field_value}', pattern: '{pattern}')"
                )
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=regex_match,
                        detail=detail,
                        severity=severity,
                    )
                )
                if not regex_match:
                    failed_rule_names.append(rule_name)

        else:
            logger.warning(
                "Unknown rule type in regional YAML",
                rule_type=rule_type,
                rule_name=rule_name,
            )

    overall_passed = len(failed_rule_names) == 0

    logger.info(
        "Regional validation complete",
        country_code=country_code,
        passed=overall_passed,
        failed_count=len(failed_rule_names),
    )

    return ValidationResponse(
        document_type=document_type,
        passed=overall_passed,
        failed_rules=failed_rule_names,
        rule_results=results,
    )


def get_supported_regional_countries() -> list[str]:
    """Return list of country codes that have regional rule files configured."""
    return [p.stem for p in REGIONAL_RULES_DIR.glob("*.yaml") if p.is_file()]
