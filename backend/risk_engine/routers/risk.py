"""
Risk Scoring Router — POST /score

Accepts a structured RiskScoreRequest from the orchestrator,
runs the weighted formula, generates human-readable reasons,
and returns a complete RiskScoreResponse.
"""

from fastapi import APIRouter, HTTPException

from backend.logging_config import get_logger
from backend.risk_engine.core.scoring import build_risk_response
from backend.risk_engine.schemas.risk import RiskScoreRequest, RiskScoreResponse

logger = get_logger("risk_engine.router")

router = APIRouter(prefix="/score", tags=["risk"])


@router.post("/", response_model=RiskScoreResponse)
async def score(request: RiskScoreRequest) -> RiskScoreResponse:
    """
    Compute a weighted risk score from all upstream module signals.

    Accepts a RiskScoreRequest containing normalized sub-scores from:
      - Validation Service (Module 2)
      - Tampering Detection Service (Module 3)
      - Face Verification Service (Module 4)
      - Blacklist lookup

    Returns a RiskScoreResponse with:
      - score: 0–100
      - band: low / medium / high / critical
      - reasons: plain-language list of every fired signal
      - sub_scores: per-module breakdown for transparency
    """
    try:
        response = build_risk_response(request)
        logger.info(
            "score_endpoint_success",
            document_id=request.document_id,
            score=response.score,
            band=response.band.value,
        )
        return response
    except Exception as exc:
        logger.error(
            "score_endpoint_error",
            document_id=request.document_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Risk scoring failed: {exc}") from exc
