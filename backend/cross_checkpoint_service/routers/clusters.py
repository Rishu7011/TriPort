"""
Clusters Router — FastAPI endpoints for Cross-Checkpoint Multi-Identity Analytics.
"""

from fastapi import APIRouter, HTTPException, status

from backend.logging_config import get_logger
from backend.cross_checkpoint_service.core.face_graph import (
    analyze_cluster,
    get_cluster_history,
    register_cluster_document,
)
from backend.cross_checkpoint_service.schemas.cross_checkpoint import (
    ClusterAnalysisRequest,
    ClusterAnalysisResponse,
    ClusterDocument,
    ClusterHistoryResponse,
    ClusterSeedRequest,
)

logger = get_logger("cross_checkpoint_service.router")

router = APIRouter(prefix="/api/v1/clusters", tags=["Cross-Checkpoint Multi-Identity"])


@router.get(
    "/{person_cluster_id}",
    response_model=ClusterHistoryResponse,
    summary="Retrieve full cross-checkpoint dossier for a person cluster",
)
async def get_cluster_dossier(person_cluster_id: str) -> ClusterHistoryResponse:
    """
    Fetch comprehensive cross-checkpoint history and anomaly flags for a person cluster UUID.
    Used by the Central Command Dashboard.
    """
    try:
        response = await get_cluster_history(person_cluster_id)
        return response
    except Exception as exc:
        logger.error("Failed to retrieve cluster history", cluster_id=person_cluster_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query cluster history: {exc}",
        ) from exc


@router.post(
    "/analyze",
    response_model=ClusterAnalysisResponse,
    summary="Analyze a person cluster for cross-checkpoint fraud and repeat offenses",
)
async def analyze_cluster_endpoint(request: ClusterAnalysisRequest) -> ClusterAnalysisResponse:
    """
    Evaluate real-time multi-identity flags, name discrepancies, velocity anomalies,
    and repeat-offender risk escalation for a cluster during document scanning.
    """
    current_doc: ClusterDocument | None = None
    if request.current_document_id:
        current_doc = ClusterDocument(
            document_id=request.current_document_id,
            checkpoint_type=request.current_checkpoint_type,
            checkpoint_id=request.current_checkpoint_id,
            uploaded_at=request.current_timestamp,
            name=request.current_name,
            document_number=request.current_document_number,
            nationality=request.current_nationality,
            date_of_birth=request.current_date_of_birth,
            risk_score=request.current_risk_score,
            risk_band=request.current_risk_band,
        )

    try:
        response = await analyze_cluster(
            person_cluster_id=request.person_cluster_id,
            current_doc=current_doc,
            current_risk_band=request.current_risk_band or "low",
            seed_documents=request.seed_documents,
        )
        return response
    except Exception as exc:
        logger.error("Failed to analyze cluster", cluster_id=request.person_cluster_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cluster analysis failed: {exc}",
        ) from exc


@router.post(
    "/seed",
    summary="Seed synthetic cross-checkpoint document records for testing and demos",
)
async def seed_cluster_document(request: ClusterSeedRequest) -> dict:
    """Register a document scan into a person cluster for simulation."""
    register_cluster_document(request.person_cluster_id, request.document)
    return {
        "status": "success",
        "person_cluster_id": request.person_cluster_id,
        "document_id": request.document.document_id,
    }
