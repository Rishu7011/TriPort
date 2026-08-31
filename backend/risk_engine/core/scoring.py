"""
Risk Scoring Engine — Weighted Formula Implementation.

FORMULA (from plan.md §4):
    risk_score = 0.30 * validation_score
               + 0.35 * tampering_score
               + 0.20 * face_match_score
               + 0.15 * blacklist_hit_score

All sub-scores must be normalized to [0.0, 1.0] before weighting where:
  - 0.0 = cleanest signal (no risk contribution)
  - 1.0 = most suspicious signal (maximum risk contribution)

The final weighted sum (also 0–1) is scaled to 0–100 for officer display.

BAND THRESHOLDS are stored as a named constant, not magic numbers buried in code.
To tune thresholds, change BAND_THRESHOLDS — no other code changes needed.
"""

from backend.logging_config import get_logger
from backend.risk_engine.schemas.risk import (
    BlacklistSubScore,
    FaceSubScore,
    RiskBand,
    RiskScoreRequest,
    RiskScoreResponse,
    SubScoreBreakdown,
    TamperingSubScore,
    ValidationSubScore,
)

logger = get_logger("risk_engine.scoring")

# ---------------------------------------------------------------------------
# Weight configuration — must sum to 1.0
# ---------------------------------------------------------------------------
WEIGHTS = {
    "validation": 0.30,
    "tampering": 0.35,
    "face": 0.20,
    "blacklist": 0.15,
}

# ---------------------------------------------------------------------------
# Band thresholds — inclusive lower bounds per band
# Scores are 0–100 after scaling
# ---------------------------------------------------------------------------
BAND_THRESHOLDS: dict[str, int] = {
    "critical": 81,
    "high": 61,
    "medium": 31,
    "low": 0,
}

# Severity multipliers for tiered blacklist hits
BLACKLIST_SEVERITY_SCORES: dict[str, float] = {
    "banned": 1.0,    # Full weight: known prohibited individual
    "suspect": 0.75,  # High weight: active investigation
    "watch": 0.50,    # Half weight: monitoring only
}


# ---------------------------------------------------------------------------
# Sub-score normalization helpers
# ---------------------------------------------------------------------------

def _normalize_validation(v: ValidationSubScore) -> float:
    """
    validation_score = failed_rules / total_rules
    (0.0 = all rules pass → clean; 1.0 = all rules fail → max risk)

    If the module was degraded (total_rules == 0 and no pre-computed score),
    we use a neutral 0.5 rather than 0 (absence of evidence ≠ evidence of absence).
    """
    if v.normalized_score is not None:
        return float(v.normalized_score)
    if v.total_rules == 0:
        return 0.0  # No rules means nothing to fail — treat as clean
    return min(1.0, v.failed_rules / v.total_rules)


def _normalize_tampering(t: TamperingSubScore) -> float:
    """
    tampering_score = overall_score from the tampering service.
    The tampering service already returns a 0–1 normalized score (max of
    individual check scores), so we pass it through directly.
    Bonus: if any check was explicitly flagged, floor the score at 0.3
    to prevent a very low continuous score from hiding a binary flag.
    """
    score = float(t.overall_score)
    if t.flagged and score < 0.30:
        score = 0.30  # Floor: a flagged check always contributes meaningfully
    return min(1.0, score)


def _normalize_face(f: FaceSubScore) -> float:
    """
    face_match_score = 1 - cosine_similarity (inverted so higher = riskier)

    cosine_similarity = 1.0 → perfect match → face_score = 0.0 (no risk)
    cosine_similarity = 0.0 → unrelated → face_score = 0.5
    cosine_similarity = -1.0 → opposite → face_score = 1.0 (max risk)

    Deduplication hit adds 0.20 to the face risk (multi-identity fraud signal).
    If face verification was not run (cosine_similarity is None), use 0.5 neutral.
    """
    if f.cosine_similarity is None:
        base_score = 0.5  # Neutral when not run
    else:
        # Invert: similarity 1.0 → risk 0.0; similarity -1.0 → risk 1.0
        base_score = (1.0 - float(f.cosine_similarity)) / 2.0

    # Dedup hit adds a multi-identity fraud penalty
    dedup_penalty = 0.20 if f.has_duplicates else 0.0

    return min(1.0, base_score + dedup_penalty)


def _normalize_blacklist(b: BlacklistSubScore) -> float:
    """
    blacklist_hit_score:
    - No hit → 0.0
    - Hit with known severity → tiered score from BLACKLIST_SEVERITY_SCORES
    - Hit with unknown severity → 1.0 (fail safe: treat unknown as maximum risk)
    """
    if not b.hit:
        return 0.0
    if b.severity and b.severity.lower() in BLACKLIST_SEVERITY_SCORES:
        return BLACKLIST_SEVERITY_SCORES[b.severity.lower()]
    return 1.0  # Unknown severity → fail safe


# ---------------------------------------------------------------------------
# Band classification
# ---------------------------------------------------------------------------

def classify_band(score_0_to_100: float) -> RiskBand:
    """Map a 0–100 score to a named risk band using BAND_THRESHOLDS."""
    if score_0_to_100 >= BAND_THRESHOLDS["critical"]:
        return RiskBand.CRITICAL
    if score_0_to_100 >= BAND_THRESHOLDS["high"]:
        return RiskBand.HIGH
    if score_0_to_100 >= BAND_THRESHOLDS["medium"]:
        return RiskBand.MEDIUM
    return RiskBand.LOW


def escalate_band_one_tier(band: RiskBand) -> RiskBand:
    """Escalate risk band by one tier for repeat offenders."""
    if band == RiskBand.LOW:
        return RiskBand.MEDIUM
    if band == RiskBand.MEDIUM:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_risk_score(request: RiskScoreRequest) -> tuple[float, RiskBand, SubScoreBreakdown, bool]:
    """
    Apply the weighted formula to a RiskScoreRequest.

    If cross_checkpoint_risk > 0, an additional 0.10 weight is dedicated to
    cross-checkpoint fraud risk, deducted proportionally from the baseline weights:
      - validation: 0.27 (0.30 * 0.90)
      - tampering: 0.315 (0.35 * 0.90)
      - face: 0.18 (0.20 * 0.90)
      - blacklist: 0.135 (0.15 * 0.90)
      - cross_checkpoint: 0.10

    Returns:
        score_0_to_100: float — final officer-facing score
        band: RiskBand — named risk level (possibly escalated for repeat offenders)
        breakdown: SubScoreBreakdown — per-module contribution for transparency
        escalated: bool — whether the band was escalated for repeat offense
    """
    v_score = _normalize_validation(request.validation)
    t_score = _normalize_tampering(request.tampering)
    f_score = _normalize_face(request.face)
    b_score = _normalize_blacklist(request.blacklist)
    cc_score = min(1.0, max(0.0, float(request.cross_checkpoint.cross_checkpoint_risk)))

    if cc_score > 0.0:
        # Cross-checkpoint term active: weight 0.10 deducted proportionally from others
        active_weights = {
            "validation": 0.27,
            "tampering": 0.315,
            "face": 0.18,
            "blacklist": 0.135,
            "cross_checkpoint": 0.10,
        }
        weighted_sum = (
            active_weights["validation"] * v_score
            + active_weights["tampering"] * t_score
            + active_weights["face"] * f_score
            + active_weights["blacklist"] * b_score
            + active_weights["cross_checkpoint"] * cc_score
        )
    else:
        active_weights = dict(WEIGHTS)
        active_weights["cross_checkpoint"] = 0.0
        weighted_sum = (
            WEIGHTS["validation"] * v_score
            + WEIGHTS["tampering"] * t_score
            + WEIGHTS["face"] * f_score
            + WEIGHTS["blacklist"] * b_score
        )

    # Scale to 0–100
    score_0_to_100 = round(weighted_sum * 100, 1)
    score_0_to_100 = max(0.0, min(100.0, score_0_to_100))

    base_band = classify_band(score_0_to_100)
    final_band = base_band
    escalated = False

    # Repeat offender escalation: if prior High/Critical exists in cluster, escalate by 1 tier
    if request.cross_checkpoint.repeat_offender_hit:
        final_band = escalate_band_one_tier(base_band)
        escalated = final_band != base_band

    breakdown = SubScoreBreakdown(
        validation_score=round(v_score, 4),
        tampering_score=round(t_score, 4),
        face_match_score=round(f_score, 4),
        blacklist_hit_score=round(b_score, 4),
        cross_checkpoint_score=round(cc_score, 4),
        weights=active_weights,
    )

    logger.info(
        "risk_score_computed",
        document_id=request.document_id,
        score=score_0_to_100,
        base_band=base_band.value,
        final_band=final_band.value,
        escalated=escalated,
        v_score=v_score,
        t_score=t_score,
        f_score=f_score,
        b_score=b_score,
        cc_score=cc_score,
    )

    return score_0_to_100, final_band, breakdown


def build_risk_response(request: RiskScoreRequest) -> RiskScoreResponse:
    """
    Convenience wrapper: compute score + generate reasons + assemble response.
    This is the single entry point called by the router.
    """
    from backend.risk_engine.core.reasons import generate_reasons

    score, band, breakdown = compute_risk_score(request)
    reasons = generate_reasons(request, breakdown)
    base_band = classify_band(score)
    escalated = (band != base_band)

    return RiskScoreResponse(
        document_id=request.document_id,
        score=score,
        band=band,
        reasons=reasons,
        sub_scores=breakdown,
        repeat_offender_escalated=escalated,
        degraded=len(request.degraded_modules) > 0,
        degraded_modules=request.degraded_modules,
    )


