"""
Orchestrator Pydantic Schemas — Pipeline requests and responses.

These schemas are the "face" of the orchestrator to the outside world:
  - UploadRequest: multipart form data isn't modeled here (FastAPI handles
    that via File/Form params), but the structured pipeline result is.
  - PipelineResult: aggregated output from all five downstream services.
  - DecisionRequest: officer decision (approve/flag/reject) body.
"""

from typing import Any
from pydantic import BaseModel, Field

from backend.ocr_service.schemas.extraction import ExtractionResponse
from backend.validation_service.schemas.validation import ValidationResponse
from backend.tampering_service.schemas.tampering import TamperingResponse
from backend.face_service.schemas.face import FullFaceVerificationResponse
from backend.risk_engine.schemas.risk import RiskScoreResponse


from backend.cross_checkpoint_service.schemas.cross_checkpoint import ClusterAnalysisResponse


# ---------------------------------------------------------------------------
# Pipeline result — aggregated output from all modules
# ---------------------------------------------------------------------------
class ServiceStatus(BaseModel):
    """Status of a single downstream service call within the pipeline."""
    available: bool = Field(..., description="True if the service responded successfully")
    error: str | None = Field(None, description="Error message if service call failed")


class PipelineServiceStatuses(BaseModel):
    """Per-service availability flags for a pipeline run."""
    ocr: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    validation: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    tampering: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    face: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    cross_checkpoint: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    risk_engine: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))
    audit_ledger: ServiceStatus = Field(default_factory=lambda: ServiceStatus(available=True))


class PipelineResult(BaseModel):
    """
    Aggregated result of a full document pipeline run.
    Returned by POST /api/v1/documents/upload.
    """
    document_id: str
    degraded: bool = Field(
        default=False,
        description="True if one or more services failed — partial result",
    )
    service_statuses: PipelineServiceStatuses = Field(
        default_factory=PipelineServiceStatuses,
    )
    extraction: ExtractionResponse | None = None
    validation: ValidationResponse | None = None
    tampering: TamperingResponse | None = None
    face: FullFaceVerificationResponse | None = None
    cross_checkpoint: ClusterAnalysisResponse | None = None
    risk_score: RiskScoreResponse | None = None



# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------
class UploadResponse(BaseModel):
    """
    Immediate response after POST /api/v1/documents/upload or GET /documents/{id}/pipeline.
    Contains the full pipeline result and image URLs.
    """
    document_id: str
    status: str = Field(
        default="complete",
        description="'complete' | 'degraded' | 'failed' | 'pending_biometric'",
    )
    pipeline: PipelineResult
    doc_image_url: str | None = None
    doc_face_crop_url: str | None = None
    live_image_url: str | None = None
    inspection_status: str | None = None


# ---------------------------------------------------------------------------
# Officer decision
# ---------------------------------------------------------------------------
class DecisionChoice(str):
    APPROVE = "approve"
    FLAG = "flag"
    REJECT = "reject"


class DecisionRequest(BaseModel):
    """Body for POST /api/v1/documents/{id}/decision."""
    officer_id: str = Field(..., description="UUID of the officer making the decision")
    decision: str = Field(
        ...,
        pattern="^(approve|flag|reject)$",
        description="Officer verdict: approve | flag | reject",
    )
    notes: str | None = Field(
        None,
        description="Optional free-text notes — recorded in the audit ledger",
    )


class DecisionResponse(BaseModel):
    """Response after recording an officer decision."""
    document_id: str
    decision: str
    recorded: bool = Field(default=True)
    ledger_sequence: int | None = Field(
        None,
        description="Audit ledger sequence number for this decision event",
    )


# ---------------------------------------------------------------------------
# Document not found error body
# ---------------------------------------------------------------------------
class DocumentNotFoundError(BaseModel):
    """Standard 404 error body for unknown document IDs (cross-cutting rule #4)."""
    error: str = "document_not_found"
    document_id: str
