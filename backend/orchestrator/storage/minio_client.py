"""
MinIO Object Storage Client Wrapper.

Handles uploading document scans and retrieving object URLs (or presigned URLs).
Gracefully falls back in local/offline test environments if MinIO is not running.
"""

import io
from datetime import timedelta
from typing import Any

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger("orchestrator.storage")

_minio_client: Any = None


def get_minio_client():
    """Lazy initialize MinIO client."""
    global _minio_client
    if _minio_client is None:
        try:
            from minio import Minio
            _minio_client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_use_ssl,
            )
            # Ensure bucket exists if reachable
            try:
                if not _minio_client.bucket_exists(settings.minio_bucket_documents):
                    _minio_client.make_bucket(settings.minio_bucket_documents)
                    logger.info("MinIO bucket created", bucket=settings.minio_bucket_documents)
            except Exception as b_err:
                logger.warning("Could not verify/create MinIO bucket", error=str(b_err))
        except Exception as e:
            logger.warning("MinIO client initialization failed (using local dummy)", error=str(e))
            _minio_client = False
    return _minio_client


async def upload_document_image(
    image_bytes: bytes,
    document_id: str,
    content_type: str = "image/jpeg",
) -> str:
    """
    Upload document image bytes to MinIO.

    Returns:
        object_key: The storage key pointing to the object in the documents bucket.
    """
    object_key = f"documents/{document_id}.jpg"
    client = get_minio_client()

    if client:
        try:
            data_stream = io.BytesIO(image_bytes)
            client.put_object(
                bucket_name=settings.minio_bucket_documents,
                object_name=object_key,
                data=data_stream,
                length=len(image_bytes),
                content_type=content_type,
            )
            logger.info("Uploaded document to MinIO", document_id=document_id, object_key=object_key)
            return object_key
        except Exception as exc:
            logger.error("Failed to upload image to MinIO", document_id=document_id, error=str(exc))
            # Return object_key anyway so DB record points to expected location
            return object_key

    logger.debug("MinIO not active; recorded virtual object key", object_key=object_key)
    return object_key


def get_document_image_url(object_key: str | None) -> str | None:
    """
    Generate presigned URL for viewing document scan from MinIO.
    """
    if not object_key:
        return None

    client = get_minio_client()
    if client:
        try:
            url = client.presigned_get_object(
                bucket_name=settings.minio_bucket_documents,
                object_name=object_key,
                expires=timedelta(hours=2),
            )
            return url
        except Exception as exc:
            logger.warning("Could not generate presigned URL", object_key=object_key, error=str(exc))
            return f"http://{settings.minio_endpoint}/{settings.minio_bucket_documents}/{object_key}"

    return f"http://{settings.minio_endpoint}/{settings.minio_bucket_documents}/{object_key}"
