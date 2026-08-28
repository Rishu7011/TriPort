"""
Pydantic schemas for the OCR Service.

CONCEPT: Pydantic schemas serve two purposes:
  1. VALIDATION — FastAPI automatically rejects requests that don't match
     the schema, with a clear error message. No manual if/else needed.
  2. DOCUMENTATION — FastAPI generates OpenAPI docs (Swagger UI at /docs)
     from these schemas automatically. Every field gets a description.

TWO TYPES of schemas here:
  - Request schemas (what comes IN to our API)
  - Response schemas (what goes OUT from our API)

We keep them in separate files per service so each service is self-contained.
"""

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums — fixed allowed values
# ---------------------------------------------------------------------------
class DocumentType(str, Enum):
    """
    WHY Enum instead of plain str?
    If a caller sends document_type="pasport" (typo), Pydantic rejects it
    immediately with a clear error. With plain str, the typo silently
    flows through and causes confusing bugs deep in the OCR pipeline.
    """
    PASSPORT = "passport"
    VISA = "visa"
    NATIONAL_ID = "national_id"
    DRIVING_LICENSE = "driving_license"
    PERMIT = "permit"


class ExtractionMethod(str, Enum):
    """Tracks HOW a field was extracted — critical for debugging and audit."""
    OCR = "ocr"          # PaddleOCR extracted this field
    MRZ = "mrz"          # PassportEye extracted this from the Machine Readable Zone
    LLM = "llm_fallback" # Claude API was used (OCR confidence too low, or no MRZ)


# ---------------------------------------------------------------------------
# Individual field result
# ---------------------------------------------------------------------------
class ExtractedField(BaseModel):
    """
    One extracted field from a document.
    e.g. {"field_name": "date_of_expiry", "field_value": "2028-10-15", "confidence": 0.97}

    WHY confidence?
    OCR models output a probability alongside each text detection.
    A confidence of 0.4 means the model is unsure — we might want to flag
    this field for human review or re-route to the LLM fallback.
    """
    field_name: str = Field(..., description="e.g. 'name', 'passport_number', 'date_of_expiry'")
    field_value: str | None = Field(None, description="Extracted text value, None if not found")
    confidence: float | None = Field(
        None,
        ge=0.0,   # ge = greater than or equal — Pydantic enforces this bound
        le=1.0,   # le = less than or equal
        description="OCR model confidence, 0.0–1.0. None for MRZ/LLM extractions.",
    )
    extraction_method: ExtractionMethod = Field(
        ExtractionMethod.OCR,
        description="Which method produced this field",
    )


# ---------------------------------------------------------------------------
# MRZ-specific result block
# ---------------------------------------------------------------------------
class MRZResult(BaseModel):
    """
    The MRZ (Machine Readable Zone) is the two-line `<<<` block at the
    bottom of passports. PassportEye reads it and validates the ICAO
    checksum digits embedded in each field.

    WHY this matters:
    The checksum is a mathematical property of the document — you can't
    forge the DOB without also changing the check digit. If mrz_present
    is True but checksum_valid is False, that's an instant red flag
    requiring no ML model at all.
    """
    mrz_present: bool = Field(..., description="Was an MRZ zone detected in the image?")
    checksum_valid: bool | None = Field(
        None,
        description="Did ALL MRZ check digits pass? None if no MRZ was found.",
    )
    checksum_failures: list[str] = Field(
        default_factory=list,
        description="Field names where the checksum failed, e.g. ['date_of_birth', 'doc_number']",
    )
    mrz_fields: dict[str, str | None] = Field(
        default_factory=dict,
        description="Raw field values extracted from the MRZ zone",
    )


# ---------------------------------------------------------------------------
# Full extraction response
# ---------------------------------------------------------------------------
class ExtractionResponse(BaseModel):
    """
    The complete response from POST /extract.

    WHY include extraction_method at the top level?
    When an officer reviews a flagged document, they should know if fields
    came from reliable OCR or from the LLM fallback (which is less precise).
    The audit ledger also records this for traceability.

    WHY include warnings?
    Low-confidence fields shouldn't silently pass. We surface them here so
    the orchestrator (and eventually the risk engine) can weight them correctly.
    """
    document_id: str | None = Field(
        None,
        description="UUID of the document row created in Postgres, if persisted",
    )
    document_type: DocumentType
    extraction_method: ExtractionMethod = Field(
        ...,
        description="Primary method used (ocr/mrz/llm_fallback). Fields may mix methods.",
    )
    fields: list[ExtractedField] = Field(
        ...,
        description="All extracted fields as a flat list",
    )
    mrz: MRZResult = Field(
        ...,
        description="MRZ parsing result — always present (mrz_present=False if no MRZ found)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues, e.g. 'Low confidence on date_of_birth (0.41)'",
    )


# ---------------------------------------------------------------------------
# Error response (returned on 422 / 500)
# ---------------------------------------------------------------------------
class ExtractionError(BaseModel):
    """
    WHY a typed error response?
    The orchestrator needs to distinguish between:
      - extraction_failed: image unreadable, no fields at all
      - partial_extraction: some fields extracted, some missing
    Both are different signals for the risk engine.
    """
    error: str = Field(..., description="'extraction_failed' or 'partial_extraction'")
    reason: str = Field(..., description="Human-readable explanation of what went wrong")
    document_type: DocumentType | None = None
