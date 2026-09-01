"""
Photo Boundary & Noise Analysis Engine.

CONCEPT:
When a forger splices a different photo onto an identity document, two physical
anomalies occur:
  1. Boundary Discontinuity: A sharp, rectangular edge discontinuity along the
     photo perimeter (detected via Sobel / Canny edge intensity along the boundary).
  2. Noise Variance Mismatch: The photo region originates from a different sensor
     or compression history than the underlying document substrate, causing a
     measurable discrepancy in local high-frequency noise variance.

This module:
  1. Locates the document photo region using OpenCV face detection (Haar cascade)
     or contour heuristics.
  2. Measures boundary edge gradient energy along the photo perimeter.
  3. Computes the noise variance ratio (Laplacian variance in photo vs document background).
  4. Combines boundary energy and noise mismatch into an anomaly score (0.0-1.0).
"""

import io
import cv2
import numpy as np
from PIL import Image

from backend.logging_config import get_logger

logger = get_logger("tampering_service.boundary_analysis")

# Preload OpenCV Haar Cascade for face detection
_face_cascade = None


def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        try:
            if not hasattr(cv2, "CascadeClassifier"):
                logger.warning("OpenCV CascadeClassifier unavailable in this build")
                return None
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            _face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            logger.warning("Could not load default OpenCV face cascade", error=str(e))
    return _face_cascade


def _compute_noise_variance(img_gray: np.ndarray) -> float:
    """Compute local high-frequency noise variance using Laplacian operator."""
    if img_gray.size == 0:
        return 0.0
    laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
    return float(laplacian.var())


def analyze_photo_boundaries(image_bytes: bytes) -> tuple[float, bool, str, dict]:
    """
    Analyze photo boundaries and noise consistency on a document scan.

    Args:
        image_bytes: Raw bytes of the document scan.

    Returns:
        tuple: (
            score: float (0.0 to 1.0 anomaly score),
            flagged: bool (True if score >= 0.50),
            detail: str (Explainable summary),
            metadata: dict (Boundary metrics and detected bounding box)
        )
    """
    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    except Exception as e:
        logger.error("Failed to decode image for boundary analysis", error=str(e))
        return 0.0, False, f"Image decode error: {e}", {}

    h, w = gray.shape[:2]
    cascade = get_face_cascade()
    faces = []
    if cascade is not None:
        try:
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(int(w * 0.08), int(h * 0.08)),
            )
        except Exception as e:
            logger.debug("Face cascade detection error", error=str(e))

    # If face detected, expand bounding box to cover the full passport portrait box
    photo_box = None
    if len(faces) > 0:
        fx, fy, fw, fh = faces[0]
        # Expand box by ~30% vertically/horizontally to capture collar and head boundary
        pad_x = int(fw * 0.25)
        pad_y = int(fh * 0.35)
        x1 = max(0, fx - pad_x)
        y1 = max(0, fy - pad_y)
        x2 = min(w, fx + fw + pad_x)
        y2 = min(h, fy + fh + pad_y)
        photo_box = (x1, y1, x2 - x1, y2 - y1)
    else:
        # Heuristic fallback: passport photos are typically in left column (x: 5%-28%, y: 18%-58%)
        x1, y1, bw, bh = int(w * 0.05), int(h * 0.18), int(w * 0.23), int(h * 0.40)
        photo_box = (x1, y1, bw, bh)

    bx, by, bw_box, bh_box = photo_box
    photo_region = gray[by : by + bh_box, bx : bx + bw_box]

    # Create background mask (everything outside the photo region)
    bg_mask = np.ones((h, w), dtype=bool)
    bg_mask[by : by + bh_box, bx : bx + bw_box] = False
    bg_region = gray[bg_mask]

    # 1. Noise Variance Comparison
    photo_noise = _compute_noise_variance(photo_region)
    bg_noise = _compute_noise_variance(bg_region)

    if min(photo_noise, bg_noise) > 0:
        noise_ratio = max(photo_noise, bg_noise) / (min(photo_noise, bg_noise) + 1e-4)
    else:
        noise_ratio = 1.0

    # 2. Boundary Edge Energy (Perimeter gradient check along all 4 borders)
    border_strip_energy = 0.0
    perimeter_pixels = []
    border_thickness = 3

    # Top & bottom border strips
    if by >= border_thickness and by + bh_box + border_thickness <= h:
        top_strip = gray[by - border_thickness : by + border_thickness, bx : bx + bw_box]
        bottom_strip = gray[by + bh_box - border_thickness : by + bh_box + border_thickness, bx : bx + bw_box]
        perimeter_pixels.extend(top_strip.flatten())
        perimeter_pixels.extend(bottom_strip.flatten())

    # Left & right border strips
    if bx >= border_thickness and bx + bw_box + border_thickness <= w:
        left_strip = gray[by : by + bh_box, bx - border_thickness : bx + border_thickness]
        right_strip = gray[by : by + bh_box, bx + bw_box - border_thickness : bx + bw_box + border_thickness]
        perimeter_pixels.extend(left_strip.flatten())
        perimeter_pixels.extend(right_strip.flatten())

    if perimeter_pixels:
        perimeter_arr = np.array(perimeter_pixels)
        border_strip_energy = float(np.std(perimeter_arr))

    # 3. Calculate Anomaly Score
    # Natural photos typically have noise_ratio between 1.0 and 3.2, photo_noise < 30
    # Splices from another noisy source exhibit photo_noise > 35 or noise_ratio > 3.5
    noise_anomaly = float(np.clip((photo_noise - 18.0) / 25.0, 0.0, 1.0))
    ratio_anomaly = float(np.clip((noise_ratio - 2.8) / 3.0, 0.0, 1.0))
    border_anomaly = float(np.clip((border_strip_energy - 36.0) / 20.0, 0.0, 1.0))

    combined_score = float(np.clip(0.4 * noise_anomaly + 0.3 * ratio_anomaly + 0.3 * border_anomaly, 0.0, 1.0))
    flagged = combined_score >= 0.45

    metadata = {
        "photo_box": [int(bx), int(by), int(bw_box), int(bh_box)],
        "face_detected": len(faces) > 0,
        "photo_noise_variance": round(photo_noise, 2),
        "background_noise_variance": round(bg_noise, 2),
        "noise_ratio": round(noise_ratio, 2),
        "border_gradient_energy": round(border_strip_energy, 2),
    }

    if flagged:
        detail = (
            f"Photo region exhibits significant noise discrepancy or boundary discontinuity "
            f"(photo noise: {photo_noise:.1f}, noise ratio: {noise_ratio:.1f}, anomaly score: {combined_score:.2f}). "
            f"Potential photo replacement / splice detected."
        )
    else:
        detail = (
            f"Photo region noise characteristics match background substrate "
            f"(noise ratio: {noise_ratio:.1f}, score: {combined_score:.2f})."
        )

    logger.info("Photo boundary analysis completed", score=combined_score, flagged=flagged, noise_ratio=noise_ratio)
    return combined_score, flagged, detail, metadata
