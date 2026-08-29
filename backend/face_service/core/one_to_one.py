"""
1:1 Face Verification Engine.

CONCEPT:
1:1 Verification compares the portrait photo extracted from an identity document
against a live image captured at the checkpoint kiosk camera.

This module:
  1. Computes the cosine similarity between two 512-dim embedding vectors:
     CosineSimilarity(u, v) = (u . v) / (||u|| * ||v||)
  2. Compares against an ICAO/NIST standard decision threshold (default: 0.60).
  3. Calibrates raw cosine distance into a 0.0–1.0 confidence match score.
"""

import numpy as np
from backend.logging_config import get_logger
from backend.face_service.core.embedding import extract_face_embedding

logger = get_logger("face_service.one_to_one")

DEFAULT_COSINE_THRESHOLD = 0.60


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two unit embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-6 or norm_b < 1e-6:
        return 0.0
    sim = float(np.dot(a, b) / (norm_a * norm_b))
    return float(np.clip(sim, -1.0, 1.0))


def verify_one_to_one(
    doc_image_bytes: bytes | None = None,
    live_image_bytes: bytes | None = None,
    doc_embedding: list[float] | None = None,
    live_embedding: list[float] | None = None,
    threshold: float = DEFAULT_COSINE_THRESHOLD,
) -> tuple[bool, float, float, str]:
    """
    Perform 1:1 face match between document portrait and live capture photo.

    Args:
        doc_image_bytes: Raw bytes of the document photo (optional if embedding provided).
        live_image_bytes: Raw bytes of the live checkpoint photo (optional if embedding provided).
        doc_embedding: Precomputed 512-dim embedding for doc photo.
        live_embedding: Precomputed 512-dim embedding for live capture.
        threshold: Cosine similarity cutoff threshold (default: 0.60).

    Returns:
        tuple: (
            matched: bool,
            match_score: float (0.0 to 1.0 calibrated confidence),
            cosine_similarity: float (-1.0 to 1.0),
            detail: str
        )
    """
    # 1. Resolve document embedding
    if doc_embedding is None:
        if not doc_image_bytes:
            return False, 0.0, 0.0, "Missing document photo image or embedding."
        ok, emb, _, msg = extract_face_embedding(doc_image_bytes)
        if not ok or not emb:
            return False, 0.0, 0.0, f"Document face extraction failed: {msg}"
        doc_embedding = emb

    # 2. Resolve live capture embedding
    if live_embedding is None:
        if not live_image_bytes:
            return False, 0.0, 0.0, "Missing live capture photo image or embedding."
        ok, emb, _, msg = extract_face_embedding(live_image_bytes)
        if not ok or not emb:
            return False, 0.0, 0.0, f"Live capture face extraction failed: {msg}"
        live_embedding = emb

    # 3. Calculate Cosine Similarity
    sim = compute_cosine_similarity(doc_embedding, live_embedding)

    # 4. Calibrate match score
    # Score maps [threshold - 0.2, 1.0] -> [0.0, 1.0] smoothly
    calibrated_score = float(np.clip((sim - (threshold - 0.20)) / (1.0 - (threshold - 0.20)), 0.0, 1.0))
    matched = sim >= threshold

    if matched:
        detail = (
            f"Face verification PASSED. Biometric match confirmed with "
            f"cosine similarity {sim:.3f} (confidence: {calibrated_score:.1%}, threshold: {threshold:.2f})."
        )
    else:
        detail = (
            f"Face verification FAILED. Biometric discrepancy detected. "
            f"Similarity {sim:.3f} below security threshold {threshold:.2f}."
        )

    logger.info("1:1 verification completed", matched=matched, similarity=sim, match_score=calibrated_score)
    return matched, round(calibrated_score, 4), round(sim, 4), detail
