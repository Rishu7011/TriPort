"""
Validation Router — FastAPI endpoints for document validation.

Endpoints:
  POST /api/v1/validation/validate
      Apply YAML rules engine to extracted document fields.
      Supports all 5 active document types and optional cross-document checks.

  POST /api/v1/validation/database-check
      Run SLTD + national blacklist + visa-validity checks against mock DB tables.
      Falls back to offline SQLite cache when Postgres is unreachable.

  POST /api/v1/validation/regional-validate
      Apply country-specific format rules for land-border neighboring countries
      (Nepal, Bhutan, Bangladesh, Myanmar).

  GET  /api/v1/validation/regional-countries
      List nationality codes that have dedicated regional rule files.

  GET  /api/v1/validation/cache-stats
      Offline cache statistics for monitoring and health checks.
"""

from fastapi import APIRouter, HTTPException, status

from backend.logging_config import get_logger
from backend.validation_service.core.database_check import run_all_database_checks
from backend.validation_service.core.offline_cache import get_offline_cache
from backend.validation_service.core.regional_rules import (
    apply_regional_rules,
    get_supported_regional_countries,
)
from backend.validation_service.core.rules_engine import validate_document
from backend.validation_service.schemas.validation import (
    DatabaseCheckRequest,
    DatabaseCheckResponse,
    RegionalValidationRequest,
    ValidationRequest,
    ValidationResponse,
)

logger = get_logger("validation_service.router")

router = APIRouter(prefix="/api/v1/validation", tags=["Document Validation"])


# ---------------------------------------------------------------------------
# 1. YAML Rules Engine — primary validation endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate extracted document fields against YAML business rules",
    description=(
        "Evaluates OCR-extracted fields against configured document rules "
        "(date checks, regex format, cross-field, MRZ checksum). "
        "Returns per-rule pass/fail with detailed reason strings. "
        "Hot-reload: YAML rules are re-read on every request — add a rule to "
        "the YAML file and it takes effect on the very next call."
    ),
)
async def validate_extracted_fields(request: ValidationRequest) -> ValidationResponse:
    logger.info(
        "Received validation request",
        document_type=request.document_type.value,
        field_count=len(request.fields),
        has_related_doc=request.related_document_fields is not None,
        mrz_checksum_valid=request.mrz_checksum_valid,
    )

    response = validate_document(
        document_type=request.document_type,
        fields=request.fields,
        related_document_fields=request.related_document_fields,
        mrz_checksum_valid=request.mrz_checksum_valid,
        mrz_checksum_failures=request.mrz_checksum_failures,
    )

    logger.info(
        "Validation complete",
        passed=response.passed,
        failed_count=len(response.failed_rules),
        failed_rules=response.failed_rules,
    )
    return response


# ---------------------------------------------------------------------------
# 2. Database Cross-Check — SLTD + Blacklist + Visa Validity
# ---------------------------------------------------------------------------

@router.post(
    "/database-check",
    response_model=DatabaseCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Cross-check document against SLTD, national blacklist, and visa validity databases",
    description=(
        "Runs all three mock government database queries concurrently. "
        "Returns composite hit status. Falls back to offline SQLite cache "
        "when Postgres is unreachable and logs mode='offline_cached'."
    ),
)
async def database_cross_check(request: DatabaseCheckRequest) -> DatabaseCheckResponse:
    logger.info(
        "Database cross-check request",
        document_number=request.document_number,
        has_name=bool(request.name),
        has_dob=bool(request.date_of_birth),
        has_visa=bool(request.visa_type and request.nationality),
    )

    sltd_result, blacklist_result, visa_result = await run_all_database_checks(
        document_number=request.document_number,
        name=request.name,
        date_of_birth=request.date_of_birth,
        visa_type=request.visa_type,
        nationality=request.nationality,
    )

    any_hit = sltd_result.sltd_hit or blacklist_result.blacklist_hit

    logger.info(
        "Database cross-check complete",
        sltd_hit=sltd_result.sltd_hit,
        blacklist_hit=blacklist_result.blacklist_hit,
        visa_valid=visa_result.is_valid_combination if visa_result else None,
        any_hit=any_hit,
    )

    return DatabaseCheckResponse(
        sltd=sltd_result,
        blacklist=blacklist_result,
        visa_validity=visa_result,
        any_hit=any_hit,
    )


# ---------------------------------------------------------------------------
# 3. Regional Validation — neighboring-country document formats
# ---------------------------------------------------------------------------

@router.post(
    "/regional-validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply country-specific document format rules for land-border nationals",
    description=(
        "Validates documents from neighboring land-border countries using "
        "country-specific YAML rules (Nepal, Bhutan, Bangladesh, Myanmar). "
        "Pass ISO alpha-2 or alpha-3 nationality code. "
        "Returns passed=True with an informational note if no country-specific "
        "rules are configured — absence of regional rules is not a failure."
    ),
)
async def regional_validate(request: RegionalValidationRequest) -> ValidationResponse:
    logger.info(
        "Regional validation request",
        nationality=request.nationality,
        document_type=request.document_type.value,
        field_count=len(request.fields),
    )

    response = apply_regional_rules(
        nationality=request.nationality,
        document_type=request.document_type,
        fields=request.fields,
    )

    logger.info(
        "Regional validation complete",
        nationality=request.nationality,
        passed=response.passed,
        failed_rules=response.failed_rules,
    )
    return response


# ---------------------------------------------------------------------------
# 4. Utility endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/regional-countries",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List nationality codes with dedicated regional rule files",
)
async def list_regional_countries() -> list[str]:
    """Return all country codes that have a regional YAML rule file configured."""
    return get_supported_regional_countries()


@router.get(
    "/cache-stats",
    status_code=status.HTTP_200_OK,
    summary="Offline cache statistics",
    description="Returns count of cached rule sets, blacklist entries, and pending sync decisions.",
)
async def cache_stats() -> dict:
    """Return offline SQLite cache statistics."""
    stats = get_offline_cache().stats()
    return {"status": "ok", "cache": stats}
