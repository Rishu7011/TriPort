"""
Metadata & EXIF Forensics Engine.

CONCEPT:
Physical documents photographed at checkpoints or legitimate scans typically exhibit
consistent camera/scanner metadata. Edited or forged documents frequently carry
signatures of editing tools (Photoshop, GIMP, Snapseed) in their EXIF/XMP tags,
inconsistent modification timestamps, or stripped hardware profiles.

This module:
  1. Parses raw EXIF, TIFF, and JPEG application markers (via Pillow and exifread).
  2. Scans for known image manipulation software signatures.
  3. Checks timestamp discrepancies (e.g. ModifyDate != CreateDate).
  4. Generates an explainable forensics report and anomaly score.
"""

import io
from typing import Any
import exifread
from PIL import Image, ExifTags

from backend.logging_config import get_logger

logger = get_logger("tampering_service.metadata_forensics")

SUSPICIOUS_SOFTWARE_KEYWORDS = [
    "photoshop",
    "gimp",
    "snapseed",
    "canva",
    "pixlr",
    "photoscape",
    "paint.net",
    "lightroom",
    "affinity",
    "coreldraw",
    "picsart",
    "facetune",
    "vsco",
]


def analyze_metadata(image_bytes: bytes) -> tuple[float, bool, list[str], dict[str, Any], str]:
    """
    Perform forensic analysis on image metadata/EXIF headers.

    Args:
        image_bytes: Raw bytes of the document scan.

    Returns:
        tuple: (
            score: float (0.0 to 1.0 suspiciousness score),
            flagged: bool (True if score >= 0.5),
            flags: list[str] (List of specific detected red flags),
            raw_metadata: dict[str, Any] (Extracted metadata fields),
            detail: str (Human-readable forensic summary),
        )
    """
    flags: list[str] = []
    raw_metadata: dict[str, Any] = {}
    score = 0.0

    # 1. Parse using exifread
    try:
        tags = exifread.process_file(io.BytesIO(image_bytes), details=False)
        for k, v in tags.items():
            if k not in ("JPEGThumbnail", "TIFFThumbnail"):
                raw_metadata[str(k)] = str(v)
    except Exception as e:
        logger.debug("exifread parsing error", error=str(e))

    # 2. Parse using Pillow EXIF tags for additional coverage
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        exif_data = pil_img.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="ignore")
                    except Exception:
                        value = str(value)
                raw_metadata[tag_name] = str(value)
    except Exception as e:
        logger.debug("Pillow EXIF extraction error", error=str(e))

    # 3. Check for Editing Software Signatures
    software_val = (
        raw_metadata.get("Image Software")
        or raw_metadata.get("Software")
        or raw_metadata.get("ProcessingSoftware")
        or ""
    ).lower()

    artist_val = (raw_metadata.get("Image Artist") or raw_metadata.get("Artist") or "").lower()
    description_val = (raw_metadata.get("Image ImageDescription") or raw_metadata.get("ImageDescription") or "").lower()

    combined_text = f"{software_val} {artist_val} {description_val}"

    detected_software = []
    for kw in SUSPICIOUS_SOFTWARE_KEYWORDS:
        if kw in combined_text:
            detected_software.append(kw.capitalize())

    if detected_software:
        flags.append(f"Image manipulation software detected in EXIF: {', '.join(detected_software)}")
        score += 0.70

    # 4. Check for Timestamp Discrepancies
    date_original = raw_metadata.get("EXIF DateTimeOriginal") or raw_metadata.get("DateTimeOriginal")
    date_modify = raw_metadata.get("Image DateTime") or raw_metadata.get("DateTime") or raw_metadata.get("ModifyDate")

    if date_original and date_modify and date_original != date_modify:
        flags.append(f"Timestamp mismatch: Captured {date_original} but modified {date_modify}")
        score += 0.25

    # 5. Check for stripped metadata / software re-encoding
    # If the file has color profile or compression headers commonly injected by web converters
    if "Adobe Photoshop" in str(raw_metadata):
        if "Photoshop" not in detected_software:
            flags.append("Adobe Photoshop XMP profile detected in file headers")
            score += 0.60

    score = float(min(score, 1.0))
    flagged = score >= 0.50

    if flagged:
        detail = f"Forensic analysis detected suspicious metadata flags: {'; '.join(flags)}."
    elif flags:
        detail = f"Minor metadata anomalies noted: {'; '.join(flags)} (score: {score:.2f})."
    else:
        detail = "No editing software signatures or metadata inconsistencies detected."

    logger.info("Metadata forensics completed", score=score, flagged=flagged, flags_count=len(flags))
    return score, flagged, flags, raw_metadata, detail
