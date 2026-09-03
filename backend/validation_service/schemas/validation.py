"""
Pydantic Schemas for Validation Service.

Defines the structure for input validation requests, per-rule verification
reports, and database cross-check (SLTD / national blacklist / visa validity)
response models.
"""

from typing import Optional
from pydantic import BaseModel, Field
from backend.ocr_service.schemas.extraction import DocumentType, ExtractedField


# ---------------------------------------------------------------------------
# Core rule engine schemas
# ---------------------------------------------------------------------------

class RuleResult(BaseModel):
    """Result of evaluating a single rule."""
    rule_name: str = Field(..., description="Unique rule identifier")
    passed: bool = Field(..., description="True if rule passed, False if violated")
    detail: str = Field(..., description="Human-readable explanation of the result")
    severity: Optional[str] = Field(
        default=None,
        description="Rule severity level: critical, high, medium",
    )


class ValidationRequest(BaseModel):
    """
    Validation request body.
    Accepts the extracted fields from OCR and an optional secondary document
    (for cross-document validation, e.g. passport fields when validating a visa).
    Also accepts pre-parsed MRZ checksum results from the OCR service.
    """
    document_type: DocumentType
    fields: list[ExtractedField]
    related_document_fields: list[ExtractedField] | None = Field(
        None,
        description="Optional: fields from a secondary document (e.g. passport when validating a visa)",
    )
    mrz_checksum_valid: bool | None = Field(
        None,
        description="Pre-parsed MRZ overall checksum validity from ocr_service (None if no MRZ)",
    )
    mrz_checksum_failures: list[str] | None = Field(
        None,
        description="Field names where MRZ checksums failed, e.g. ['date_of_birth', 'doc_number']",
    )


class ValidationResponse(BaseModel):
    """Overall document validation report."""
    document_type: DocumentType
    passed: bool = Field(..., description="True if all rules passed; False if any rule failed")
    failed_rules: list[str] = Field(default_factory=list, description="Names of all failed rules")
    rule_results: list[RuleResult] = Field(..., description="Detailed per-rule breakdown")


# ---------------------------------------------------------------------------
# SLTD (Stolen & Lost Travel Documents) check schemas
# ---------------------------------------------------------------------------

class SLTDRecord(BaseModel):
    """A single hit from the Interpol SLTD mock database."""
    document_number: str
    report_type: str = Field(..., description="e.g. 'stolen', 'lost', 'fraudulent'")
    reporting_country: str
    reported_at: str = Field(..., description="ISO date string of report")


class SLTDResult(BaseModel):
    """Result of a Stolen/Lost Travel Document database lookup."""
    sltd_hit: bool = Field(..., description="True if the document number is in the SLTD database")
    sltd_record: Optional[SLTDRecord] = Field(
        None,
        description="Full SLTD record if a hit was found, null otherwise",
    )
    mode: str = Field(default="online", description="'online' or 'offline_cached'")


# ---------------------------------------------------------------------------
# National Blacklist check schemas
# ---------------------------------------------------------------------------

class BlacklistRecord(BaseModel):
    """A single entry from the national blacklist."""
    name: str
    date_of_birth: str
    document_number: Optional[str] = None
    severity: str = Field(..., description="e.g. 'watchlist', 'banned', 'investigate'")
    reason: str


class BlacklistResult(BaseModel):
    """Result of a national blacklist lookup."""
    blacklist_hit: bool = Field(..., description="True if the identity matches a blacklist entry")
    matched_record: Optional[BlacklistRecord] = Field(None)
    match_basis: list[str] = Field(
        default_factory=list,
        description="Which fields matched: e.g. ['document_number', 'name+dob']",
    )
    mode: str = Field(default="online", description="'online' or 'offline_cached'")


# ---------------------------------------------------------------------------
# Visa validity record check schemas
# ---------------------------------------------------------------------------

class VisaValidityResult(BaseModel):
    """Result of a visa-type + nationality validity check."""
    is_valid_combination: bool = Field(
        ...,
        description="True if this visa_type is valid for the given nationality",
    )
    max_stay_days: Optional[int] = Field(
        None,
        description="Maximum permitted stay duration in days (null if not found)",
    )
    mode: str = Field(default="online", description="'online' or 'offline_cached'")


# ---------------------------------------------------------------------------
# Composite database-check request / response
# ---------------------------------------------------------------------------

class DatabaseCheckRequest(BaseModel):
    """
    Request for a full database cross-check against all three mock databases.
    At minimum document_number must be provided; additional fields allow
    richer blacklist matching.
    """
    document_number: str = Field(..., description="The document number to check against SLTD and blacklist")
    name: Optional[str] = Field(None, description="Holder name for blacklist cross-reference")
    date_of_birth: Optional[str] = Field(None, description="Date of birth for blacklist cross-reference")
    visa_type: Optional[str] = Field(None, description="Visa type for visa validity check")
    nationality: Optional[str] = Field(None, description="Nationality code for visa validity check")


class DatabaseCheckResponse(BaseModel):
    """Composite result of all three database cross-check queries."""
    sltd: SLTDResult
    blacklist: BlacklistResult
    visa_validity: Optional[VisaValidityResult] = Field(
        None,
        description="Only present when visa_type and nationality are provided in the request",
    )
    any_hit: bool = Field(
        ...,
        description="Convenience flag: True if any of the three checks returned a hit",
    )


# ---------------------------------------------------------------------------
# Regional validation schemas
# ---------------------------------------------------------------------------

class RegionalValidationRequest(BaseModel):
    """Request for country-specific document format validation."""
    nationality: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 country code (e.g. 'NP', 'BT', 'BD', 'MM')",
        min_length=2,
        max_length=3,
    )
    document_type: DocumentType
    fields: list[ExtractedField]
