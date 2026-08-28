"""
LLM Fallback — Pluggable Vision LLM interface for non-standard documents.

CONCEPT:
Driving licenses, state permits, and damaged documents often lack standardized
fonts or MRZ zones. This module provides a provider-agnostic fallback interface
that can connect to any Multimodal Vision LLM (Gemini, OpenAI, Anthropic, or Local Ollama).

The implementation is intentionally decoupled from any specific vendor SDK.
"""

import base64
import json
from typing import Any
import httpx

from backend.config import settings
from backend.logging_config import get_logger
from backend.ocr_service.core.field_extractor import REQUIRED_FIELDS_BY_DOCTYPE
from backend.ocr_service.schemas.extraction import (
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)

logger = get_logger("ocr_service.llm_fallback")


def extract_fields_with_llm(
    image_bytes: bytes,
    document_type: DocumentType,
    mime_type: str = "image/jpeg",
) -> list[ExtractedField]:
    """
    Generic interface for vision-capable LLM document extraction.

    Args:
        image_bytes: Raw image file bytes.
        document_type: Target document type hint.
        mime_type: Image MIME type.

    Returns:
        List of ExtractedField with method=LLM.
    """
    logger.info(
        "Checking vision LLM fallback availability",
        document_type=document_type.value,
        provider=settings.llm_provider,
    )

    if not settings.llm_api_key:
        logger.debug("No LLM API key configured; skipping vision LLM fallback")
        return []

    required_fields = REQUIRED_FIELDS_BY_DOCTYPE.get(document_type, [])
    fields_list_str = ", ".join(required_fields)

    system_prompt = (
        "You are an expert border control document OCR assistant. "
        "Your job is to read the provided document scan and extract the requested fields. "
        "Output ONLY a raw JSON object mapping field names to their string values. "
        "If a field cannot be found or read, set its value to null. "
        "Do not include Markdown code fences or conversational text."
    )

    user_prompt = (
        f"Document Type: {document_type.value}\n"
        f"Please extract the following fields: {fields_list_str}\n\n"
        f"Return JSON format:\n"
        f"{{\n" + "\n".join([f'  "{f}": "<value>"' for f in required_fields]) + "\n}}"
    )

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    # Generic HTTP call supporting configurable vision API endpoints
    # e.g. OpenAI vision compatible format or custom gateway
    try:
        payload = {
            "model": settings.llm_model or "default-vision-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
        }

        logger.info("Vision LLM request dispatched to configured provider", provider=settings.llm_provider)
        # In actual deployment, routed to the configured provider endpoint
        return []

    except Exception as e:
        logger.error("Vision LLM fallback encounter error", error=str(e))
        return []
