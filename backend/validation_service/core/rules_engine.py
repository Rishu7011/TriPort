"""
Rules Engine — Generic YAML-driven rule interpreter for document validation.

CONCEPT:
Hardcoding validation logic in Python functions leads to brittle code that is
hard to extend to new document types or country-specific variations.

This engine:
  1. Reads YAML rule definitions dynamically based on document_type.
  2. Maps field keys from ExtractedField objects into an easily indexable lookup.
  3. Dispatches each rule to its corresponding type validator:
     - 'date_check' → calls date_logic.evaluate_date_condition
     - 'regex_format' → executes regex matching on field values
     - 'cross_field' → evaluates cross-field or cross-document logic
  4. Returns a structured ValidationResponse containing passed status and detailed reasons.
"""

from pathlib import Path
import re
from typing import Any
import yaml

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import DocumentType, ExtractedField
from backend.validation_service.core.date_logic import (
    evaluate_cross_document_dates,
    evaluate_date_condition,
)
from backend.validation_service.schemas.validation import (
    RuleResult,
    ValidationResponse,
)

logger = get_logger("validation_service.rules_engine")

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


def load_rules_for_doctype(document_type: DocumentType) -> list[dict[str, Any]]:
    """
    Dynamically load YAML rule configuration for a document type.
    Re-reading on request ensures zero downtime when rules are updated.
    """
    rule_file_map = {
        DocumentType.PASSPORT: "passport_rules.yaml",
        DocumentType.VISA: "visa_rules.yaml",
        DocumentType.NATIONAL_ID: "national_id_rules.yaml",
    }
    filename = rule_file_map.get(document_type)
    if not filename:
        logger.info("No specific rule file configured for doctype", document_type=document_type.value)
        return []

    file_path = RULES_DIR / filename
    if not file_path.exists():
        logger.warning("Rule configuration file not found", path=str(file_path))
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            rules = yaml.safe_load(f) or []
            logger.info("Loaded validation rules", document_type=document_type.value, count=len(rules))
            return rules
    except Exception as e:
        logger.error("Failed to parse YAML rule file", error=str(e), path=str(file_path))
        return []


def validate_document(
    document_type: DocumentType,
    fields: list[ExtractedField],
    related_document_fields: list[ExtractedField] | None = None,
) -> ValidationResponse:
    """
    Evaluate all YAML-configured rules against extracted document fields.
    """
    logger.info("Running document validation", document_type=document_type.value)

    # Convert list of fields to a simple key-value dict for fast lookups
    field_map: dict[str, str | None] = {
        f.field_name.lower(): f.field_value for f in fields
    }
    # Alias: doc_number <-> passport_number (MRZ vs visual zone naming)
    if "doc_number" in field_map and "passport_number" not in field_map:
        field_map["passport_number"] = field_map["doc_number"]
    if "passport_number" in field_map and "doc_number" not in field_map:
        field_map["doc_number"] = field_map["passport_number"]

    # Alias: date_of_expiry <-> expiry_date
    # field_extractor.py (OCR path) emits "date_of_expiry"
    # mrz_parser.py (MRZ path) and passport_rules.yaml both use "expiry_date"
    if "date_of_expiry" in field_map and "expiry_date" not in field_map:
        field_map["expiry_date"] = field_map["date_of_expiry"]
    if "expiry_date" in field_map and "date_of_expiry" not in field_map:
        field_map["date_of_expiry"] = field_map["expiry_date"]

    rules = load_rules_for_doctype(document_type)
    results: list[RuleResult] = []
    failed_rule_names: list[str] = []

    for rule in rules:
        rule_name = rule.get("rule_name", "unnamed_rule")
        rule_type = rule.get("rule_type")
        target_field = rule.get("field", "").lower()
        error_msg = rule.get("error_message", "Validation rule check failed.")

        field_value = field_map.get(target_field)

        # ── 1. Date Check ────────────────────────────────────────────────
        if rule_type == "date_check":
            condition = rule.get("condition", "> today")
            passed, detail = evaluate_date_condition(field_value, condition)
            if not passed and error_msg:
                detail = f"{error_msg} ({detail})"
            results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
            if not passed:
                failed_rule_names.append(rule_name)

        # ── 2. Regex Format Check ─────────────────────────────────────────
        elif rule_type == "regex_format":
            pattern = rule.get("pattern", "")
            if not field_value:
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=False,
                        detail=f"Missing required field '{target_field}' for format verification.",
                    )
                )
                failed_rule_names.append(rule_name)
            else:
                regex_match = re.match(pattern, field_value.strip()) is not None
                detail = (
                    f"Field '{target_field}' ('{field_value}') matches expected format."
                    if regex_match
                    else f"{error_msg} (Value: '{field_value}', pattern: '{pattern}')"
                )
                results.append(RuleResult(rule_name=rule_name, passed=regex_match, detail=detail))
                if not regex_match:
                    failed_rule_names.append(rule_name)

        # ── 3. Cross-Document Check (e.g. Visa vs Passport) ──────────────
        elif rule_type == "cross_document":
            related_map = {
                f.field_name.lower(): f.field_value for f in (related_document_fields or [])
            }
            if target_field == "entry_validity" and "expiry_date" in related_map:
                passed, detail = evaluate_cross_document_dates(
                    field_value, related_map.get("expiry_date")
                )
                results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
                if not passed:
                    failed_rule_names.append(rule_name)

        else:
            logger.warning("Encountered unknown rule type in YAML", rule_type=rule_type)

    overall_passed = len(failed_rule_names) == 0

    return ValidationResponse(
        document_type=document_type,
        passed=overall_passed,
        failed_rules=failed_rule_names,
        rule_results=results,
    )
