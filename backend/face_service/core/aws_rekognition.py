"""
AWS Rekognition Integration Module for Face Verification and Analysis.

Provides cloud-grade 1:1 facial comparison (CompareFaces), facial attribute
detection (DetectFaces), and collection indexing with automatic error handling
and graceful fallback when credentials are not configured or offline.
"""

import os
import io
from PIL import Image
from backend.logging_config import get_logger

logger = get_logger("face_service.aws_rekognition")

_boto3_client = None


def get_rekognition_client():
    """Lazy-load and return configured boto3 Rekognition client."""
    global _boto3_client
    if _boto3_client is not None:
        return _boto3_client

    try:
        from dotenv import load_dotenv
        load_dotenv("backend/.env")
        load_dotenv(".env")
    except Exception:
        pass

    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))

    if not aws_access_key or not aws_secret_key:
        logger.debug("AWS credentials not configured — Rekognition client unavailable")
        return None

    try:
        import boto3
        from botocore.config import Config

        cfg = Config(
            region_name=aws_region,
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 2},
        )
        _boto3_client = boto3.client(
            "rekognition",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            config=cfg,
        )
        logger.info("AWS Rekognition client initialized successfully", region=aws_region)
        return _boto3_client
    except Exception as exc:
        logger.warning("Failed to initialize AWS Rekognition client", error=str(exc))
        return None


def is_aws_rekognition_available() -> bool:
    """Return True if AWS Rekognition client is ready for requests."""
    return get_rekognition_client() is not None


def _ensure_jpeg_or_png_bytes(img_bytes: bytes) -> bytes:
    """Ensure image bytes are in valid JPEG/PNG format supported by AWS Rekognition."""
    try:
        pil_img = Image.open(io.BytesIO(img_bytes))
        if pil_img.format in ("JPEG", "PNG"):
            return img_bytes
        # Convert format to JPEG
        buf = io.BytesIO()
        pil_img.convert("RGB").save(buf, format="JPEG", quality=95)
        return buf.getvalue()
    except Exception:
        return img_bytes


def aws_compare_faces(
    source_bytes: bytes,
    target_bytes: bytes,
    similarity_threshold: float = 70.0,
) -> tuple[bool, float, float, str, dict]:
    """
    Compare document face photo (source) against live capture photo (target).

    Args:
        source_bytes: Document photo bytes.
        target_bytes: Live webcam capture bytes.
        similarity_threshold: Minimum match confidence (0.0–100.0, default: 70.0%).

    Returns:
        tuple: (
            matched: bool,
            similarity: float (0.0 to 1.0),
            confidence: float (0.0 to 1.0),
            detail: str,
            metadata: dict
        )
    """
    client = get_rekognition_client()
    if client is None:
        return False, 0.0, 0.0, "AWS Rekognition not configured", {}

    try:
        src_clean = _ensure_jpeg_or_png_bytes(source_bytes)
        tgt_clean = _ensure_jpeg_or_png_bytes(target_bytes)

        response = client.compare_faces(
            SourceImage={"Bytes": src_clean},
            TargetImage={"Bytes": tgt_clean},
            SimilarityThreshold=similarity_threshold,
            QualityFilter="AUTO",
        )

        face_matches = response.get("FaceMatches", [])
        unmatched_faces = response.get("UnmatchedFaces", [])
        source_face = response.get("SourceImageFace", {})

        metadata = {
            "source_face_confidence": source_face.get("Confidence", 0.0),
            "matches_count": len(face_matches),
            "unmatched_count": len(unmatched_faces),
        }

        if face_matches:
            top_match = face_matches[0]
            sim_pct = float(top_match.get("Similarity", 0.0))
            sim_norm = sim_pct / 100.0
            face_conf = float(top_match.get("Face", {}).get("Confidence", 99.0)) / 100.0

            detail = (
                f"AWS Rekognition CompareFaces: MATCH (Similarity={sim_pct:.1f}%, "
                f"Confidence={face_conf * 100:.1f}%, threshold={similarity_threshold}%)"
            )
            logger.info("aws_compare_faces_match", similarity=sim_pct, matched=True)
            return True, sim_norm, face_conf, detail, metadata

        # If there are unmatched faces in target
        if unmatched_faces:
            top_unmatched = unmatched_faces[0]
            face_conf = float(top_unmatched.get("Confidence", 90.0)) / 100.0
            detail = (
                f"AWS Rekognition CompareFaces: NO MATCH — Face detected in live capture "
                f"does not match document (threshold={similarity_threshold}%)"
            )
            logger.info("aws_compare_faces_mismatch", matched=False)
            return False, 0.0, face_conf, detail, metadata

        detail = "AWS Rekognition: No face found in target live image."
        logger.warning("aws_compare_faces_no_target_face")
        return False, 0.0, 0.0, detail, metadata

    except Exception as exc:
        err_msg = str(exc)
        logger.warning("AWS Rekognition CompareFaces call failed", error=err_msg)
        return False, 0.0, 0.0, f"AWS Rekognition error: {err_msg}", {"error": err_msg}
