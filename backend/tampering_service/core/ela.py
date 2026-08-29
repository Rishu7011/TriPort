"""
Error Level Analysis (ELA) Engine.

CONCEPT:
When an image is saved as a JPEG, each 8x8 block is compressed at a specific
quality level. If a portion of the image is modified (e.g. text edited or a photo
spliced in) and the image is resaved, the modified region undergoes a different
error rate compared to unmodified regions.

This module:
  1. Recompresses the image at a known quality (e.g. 90).
  2. Computes the absolute difference between original and recompressed pixels.
  3. Amplifies the error level difference to generate a colorized heatmap (using cv2 JET colormap).
  4. Calculates statistical anomaly metrics (peak local error vs global mean error) to output a 0.0-1.0 score.
"""

import base64
import io
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from backend.logging_config import get_logger

logger = get_logger("tampering_service.ela")

ELA_JPEG_QUALITY = 90
ELA_SCALE_FACTOR = 15
ELA_ANOMALY_THRESHOLD = 0.45


def compute_ela(
    image_bytes: bytes,
    quality: int = ELA_JPEG_QUALITY,
    scale_factor: int = ELA_SCALE_FACTOR,
) -> tuple[float, bool, bytes, str]:
    """
    Perform Error Level Analysis on image bytes.

    Args:
        image_bytes: Raw bytes of the document scan.
        quality: JPEG recompression quality (default: 90).
        scale_factor: Multiplier for difference amplification (default: 15).

    Returns:
        tuple: (
            score: float (0.0 to 1.0 anomaly score),
            flagged: bool (True if score >= ELA_ANOMALY_THRESHOLD),
            heatmap_png_bytes: bytes (Colorized PNG heatmap),
            detail: str (Explainable summary of findings),
        )
    """
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        logger.error("Failed to open image for ELA", error=str(e))
        return 0.0, False, b"", f"Invalid image format: {e}"

    # 1. Resave at target quality into an in-memory buffer
    buffer = io.BytesIO()
    original.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")

    # 2. Compute absolute difference between original and recompressed
    ela_diff = ImageChops.difference(original, recompressed)

    # 3. Amplify differences for human visualization
    extrema = ela_diff.getextrema()
    max_diff = max([ex[1] for ex in extrema]) if extrema else 1
    if max_diff == 0:
        max_diff = 1

    scale = 255.0 / max_diff * (scale_factor / 10.0)
    scale = min(scale, 30.0)  # Bound amplification to avoid blowup
    enhanced = ImageEnhance.Brightness(ela_diff).enhance(scale)

    # 4. Generate colorized heatmap using OpenCV JET colormap
    np_diff = np.array(enhanced)
    gray_diff = cv2.cvtColor(np_diff, cv2.COLOR_RGB2GRAY)
    heatmap_bgr = cv2.applyColorMap(gray_diff, cv2.COLORMAP_JET)

    # Blend heatmap 60% with original grayscale document 40% for visual context
    orig_np = np.array(original)
    orig_gray = cv2.cvtColor(orig_np, cv2.COLOR_RGB2GRAY)
    orig_bgr = cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR)
    blended = cv2.addWeighted(heatmap_bgr, 0.65, orig_bgr, 0.35, 0)

    # Convert blended heatmap to PNG bytes
    is_success, buffer_png = cv2.imencode(".png", blended)
    heatmap_png_bytes = buffer_png.tobytes() if is_success else b""

    # 5. Statistical Anomaly Calculation
    # Tampered regions produce high local variance / localized clusters of high error
    # Compute std deviation and 98th percentile error vs mean
    mean_err = float(np.mean(gray_diff))
    std_err = float(np.std(gray_diff))
    p98_err = float(np.percentile(gray_diff, 98))

    # Anomaly metric: high ratio of top 2% intensity to global mean indicates localized edits
    if mean_err > 0.001:
        ratio = p98_err / (mean_err + 1e-5)
    else:
        ratio = 1.0

    # Normalize ratio into 0.0 - 1.0 range
    # In pristine images, ratio typically ranges 1.5 - 3.5.
    # In edited images (e.g. text modification / photo swap), ratio spikes > 5.0 - 10.0.
    raw_score = (ratio - 2.0) / 7.0
    score = float(np.clip(raw_score, 0.0, 1.0))
    flagged = score >= ELA_ANOMALY_THRESHOLD

    if flagged:
        detail = (
            f"ELA detected localized compression disparity (anomaly score: {score:.2f}, "
            f"peak/mean ratio: {ratio:.1f}). Possible text alteration or spliced region."
        )
    else:
        detail = f"ELA compression levels are uniform across document (score: {score:.2f})."

    logger.info("ELA analysis completed", score=score, flagged=flagged, ratio=ratio)
    return score, flagged, heatmap_png_bytes, detail


def ela_to_base64(heatmap_bytes: bytes) -> str:
    """Convert PNG heatmap bytes to a base64 data URI string."""
    if not heatmap_bytes:
        return ""
    b64_str = base64.b64encode(heatmap_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"
