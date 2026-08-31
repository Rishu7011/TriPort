"""
Text Manipulation & Font Consistency Analysis Engine.

CONCEPT:
When text on an identity document (e.g., expiry date, name, or document number)
is digitally forged or altered, subtle anomalies occur:
  1. Font & Stroke-Width Inconsistency: The forged text often has a different stroke width,
     weight, or kerning compared to the document's baseline typography.
  2. Local Inconsistency / Splice Edges: Replaced text blocks frequently show sharp whiteout
     boundaries, background color discontinuity, or resolution/blur mismatches.
  3. Distance Transform Discrepancy: Skeletonized stroke widths (computed via morphological
     distance transform) vary sharply between genuine printed fields and forged inserts.

This module:
  1. Locates text contours and character components using OpenCV.
  2. Computes the document-wide baseline stroke-width distribution using Euclidean Distance Transform.
  3. Evaluates local stroke-width variance, height consistency, and background uniformity across text lines.
  4. Flags outlier text regions and computes an explainable text anomaly score (0.0 - 1.0).
"""

import io
from typing import Any
import cv2
import numpy as np
from PIL import Image

from backend.logging_config import get_logger

logger = get_logger("tampering_service.text_analysis")

TEXT_ANOMALY_THRESHOLD = 0.45


def _estimate_stroke_width(binary_text_mask: np.ndarray) -> tuple[float, float]:
    """
    Estimate mean and standard deviation of stroke width across a binary text mask
    using Euclidean Distance Transform.
    """
    if np.count_nonzero(binary_text_mask) == 0:
        return 0.0, 0.0

    # Distance transform assigns each text pixel its distance to the nearest background pixel
    dist = cv2.distanceTransform(binary_text_mask, cv2.DIST_L2, 5)
    # Stroke width is approximately 2 * distance at local maxima (medial axis)
    text_dist_values = dist[binary_text_mask > 0]
    if len(text_dist_values) == 0:
        return 0.0, 0.0

    mean_sw = float(np.mean(text_dist_values) * 2.0)
    std_sw = float(np.std(text_dist_values) * 2.0)
    return mean_sw, std_sw


def analyze_text_manipulation(
    image_bytes: bytes,
    known_fields: list[dict[str, Any]] | None = None,
) -> tuple[float, bool, list[dict[str, Any]], str, dict[str, Any]]:
    """
    Perform text manipulation and font consistency analysis on a document scan.

    Args:
        image_bytes: Raw bytes of the document scan.
        known_fields: Optional list of extracted field bounding boxes or names.

    Returns:
        tuple: (
            score: float (0.0 to 1.0 text anomaly score),
            flagged: bool (True if score >= TEXT_ANOMALY_THRESHOLD),
            flagged_fields: list[dict] (Specific text anomalies detected),
            detail: str (Human-readable forensic summary),
            metadata: dict (Global text metrics and region stats),
        )
    """
    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    except Exception as e:
        logger.error("Failed to decode image for text analysis", error=str(e))
        return 0.0, False, [], f"Image decode error: {e}", {}

    h, w = gray.shape[:2]

    # 1. Binarize image to segment dark text on light document background
    # Adaptive thresholding handles varying lighting across document scans
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        8,
    )

    # Exclude photo region and large graphics (contours that are too large or too small)
    min_char_area = (w * h) * 0.00002   # e.g., ~15-20 pixels minimum
    max_char_area = (w * h) * 0.02      # exclude huge passport photo/stamps

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_text_boxes = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_char_area <= area <= max_char_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Text characters typically have reasonable aspect ratios (0.15 to 4.0)
            aspect = bw / float(bh) if bh > 0 else 0
            if 0.1 <= aspect <= 5.0 and bh > 4:
                valid_text_boxes.append((x, y, bw, bh))

    if len(valid_text_boxes) < 5:
        detail = "Insufficient text contours detected on document for font consistency analysis."
        return 0.0, False, [], detail, {"char_count": len(valid_text_boxes)}

    # 2. Compute Global Stroke Width Baseline
    global_mask = np.zeros_like(thresh)
    for x, y, bw, bh in valid_text_boxes:
        global_mask[y : y + bh, x : x + bw] = thresh[y : y + bh, x : x + bw]

    global_mean_sw, global_std_sw = _estimate_stroke_width(global_mask)

    # 3. Group character boxes into horizontal text lines / local clusters
    # Sort boxes top-to-bottom, then group by Y coordinate proximity (within 10-15 px)
    valid_text_boxes.sort(key=lambda b: (b[1] // 18, b[0]))

    text_clusters: list[list[tuple[int, int, int, int]]] = []
    current_cluster: list[tuple[int, int, int, int]] = []

    for box in valid_text_boxes:
        if not current_cluster:
            current_cluster.append(box)
        else:
            prev_box = current_cluster[-1]
            # Same horizontal line if vertical overlap is high and horizontal distance is close
            y_diff = abs(box[1] - prev_box[1])
            x_gap = box[0] - (prev_box[0] + prev_box[2])
            if y_diff <= 14 and -5 <= x_gap <= 35:
                current_cluster.append(box)
            else:
                if len(current_cluster) >= 3:
                    text_clusters.append(current_cluster)
                current_cluster = [box]

    if current_cluster and len(current_cluster) >= 3:
        text_clusters.append(current_cluster)

    # 4. Analyze Local Clusters against Document Baseline
    # Compute document-wide median character height across text clusters
    cluster_means_h = [float(np.mean([b[3] for b in c])) for c in text_clusters]
    doc_median_h = float(np.median(cluster_means_h)) if cluster_means_h else 8.0

    flagged_fields = []
    cluster_scores = []
    outlier_count = 0

    for idx, cluster in enumerate(text_clusters):
        cx1 = min(b[0] for b in cluster)
        cy1 = min(b[1] for b in cluster)
        cx2 = max(b[0] + b[2] for b in cluster)
        cy2 = max(b[1] + b[3] for b in cluster)
        cw, ch = cx2 - cx1, cy2 - cy1

        # Local text mask
        local_mask = np.zeros_like(thresh)
        local_mask[cy1:cy2, cx1:cx2] = thresh[cy1:cy2, cx1:cx2]
        local_mean_sw, local_std_sw = _estimate_stroke_width(local_mask)

        # Character height stats in this cluster
        heights = [b[3] for b in cluster]
        mean_h = float(np.mean(heights))
        std_h = float(np.std(heights))

        # Check background variance around the text cluster
        pad = 4
        by1 = max(0, cy1 - pad)
        by2 = min(h, cy2 + pad)
        bx1 = max(0, cx1 - pad)
        bx2 = min(w, cx2 + pad)
        bg_patch = gray[by1:by2, bx1:bx2]
        bg_std = float(np.std(bg_patch))

        # Scale-invariant relative metrics
        rel_stroke_variance = local_std_sw / (local_mean_sw + 1e-4)
        rel_h_discrepancy = abs(mean_h - doc_median_h) / max(doc_median_h, 1.0)
        rel_height_std = std_h / (mean_h + 1e-4)

        local_score = 0.0
        reasons = []

        if rel_stroke_variance >= 0.08:
            local_score += min(0.60, (rel_stroke_variance - 0.06) * 6.0)
            reasons.append(f"Intra-field stroke-width variance (rel_std: {rel_stroke_variance:.2f})")

        if rel_h_discrepancy >= 0.35 and len(cluster) >= 4:
            local_score += 0.35
            reasons.append(f"Font height discrepancy vs document baseline ({mean_h:.1f}px vs {doc_median_h:.1f}px)")

        if rel_height_std >= 0.38 and len(cluster) >= 5:
            local_score += 0.25
            reasons.append(f"Inconsistent character heights (std: {std_h:.1f}px)")

        # Local background patch or contrast discontinuity around text box
        if bg_std >= 35.0 and local_score > 0.15:
            local_score += 0.20
            reasons.append("Background patch border discontinuity detected")

        if local_score >= 0.30 and len(cluster) >= 4:
            outlier_count += 1
            flagged_fields.append({
                "cluster_index": idx,
                "bbox": [int(cx1), int(cy1), int(cw), int(ch)],
                "anomaly_score": round(min(local_score, 1.0), 3),
                "reasons": reasons,
                "local_stroke_width": round(local_mean_sw, 2),
                "baseline_stroke_width": round(global_mean_sw, 2),
            })
            cluster_scores.append(local_score)

    # 5. Composite Text Anomaly Score (Scale-Invariant)
    # A forgery is characterized by localized anomalies (1-3 tampered fields).
    # If a huge fraction (>30%) of lines are flagged, it indicates natural multi-font document design, not isolated forgery.
    total_clusters_count = max(len(text_clusters), 1)
    outlier_ratio = outlier_count / total_clusters_count

    if cluster_scores and outlier_count > 0:
        max_cluster_score = max(cluster_scores)
        if outlier_ratio <= 0.30:
            # Genuine isolated text tampering
            score = float(np.clip(max_cluster_score, 0.0, 1.0))
        else:
            # Multi-tier font layout across entire document (e.g. passport header vs labels)
            score = float(np.clip(max_cluster_score * 0.3, 0.0, 0.30))
    else:
        score = 0.0

    flagged = score >= TEXT_ANOMALY_THRESHOLD and outlier_count > 0 and outlier_ratio <= 0.30

    metadata = {
        "total_text_clusters": len(text_clusters),
        "outlier_clusters_count": outlier_count,
        "global_mean_stroke_width": round(global_mean_sw, 2),
        "global_std_stroke_width": round(global_std_sw, 2),
        "flagged_regions": flagged_fields,
    }

    if flagged:
        reasons_summary = "; ".join([r for f in flagged_fields for r in f["reasons"]][:3])
        detail = (
            f"Text analysis detected font/stroke anomalies in {outlier_count} region(s) "
            f"(anomaly score: {score:.2f}): {reasons_summary}."
        )
    else:
        detail = (
            f"Typography and stroke-width uniformity are consistent across document "
            f"(baseline stroke width: {global_mean_sw:.1f}px, score: {score:.2f})."
        )

    logger.info("Text manipulation analysis completed", score=score, flagged=flagged, outliers=outlier_count)
    return score, flagged, flagged_fields, detail, metadata
