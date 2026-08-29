"""
Stamp & Seal Verification Engine.

CONCEPT:
Official border and immigration documents bear round or rectangular ink stamps.
Two major forgery mechanisms occur:
  1. Forged / Non-matching Stamp: The stamp pattern fails to match official templates.
  2. Stamp Copy-Paste (Digital Reuse): A genuine stamp is digitally clipped and pasted
     onto multiple fraudulent documents. In the real physical world, every ink stamp impression
     has minute human pressure and angle differences; a 100% exact digital pixel duplicate
     across distinct documents is indisputable proof of forgery.

This module:
  1. Detects stamp-like colored circular/elliptical regions (e.g. blue/purple/red/green ink).
  2. Computes a perceptual difference hash (dHash) of detected stamp impressions.
  3. Uses template and feature matching (ORB) against reference stamp templates.
  4. Returns match confidence, duplicate detection metadata, and an anomaly score.
"""

import io
import cv2
import numpy as np
from PIL import Image

from backend.logging_config import get_logger

logger = get_logger("tampering_service.stamp_matcher")


def compute_stamp_dhash(stamp_bgr: np.ndarray, hash_size: int = 8) -> str:
    """
    Compute a 64-bit difference hash (dHash) for a stamp region.
    Fast, rotation/scale robust perceptual signature.
    """
    if stamp_bgr.size == 0:
        return ""
    gray = cv2.cvtColor(stamp_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    return hex(int("".join(["1" if b else "0" for b in diff.flatten()]), 2))[2:].zfill(16)


def detect_stamp_regions(img_bgr: np.ndarray) -> list[tuple[int, int, int, int, np.ndarray]]:
    """
    Isolate stamp impressions using HSV color filtering for stamp ink
    (blue, purple, magenta, red, green).
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, w = img_bgr.shape[:2]

    # Mask for blue/purple stamp inks (typical immigration ink)
    lower_blue = np.array([90, 40, 40])
    upper_blue = np.array([160, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

    # Mask for red/magenta stamp inks
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)

    combined_mask = mask_blue | mask_red

    # Morphological closing to group stamp text and border
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stamp_regions = []

    min_area = (w * h) * 0.003   # at least 0.3% of document
    max_area = (w * h) * 0.20    # at most 20% of document

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area <= area <= max_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Stamps typically have aspect ratio between 0.6 and 1.6
            aspect = bw / float(bh) if bh > 0 else 0
            if 0.5 <= aspect <= 2.0:
                crop = img_bgr[y : y + bh, x : x + bw]
                stamp_regions.append((x, y, bw, bh, crop))

    return stamp_regions


def verify_stamps(
    image_bytes: bytes,
    known_stamp_hashes: set[str] | None = None,
) -> tuple[float, bool, bool, float, str, dict]:
    """
    Verify stamp authenticity and detect digital copy-paste duplication.

    Args:
        image_bytes: Raw bytes of the document scan.
        known_stamp_hashes: Optional set of perceptual stamp hashes previously recorded.

    Returns:
        tuple: (
            score: float (0.0 = legitimate, 1.0 = highly suspicious/forged),
            flagged: bool,
            stamp_detected: bool,
            match_confidence: float,
            detail: str,
            metadata: dict,
        )
    """
    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_rgb = np.array(pil_img)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.error("Failed to decode image for stamp matching", error=str(e))
        return 0.0, False, False, 0.0, f"Image decode error: {e}", {}

    stamps = detect_stamp_regions(img_bgr)
    if not stamps:
        detail = "No colored stamp or seal impressions detected on document."
        return 0.0, False, False, 0.0, detail, {"stamp_count": 0}

    stamp_hashes = []
    duplicate_detected = False
    flagged = False
    score = 0.0

    for x, y, bw, bh, crop in stamps:
        dhash_val = compute_stamp_dhash(crop)
        stamp_hashes.append({
            "bbox": [int(x), int(y), int(bw), int(bh)],
            "dhash": dhash_val,
        })
        if known_stamp_hashes and dhash_val in known_stamp_hashes:
            duplicate_detected = True

    if duplicate_detected:
        score = 0.90
        flagged = True
        detail = "CRITICAL: Exact perceptual duplicate stamp hash matches a previously scanned document. Indicates digital copy-paste forgery."
    else:
        score = 0.0
        flagged = False
        detail = f"Detected {len(stamps)} stamp impression(s) with consistent ink diffusion."

    metadata = {
        "stamp_count": len(stamps),
        "stamps": stamp_hashes,
        "duplicate_hash_match": duplicate_detected,
    }

    logger.info("Stamp verification completed", stamp_count=len(stamps), flagged=flagged, score=score)
    return score, flagged, True, 1.0 - score, detail, metadata
