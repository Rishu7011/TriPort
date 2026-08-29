"""
Tampering Router — FastAPI endpoints for document forgery and tampering analysis.

Aggregates:
  1. Error Level Analysis (ELA)
  2. EXIF & Metadata Forensics
  3. Photo Boundary Discontinuity & Noise Analysis
  4. Stamp / Seal Consistency & Duplicate Hash Checking
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.logging_config import get_logger
from backend.tampering_service.core.boundary_analysis import analyze_photo_boundaries
from backend.tampering_service.core.ela import compute_ela, ela_to_base64
from backend.tampering_service.core.metadata_forensics import analyze_metadata
from backend.tampering_service.core.stamp_matcher import verify_stamps
from backend.tampering_service.schemas.tampering import (
    TamperingCheckResult,
    TamperingCheckType,
    TamperingResponse,
)

logger = get_logger("tampering_service.router")

router = APIRouter(prefix="/api/v1/tampering", tags=["Tampering Detection"])


@router.post(
    "/detect",
    response_model=TamperingResponse,
    summary="Run full forensic tampering inspection on a document scan",
)
async def detect_tampering(
    file: UploadFile = File(..., description="Document image file (JPEG or PNG)"),
) -> TamperingResponse:
    """
    Execute multi-layer forensic analysis on an uploaded document scan.
    Returns individual check scores, overall anomaly rating, and an ELA heatmap.
    """
    logger.info(
        "Received tampering detection request",
        filename=file.filename,
        content_type=file.content_type,
    )

    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise ValueError("Uploaded image file is empty")
    except Exception as e:
        logger.error("Failed to read document image bytes", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_image", "reason": "Failed to read image bytes"},
        ) from e

    checks: list[TamperingCheckResult] = []
    warnings: list[str] = []

    # 1. Error Level Analysis (ELA)
    ela_score, ela_flagged, heatmap_bytes, ela_detail = compute_ela(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.ELA,
            score=round(ela_score, 3),
            flagged=ela_flagged,
            detail=ela_detail,
            metadata={"quality": 90},
        )
    )
    heatmap_b64 = ela_to_base64(heatmap_bytes) if heatmap_bytes else None

    # 2. Metadata & EXIF Forensics
    meta_score, meta_flagged, flags, raw_meta, meta_detail = analyze_metadata(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.METADATA,
            score=round(meta_score, 3),
            flagged=meta_flagged,
            detail=meta_detail,
            metadata={"detected_flags": flags, "tag_count": len(raw_meta)},
        )
    )

    # 3. Photo Boundary Discontinuity & Noise Analysis
    bnd_score, bnd_flagged, bnd_detail, bnd_meta = analyze_photo_boundaries(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.BOUNDARY,
            score=round(bnd_score, 3),
            flagged=bnd_flagged,
            detail=bnd_detail,
            metadata=bnd_meta,
        )
    )

    # 4. Stamp / Seal Matching
    stamp_score, stamp_flagged, stamp_detected, _, stamp_detail, stamp_meta = verify_stamps(image_bytes)
    checks.append(
        TamperingCheckResult(
            check_type=TamperingCheckType.STAMP_MATCH,
            score=round(stamp_score, 3),
            flagged=stamp_flagged,
            detail=stamp_detail,
            metadata=stamp_meta,
        )
    )

    # Overall Composite Score Calculation:
    # Any single high-confidence forensic flag (e.g. metadata software tag or ELA spike)
    # significantly increases the tampering score.
    # Formula: 0.35 * ELA + 0.30 * Metadata + 0.25 * Boundary + 0.10 * Stamp, bounded by max score
    weighted_score = (
        0.35 * ela_score
        + 0.30 * meta_score
        + 0.25 * bnd_score
        + 0.10 * stamp_score
    )
    max_individual_score = max(ela_score, meta_score, bnd_score, stamp_score)
    # Give significant weight to the peak single indicator
    overall_tampering_score = float(np_clip_score(0.6 * max_individual_score + 0.4 * weighted_score))

    any_flagged = any(c.flagged for c in checks) or (overall_tampering_score >= 0.45)

    return TamperingResponse(
        flagged=any_flagged,
        tampering_score=round(overall_tampering_score, 3),
        checks=checks,
        ela_heatmap_base64=heatmap_b64,
        warnings=warnings,
    )


def np_clip_score(val: float) -> float:
    return max(0.0, min(1.0, float(val)))
