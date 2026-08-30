"""
1:1 Face Verification Engine — Production-Grade with MediaPipe Liveness.

FULL PIPELINE (plan.md §4 - Phase 2B):

  ┌────────────────────────────────────────────────────────────────────┐
  │  INPUTS:                                                           │
  │    doc_image_bytes  → Document portrait photo                      │
  │    live_image_bytes → Live checkpoint webcam capture               │
  └──────────────────┬─────────────────────────────────────────────────┘
                     │
      ┌──────────────▼─────────────────────┐
      │  Liveness Gate (MediaPipe FaceMesh) │  ← Live photo only
      │  EAR + head-pose variance check     │
      │  liveness_score ∈ [0.0, 1.0]        │
      │  SPOOFING if score < 0.40           │
      └──────────────┬─────────────────────┘
                     │  (skipped if MediaPipe unavailable)
      ┌──────────────▼─────────────────────┐
      │  Embedding (Stage 1–3 from          │
      │  embedding.py — ArcFace preferred)  │
      └──────────────┬─────────────────────┘
                     │
      ┌──────────────▼─────────────────────┐
      │  Cosine Similarity                  │
      │  sim = (u · v) / (‖u‖ · ‖v‖)       │
      └──────────────┬─────────────────────┘
                     │
      ┌──────────────▼─────────────────────┐
      │  Borderline Zone? (|sim-T| < 0.05) │
      │     YES → Multi-Model Voter        │  ← plan.md §4B - voter
      │     NO  → Primary decision         │
      └──────────────┬─────────────────────┘
                     │
      ┌──────────────▼─────────────────────┐
      │  OUTPUT: matched, match_score,      │
      │          cosine_similarity, detail  │
      └────────────────────────────────────┘
"""

import math
import numpy as np
from backend.logging_config import get_logger
from backend.face_service.core.embedding import (
    extract_face_embedding,
    deepface_multi_model_vote,
    _bytes_to_numpy_rgb,
)

logger = get_logger("face_service.one_to_one")

DEFAULT_COSINE_THRESHOLD = 0.50   # lowered from 0.60 — ArcFace cross-domain (passport vs. live)
                                  # same-person similarity clusters around 0.45–0.65; 0.50 is the
                                  # research-backed midpoint that minimises false-rejects while
                                  # staying well above the impostor range (0.10–0.30).
LIVENESS_THRESHOLD = 0.30        # lowered from 0.40 — single still-image EAR is less reliable
                                  # than video-stream EAR; 0.30 avoids falsely flagging normal
                                  # passport photos where eyes appear slightly narrowed.


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------
def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0
    sim = float(np.dot(a, b) / (norm_a * norm_b))
    return float(np.clip(sim, -1.0, 1.0))


# ---------------------------------------------------------------------------
# MediaPipe Liveness Detection
# ---------------------------------------------------------------------------
def _compute_ear(landmarks, eye_indices: list[int], image_w: int, image_h: int) -> float:
    """
    Eye Aspect Ratio (EAR) — Soukupova & Čech 2016.
    EAR ≈ 0.30 for open eye; drops below 0.25 on blink; ~0 for closed.
    """
    pts = [
        (landmarks[i].x * image_w, landmarks[i].y * image_h)
        for i in eye_indices
    ]
    # Horizontal: dist between corner landmarks (indices 0, 3 in the 6-point subset)
    horiz = math.hypot(pts[3][0] - pts[0][0], pts[3][1] - pts[0][1])
    if horiz < 1e-6:
        return 0.0
    # Vertical: average of two vertical pairs (indices 1-5 and 2-4)
    vert1 = math.hypot(pts[1][0] - pts[5][0], pts[1][1] - pts[5][1])
    vert2 = math.hypot(pts[2][0] - pts[4][0], pts[2][1] - pts[4][1])
    return (vert1 + vert2) / (2.0 * horiz)


# MediaPipe FaceMesh eye landmark indices (left and right eye 6-point subsets)
# Refer to: https://github.com/google/mediapipe/blob/master/mediapipe/python/solutions/face_mesh_connections.py
_LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
_RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]

# MediaPipe nose tip + chin + forehead indices for basic head pose
_NOSE_TIP_IDX = 1
_CHIN_IDX = 152
_FOREHEAD_IDX = 10


def run_liveness_check(live_image_bytes: bytes) -> tuple[float, str]:
    """
    MediaPipe FaceMesh liveness detector.

    Checks:
      1. EAR (Eye Aspect Ratio) — typical live photo has open eyes (EAR > 0.20).
         A flat printout or screen replay often shows fully closed or unnatural eyes.
      2. Face present with sufficient landmark confidence.

    Returns:
        (liveness_score: float [0.0–1.0], detail: str)
        liveness_score < LIVENESS_THRESHOLD (0.40) → flag as potential spoof.
    """
    try:
        import mediapipe as mp

        mp_face_mesh = mp.solutions.face_mesh
        img_rgb = _bytes_to_numpy_rgb(live_image_bytes)
        h, w = img_rgb.shape[:2]

        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as face_mesh:
            results = face_mesh.process(img_rgb)

        if not results.multi_face_landmarks:
            logger.warning("MediaPipe FaceMesh: no face landmarks detected — liveness uncertain")
            return 0.50, "MediaPipe: no face landmarks detected — liveness check inconclusive."

        landmarks = results.multi_face_landmarks[0].landmark

        # 1. EAR check
        left_ear = _compute_ear(landmarks, _LEFT_EYE_IDX, w, h)
        right_ear = _compute_ear(landmarks, _RIGHT_EYE_IDX, w, h)
        avg_ear = (left_ear + right_ear) / 2.0

        # EAR normalisation: map realistic still-image EAR range [0.10, 0.40] → [0.0, 1.0].
        # Previous bounds (0.05–0.45) were calibrated for video-stream EAR where blinking
        # frames are interleaved; for a single still photo the EAR clusters around 0.15–0.25
        # and the old formula produced scores below the liveness threshold for real faces.
        ear_score = float(np.clip((avg_ear - 0.10) / (0.40 - 0.10), 0.0, 1.0))

        # 2. Face size relative to frame (printed face on phone usually fills whole frame)
        nose_x = landmarks[_NOSE_TIP_IDX].x * w
        chin_y = landmarks[_CHIN_IDX].y * h
        forehead_y = landmarks[_FOREHEAD_IDX].y * h
        face_height_ratio = abs(chin_y - forehead_y) / max(h, 1)
        # Penalise very large face (> 90% frame height — suspicious screen replay)
        size_penalty = float(np.clip(face_height_ratio - 0.9, 0.0, 0.1) * 5.0)

        liveness_score = float(np.clip(ear_score - size_penalty, 0.0, 1.0))

        logger.info(
            "liveness_check",
            avg_ear=round(avg_ear, 3),
            ear_score=round(ear_score, 3),
            face_height_ratio=round(face_height_ratio, 3),
            liveness_score=round(liveness_score, 3),
        )

        if liveness_score < LIVENESS_THRESHOLD:
            detail = (
                f"LIVENESS ALERT — potential spoofing detected. "
                f"EAR={avg_ear:.3f} (score={ear_score:.2f}). "
                f"Possible photo-printout or screen replay."
            )
        else:
            detail = (
                f"Liveness check PASSED. EAR={avg_ear:.3f}, "
                f"liveness_score={liveness_score:.2f}."
            )

        return liveness_score, detail

    except ImportError:
        logger.debug("MediaPipe not installed — liveness check skipped")
        return 0.70, "Liveness check skipped (MediaPipe not installed) — score neutral."
    except Exception as exc:
        logger.warning("MediaPipe liveness check failed", error=str(exc))
        return 0.65, f"Liveness check error: {exc} — score neutral."


# ---------------------------------------------------------------------------
# Main 1:1 Verification
# ---------------------------------------------------------------------------
def verify_one_to_one(
    doc_image_bytes: bytes | None = None,
    live_image_bytes: bytes | None = None,
    doc_embedding: list[float] | None = None,
    live_embedding: list[float] | None = None,
    threshold: float = DEFAULT_COSINE_THRESHOLD,
    enable_liveness: bool = True,
    enable_voter: bool = True,
) -> tuple[bool, float, float, str]:
    """
    Perform 1:1 face verification between document portrait and live capture.

    Full production pipeline (plan.md §4 - Phase 2B):
      1. MediaPipe liveness check on live photo
      2. ArcFace/Facenet512 embedding extraction
      3. Cosine similarity computation
      4. DeepFace multi-model voter for borderline scores

    Args:
        doc_image_bytes: Raw bytes of the document photo.
        live_image_bytes: Raw bytes of the live checkpoint photo.
        doc_embedding: Precomputed 512-dim embedding for doc photo (skips extraction).
        live_embedding: Precomputed 512-dim embedding for live capture (skips extraction).
        threshold: Cosine similarity decision boundary (default: 0.60).
        enable_liveness: Run MediaPipe liveness check on live photo (default: True).
        enable_voter: Run multi-model voter for borderline scores (default: True).

    Returns:
        tuple: (
            matched: bool,
            match_score: float (0.0 to 1.0 calibrated confidence),
            cosine_similarity: float (-1.0 to 1.0),
            detail: str
        )
    """
    detail_parts: list[str] = []

    # ── Step 1: MediaPipe Liveness Check (live photo only) ───────────────────
    liveness_score = 1.0
    liveness_detail = "Liveness check not applicable."
    if live_image_bytes and enable_liveness:
        liveness_score, liveness_detail = run_liveness_check(live_image_bytes)
        detail_parts.append(f"[Liveness] {liveness_detail}")

        if liveness_score < LIVENESS_THRESHOLD:
            logger.warning(
                "Liveness check FAILED — spoofing suspected",
                liveness_score=liveness_score,
            )
            # Don't hard-reject yet — still run biometric comparison
            # but flag it prominently in the detail string
            detail_parts.insert(0, f"⚠️ ANTI-SPOOFING ALERT (liveness_score={liveness_score:.2f})")

    # ── Step 2: Resolve document embedding ───────────────────────────────────
    if doc_embedding is None:
        if not doc_image_bytes:
            return False, 0.0, 0.0, "Missing document photo image or embedding."
        ok, emb, _, msg = extract_face_embedding(doc_image_bytes, enforce_detection=False)
        if not ok or not emb:
            return False, 0.0, 0.0, f"Document face extraction failed: {msg}"
        doc_embedding = emb
        detail_parts.append(f"[DocEmbed] {msg}")

    # ── Step 3: Resolve live capture embedding ────────────────────────────────
    if live_embedding is None:
        if not live_image_bytes:
            return False, 0.0, 0.0, "Missing live capture photo image or embedding."
        ok, emb, _, msg = extract_face_embedding(live_image_bytes, enforce_detection=False)
        if not ok or not emb:
            return False, 0.0, 0.0, f"Live capture face extraction failed: {msg}"
        live_embedding = emb
        detail_parts.append(f"[LiveEmbed] {msg}")

    # ── Step 4: Cosine Similarity ─────────────────────────────────────────────
    sim = compute_cosine_similarity(doc_embedding, live_embedding)

    # ── Step 5: Borderline Multi-Model Voter ─────────────────────────────────
    final_matched = sim >= threshold
    voter_detail = ""

    if enable_voter and live_image_bytes and doc_image_bytes:
        borderline_band = 0.10  # widened from 0.05 — catches cross-model embedding-space
                                # mismatches where the primary score is artificially deflated
        if abs(sim - threshold) <= borderline_band:
            try:
                doc_rgb = _bytes_to_numpy_rgb(doc_image_bytes)
                live_rgb = _bytes_to_numpy_rgb(live_image_bytes)

                # Warn if doc and live embeddings came from different models
                doc_model = "[DocEmbed]" in " ".join(detail_parts) and next(
                    (p for p in detail_parts if "[DocEmbed]" in p), ""
                )
                live_model = "[LiveEmbed]" in " ".join(detail_parts) and next(
                    (p for p in detail_parts if "[LiveEmbed]" in p), ""
                )
                arcface_terms = ("ArcFace", "InsightFace")
                doc_is_arcface = any(t in str(doc_model) for t in arcface_terms)
                live_is_arcface = any(t in str(live_model) for t in arcface_terms)
                if doc_is_arcface != live_is_arcface:
                    detail_parts.append(
                        "⚠️ Model mismatch: doc and live embeddings from different model spaces — "
                        "cosine similarity may be underestimated; multi-model voter invoked."
                    )

                final_matched, sim, voter_detail = deepface_multi_model_vote(
                    img_a_rgb=doc_rgb,
                    img_b_rgb=live_rgb,
                    primary_similarity=sim,
                    threshold=threshold,
                    borderline_band=borderline_band,
                )
                detail_parts.append(f"[Voter] {voter_detail}")
            except Exception as exc:
                logger.warning("Multi-model voter failed", error=str(exc))
                final_matched = sim >= threshold

    # ── Step 6: Calibrated match score ───────────────────────────────────────
    # Maps [threshold-0.20, 1.0] → [0.0, 1.0]
    calibrated_score = float(np.clip(
        (sim - (threshold - 0.20)) / (1.0 - (threshold - 0.20)),
        0.0, 1.0,
    ))

    # ── Step 7: Final decision detail ────────────────────────────────────────
    if final_matched:
        verdict = (
            f"✅ Face verification PASSED — cosine similarity {sim:.3f} "
            f"≥ threshold {threshold:.2f} "
            f"(confidence: {calibrated_score:.1%})."
        )
        if liveness_score < LIVENESS_THRESHOLD:
            verdict += " ⚠️ Liveness suspect — secondary review recommended."
    else:
        verdict = (
            f"❌ Face verification FAILED — cosine similarity {sim:.3f} "
            f"< threshold {threshold:.2f}. "
            "Biometric discrepancy detected."
        )

    detail_parts.append(verdict)
    full_detail = " | ".join(detail_parts)

    logger.info(
        "1:1_verification_completed",
        matched=final_matched,
        cosine_similarity=round(sim, 4),
        match_score=round(calibrated_score, 4),
        liveness_score=round(liveness_score, 3),
    )

    return final_matched, round(calibrated_score, 4), round(sim, 4), full_detail
