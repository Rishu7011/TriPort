"""
Validation Router — FastAPI endpoint for document validation.

Accepts extracted fields and document type, invokes the YAML rules engine,
and returns per-rule check results.
"""

from fastapi import APIRouter, status

from backend.logging_config import get_logger
from backend.validation_service.core.rules_engine import validate_document
from backend.validation_service.schemas.validation import (
    ValidationRequest,
    ValidationResponse,
)

logger = get_logger("validation_service.router")

router = APIRouter(prefix="/api/v1/validation", tags=["Document Validation"])


@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate extracted document fields against YAML business rules",
)
async def validate_extracted_fields(request: ValidationRequest) -> ValidationResponse:
    """
    Evaluate OCR-extracted fields against configured document rules (dates, formats, cross-checks).
    """
    logger.info(
        "Received validation request",
        document_type=request.document_type.value,
        field_count=len(request.fields),
    )

    response = validate_document(
        document_type=request.document_type,
        fields=request.fields,
        related_document_fields=request.related_document_fields,
    )

    logger.info(
        "Validation complete",
        passed=response.passed,
        failed_rules=response.failed_rules,
    )
    return response
