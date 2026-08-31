"""
Repeat Offender Engine — Historical Cluster Threat Tracking & Risk Escalation.

CONCEPT:
A traveler who previously attempted border crossing with a fraudulent or high-risk
document poses a heightened risk when attempting another crossing at any checkpoint.

This module:
  1. Inspects all prior document records linked to a `person_cluster_id`.
  2. Detects if the individual has prior 'High' or 'Critical' risk scores.
  3. Triggers the `repeat_offender_hit` flag on the current scan.
  4. Auto-escalates the current risk band by one tier (e.g. Medium → High, High → Critical).
  5. Formats structured audit events with event type `REPEAT_OFFENDER_FLAG`.
"""

from typing import Any
from backend.logging_config import get_logger
from backend.cross_checkpoint_service.schemas.cross_checkpoint import ClusterDocument

logger = get_logger("cross_checkpoint_service.repeat_offender")

TIER_ESCALATION: dict[str, str] = {
    "low": "medium",
    "medium": "high",
    "high": "critical",
    "critical": "critical",
}

SEVERITY_ORDER: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def check_repeat_offender(
    documents: list[ClusterDocument],
    current_document_id: str | None = None,
    current_risk_band: str | None = "low",
) -> tuple[bool, str | None, float | None, bool, str | None, list[str]]:
    """
    Evaluate cluster history to detect prior severe offenses and determine band escalation.

    Args:
        documents: All documents associated with this person cluster.
        current_document_id: Optional ID of the document currently being scanned to exclude.
        current_risk_band: Initial risk band of the current scan before escalation.

    Returns:
        tuple: (
            is_repeat_offender: bool,
            highest_prior_band: str | None,
            highest_prior_score: float | None,
            escalate_risk_tier: bool,
            escalated_risk_band: str | None,
            prior_offense_details: list[str]
        )
    """
    prior_docs = [
        d for d in documents
        if not current_document_id or str(d.document_id) != str(current_document_id)
    ]

    if not prior_docs:
        return False, None, None, False, current_risk_band, []

    prior_offenses = []
    highest_severity_val = 0
    highest_prior_band: str | None = None
    highest_prior_score: float | None = None

    for doc in prior_docs:
        band = (doc.risk_band or "").lower().strip()
        score = doc.risk_score

        if score is not None:
            if highest_prior_score is None or score > highest_prior_score:
                highest_prior_score = score

        if band:
            sev = SEVERITY_ORDER.get(band, 0)
            if sev > highest_severity_val:
                highest_severity_val = sev
                highest_prior_band = band

        # High (61+) or Critical (81+) constitutes a severe prior offense
        if band in ["high", "critical"] or (score is not None and score >= 61.0):
            doc_id_short = str(doc.document_id)[:8]
            loc_str = doc.checkpoint_name or doc.checkpoint_type or "Unknown Checkpoint"
            time_str = f" on {doc.uploaded_at[:10]}" if doc.uploaded_at else ""
            score_str = f" (Score: {score:.1f}/100)" if score is not None else ""
            prior_offenses.append(
                f"Prior {band.upper()} risk document {doc_id_short}... at {loc_str}{time_str}{score_str}"
            )

    is_repeat_offender = len(prior_offenses) > 0
    escalate_risk_tier = is_repeat_offender
    
    current_band_clean = (current_risk_band or "low").lower().strip()
    escalated_risk_band = (
        TIER_ESCALATION.get(current_band_clean, current_band_clean)
        if escalate_risk_tier
        else current_band_clean
    )

    if is_repeat_offender:
        logger.warning(
            "REPEAT OFFENDER DETECTED",
            prior_offense_count=len(prior_offenses),
            highest_prior_band=highest_prior_band,
            highest_prior_score=highest_prior_score,
            original_band=current_risk_band,
            escalated_band=escalated_risk_band,
        )
    else:
        logger.debug("No severe prior offenses in cluster", cluster_docs=len(prior_docs))

    return (
        is_repeat_offender,
        highest_prior_band,
        highest_prior_score,
        escalate_risk_tier,
        escalated_risk_band,
        prior_offenses,
    )


def create_repeat_offender_audit_event(
    person_cluster_id: str,
    document_id: str,
    prior_offense_count: int,
    highest_prior_band: str,
    escalated_band: str,
    officer_id: str | None = None,
) -> dict[str, Any]:
    """
    Construct payload for the tamper-evident audit ledger with event type REPEAT_OFFENDER_FLAG.
    """
    return {
        "event_type": "REPEAT_OFFENDER_FLAG",
        "document_id": str(document_id),
        "person_cluster_id": str(person_cluster_id),
        "officer_id": str(officer_id) if officer_id else None,
        "payload": {
            "flag": "repeat_offender_hit",
            "prior_offense_count": prior_offense_count,
            "highest_prior_band": highest_prior_band,
            "escalated_band": escalated_band,
            "action_taken": "risk_tier_escalated_by_one_level",
        },
    }
