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
  4. Caches loaded rules to the offline SQLite store so validation can continue
     when Postgres is unreachable (land/sea low-connectivity scenario).
  5. Returns a structured ValidationResponse containing passed status and
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
    # FERRY_TICKET: deferred to Future Scope
}


def load_rules_for_doctype(document_type: DocumentType) -> list[dict[str, Any]]:
    """
    Dynamically load YAML rule configuration for a document type.

    Hot-reload guarantee: re-reads the YAML file on *every* call so that a
    new rule added to the file is picked up on the next request with zero
    service restart required (Phase 3 'Definition of Done' criterion).

    On YAML load failure the engine falls through to the offline SQLite cache
    (imported lazily to avoid a circular-import at module level).
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
        return _load_from_offline_cache(document_type.value)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            rules: list[dict[str, Any]] = yaml.safe_load(f) or []

        logger.info(
            "Loaded validation rules",
            document_type=document_type.value,
            count=len(rules),
        )

        # Persist fresh copy to offline cache for future degraded-mode use
        _store_to_offline_cache(document_type.value, rules)
        return rules

    except Exception as e:
        logger.error(
            "Failed to parse YAML rule file",
            error=str(e),
            path=str(file_path),
        )
        return _load_from_offline_cache(document_type.value)


def _store_to_offline_cache(document_type_val: str, rules: list[dict[str, Any]]) -> None:
    """Persist rules to SQLite offline cache (best-effort, non-blocking)."""
    try:
        from backend.validation_service.core.offline_cache import get_offline_cache
        get_offline_cache().cache_rules(document_type_val, rules)
    except Exception as e:
        logger.debug("Offline cache store skipped", reason=str(e))


def _load_from_offline_cache(document_type_val: str) -> list[dict[str, Any]]:
    """Retrieve previously cached rules from SQLite (degraded-mode fallback)."""
    try:
        from backend.validation_service.core.offline_cache import get_offline_cache
        cached = get_offline_cache().get_cached_rules(document_type_val)
        if cached:
            logger.warning(
                "Using offline-cached rules",
                document_type=document_type_val,
                mode="offline_cached",
            )
            return cached
    except Exception as e:
        logger.debug("Offline cache read failed", reason=str(e))
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

    # Alias: date_of_expiry ↔ expiry_date
    if "date_of_expiry" in field_map and "expiry_date" not in field_map:
        field_map["expiry_date"] = field_map["date_of_expiry"]
    if "expiry_date" in field_map and "date_of_expiry" not in field_map:
        field_map["date_of_expiry"] = field_map["expiry_date"]

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
                regex_match = re.match(pattern, field_value.strip()) is not None
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
