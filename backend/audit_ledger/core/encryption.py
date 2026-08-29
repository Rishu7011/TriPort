"""
Field-Level & Scan AES-256-GCM Symmetric Encryption (Phase 4).

Features:
  - AES-GCM authenticated encryption for PII fields and image payloads at rest.
  - Automatic 96-bit random nonce generation per encryption.
  - PII masking helpers for visual UI redaction (e.g. "U569****").
"""

import base64
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger("audit_ledger.encryption")


def _get_encryption_key() -> bytes:
    """Derive deterministic 256-bit (32-byte) key from configuration secret."""
    raw_secret = getattr(settings, "encryption_secret", None) or settings.jwt_secret
    return hashlib.sha256(raw_secret.encode("utf-8")).digest()


def encrypt_bytes(data: bytes) -> bytes:
    """
    Encrypt raw bytes using AES-256-GCM.
    Returns: nonce (12 bytes) + ciphertext + authentication tag.
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_bytes(encrypted_payload: bytes) -> bytes:
    """
    Decrypt bytes with AES-256-GCM.
    Expects 12-byte nonce prepended to ciphertext.
    """
    if len(encrypted_payload) < 13:
        raise ValueError("Invalid encrypted payload size")
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = encrypted_payload[:12]
    ciphertext = encrypted_payload[12:]
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_text(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    encrypted = encrypt_bytes(plaintext.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_text(encrypted_b64: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext string."""
    raw = base64.b64decode(encrypted_b64.encode("utf-8"))
    return decrypt_bytes(raw).decode("utf-8")


def mask_pii(text: str, visible_prefix: int = 4) -> str:
    """
    Redact sensitive PII strings for unauthorized UI viewports.
    Example: 'U5691319' -> 'U569****'
    """
    if not text:
        return ""
    if len(text) <= visible_prefix:
        return "*" * len(text)
    return text[:visible_prefix] + "*" * (len(text) - visible_prefix)
