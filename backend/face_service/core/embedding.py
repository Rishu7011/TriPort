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
from typing import Any
from PIL import Image

from backend.logging_config import get_logger

logger = get_logger("face_service.embedding")

EMBEDDING_DIM = 512

# ── Lazy-loaded model singletons ─────────────────────────────────────────────
_insightface_app = None       # InsightFace FaceAnalysis (RetinaFace + ArcFace)
_insightface_attempted = False
_deepface_models: dict = {}   # DeepFace model cache
_mediapipe_available: bool | None = None
_deepface_available: bool | None = None


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
    global _insightface_app, _insightface_attempted
    if _insightface_attempted:
        return _insightface_app

    _insightface_attempted = True
    try:
        import insightface
        from insightface.app import FaceAnalysis
        from insightface.model_zoo import model_zoo

        # Ensure buffalo_l model pack is present; download if not.
        try:
            model_zoo.get_model("buffalo_l")  # no-op if already downloaded
        except Exception as dl_exc:
            logger.info(
                "Downloading InsightFace buffalo_l model pack (first run only) …",
                error=str(dl_exc),
            )

        app = FaceAnalysis(
            name="buffalo_l",          # buffalo_l bundles RetinaFace + ArcFace W600K R50
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        app.prepare(ctx_id=0, det_size=(640, 640))
        _insightface_app = app
        logger.info("InsightFace FaceAnalysis (RetinaFace+ArcFace) initialized successfully")
    except Exception as exc:
        logger.warning(
            "InsightFace unavailable — will use DeepFace/Haar cascade fallback.",
            error=str(exc),
        )
        _insightface_app = None
    return _insightface_app


def _pad_for_detection(img_rgb: np.ndarray, pad_fraction: float = 0.25) -> np.ndarray:
    """Add white padding around the image so tight-cropped faces can be detected.

    Both RetinaFace and Haar cascade require some background margin around the
    face bounding box to fire reliably. Passport photos cropped to just the face
    (face filling 80-100% of frame) consistently fail detection without this step.
    """
    h, w = img_rgb.shape[:2]
    pad_h = int(h * pad_fraction)
    pad_w = int(w * pad_fraction)
    padded = np.full(
        (h + 2 * pad_h, w + 2 * pad_w, 3),
        fill_value=240,  # light-grey background — neutral for face detectors
        dtype=np.uint8,
    )
    padded[pad_h:pad_h + h, pad_w:pad_w + w] = img_rgb
    return padded


def _is_tight_crop(img_rgb: np.ndarray) -> bool:
    """Heuristic: is this likely a tight face crop (face fills most of the frame)?

    We check a small central region for skin-tone pixels. If the centre of the
    image is predominantly skin-toned AND the image is roughly portrait-aspect,
    we assume a passport-style crop and pre-pad it before detection.
    """
    h, w = img_rgb.shape[:2]
    # Typical passport photo: portrait aspect, small absolute size
    if h == 0 or w == 0:
        return False
    aspect = h / w
    if not (0.9 <= aspect <= 1.6):
        return False
    # Sample the centre 40% of the image and check average saturation
    cy, cx = h // 2, w // 2
    region = img_rgb[
        max(0, cy - h // 5): cy + h // 5,
        max(0, cx - w // 5): cx + w // 5,
    ]
    if region.size == 0:
        return False
    # HSV saturation heuristic — skin tones have moderate saturation
    import colorsys
    r, g, b = region[:, :, 0].mean() / 255, region[:, :, 1].mean() / 255, region[:, :, 2].mean() / 255
    _, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s < 0.55 and v > 0.35  # low saturation, non-dark → likely skin/neutral


def _extract_arcface_embedding(img_rgb: np.ndarray) -> tuple[list[float], str] | None:
    """
    Stage 1: Extract ArcFace 512-dim embedding via InsightFace.

    Returns (embedding_list, detail_str) on success, None on failure.
    RetinaFace handles detection + 5-landmark alignment internally.

    Pre-pads tight passport crops before detection, because RetinaFace needs
    some background margin to reliably fire its bounding-box detector.
    """
    app = _get_insightface_app()
    if app is None:
        return None

    try:
        # InsightFace expects BGR
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        faces = app.get(img_bgr)

        # ── Tight-crop retry: add padding and re-detect ──────────────────────
        if not faces and _is_tight_crop(img_rgb):
            logger.debug("InsightFace: no face on first pass — retrying with padded image")
            padded_rgb = _pad_for_detection(img_rgb, pad_fraction=0.30)
            padded_bgr = cv2.cvtColor(padded_rgb, cv2.COLOR_RGB2BGR)
            faces = app.get(padded_bgr)

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

# Ordered list of DeepFace detector backends to try when the primary (opencv)
# fails. "skip" tells DeepFace to embed the entire image without detection —
# this is the last resort for tightly-cropped passport photos where no
# detector fires but the whole image IS the face.
_DEEPFACE_DETECTOR_BACKENDS = ["opencv", "ssd", "skip"]


def _extract_deepface_facenet512(
    img_rgb: np.ndarray,
    enforce_detection: bool = False,
) -> tuple[list[float], str] | None:
    """
    Stage 2: Extract 512-dim embedding using DeepFace Facenet512.
    Falls back to this when InsightFace is unavailable.

    Tries multiple detector backends in order (opencv → ssd → skip) so that
    tightly-cropped passport photos — which defeat opencv's Haar cascade —
    still get embedded via the 'skip' backend (whole-image embedding).
    """
    try:
        from deepface import DeepFace
    except ImportError:
        logger.debug("DeepFace not installed — Stage 2 unavailable")
        return None

    for backend in _DEEPFACE_DETECTOR_BACKENDS:
        try:
            representations = DeepFace.represent(
                img_path=img_rgb,
                model_name="Facenet512",
                enforce_detection=enforce_detection if backend != "skip" else False,
                align=(backend != "skip"),   # alignment requires detection
                detector_backend=backend,
            )
            if representations and len(representations) > 0:
                raw_vec = np.array(representations[0]["embedding"], dtype=np.float64)
                raw_vec = _ensure_512d(raw_vec)
                raw_vec = _l2_normalize(raw_vec)
                label = f"DeepFace Facenet512 [detector={backend}]"
                if backend == "skip":
                    label += " — whole-image embedding (tight crop mode)"
                logger.info("DeepFace Facenet512 embedding extracted", dims=len(raw_vec), backend=backend)
                return raw_vec.tolist(), label
        except Exception as exc:
            logger.debug(f"DeepFace Facenet512 [{backend}] failed", error=str(exc))
            continue

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


def _detect_faces_opencv(img_rgb: np.ndarray) -> tuple[int, Any]:
    """Return face count and detections using Haar cascades when available."""
    if not hasattr(cv2, "CascadeClassifier"):
        return 0, None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    detected_faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
    )
    return len(detected_faces), detected_faces


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
    face_count, _ = _detect_faces_opencv(img_rgb)

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
      2. MediaPipe Face Detection / Mesh (if available)
      3. OpenCV Haar cascades (multiple cascade profiles + histogram equalization)
      4. DeepFace face detector (if available)

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
    if h < 20 or w < 20:
        return None, False

    def _crop_and_encode(x1: int, y1: int, x2: int, y2: int, pad_pct: float = 0.22) -> bytes | None:
        pw = int((x2 - x1) * pad_pct)
        ph = int((y2 - y1) * (pad_pct + 0.08))  # slightly more vertical headroom for hair & chin
        nx1 = max(0, x1 - pw)
        ny1 = max(0, y1 - ph)
        nx2 = min(w, x2 + pw)
        ny2 = min(h, y2 + ph)

        crop_rgb = img_rgb[ny1:ny2, nx1:nx2]
        if crop_rgb.shape[0] < 10 or crop_rgb.shape[1] < 10:
            return None

        pil_crop = Image.fromarray(crop_rgb)
        buf = io.BytesIO()
        pil_crop.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    # ── Strategy 1: InsightFace RetinaFace bounding box ──────────────────────
    app = _get_insightface_app()
    if app is not None:
        try:
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            faces = app.get(img_bgr)
            if not faces and _is_tight_crop(img_rgb):
                padded_rgb = _pad_for_detection(img_rgb, pad_fraction=0.30)
                padded_bgr = cv2.cvtColor(padded_rgb, cv2.COLOR_RGB2BGR)
                faces = app.get(padded_bgr)
            if faces:
                best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                x1, y1, x2, y2 = [int(v) for v in best.bbox]
                crop = _crop_and_encode(x1, y1, x2, y2, pad_pct=0.20)
                if crop:
                    logger.info("Face crop extracted via InsightFace RetinaFace", bbox=[x1, y1, x2, y2])
                    return crop, True
        except Exception as exc:
            logger.debug("InsightFace crop attempt failed", error=str(exc))

    global _mediapipe_available, _deepface_available

    # ── Strategy 2: MediaPipe Face Detection ─────────────────────────────────
    if _mediapipe_available is not False:
        try:
            import mediapipe as mp
            _mediapipe_available = True
            mp_face_detection = mp.solutions.face_detection
            with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.45) as detector:
                results = detector.process(img_rgb)
                if results.detections:
                    best_det = max(
                        results.detections,
                        key=lambda d: d.location_data.relative_bounding_box.width * d.location_data.relative_bounding_box.height,
                    )
                    bb = best_det.location_data.relative_bounding_box
                    x1 = int(bb.xmin * w)
                    y1 = int(bb.ymin * h)
                    x2 = int((bb.xmin + bb.width) * w)
                    y2 = int((bb.ymin + bb.height) * h)
                    crop = _crop_and_encode(x1, y1, x2, y2, pad_pct=0.20)
                    if crop:
                        logger.info("Face crop extracted via MediaPipe FaceDetection", bbox=[x1, y1, x2, y2])
                        return crop, True
        except Exception as exc:
            _mediapipe_available = False
            logger.debug("MediaPipe FaceDetection unavailable", error=str(exc))

    # ── Strategy 3: OpenCV Haar Cascades ──────────────────────────────────────
    try:
        if hasattr(cv2, "CascadeClassifier"):
            cascade_names = [
                "haarcascade_frontalface_default.xml",
                "haarcascade_frontalface_alt2.xml",
                "haarcascade_frontalface_alt.xml",
                "haarcascade_profileface.xml",
            ]
            gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
            gray_eq = cv2.equalizeHist(gray)

            # Downscale large images for 10x faster Haar cascade detection
            scale = 1.0
            if max(w, h) > 1000:
                scale = 1000.0 / float(max(w, h))
                dw, dh = int(w * scale), int(h * scale)
                d_gray = cv2.resize(gray, (dw, dh), interpolation=cv2.INTER_LINEAR)
                d_gray_eq = cv2.resize(gray_eq, (dw, dh), interpolation=cv2.INTER_LINEAR)
            else:
                d_gray, d_gray_eq = gray, gray_eq

            for c_name in cascade_names:
                cascade_path = cv2.data.haarcascades + c_name
                face_cascade = cv2.CascadeClassifier(cascade_path)
                if face_cascade.empty():
                    continue

                for g_img in (d_gray, d_gray_eq):
                    faces_haar = face_cascade.detectMultiScale(
                        g_img, scaleFactor=1.08, minNeighbors=3, minSize=(30, 30)
                    )
                    if len(faces_haar) > 0:
                        sx, sy, sfw, sfh = max(faces_haar, key=lambda r: r[2] * r[3])
                        x = int(sx / scale)
                        y = int(sy / scale)
                        fw = int(sfw / scale)
                        fh = int(sfh / scale)
                        crop = _crop_and_encode(x, y, x + fw, y + fh, pad_pct=0.22)
                        if crop:
                            logger.info(
                                "Face crop extracted via OpenCV Haar cascade",
                                cascade=c_name,
                                bbox=[x, y, x + fw, y + fh],
                            )
                            return crop, True
    except Exception as exc:
        logger.debug("OpenCV Haar crop attempt failed", error=str(exc))

    # ── Strategy 4: DeepFace extract_faces fallback ──────────────────────────
    if _deepface_available is not False:
        try:
            from deepface import DeepFace
            _deepface_available = True
            for backend in ["opencv", "ssd", "retinaface"]:
                try:
                    extracted = DeepFace.extract_faces(
                        img_path=img_rgb,
                        detector_backend=backend,
                        enforce_detection=False,
                        align=True,
                    )
                    if extracted and len(extracted) > 0:
                        fa = extracted[0].get("facial_area", {})
                        x = fa.get("x", 0)
                        y = fa.get("y", 0)
                        fw = fa.get("w", 0)
                        fh = fa.get("h", 0)
                        if fw > 20 and fh > 20:
                            crop = _crop_and_encode(x, y, x + fw, y + fh, pad_pct=0.18)
                            if crop:
                                logger.info("Face crop extracted via DeepFace", backend=backend, bbox=[x, y, x + fw, y + fh])
                                return crop, True
                except Exception:
                    continue
        except Exception as exc:
            _deepface_available = False
            logger.debug("DeepFace unavailable", error=str(exc))

    # ── Strategy 5: ICAO 9303 Passport Photo Window Heuristic ─────────────────
    # If the document is a standard landscape ID-3 passport (w > h), standard
    # specifications position the portrait in the left quadrant.
    if w >= 300 and h >= 200 and w > h:
        px1 = int(w * 0.04)
        py1 = int(h * 0.16)
        px2 = int(w * 0.32)
        py2 = int(h * 0.65)
        crop = _crop_and_encode(px1, py1, px2, py2, pad_pct=0.0)
        if crop:
            logger.info("Face crop extracted via ICAO 9303 layout positioning", bbox=[px1, py1, px2, py2])
            return crop, True

    logger.info("No face detected for crop — returning None")
    return None, False

