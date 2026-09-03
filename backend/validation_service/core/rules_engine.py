"""
Rules Engine — Generic YAML-driven rule interpreter for document validation.

CONCEPT:
Hardcoding validation logic in Python functions leads to brittle code that is
hard to extend to new document types or country-specific variations.

This engine:
  1. Reads YAML rule definitions dynamically based on document_type.
     Zero-restart hot-reload: the YAML is re-read on every request, so adding
     a new rule to a YAML file takes effect on the *very next* validation call
     without restarting the service.
  2. Maps field keys from ExtractedField objects into an easily indexable lookup.
  3. Dispatches each rule to its corresponding type validator:
     - 'date_check'    → calls date_logic.evaluate_date_condition
     - 'regex_format'  → executes regex matching on field values
     - 'cross_field'   → evaluates cross-field condition within one document
     - 'cross_document'→ evaluates cross-document date comparisons (e.g. visa vs passport)
     - 'checksum'      → validates MRZ check-digit results already parsed by ocr_service
  4. Returns a structured ValidationResponse containing passed status and
     detailed per-rule reasons.
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

# Map every active DocumentType to its YAML rule file.
# Adding a new document type only requires: (a) adding it here, (b) creating the YAML.
RULE_FILE_MAP: dict[DocumentType, str] = {
    DocumentType.PASSPORT: "passport_rules.yaml",
    DocumentType.VISA: "visa_rules.yaml",
    DocumentType.NATIONAL_ID: "national_id_rules.yaml",
    DocumentType.DRIVING_LICENSE: "driving_license_rules.yaml",
    DocumentType.PERMIT: "permit_rules.yaml",
    DocumentType.PAN_CARD: "pan_card_rules.yaml",
    DocumentType.VOTER_ID: "voter_id_rules.yaml",
    # FERRY_TICKET: deferred to Future Scope
}


def load_rules_for_doctype(document_type: DocumentType) -> list[dict[str, Any]]:
    """
    Dynamically load YAML rule configuration for a document type.

    Hot-reload guarantee: re-reads the YAML file on *every* call so that a
    new rule added to the file is picked up on the next request with zero
    service restart required (Phase 3 'Definition of Done' criterion).

    On YAML load failure the engine returns an empty rule set for that document type.
    """
    filename = RULE_FILE_MAP.get(document_type)
    if not filename:
        logger.info(
            "No rule file configured for doctype",
            document_type=document_type.value,
        )
        return []

    file_path = RULES_DIR / filename
    if not file_path.exists():
        logger.warning("Rule configuration file not found", path=str(file_path))
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            rules: list[dict[str, Any]] = yaml.safe_load(f) or []

        logger.info(
            "Loaded validation rules",
            document_type=document_type.value,
            count=len(rules),
        )
        return rules

    except Exception as e:
        logger.error(
            "Failed to parse YAML rule file",
            error=str(e),
            path=str(file_path),
        )
        return []


# ---------------------------------------------------------------------------
# Field-value normalisation helpers
# ---------------------------------------------------------------------------

def _build_field_map(fields: list[ExtractedField]) -> dict[str, str | None]:
    """
    Convert ExtractedField list → lowercase-keyed dict for fast lookup.

    Also creates common field-name aliases so both MRZ-style names
    (e.g. 'doc_number', 'expiry_date') and VIZ-style names
    (e.g. 'passport_number', 'date_of_expiry') resolve to the same value.
    """
    field_map: dict[str, str | None] = {
        f.field_name.lower(): f.field_value for f in fields
    }

    # Alias: doc_number ↔ passport_number
    if "doc_number" in field_map and "passport_number" not in field_map:
        field_map["passport_number"] = field_map["doc_number"]
    if "passport_number" in field_map and "doc_number" not in field_map:
        field_map["doc_number"] = field_map["passport_number"]

    # Alias: date_of_expiry ↔ expiry_date ↔ valid_until
    for exp_key in ["date_of_expiry", "expiry_date", "valid_until"]:
        if exp_key in field_map and field_map[exp_key]:
            val = field_map[exp_key]
            field_map.setdefault("date_of_expiry", val)
            field_map.setdefault("expiry_date", val)
            field_map.setdefault("valid_until", val)
            break

    # Alias: voter_id_number ↔ epic_number ↔ voter_id ↔ epic_no
    for v_alias in ["epic_number", "voter_id", "epic_no", "voter_number", "elector_id"]:
        if v_alias in field_map and "voter_id_number" not in field_map:
            field_map["voter_id_number"] = field_map[v_alias]
        if "voter_id_number" in field_map and v_alias not in field_map:
            field_map[v_alias] = field_map["voter_id_number"]

    # Alias: aadhaar_number ↔ id_number
    if "aadhaar_number" in field_map and "id_number" not in field_map:
        field_map["id_number"] = field_map["aadhaar_number"]
    if "id_number" in field_map and "aadhaar_number" not in field_map:
        field_map["aadhaar_number"] = field_map["id_number"]

    # Alias: driving_license_number ↔ license_number
    if "driving_license_number" in field_map and "license_number" not in field_map:
        field_map["license_number"] = field_map["driving_license_number"]
    if "license_number" in field_map and "driving_license_number" not in field_map:
        field_map["driving_license_number"] = field_map["license_number"]

    return field_map


# ---------------------------------------------------------------------------
# Core validation dispatcher
# ---------------------------------------------------------------------------

def validate_document(
    document_type: DocumentType,
    fields: list[ExtractedField],
    related_document_fields: list[ExtractedField] | None = None,
    mrz_checksum_valid: bool | None = None,
    mrz_checksum_failures: list[str] | None = None,
) -> ValidationResponse:
    """
    Evaluate all YAML-configured rules against extracted document fields.

    Args:
        document_type:            Classified document type.
        fields:                   OCR/MRZ/LLM-extracted fields for this document.
        related_document_fields:  Optional fields from a secondary document used
                                  in cross-document checks (e.g. passport when
                                  validating a visa).
        mrz_checksum_valid:       Pre-parsed MRZ overall checksum result from
                                  ocr_service — passed through for 'checksum' rules.
        mrz_checksum_failures:    List of field names where MRZ checksums failed.

    Returns:
        ValidationResponse with per-rule results and overall pass/fail.
    """
    logger.info(
        "Running document validation",
        document_type=document_type.value,
        field_count=len(fields),
    )

    field_map = _build_field_map(fields)

    rules = load_rules_for_doctype(document_type)
    results: list[RuleResult] = []
    failed_rule_names: list[str] = []

    for rule in rules:
        rule_name: str = rule.get("rule_name", "unnamed_rule")
        rule_type: str | None = rule.get("rule_type")
        target_field: str = rule.get("field", "").lower()
        error_msg: str = rule.get("error_message", "Validation rule check failed.")

        field_value = field_map.get(target_field)

        # ── 1. Date Check ─────────────────────────────────────────────────
        if rule_type == "date_check":
            condition: str = rule.get("condition", "> today")
            passed, detail = evaluate_date_condition(field_value, condition)
            if not passed and error_msg:
                detail = f"{error_msg} ({detail})"
            results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
            if not passed:
                failed_rule_names.append(rule_name)

        # ── 2. Regex Format Check ─────────────────────────────────────────
        elif rule_type == "regex_format":
            pattern: str = rule.get("pattern", "")
            if not field_value:
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=False,
                        detail=f"Missing required field '{target_field}' for format check.",
                    )
                )
                failed_rule_names.append(rule_name)
            else:
                raw_val = field_value.strip()
                clean_val = re.sub(r"\s+", "", raw_val)
                regex_match = (
                    re.match(pattern, raw_val, re.IGNORECASE) is not None
                    or re.match(pattern, clean_val, re.IGNORECASE) is not None
                )
                detail = (
                    f"Field '{target_field}' ('{field_value}') matches expected format."
                    if regex_match
                    else f"{error_msg} (Value: '{field_value}', pattern: '{pattern}')"
                )
                results.append(RuleResult(rule_name=rule_name, passed=regex_match, detail=detail))
                if not regex_match:
                    failed_rule_names.append(rule_name)

        # ── 3. Cross-Field Check (within one document) ────────────────────
        elif rule_type == "cross_field":
            ref_field: str = rule.get("reference_field", "").lower()
            ref_value = field_map.get(ref_field)
            condition_str: str = rule.get("condition", "")

            if not field_value or not ref_value:
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=False,
                        detail=(
                            f"Cross-field check requires both '{target_field}' and "
                            f"'{ref_field}' to be present."
                        ),
                    )
                )
                failed_rule_names.append(rule_name)
            elif "field <= reference_field" in condition_str or "field < reference_field" in condition_str:
                # Date comparison: field must be ≤ reference_field
                passed, detail = evaluate_cross_document_dates(field_value, ref_value)
                if not passed and error_msg:
                    detail = f"{error_msg} ({detail})"
                results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
                if not passed:
                    failed_rule_names.append(rule_name)
            else:
                logger.warning(
                    "Unsupported cross_field condition",
                    rule_name=rule_name,
                    condition=condition_str,
                )

        # ── 4. Cross-Document Check (e.g. Visa validity vs Passport) ──────
        elif rule_type == "cross_document":
            related_map: dict[str, str | None] = {
                f.field_name.lower(): f.field_value
                for f in (related_document_fields or [])
            }
            if target_field == "entry_validity" and "expiry_date" in related_map:
                passed, detail = evaluate_cross_document_dates(
                    field_value, related_map.get("expiry_date")
                )
                results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
                if not passed:
                    failed_rule_names.append(rule_name)

        # ── 5. MRZ Checksum Rule ──────────────────────────────────────────
        elif rule_type == "checksum":
            # The MRZ checksum results are pre-computed by the ocr_service
            # and passed in as arguments — the rules engine does not re-parse the MRZ.
            if mrz_checksum_valid is None:
                # No MRZ data provided — treat as not applicable for non-MRZ docs
                results.append(
                    RuleResult(
                        rule_name=rule_name,
                        passed=True,
                        detail="MRZ checksum check not applicable (no MRZ data provided).",
                    )
                )
            else:
                failures = mrz_checksum_failures or []
                passed = mrz_checksum_valid
                detail = (
                    "All MRZ check digits are valid."
                    if passed
                    else (
                        f"MRZ checksum failed for field(s): "
                        f"{', '.join(failures)}. This is a hard forgery signal."
                    )
                )
                if not passed and error_msg:
                    detail = f"{error_msg} — {detail}"
                results.append(RuleResult(rule_name=rule_name, passed=passed, detail=detail))
                if not passed:
                    failed_rule_names.append(rule_name)

        else:
            logger.warning(
                "Encountered unknown rule type in YAML",
                rule_type=rule_type,
                rule_name=rule_name,
            )

    overall_passed = len(failed_rule_names) == 0

    logger.info(
        "Validation complete",
        document_type=document_type.value,
        passed=overall_passed,
        failed_count=len(failed_rule_names),
        failed_rules=failed_rule_names,
    )

    return ValidationResponse(
        document_type=document_type,
        passed=overall_passed,
        failed_rules=failed_rule_names,
        rule_results=results,
    )
