"""
Pydantic schemas for the OCR Service — Multi-Modal TriPort Document Extraction.

Covers:
  - Checkpoint Types: Airport, Land Border, Sea (Passenger)
  - Document Types: Passport, Visa, National ID, Driving License, Permit, Ferry Ticket
  - Extraction Methods: OCR, MRZ, LLM Fallback
  - Classification, Single Extraction, and Batch Mode Schemas
"""

from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums — fixed allowed values
# ---------------------------------------------------------------------------
class CheckpointType(str, Enum):
    """The 3 Port types handled by TriPort."""
    AIRPORT = "airport"
    LAND_BORDER = "land_border"
    SEA = "sea"


class DocumentType(str, Enum):
    """Supported document types across all 3 checkpoint domains."""
    PASSPORT = "passport"
    VISA = "visa"
    NATIONAL_ID = "national_id"
    DRIVING_LICENSE = "driving_license"
    PERMIT = "permit"
    FERRY_TICKET = "ferry_ticket"
    PAN_CARD = "pan_card"
    VOTER_ID = "voter_id"


class ExtractionMethod(str, Enum):
    """Tracks HOW a field was extracted — critical for debugging and audit."""
    OCR = "ocr"          # Primary OCR engine
    MRZ = "mrz"          # Machine Readable Zone (ICAO 9303 standard)
    LLM = "llm_fallback" # Vision LLM Fallback (for degraded/non-standard docs)


# ---------------------------------------------------------------------------
# Classification Result
# ---------------------------------------------------------------------------
class ClassificationResult(BaseModel):
    """Result of document type pre-classification."""
    document_type: DocumentType = Field(..., description="Predicted document type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")
    scores: dict[str, float] = Field(default_factory=dict, description="Raw category scores")
    matched_features: list[str] = Field(default_factory=list, description="Visual / text features matched")
    provider: str = Field(default="local", description="Provider used ('local' or 'api')")


# ---------------------------------------------------------------------------
# Individual field result
# ---------------------------------------------------------------------------
class ExtractedField(BaseModel):
    """
    One extracted field from a document.
    e.g. {"field_name": "date_of_expiry", "field_value": "2028-10-15", "confidence": 0.97}
    """
    field_name: str = Field(..., description="e.g. 'name', 'passport_number', 'date_of_expiry'")
    field_value: str | None = Field(None, description="Extracted text value, None if not found")
    confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="OCR model confidence, 0.0–1.0.",
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
    The MRZ (Machine Readable Zone) parsing result.
    Validates ICAO 9303 check digits embedded in fields.
    """
    mrz_present: bool = Field(..., description="Was an MRZ zone detected in the image?")
    mrz_format: str | None = Field(None, description="MRZ format detected: TD3, TD2, TD1, or None")
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
    """Complete response from POST /extract."""
    document_id: str | None = Field(
        None,
        description="UUID of the document row created in Postgres, if persisted",
    )
    document_type: DocumentType
    checkpoint_type: CheckpointType = Field(
        default=CheckpointType.AIRPORT,
        description="Checkpoint context: airport, land_border, or sea",
    )
    provider_used: str = Field(
        default="local",
        description="ML Provider used ('local' or 'api')",
    )
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
# Batch Extraction Schemas (For Bulk Bus & Ferry Passenger Queues)
# ---------------------------------------------------------------------------
class BatchItemResult(BaseModel):
    """Result for an individual document scan in a batch queue."""
    index: int
    filename: str | None = None
    success: bool
    result: ExtractionResponse | None = None
    error: str | None = None


class BatchExtractionResponse(BaseModel):
    """Aggregated response for bulk batch arrival processing."""
    total_processed: int
    successful_count: int
    failed_count: int
    checkpoint_type: CheckpointType
    items: list[BatchItemResult]


# ---------------------------------------------------------------------------
# Error response (returned on 422 / 500)
# ---------------------------------------------------------------------------
class ExtractionError(BaseModel):
    """Typed error response for unreadable or invalid image uploads."""
    error: str = Field(..., description="'extraction_failed' or 'partial_extraction'")
    reason: str = Field(..., description="Human-readable explanation of what went wrong")
    document_type: DocumentType | None = None
