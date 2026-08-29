"""
Pydantic schemas for the Tampering Detection Service.

Defines schemas for Error Level Analysis (ELA), EXIF metadata forensics,
photo boundary discontinuity/noise analysis, and stamp verification.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TamperingCheckType(str, Enum):
    """Types of forensic tampering checks performed."""
    ELA = "ela"
    METADATA = "metadata"
    BOUNDARY = "boundary"
    STAMP_MATCH = "stamp_match"
    CNN = "cnn"


class TamperingCheckResult(BaseModel):
    """Result of an individual tampering detection check."""
    check_type: TamperingCheckType = Field(..., description="Check identifier")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Anomaly score (0.0 = clean, 1.0 = highly suspicious/tampered)",
    )
    flagged: bool = Field(..., description="True if check exceeded anomaly threshold")
    detail: str = Field(..., description="Explainable description of findings")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Check-specific forensic metadata (e.g. EXIF tags, edge variance)",
    )


class TamperingResponse(BaseModel):
    """Aggregated tampering detection report for a document scan."""
    document_id: str | None = Field(None, description="Document UUID if known")
    flagged: bool = Field(..., description="True if any forensic check flagged tampering")
    tampering_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall weighted tampering confidence score (0.0 to 1.0)",
    )
    checks: list[TamperingCheckResult] = Field(
        ...,
        description="Detailed results for each forensic module",
    )
    ela_heatmap_base64: str | None = Field(
        None,
        description="Base64-encoded PNG ELA heatmap visualizing compression anomalies",
    )
    ela_heatmap_url: str | None = Field(
        None,
        description="MinIO/S3 object storage URL for the ELA heatmap if persisted",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during analysis",
    )
