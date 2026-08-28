"""
Pydantic Schemas for Validation Service.

Defines the structure for input validation requests and per-rule verification reports.
"""

from pydantic import BaseModel, Field
from backend.ocr_service.schemas.extraction import DocumentType, ExtractedField


class RuleResult(BaseModel):
    """Result of evaluating a single rule."""
    rule_name: str = Field(..., description="Unique rule identifier")
    passed: bool = Field(..., description="True if rule passed, False if violated")
    detail: str = Field(..., description="Human-readable explanation of the result")


class ValidationRequest(BaseModel):
    """
    Validation request body.
    Accepts the extracted fields from OCR and an optional secondary document (for cross-validation).
    """
    document_type: DocumentType
    fields: list[ExtractedField]
    related_document_fields: list[ExtractedField] | None = Field(
        None,
        description="Optional fields from a secondary document (e.g. passport fields when validating a visa)",
    )


class ValidationResponse(BaseModel):
    """Overall document validation report."""
    document_type: DocumentType
    passed: bool = Field(..., description="True if all rules passed; False if any rule failed")
    failed_rules: list[str] = Field(default_factory=list, description="Names of all failed rules")
    rule_results: list[RuleResult] = Field(..., description="Detailed per-rule breakdown")
