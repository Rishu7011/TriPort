"""
Face Router — FastAPI endpoints for Face Embedding, 1:1 Verification, and 1:N Deduplication.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.logging_config import get_logger
from backend.face_service.core.dedup_search import search_duplicates
from backend.face_service.core.embedding import extract_face_embedding
from backend.face_service.core.one_to_one import verify_one_to_one
from backend.face_service.schemas.face import (
    DedupSearchResponse,
    FaceEmbeddingResponse,
    OneToOneVerifyResponse,
)

logger = get_logger("face_service.router")

router = APIRouter(prefix="/api/v1/face", tags=["Face Verification"])


@router.post(
    "/embed",
    response_model=FaceEmbeddingResponse,
    summary="Generate 512-dim facial embedding vector from a photo",
)
async def generate_embedding(
    file: UploadFile = File(..., description="Document portrait or live capture photo"),
) -> FaceEmbeddingResponse:
    """Extract a 512-dimensional facial embedding vector from an uploaded face image."""
    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Uploaded image is empty")
    except Exception as e:
        logger.error("Failed to read face image file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_image", "reason": "Failed to read image bytes"},
        ) from e

    ok, emb, count, msg = extract_face_embedding(image_bytes)
    if not ok or not emb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "face_extraction_failed", "reason": msg},
        )

    return FaceEmbeddingResponse(
        face_detected=True,
        embedding=emb,
        face_count=count,
        detail=msg,
    )


@router.post(
    "/verify",
    response_model=OneToOneVerifyResponse,
    summary="1:1 verification between document photo and live checkpoint capture",
)
async def verify_faces(
    doc_photo: UploadFile = File(..., description="Portrait photo extracted from document"),
    live_photo: UploadFile = File(..., description="Live webcam capture photo of traveler"),
    threshold: float = Form(default=0.60, description="Cosine similarity cutoff threshold"),
) -> OneToOneVerifyResponse:
    """Compare document portrait against live checkpoint capture."""
    try:
        doc_bytes = await doc_photo.read()
        live_bytes = await live_photo.read()
    except Exception as e:
        logger.error("Failed to read verification images", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_images", "reason": "Failed to read image byte streams"},
        ) from e

    matched, score, sim, detail = verify_one_to_one(
        doc_image_bytes=doc_bytes,
        live_image_bytes=live_bytes,
        threshold=threshold,
    )

    return OneToOneVerifyResponse(
        matched=matched,
        match_score=score,
        cosine_similarity=sim,
        threshold=threshold,
        detail=detail,
    )


@router.post(
    "/dedup",
    response_model=DedupSearchResponse,
    summary="1:N biometric search to flag multi-identity duplicate records",
)
async def dedup_check(
    file: UploadFile = File(..., description="Face image to check for multi-identity duplicates"),
    current_doc_id: str | None = Form(default=None, description="Optional current document UUID to exclude"),
    threshold: float = Form(default=0.65, description="Cosine similarity clustering cutoff"),
) -> DedupSearchResponse:
    """Check face against historical vector index for duplicate identities."""
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_image", "reason": str(e)},
        ) from e

    ok, emb, _, msg = extract_face_embedding(image_bytes)
    if not ok or not emb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "face_extraction_failed", "reason": msg},
        )

    has_dups, hits, cluster_id, detail = await search_duplicates(
        embedding=emb,
        threshold=threshold,
        current_doc_id=current_doc_id,
    )

    return DedupSearchResponse(
        has_duplicates=has_dups,
        hits=hits,
        person_cluster_id=cluster_id,
        detail=detail,
    )
