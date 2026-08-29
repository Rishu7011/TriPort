"""
Pydantic schemas for the Risk Scoring Engine.

CONCEPT:
The risk engine is the "brain" that combines all four module signals into a
single, explainable risk assessment. It receives pre-computed, normalized
sub-scores from the orchestrator and outputs a 0–100 score, a risk band, and
a human-readable reasons list.

WHY separate request/response?
The orchestrator assembles sub-scores from all upstream services and sends
one structured request to the risk engine. This keeps the scoring formula
inside the risk engine (one place to tune weights) while the orchestrator
owns data collection.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Risk Band — maps final score ranges to named threat levels
# ---------------------------------------------------------------------------
class RiskBand(str, Enum):
    """
    Named risk levels displayed to border officers.
    CRITICAL requires immediate escalation; LOW can proceed normally.
    """
    LOW = "low"           # 0–30
    MEDIUM = "medium"     # 31–60
    HIGH = "high"         # 61–80
    CRITICAL = "critical" # 81–100


# ---------------------------------------------------------------------------
# Sub-score inputs — one block per upstream module
# ---------------------------------------------------------------------------
class ValidationSubScore(BaseModel):
    """Sub-score input from the Validation Service (Module 2)."""
    total_rules: int = Field(default=0, description="Total rules evaluated")
    failed_rules: int = Field(default=0, description="Number of rules that failed")
    failed_rule_names: list[str] = Field(
        default_factory=list,
        description="Names of failed rules for reason generation",
    )
    rule_details: dict[str, str] = Field(
        default_factory=dict,
        description="Map of rule_name → detail string for failed rules",
    )
    # Pre-computed normalized score (0.0 = all pass / low risk, 1.0 = all fail)
    # If None, orchestrator passes raw counts and scoring.py computes it
    normalized_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional pre-normalized score; computed from counts if None",
    )


class TamperingSubScore(BaseModel):
    """Sub-score input from the Tampering Detection Service (Module 3)."""
    overall_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall tampering anomaly score (0.0–1.0)",
    )
    flagged: bool = Field(default=False, description="True if any check fired above threshold")
    flagged_checks: list[str] = Field(
        default_factory=list,
        description="Names of check types that were flagged (ela, metadata, boundary, stamp_match)",
    )
    check_details: dict[str, str] = Field(
        default_factory=dict,
        description="Map of check_type → detail string for flagged checks",
    )


class FaceSubScore(BaseModel):
    """Sub-score input from the Face Verification Service (Module 4)."""
    # 1:1 match score — higher cosine_similarity = better match = lower risk
    cosine_similarity: float | None = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Cosine similarity from 1:1 verification (None if not run)",
    )
    matched: bool | None = Field(
        None,
        description="Whether 1:1 verification passed the threshold (None if not run)",
    )
    # 1:N deduplication
    has_duplicates: bool = Field(
        default=False,
        description="True if this face matched a previously stored document",
    )
    dedup_hit_count: int = Field(
        default=0,
        description="Number of matching historical records found",
    )


class BlacklistSubScore(BaseModel):
    """Sub-score input from blacklist lookup."""
    hit: bool = Field(default=False, description="True if any blacklist match was found")
    matched_fields: list[str] = Field(
        default_factory=list,
        description="Which fields (name, doc_number, etc.) produced the blacklist hit",
    )
    severity: str | None = Field(
        None,
        description="Severity tier of the hit: 'watch', 'suspect', 'banned' (None if no hit)",
    )


# ---------------------------------------------------------------------------
# Full risk score request — sent by orchestrator to risk engine
# ---------------------------------------------------------------------------
class RiskScoreRequest(BaseModel):
    """
    All sub-score inputs assembled by the orchestrator from the four upstream services.
    The risk engine uses these to compute the final weighted score.
    """
    document_id: str = Field(..., description="Document UUID being scored")
    validation: ValidationSubScore = Field(default_factory=ValidationSubScore)
    tampering: TamperingSubScore = Field(default_factory=TamperingSubScore)
    face: FaceSubScore = Field(default_factory=FaceSubScore)
    blacklist: BlacklistSubScore = Field(default_factory=BlacklistSubScore)
    # Signals which upstream services were unavailable (degraded pipeline)
    degraded_modules: list[str] = Field(
        default_factory=list,
        description="Module names that failed and were skipped (score estimated for these)",
    )


# ---------------------------------------------------------------------------
# Risk score response — returned by risk engine + persisted in risk_scores table
# ---------------------------------------------------------------------------
class SubScoreBreakdown(BaseModel):
    """Breakdown of how each module contributed to the final score."""
    validation_score: float = Field(..., description="Normalized validation sub-score (0–1)")
    tampering_score: float = Field(..., description="Normalized tampering sub-score (0–1)")
    face_match_score: float = Field(..., description="Normalized face risk sub-score (0–1)")
    blacklist_hit_score: float = Field(..., description="Blacklist contribution (0 or 1, tiered)")
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "validation": 0.30,
            "tampering": 0.35,
            "face": 0.20,
            "blacklist": 0.15,
        },
        description="Weights applied to each sub-score",
    )


class RiskScoreResponse(BaseModel):
    """
    Complete risk assessment output for a document scan.
    Always includes a score, band, reasons list, and sub-score breakdown.
    Never returned without reasons — a bare number tells an officer nothing.
    """
    document_id: str
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Final risk score, 0 (cleanest) to 100 (most suspicious)",
    )
    band: RiskBand = Field(..., description="Named risk level: low/medium/high/critical")
    reasons: list[str] = Field(
        ...,
        description="Plain-language list explaining every risk signal that fired",
    )
    sub_scores: SubScoreBreakdown
    degraded: bool = Field(
        default=False,
        description="True if one or more upstream modules failed — score is an estimate",
    )
    degraded_modules: list[str] = Field(
        default_factory=list,
        description="Which modules were unavailable during this scoring run",
    )
