"""
Face Embedding Extraction Engine — Production-Grade Multi-Model Pipeline.

MODEL GRAPH (plan.md §4 - Phase 2B):

  ┌─────────────────────────────────────────────────────────────────┐
  │  INPUT: Raw image bytes (document photo OR live webcam capture) │
  └────────────────────────┬────────────────────────────────────────┘
                           │
            ┌──────────────▼────────────────┐
            │  Stage 1: RetinaFace (InsightFace) │
            │  Face Detection + 5-pt Alignment   │
            │  → Cropped & aligned face ROI       │
            └──────────────┬────────────────┘
                           │  (fallback: OpenCV Haar Cascade crop)
            ┌──────────────▼────────────────┐
            │  Stage 2: ArcFace (InsightFace)│
            │  512-dim L2-normalized vector  │
            └──────────────┬────────────────┘
                           │  (fallback: DeepFace Facenet512)
            ┌──────────────▼────────────────┐
            │  Stage 3: DeepFace Voter       │
            │  Borderline score (0.55–0.65)  │
            │  → Multi-model consensus vote  │
            └──────────────┬────────────────┘
                           │  (fallback: gradient histogram local)
            ┌──────────────▼──────────────┐
            │  OUTPUT: 512-dim unit vector  │
            └─────────────────────────────┘

LIVENESS (for live webcam photos only — called from one_to_one.py):
  MediaPipe FaceMesh → EAR eye-openness + head-pose variance check
  → liveness_score ∈ [0.0, 1.0]
"""

import io
import cv2
import numpy as np
from PIL import Image

from backend.logging_config import get_logger

logger = get_logger("face_service.embedding")

EMBEDDING_DIM = 512

# ── Lazy-loaded model singletons ─────────────────────────────────────────────
_insightface_app = None       # InsightFace FaceAnalysis (RetinaFace + ArcFace)
_deepface_models: dict = {}   # DeepFace model cache


# ---------------------------------------------------------------------------
# Utility: bytes → numpy RGB
# ---------------------------------------------------------------------------
def _bytes_to_numpy_rgb(image_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes to an RGB NumPy array."""
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(pil_img)


# ---------------------------------------------------------------------------
# Utility: L2 normalize embedding vector
# ---------------------------------------------------------------------------
def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector to unit length. Returns zero vector if degenerate."""
    norm = np.linalg.norm(vec)
    if norm < 1e-8:
        return np.zeros_like(vec, dtype=np.float64)
    return (vec / norm).astype(np.float64)


# ---------------------------------------------------------------------------
# Utility: Ensure vector is exactly 512-dim
# ---------------------------------------------------------------------------
def _ensure_512d(vec: np.ndarray) -> np.ndarray:
    if len(vec) == EMBEDDING_DIM:
        return vec
    if len(vec) > EMBEDDING_DIM:
        return vec[:EMBEDDING_DIM]
    return np.pad(vec.astype(np.float64), (0, EMBEDDING_DIM - len(vec)))


# ---------------------------------------------------------------------------
# STAGE 1: InsightFace (RetinaFace detector + ArcFace embedder)
# ---------------------------------------------------------------------------
def _get_insightface_app():
    """Lazy-load InsightFace FaceAnalysis singleton (RetinaFace + ArcFace)."""
    global _insightface_app
    if _insightface_app is None:
        try:
            import insightface
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name="buffalo_l",          # buffalo_l bundles RetinaFace + ArcFace W600K R50
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition"],
            )
            app.prepare(ctx_id=0, det_size=(640, 640))
            _insightface_app = app
            logger.info("InsightFace FaceAnalysis (RetinaFace+ArcFace) initialized successfully")
        except Exception as exc:
            logger.warning("InsightFace unavailable — will use DeepFace fallback", error=str(exc))
            _insightface_app = None
    return _insightface_app


def _extract_arcface_embedding(img_rgb: np.ndarray) -> tuple[list[float], str] | None:
    """
    Stage 1: Extract ArcFace 512-dim embedding via InsightFace.

    Returns (embedding_list, detail_str) on success, None on failure.
    RetinaFace handles detection + 5-landmark alignment internally.
    """
    app = _get_insightface_app()
    if app is None:
        return None

    try:
        # InsightFace expects BGR
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        faces = app.get(img_bgr)

        if not faces:
            logger.debug("InsightFace: no face detected in image")
            return None

        # Select the largest detected face by bounding box area
        best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

        if best_face.embedding is None or len(best_face.embedding) == 0:
            return None

        vec = np.array(best_face.embedding, dtype=np.float64)
        vec = _ensure_512d(vec)
        vec = _l2_normalize(vec)

        det_score = float(best_face.det_score) if hasattr(best_face, "det_score") else 1.0
        logger.info(
            "ArcFace embedding extracted via InsightFace",
            dims=len(vec),
            det_score=round(det_score, 3),
            face_count=len(faces),
        )
        return vec.tolist(), f"ArcFace (InsightFace buffalo_l) — det_score={det_score:.3f}, faces_found={len(faces)}"

    except Exception as exc:
        logger.warning("InsightFace ArcFace extraction failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# STAGE 2: DeepFace Facenet512 (intermediate fallback)
# ---------------------------------------------------------------------------
def _extract_deepface_facenet512(
    img_rgb: np.ndarray,
    enforce_detection: bool = False,
) -> tuple[list[float], str] | None:
    """
    Stage 2: Extract 512-dim embedding using DeepFace Facenet512.
    Falls back to this when InsightFace is unavailable.
    """
    try:
        from deepface import DeepFace

        representations = DeepFace.represent(
            img_path=img_rgb,
            model_name="Facenet512",
            enforce_detection=enforce_detection,
            align=True,
            detector_backend="opencv",    # fastest CPU detector
        )
        if representations and len(representations) > 0:
            raw_vec = np.array(representations[0]["embedding"], dtype=np.float64)
            raw_vec = _ensure_512d(raw_vec)
            raw_vec = _l2_normalize(raw_vec)
            logger.info("DeepFace Facenet512 embedding extracted", dims=len(raw_vec))
            return raw_vec.tolist(), "DeepFace Facenet512 (fallback)"

    except Exception as exc:
        logger.debug("DeepFace Facenet512 extraction failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# STAGE 3: DeepFace Multi-Model Voter (borderline disambiguation)
# ---------------------------------------------------------------------------
def deepface_multi_model_vote(
    img_a_rgb: np.ndarray,
    img_b_rgb: np.ndarray,
    primary_similarity: float,
    threshold: float = 0.60,
    borderline_band: float = 0.05,
) -> tuple[bool, float, str]:
    """
    Stage 3: Multi-model consensus vote for borderline similarity scores.

    For scores within [threshold - borderline_band, threshold + borderline_band],
    runs 3 additional DeepFace models (VGG-Face, ArcFace, SFace) and takes
    majority vote to override the borderline primary decision.

    Args:
        img_a_rgb: Document photo as RGB NumPy array.
        img_b_rgb: Live capture photo as RGB NumPy array.
        primary_similarity: Cosine similarity from the primary model.
        threshold: Decision boundary (default: 0.60).
        borderline_band: Half-width of the ambiguous zone (default: ±0.05).

    Returns:
        (matched: bool, final_similarity: float, detail: str)
    """
    low = threshold - borderline_band
    high = threshold + borderline_band

    # Only vote if score is in the borderline zone
    if not (low <= primary_similarity <= high):
        matched = primary_similarity >= threshold
        return matched, primary_similarity, f"Primary model decision (similarity={primary_similarity:.3f})"

    logger.info(
        "Borderline score — invoking multi-model voter",
        primary_similarity=primary_similarity,
        threshold=threshold,
    )

    voter_models = ["VGG-Face", "ArcFace", "SFace"]
    votes_match = 0
    votes_total = 0
    vote_details = []

    for model_name in voter_models:
        try:
            from deepface import DeepFace
            result = DeepFace.verify(
                img1_path=img_a_rgb,
                img2_path=img_b_rgb,
                model_name=model_name,
                enforce_detection=False,
                align=True,
                detector_backend="opencv",
            )
            model_match = result.get("verified", False)
            model_distance = result.get("distance", 1.0)
            votes_total += 1
            if model_match:
                votes_match += 1
            vote_details.append(f"{model_name}={'✓' if model_match else '✗'}(d={model_distance:.3f})")
            logger.debug(
                "voter_model_result",
                model=model_name,
                matched=model_match,
                distance=round(model_distance, 3),
            )
        except Exception as exc:
            logger.debug(f"Voter model {model_name} failed", error=str(exc))

    if votes_total == 0:
        # No voter models ran — fall through with primary result
        matched = primary_similarity >= threshold
        return matched, primary_similarity, f"Voter unavailable — primary decision: similarity={primary_similarity:.3f}"

    # Majority vote (include primary model as one vote)
    primary_vote = 1 if primary_similarity >= threshold else 0
    total_yes = votes_match + primary_vote
    total_votes = votes_total + 1
    final_matched = total_yes > (total_votes / 2)

    detail = (
        f"Multi-model voter: {total_yes}/{total_votes} MATCH votes "
        f"[{', '.join(vote_details)}]. "
        f"Final: {'VERIFIED' if final_matched else 'MISMATCH'}"
    )
    logger.info(
        "voter_decision",
        votes_yes=total_yes,
        votes_total=total_votes,
        final_matched=final_matched,
    )
    return final_matched, primary_similarity, detail


# ---------------------------------------------------------------------------
# STAGE 4: Local gradient histogram fallback
# ---------------------------------------------------------------------------
def _compute_fallback_embedding(img_rgb: np.ndarray) -> list[float]:
    """
    Final fallback: deterministic gradient + histogram feature vector.
    No ML dependency — always works, but identity accuracy is low.
    """
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, (64, 64))

    grad_x = cv2.Sobel(resized, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(resized, cv2.CV_64F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)

    hist = cv2.calcHist([resized], [0], None, [128], [0, 256]).flatten()
    spatial = cv2.resize(mag, (16, 16)).flatten()

    features = np.concatenate([hist, spatial, resized.flatten()[:128]])
    features = _ensure_512d(features)
    features = _l2_normalize(features)
    return features.tolist()


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------
def extract_face_embedding(
    image_bytes: bytes,
    enforce_detection: bool = False,
) -> tuple[bool, list[float], int, str]:
    """
    Extract a 512-dimensional facial embedding vector from image bytes.

    Pipeline (plan.md §4 - Phase 2B):
      1. InsightFace (RetinaFace detection + ArcFace embedding) [PRIMARY]
      2. DeepFace Facenet512 [FALLBACK-1]
      3. Local gradient histogram [FALLBACK-2]

    Args:
        image_bytes: Raw bytes of the document photo or live webcam capture.
        enforce_detection: If True, return failure when no face found.

    Returns:
        tuple: (
            face_detected: bool,
            embedding: list[float] (512-dim L2-normalized unit vector),
            face_count: int,
            detail: str
        )
    """
    try:
        img_rgb = _bytes_to_numpy_rgb(image_bytes)
    except Exception as e:
        logger.error("Failed to decode face image bytes", error=str(e))
        return False, [], 0, f"Image decode error: {e}"

    h, w = img_rgb.shape[:2]
    if h < 20 or w < 20:
        return False, [], 0, "Image resolution too low for face verification."

    # ── Stage 1: InsightFace (RetinaFace + ArcFace) ──────────────────────────
    result = _extract_arcface_embedding(img_rgb)
    if result is not None:
        embedding, detail = result
        return True, embedding, 1, detail

    # ── Face count pre-check (OpenCV Haar for face_count reporting) ──────────
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    detected_faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
    )
    face_count = len(detected_faces)

    if face_count == 0 and enforce_detection:
        logger.warning("No face detected in provided image")
        return False, [], 0, "No human face detected in document/live image."

    # ── Stage 2: DeepFace Facenet512 fallback ────────────────────────────────
    result = _extract_deepface_facenet512(img_rgb, enforce_detection=enforce_detection)
    if result is not None:
        embedding, detail = result
        return True, embedding, max(1, face_count), detail

    # ── Stage 3: Local fallback ──────────────────────────────────────────────
    fallback_vec = _compute_fallback_embedding(img_rgb)
    logger.info("Using local gradient fallback embedding", dims=len(fallback_vec))
    return True, fallback_vec, max(1, face_count), "Face embedding generated via local gradient histogram (last-resort fallback)."


# ---------------------------------------------------------------------------
# Face Crop Extraction — Returns cropped face JPEG bytes for frontend display
# ---------------------------------------------------------------------------
def extract_face_crop_bytes(image_bytes: bytes) -> tuple[bytes | None, bool]:
    """
    Detect and crop the face photo from a passport/ID document image.

    Uses a cascading strategy:
      1. InsightFace RetinaFace bounding box (if available)
      2. OpenCV Haar cascade (always available via cv2)

    Returns:
        (crop_bytes, face_detected)
        - crop_bytes: JPEG bytes of the cropped face region, None if not found
        - face_detected: True if a face was located and cropped
    """
    try:
        img_rgb = _bytes_to_numpy_rgb(image_bytes)
    except Exception as exc:
        logger.warning("extract_face_crop_bytes: image decode failed", error=str(exc))
        return None, False

    h, w = img_rgb.shape[:2]

    # ── Strategy 1: InsightFace RetinaFace bounding box ──────────────────────
    app = _get_insightface_app()
    if app is not None:
        try:
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            faces = app.get(img_bgr)
            if faces:
                best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                x1, y1, x2, y2 = [int(v) for v in best.bbox]
                # Add 20% padding around the face
                pad_x = int((x2 - x1) * 0.20)
                pad_y = int((y2 - y1) * 0.25)
                x1 = max(0, x1 - pad_x)
                y1 = max(0, y1 - pad_y)
                x2 = min(w, x2 + pad_x)
                y2 = min(h, y2 + pad_y)
                face_crop_rgb = img_rgb[y1:y2, x1:x2]
                pil_crop = Image.fromarray(face_crop_rgb)
                buf = io.BytesIO()
                pil_crop.save(buf, format="JPEG", quality=92)
                logger.info("Face crop extracted via InsightFace RetinaFace", bbox=[x1, y1, x2, y2])
                return buf.getvalue(), True
        except Exception as exc:
            logger.debug("InsightFace crop attempt failed", error=str(exc))

    # ── Strategy 2: OpenCV Haar Cascade ──────────────────────────────────────
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        faces_haar = face_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40)
        )
        if len(faces_haar) > 0:
            # Pick the largest face
            x, y, fw, fh = max(faces_haar, key=lambda r: r[2] * r[3])
            pad_x = int(fw * 0.20)
            pad_y = int(fh * 0.25)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + fw + pad_x)
            y2 = min(h, y + fh + pad_y)
            face_crop_rgb = img_rgb[y1:y2, x1:x2]
            pil_crop = Image.fromarray(face_crop_rgb)
            buf = io.BytesIO()
            pil_crop.save(buf, format="JPEG", quality=92)
            logger.info("Face crop extracted via OpenCV Haar cascade", bbox=[x1, y1, x2, y2])
            return buf.getvalue(), True
    except Exception as exc:
        logger.debug("OpenCV Haar crop attempt failed", error=str(exc))

    logger.info("No face detected for crop — returning None")
    return None, False
