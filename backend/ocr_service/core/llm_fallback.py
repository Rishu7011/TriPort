"""
LLM Fallback — Vision LLM for non-standard documents or low OCR confidence.

CONCEPT:
Driving licenses, state permits, and damaged documents often lack standardized
fonts or MRZ zones. Traditional OCR might score low confidence (< 0.6) or
fail to extract key fields due to arbitrary layout variation.

This module provides an intelligent fallback:
  1. Base64 encodes the image bytes.
  2. Sends the image + document schema prompt to a multimodal Vision LLM (e.g. Claude / Anthropic API).
  3. Prompts the model to return strict JSON containing the required fields.
  4. Parses the JSON into ExtractedField objects with extraction_method = LLM.
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
    Call vision LLM to extract structured fields from document image.

    Args:
        image_bytes: Raw image file bytes.
        document_type: Target document type hint.
        mime_type: Image MIME type ('image/jpeg' or 'image/png').

    Returns:
        List of ExtractedField with method=LLM.
    """
    logger.info(
        "Invoking LLM vision fallback",
        document_type=document_type.value,
        image_size_bytes=len(image_bytes),
    )

    api_key = settings.anthropic_api_key
    if not api_key:
        logger.warning("Anthropic API key not configured, returning empty LLM fallback")
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

    try:
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": encoded_image,
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            logger.error("LLM fallback API returned error status", status=response.status_code, body=response.text)
            return []

        resp_json = response.json()
        content_text = resp_json["content"][0]["text"].strip()

        # Strip markdown fences if present
        if content_text.startswith("```"):
            content_text = content_text.strip("`")
            if content_text.startswith("json"):
                content_text = content_text[4:].strip()

        parsed_data = json.loads(content_text)

        results: list[ExtractedField] = []
        for key, val in parsed_data.items():
            if val is not None:
                results.append(
                    ExtractedField(
                        field_name=key,
                        field_value=str(val),
                        confidence=0.90,  # High nominal confidence for LLM vision parsing
                        extraction_method=ExtractionMethod.LLM,
                    )
                )

        logger.info("LLM fallback successfully extracted fields", count=len(results))
        return results

    except Exception as e:
        logger.error("LLM fallback failed with exception", error=str(e))
        return []
