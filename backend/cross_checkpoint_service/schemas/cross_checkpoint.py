"""
Pydantic schemas for the Cross-Checkpoint Service (Module 5).

Covers:
  - Cluster document summaries and metadata
  - Cross-checkpoint fraud flags (name mismatch, doc number mismatch, impossible travel, repeat offender)
  - Full cluster history retrieval and real-time cross-checkpoint risk analysis
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CrossCheckpointFlagType(str, Enum):
    """Types of cross-checkpoint and multi-identity fraud signals."""
    NAME_MISMATCH = "name_mismatch_across_cluster"
    DOCUMENT_NUMBER_MISMATCH = "document_number_mismatch_across_cluster"
    DOB_MISMATCH = "dob_mismatch_across_cluster"
    NATIONALITY_MISMATCH = "nationality_mismatch_across_cluster"
    IMPOSSIBLE_TRAVEL = "impossible_travel_detected"
    REPEAT_OFFENDER = "repeat_offender_hit"


class CrossCheckpointFlag(BaseModel):
    """Individual anomaly flag detected across the person's identity cluster."""
    flag_type: CrossCheckpointFlagType = Field(..., description="Machine-readable fraud flag type")
    severity: str = Field(default="high", description="Severity level: low, medium, high, critical")
    detail: str = Field(..., description="Human-readable explanation of why this flag was raised")
    related_document_ids: list[str] = Field(
        default_factory=list,
        description="Document UUIDs involved in this conflicting signal",
    )
    timestamp: str | None = Field(None, description="ISO timestamp of when the condition was observed")


class ClusterDocument(BaseModel):
    """Metadata for an individual document scan associated with a person cluster."""
    document_id: str = Field(..., description="Unique document UUID")
    checkpoint_type: str | None = Field(None, description="Checkpoint type: airport, land_border, sea")
    checkpoint_id: str | None = Field(None, description="Specific checkpoint identifier or port name")
    checkpoint_name: str | None = Field(None, description="Human-readable name of checkpoint location")
    uploaded_at: str | None = Field(None, description="ISO timestamp of scan")
    document_type: str | None = Field(None, description="Type of document (passport, visa, etc.)")
    name: str | None = Field(None, description="Holder name extracted from document")
    document_number: str | None = Field(None, description="Document or passport number")
    nationality: str | None = Field(None, description="Nationality code from document")
    date_of_birth: str | None = Field(None, description="Date of birth from document")
    risk_score: float | None = Field(None, description="Final risk score computed for this scan (0-100)")
    risk_band: str | None = Field(None, description="Risk band: low, medium, high, critical")
    similarity: float | None = Field(None, description="Biometric similarity to the cluster anchor face")


class ClusterHistoryResponse(BaseModel):
    """Full historical dossier for a person cluster across all border checkpoints."""
    person_cluster_id: str = Field(..., description="Unique UUID identifying this individual's face cluster")
    total_documents: int = Field(..., description="Count of distinct document scans tied to this face")
    documents: list[ClusterDocument] = Field(default_factory=list, description="All associated document scans")
    flags: list[CrossCheckpointFlag] = Field(default_factory=list, description="All active multi-identity flags")
    cross_checkpoint_risk: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite cross-checkpoint risk score (0.0=clean, 1.0=severe fraud)",
    )
    repeat_offender_hit: bool = Field(
        default=False,
        description="True if individual has prior high or critical risk scans",
    )
    highest_prior_risk_band: str | None = Field(None, description="Highest prior risk tier on record")
    highest_prior_risk_score: float | None = Field(None, description="Highest prior risk score on record")
    recommended_escalation: bool = Field(
        default=False,
        description="True if the current scan should auto-escalate its risk band",
    )
    summary: str = Field(..., description="Executive narrative summary of cross-checkpoint findings")


class ClusterAnalysisRequest(BaseModel):
    """Request payload to analyze cross-checkpoint anomalies for a new document scan."""
    person_cluster_id: str = Field(..., description="Person cluster UUID to evaluate")
    current_document_id: str | None = Field(None, description="Document ID currently being evaluated")
    current_checkpoint_type: str | None = Field(None, description="Current checkpoint type")
    current_checkpoint_id: str | None = Field(None, description="Current checkpoint location ID")
    current_timestamp: str | None = Field(None, description="Current scan timestamp (ISO string)")
    current_name: str | None = Field(None, description="Holder name extracted from current document")
    current_document_number: str | None = Field(None, description="Current document number")
    current_nationality: str | None = Field(None, description="Current nationality code")
    current_date_of_birth: str | None = Field(None, description="Current date of birth")
    current_risk_score: float | None = Field(None, description="Initial risk score before cross-checkpoint adjust")
    current_risk_band: str | None = Field(None, description="Initial risk band before cross-checkpoint adjust")
    seed_documents: list[ClusterDocument] | None = Field(
        None,
        description="Optional list of prior documents in cluster for in-memory / testing analysis",
    )


class ClusterAnalysisResponse(BaseModel):
    """Results of cross-checkpoint graph and repeat-offender analysis."""
    person_cluster_id: str = Field(..., description="Cluster UUID evaluated")
    documents_in_cluster: list[ClusterDocument] = Field(
        default_factory=list,
        description="All documents in this cluster",
    )
    flags: list[CrossCheckpointFlag] = Field(
        default_factory=list,
        description="Detected cross-checkpoint fraud flags",
    )
    cross_checkpoint_risk: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cross-checkpoint risk contribution score (0.0 to 1.0)",
    )
    repeat_offender_hit: bool = Field(
        default=False,
        description="True if prior high/critical offenses exist",
    )
    escalate_risk_tier: bool = Field(
        default=False,
        description="True if risk band must be escalated by one tier",
    )
    original_risk_band: str | None = Field(None, description="Risk band before cross-checkpoint check")
    escalated_risk_band: str | None = Field(None, description="Updated risk band after escalation")
    prior_critical_or_high_count: int = Field(
        default=0,
        description="Number of prior High or Critical scans",
    )
    detail: str = Field(..., description="Human-readable decision explanation")


class ClusterSeedRequest(BaseModel):
    """Payload to register a synthetic document record into a cluster for testing/demos."""
    person_cluster_id: str
    document: ClusterDocument
