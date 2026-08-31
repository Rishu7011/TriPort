"""
Reason Generator — Plain-language risk explanation for border officers.

CONCEPT:
A bare risk score (e.g. "72/100") tells an officer nothing actionable.
This module converts every fired signal into a concise, specific sentence
that an officer can act on immediately:

  ✗ "MRZ checksum failed on field: date_of_birth"
  ✗ "Document expired on 2019-01-01 (rule: expiry_not_passed)"
  ✗ "ELA compression analysis detected localized editing in photo region"
  ✗ "Face match confidence 41% — below 60% threshold for verification"
  ✗ "Individual matched on BANNED blacklist — matched field: passport_number"
  ✓ "No risk signals detected — document appears genuine"

RULE:
Every flagged check MUST produce at least one reason string.
Clean checks produce nothing (silence = clean).
The caller always gets a non-empty reasons list (at minimum the "no signals" message).
"""

from backend.logging_config import get_logger
from backend.risk_engine.schemas.risk import (
    RiskScoreRequest,
    SubScoreBreakdown,
)

logger = get_logger("risk_engine.reasons")

# Score thresholds below which we generate face-match warnings
FACE_SIMILARITY_WARN_THRESHOLD = 0.60   # Below this → "face not matched"
FACE_SIMILARITY_LOW_THRESHOLD = 0.40    # Below this → "face match very low"

# Tampering score threshold for generating a reason even without a named check
TAMPERING_SCORE_WARN_THRESHOLD = 0.30


def generate_reasons(
    request: RiskScoreRequest,
    breakdown: SubScoreBreakdown,
) -> list[str]:
    """
    Generate a plain-language reasons list from all upstream module signals.

    Args:
        request: The full RiskScoreRequest with sub-score inputs.
        breakdown: The computed normalized sub-scores for context.

    Returns:
        List of human-readable reason strings.
        Always non-empty — returns a "no signals" message if everything is clean.
    """
    reasons: list[str] = []

    # ── 1. Validation reasons ────────────────────────────────────────────────
    val = request.validation
    if val.failed_rules:
        for rule_name in val.failed_rule_names:
            detail = val.rule_details.get(rule_name, "")
            if detail:
                reasons.append(f"Validation rule failed — {rule_name}: {detail}")
            else:
                reasons.append(f"Validation rule failed — {rule_name}")

    # Surface MRZ checksum failures specifically (they're especially strong signals)
    for rule_name in val.failed_rule_names:
        if "checksum" in rule_name.lower() or "mrz" in rule_name.lower():
            reasons.append(
                f"CRITICAL: MRZ integrity check failed ({rule_name}) — "
                "document data may have been altered after issuance."
            )

    # ── 2. Tampering reasons ─────────────────────────────────────────────────
    tamp = request.tampering
    check_display_names = {
        "ela": "ELA (Error Level Analysis) compression anomaly",
        "metadata": "EXIF/metadata forensics",
        "boundary": "Photo region boundary discontinuity analysis",
        "stamp_match": "Stamp/seal verification",
        "cnn": "CNN tampering classifier",
    }

    for check_name in tamp.flagged_checks:
        display = check_display_names.get(check_name.lower(), check_name)
        detail = tamp.check_details.get(check_name, "")
        if detail:
            reasons.append(f"Tampering detected — {display}: {detail}")
        else:
            reasons.append(f"Tampering detected — {display} flagged anomaly above threshold.")

    # Even if no named checks fired, a high tampering score still warrants a note
    if (
        not tamp.flagged_checks
        and breakdown.tampering_score >= TAMPERING_SCORE_WARN_THRESHOLD
    ):
        reasons.append(
            f"Elevated tampering anomaly score ({breakdown.tampering_score:.2f}) "
            "without a specific check firing — manual review recommended."
        )

    # ── 3. Face verification reasons ─────────────────────────────────────────
    face = request.face
    if face.cosine_similarity is not None:
        sim = face.cosine_similarity
        if sim < FACE_SIMILARITY_LOW_THRESHOLD:
            reasons.append(
                f"Face match FAILED — cosine similarity {sim:.2f} is far below "
                f"the {FACE_SIMILARITY_WARN_THRESHOLD:.2f} threshold. "
                "Person at checkpoint likely does not match document photo."
            )
        elif sim < FACE_SIMILARITY_WARN_THRESHOLD:
            reasons.append(
                f"Face match LOW CONFIDENCE — cosine similarity {sim:.2f} "
                f"(threshold: {FACE_SIMILARITY_WARN_THRESHOLD:.2f}). "
                "Recommend secondary verification."
            )
    elif face.cosine_similarity is None and breakdown.face_match_score > 0.0:
        reasons.append(
            "Face verification was not performed (live capture not provided). "
            "Manual identity check required."
        )

    if face.has_duplicates:
        hit_word = "hit" if face.dedup_hit_count == 1 else "hits"
        reasons.append(
            f"MULTI-IDENTITY ALERT — this face biometric matched "
            f"{face.dedup_hit_count} previously stored document {hit_word}. "
            "Individual may be using multiple identity documents."
        )

    # ── 4. Blacklist reasons ─────────────────────────────────────────────────
    bl = request.blacklist
    if bl.hit:
        severity_label = bl.severity.upper() if bl.severity else "UNKNOWN SEVERITY"
        matched_str = (
            f" (matched field(s): {', '.join(bl.matched_fields)})"
            if bl.matched_fields
            else ""
        )
        reasons.append(
            f"BLACKLIST HIT [{severity_label}]{matched_str} — "
            "individual or document is registered on the watchlist. "
            "Do not allow passage without supervisor authorization."
        )

    # ── 5. Cross-Checkpoint & Multi-Identity reasons (Module 5) ───────────────
    cc = request.cross_checkpoint
    if cc.flags:
        for flag_name in cc.flags:
            if "name_mismatch" in flag_name.lower():
                reasons.append(
                    "MULTI-IDENTITY ALERT — same facial biometric observed under multiple "
                    "conflicting names across distinct border checkpoints."
                )
            elif "document_number_mismatch" in flag_name.lower():
                reasons.append(
                    "MULTIPLE TRAVEL DOCUMENTS — same individual holds distinct passport "
                    "or ID numbers across historical border crossings."
                )
            elif "impossible_travel" in flag_name.lower():
                reasons.append(
                    "IMPOSSIBLE TRAVEL VELOCITY — traveler observed at multiple distinct "
                    "checkpoints within an implausibly short time window."
                )
            elif "repeat_offender" in flag_name.lower():
                reasons.append(
                    f"REPEAT OFFENDER HIT — traveler cluster has {cc.prior_critical_or_high_count} "
                    "prior High/Critical risk assessment(s). Risk tier auto-escalated."
                )
            else:
                reasons.append(f"Cross-checkpoint anomaly flag raised: {flag_name}")

    if cc.flag_details:
        for detail_str in cc.flag_details:
            if detail_str not in reasons:
                reasons.append(f"Cross-checkpoint detail: {detail_str}")

    if cc.repeat_offender_hit and not any("REPEAT OFFENDER" in r for r in reasons):
        reasons.append(
            "REPEAT OFFENDER ALERT — prior severe infractions on record for this individual. "
            "Risk band auto-escalated by one tier."
        )

    # ── 6. Degraded module warnings ──────────────────────────────────────────
    for module in request.degraded_modules:
        reasons.append(
            f"WARNING: {module} service was unavailable during this scan. "
            "Risk score is an estimate — reprocess when service is restored."
        )

    # ── 7. Clean document — always return something ───────────────────────────
    if not reasons:
        reasons.append(
            "No risk signals detected across all verification checks. "
            "Document appears genuine and individual identity is verified."
        )

    logger.info(
        "reasons_generated",
        document_id=request.document_id,
        reason_count=len(reasons),
    )
    return reasons

