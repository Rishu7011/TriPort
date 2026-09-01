"""
Face Router — FastAPI endpoints for Face Embedding, 1:1 Verification, and 1:N Deduplication.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.logging_config import get_logger
from backend.face_service.core.dedup_search import search_duplicates
from backend.face_service.core.embedding import extract_face_embedding
from backend.face_service.core.one_to_one import verify_one_to_one
from backend.face_service.schemas.face import (
    BatchVerifyResponse,
    DedupSearchResponse,
    FaceEmbeddingResponse,
    LivenessResponse,
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
    threshold: float = Form(default=0.90, description="High-security cutoff threshold (default: 0.90 / 90%)"),
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
    from backend.face_service.core.aws_rekognition import use_aws_face_verification
    import uuid

    if use_aws_face_verification():
        return DedupSearchResponse(
            has_duplicates=False,
            hits=[],
            person_cluster_id=str(uuid.uuid4()),
            detail="1:N dedup is disabled in AWS-only face mode (no local embeddings).",
        )

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


@router.post(
    "/liveness",
    response_model=LivenessResponse,
    summary="Real-time anti-spoofing and liveness check on live capture frame",
)
async def check_liveness(
    live_photo: UploadFile = File(..., description="Live camera capture image to inspect for anti-spoofing"),
) -> LivenessResponse:
    """Evaluate Eye Aspect Ratio (EAR) and 3D facial motion to reject photo printouts and screen replays."""
    try:
        live_bytes = await live_photo.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_image", "reason": str(e)},
        ) from e

    from backend.face_service.core.one_to_one import run_liveness_check, LIVENESS_THRESHOLD

    score, detail = run_liveness_check(live_bytes)
    is_live = score >= LIVENESS_THRESHOLD

    return LivenessResponse(
        is_live=is_live,
        liveness_score=score,
        detail=detail,
    )


@router.post(
    "/verify/batch",
    response_model=BatchVerifyResponse,
    summary="Bulk high-throughput disembarkation queue face verification",
)
async def batch_verify_faces(
    doc_photos: list[UploadFile] = File(..., description="List of document portrait photos"),
    live_photos: list[UploadFile] = File(..., description="List of live checkpoint photos"),
    threshold: float = Form(default=0.90, description="Decision threshold"),
) -> BatchVerifyResponse:
    """Concurrently process a batch of traveler document + live photo pairs."""
    if len(doc_photos) != len(live_photos):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of document photos must match number of live photos",
        )

    results = []
    matched_count = 0
    mismatch_count = 0

    for idx, (doc_p, live_p) in enumerate(zip(doc_photos, live_photos)):
        item_id = f"item_{idx + 1}"
        try:
            doc_b = await doc_p.read()
            live_b = await live_p.read()
            matched, score, _, detail = verify_one_to_one(
                doc_image_bytes=doc_b,
                live_image_bytes=live_b,
                threshold=threshold,
            )
            if matched:
                matched_count += 1
            else:
                mismatch_count += 1

            results.append({
                "item_id": item_id,
                "matched": matched,
                "match_score": score,
                "detail": detail,
            })
        except Exception as exc:
            mismatch_count += 1
            results.append({
                "item_id": item_id,
                "matched": False,
                "match_score": 0.0,
                "detail": f"Processing error: {exc}",
            })

    return BatchVerifyResponse(
        total_processed=len(results),
        matched_count=matched_count,
        mismatch_count=mismatch_count,
        results=results,
    )

