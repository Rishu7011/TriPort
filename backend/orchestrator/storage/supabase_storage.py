"""
Supabase Storage Client — replaces minio_client.py.

Handles uploading document scans and live-capture images to Supabase Storage
and generating signed URLs for the frontend to fetch them.

Bucket layout:
  document-images/
      {scan_event_id}/doc.jpg
      {scan_event_id}/face_crop.jpg
  live-captures/
      {scan_event_id}/live.jpg

Key-naming rationale: using scan_event_id as the path prefix means:
  - All images for a scan are co-located under one prefix.
  - Purging a scan's images is a single folder delete.
  - No filename collisions (UUIDs are globally unique).

Signed URL TTL is 3600 seconds (1 hour) — enough for a single officer review
session. In production, use shorter TTLs with re-signing on demand.

The service-role key is used for uploads (bypasses RLS).
The anon key is sufficient for generating signed URLs.

Falls back gracefully: if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are not
configured, all upload calls return None (same offline behaviour as the old
MinIO stub) and the system continues with no image URLs stored.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import httpx

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger("orchestrator.storage")

# Signed URL validity in seconds
_SIGNED_URL_TTL = 3600

# Lazy-initialised httpx client for Storage REST calls
_http_client: httpx.AsyncClient | None = None


def _is_configured() -> bool:
    """Return True if Supabase Storage credentials are available."""
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _storage_base() -> str:
    """Base URL for Supabase Storage REST API."""
    return f"{settings.supabase_url.rstrip('/')}/storage/v1"


def _auth_headers() -> dict[str, str]:
    """Headers using the service-role key (bypasses RLS for server-side uploads)."""
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    return _http_client


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

async def upload_document_image(
    image_bytes: bytes,
    scan_event_id: str,
    content_type: str = "image/jpeg",
) -> str | None:
    """
    Upload the full document scan image to Supabase Storage.

    Key: {scan_event_id}/doc.jpg
    Bucket: SUPABASE_BUCKET_DOCUMENTS

    Returns:
        Signed URL (str) on success, None on failure or if Storage is not configured.
    """
    return await _upload(
        bucket=settings.supabase_bucket_documents,
        path=f"{scan_event_id}/doc.jpg",
        data=image_bytes,
        content_type=content_type,
        label="document",
        scan_event_id=scan_event_id,
    )


async def upload_face_crop_image(
    image_bytes: bytes,
    scan_event_id: str,
    content_type: str = "image/jpeg",
) -> str | None:
    """
    Upload the cropped face photo extracted from the document.

    Key: {scan_event_id}/face_crop.jpg
    Bucket: SUPABASE_BUCKET_DOCUMENTS
    """
    return await _upload(
        bucket=settings.supabase_bucket_documents,
        path=f"{scan_event_id}/face_crop.jpg",
        data=image_bytes,
        content_type=content_type,
        label="face_crop",
        scan_event_id=scan_event_id,
    )


async def upload_live_capture_image(
    image_bytes: bytes,
    scan_event_id: str,
    content_type: str = "image/jpeg",
) -> str | None:
    """
    Upload the live webcam capture photo.

    Key: {scan_event_id}/live.jpg
    Bucket: SUPABASE_BUCKET_LIVE
    """
    return await _upload(
        bucket=settings.supabase_bucket_live,
        path=f"{scan_event_id}/live.jpg",
        data=image_bytes,
        content_type=content_type,
        label="live_capture",
        scan_event_id=scan_event_id,
    )


async def _upload(
    bucket: str,
    path: str,
    data: bytes,
    content_type: str,
    label: str,
    scan_event_id: str,
) -> str | None:
    """
    Core upload function. Uploads bytes to a Supabase Storage bucket via REST.
    On success, generates and returns a signed URL for the object.
    """
    if not _is_configured():
        logger.warning(
            "supabase_storage_not_configured",
            label=label,
            scan_event_id=scan_event_id,
            hint="Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env",
        )
        return None

    url = f"{_storage_base()}/object/{bucket}/{path}"
    headers = {
        **_auth_headers(),
        "Content-Type": content_type,
        "x-upsert": "true",  # overwrite if exists (idempotent on retry)
    }

    try:
        client = await _get_client()
        response = await client.post(url, content=data, headers=headers)

        if response.status_code not in (200, 201):
            logger.error(
                "supabase_storage_upload_failed",
                label=label,
                scan_event_id=scan_event_id,
                status=response.status_code,
                body=response.text[:200],
            )
            return None

        logger.info(
            "supabase_storage_upload_ok",
            label=label,
            scan_event_id=scan_event_id,
            bucket=bucket,
            path=path,
        )
        return await _get_signed_url(bucket=bucket, path=path)

    except Exception as exc:
        logger.error(
            "supabase_storage_upload_exception",
            label=label,
            scan_event_id=scan_event_id,
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# Signed URL generation
# ---------------------------------------------------------------------------

async def _get_signed_url(bucket: str, path: str) -> str | None:
    """
    Generate a signed URL for a Supabase Storage object.
    TTL: _SIGNED_URL_TTL seconds (default 1 hour).
    """
    url = f"{_storage_base()}/object/sign/{bucket}/{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                url,
                json={"expiresIn": _SIGNED_URL_TTL},
                headers=_auth_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                signed_path = data.get("signedURL") or data.get("signedUrl") or ""
                if signed_path:
                    if signed_path.startswith("http://") or signed_path.startswith("https://"):
                        return signed_path
                    # Supabase returns relative path '/object/sign/...' — ensure '/storage/v1' prefix is present
                    if not signed_path.startswith("/storage/v1"):
                        clean_path = signed_path if signed_path.startswith("/") else f"/{signed_path}"
                        signed_path = f"/storage/v1{clean_path}"
                    return f"{settings.supabase_url.rstrip('/')}{signed_path}"
    except Exception as exc:
        logger.warning("supabase_signed_url_failed", error=str(exc))

    # Fallback: return the public path (works if bucket is public, else will 403)
    return f"{_storage_base()}/object/public/{bucket}/{path}"



async def get_signed_url_for_path(bucket: str, path: str) -> str | None:
    """
    Public helper — refresh or regenerate a signed URL for any stored object.
    """
    if not _is_configured():
        return None
    return await _get_signed_url(bucket=bucket, path=path)


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------

async def delete_scan_images(scan_event_id: str) -> None:
    """
    Delete all images for a scan event from both buckets.
    Useful for GDPR deletion workflows in production.
    """
    if not _is_configured():
        return

    paths_to_delete = [
        (settings.supabase_bucket_documents, f"{scan_event_id}/doc.jpg"),
        (settings.supabase_bucket_documents, f"{scan_event_id}/face_crop.jpg"),
        (settings.supabase_bucket_live, f"{scan_event_id}/live.jpg"),
    ]

    client = await _get_client()
    for bucket, path in paths_to_delete:
        url = f"{_storage_base()}/object/{bucket}/{path}"
        try:
            resp = await client.delete(url, headers=_auth_headers())
            if resp.status_code not in (200, 204, 404):
                logger.warning(
                    "supabase_storage_delete_failed",
                    bucket=bucket,
                    path=path,
                    status=resp.status_code,
                )
        except Exception as exc:
            logger.warning("supabase_storage_delete_exception", path=path, error=str(exc))
