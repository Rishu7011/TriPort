"""
Pydantic schemas for the Face Service.

Covers:
  - 512-dim Face Embedding extraction
  - 1:1 Document Photo vs Live Capture verification
  - 1:N Multi-document deduplication and person clustering
"""

from pydantic import BaseModel, Field


class FaceEmbeddingResponse(BaseModel):
    """Result of generating a facial embedding vector."""
    face_detected: bool = Field(..., description="True if a face was located in the image")
    embedding: list[float] = Field(
        default_factory=list,
        description="512-dimensional L2-normalized facial embedding vector",
    )
    face_count: int = Field(default=1, description="Number of faces found in the image")
    detail: str = Field(default="Embedding extracted successfully", description="Status detail")


class OneToOneVerifyResponse(BaseModel):
    """Result of 1:1 face verification between document photo and live capture."""
    matched: bool = Field(..., description="True if faces belong to the same person")
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) that faces match",
    )
    cosine_similarity: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Raw cosine similarity between embedding vectors",
    )
    threshold: float = Field(
        default=0.90,
        description="Decision boundary threshold used for matching",
    )
    detail: str = Field(..., description="Human-readable decision explanation")


class DedupHit(BaseModel):
    """One matching historical record from 1:N search."""
    document_id: str = Field(..., description="UUID of the previously stored matching document")
    similarity: float = Field(..., description="Cosine similarity with the matching face record")
    person_cluster_id: str | None = Field(None, description="Shared person cluster identifier")


class DedupSearchResponse(BaseModel):
    """Result of 1:N biometric deduplication search."""
    has_duplicates: bool = Field(
        ...,
        description="True if this face matches one or more previous identity documents",
    )
    hits: list[DedupHit] = Field(
        default_factory=list,
        description="List of matching historical document records",
    )
    person_cluster_id: str = Field(
        ...,
        description="Cluster UUID linking all identity documents belonging to this individual",
    )
    detail: str = Field(..., description="Deduplication finding summary")


class LivenessResponse(BaseModel):
    """Result of real-time anti-spoofing and liveness check."""
    is_live: bool = Field(..., description="True if face passes 3D motion and EAR anti-spoofing checks")
    liveness_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated liveness score (0.0=spoof, 1.0=live)")
    detail: str = Field(..., description="Detailed explanation of liveness decision")


class BatchVerifyItem(BaseModel):
    """Result for an individual traveler in a batch verification queue."""
    item_id: str = Field(..., description="Client identifier or sequence index for this traveler")
    matched: bool = Field(..., description="True if document photo matches live capture")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Verification confidence score")
    detail: str = Field(..., description="Individual verification result summary")


class BatchVerifyResponse(BaseModel):
    """Result of bulk high-throughput disembarkation batch verification."""
    total_processed: int = Field(..., description="Total pairs processed in this batch")
    matched_count: int = Field(..., description="Number of verified matches")
    mismatch_count: int = Field(..., description="Number of flagged mismatches")
    results: list[BatchVerifyItem] = Field(..., description="Individual verification results")


class FullFaceVerificationResponse(BaseModel):
    """Combined response for orchestrator / officer dashboard."""
    document_id: str | None = None
    one_to_one: OneToOneVerifyResponse | None = None
    dedup: DedupSearchResponse | None = None
    liveness: LivenessResponse | None = None
    bypassed: bool = Field(
        default=False,
        description="True if biometric check was bypassed due to document integrity/tampering issues",
    )
    bypassed_reason: str | None = Field(
        default=None,
        description="Explanation why biometric comparison was bypassed",
    )
