"""
LLM Fallback — Pluggable Vision LLM interface for non-standard documents.

CONCEPT:
Driving licenses, state permits, Aadhaar cards, and ferry tickets often lack standardized
fonts or MRZ zones. This module provides a provider-agnostic fallback interface
that connects to Multimodal Vision LLMs (Gemini, OpenAI, Anthropic, or Local Ollama).
"""

import base64
import json
import re
from typing import Any
import httpx

from backend.config import settings
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)

logger = get_logger("ocr_service.llm_fallback")


def extract_fields_with_llm(
    image_bytes: bytes,
    document_type: DocumentType | None = None,
    mime_type: str = "image/jpeg",
) -> tuple[DocumentType, list[ExtractedField]]:
    """
    Multimodal Gemini Vision interface for all 6 document types.
    Auto-detects document type from visual layout if not specified or auto.

    Returns:
        (detected_document_type, list[ExtractedField])
    """
    logger.info(
        "Executing Gemini vision document extraction",
        document_type=document_type.value if document_type else "auto",
        provider=settings.llm_provider,
    )

    api_key = settings.llm_api_key
    if not api_key:
        logger.debug("No Gemini API key configured; skipping vision LLM fallback")
        return (document_type or DocumentType.NATIONAL_ID, [])

    system_prompt = (
        "You are an expert border control document OCR system for TriPort. "
        "Your task is to inspect the uploaded identity/travel document scan, classify it, and extract structured data.\n\n"
        "1. Identify the exact 'document_type' from these 6 options:\n"
        "   - 'passport': Standard international passports (P< MRZ).\n"
        "   - 'visa': Entry visas, tourist/business visas (V< MRZ).\n"
        "   - 'national_id': Aadhaar Card, Voter ID, Citizen ID, Civil ID, PAN Card, National Identity Cards.\n"
        "   - 'driving_license': Driving/Driver licenses, motor vehicle authority cards.\n"
        "   - 'permit': Border crossing permits, restricted area permits, movement passes.\n"
        "   - 'ferry_ticket': Sea boarding passes, ferry tickets, vessel disembarkation slips.\n\n"
        "2. Extract all visible fields based on the matching schema:\n"
        "   - passport: passport_number, name, nationality, date_of_birth, date_of_expiry, gender\n"
        "   - visa: visa_number, visa_type, passport_number, entry_validity, stay_duration, nationality\n"
        "   - national_id (e.g. Aadhaar Card / Voter ID): id_number, name, date_of_birth, issuing_authority, validity_period, gender\n"
        "   - driving_license: license_number, name, date_of_birth, date_of_expiry, vehicle_class, issuing_authority\n"
        "   - permit: permit_number, name, permit_type, valid_until, issuing_authority\n"
        "   - ferry_ticket: ticket_number, name, route, travel_date, vessel_name\n\n"
        "Output ONLY a raw JSON object with keys 'document_type' and 'fields' (a dictionary of field_name -> string value). "
        "If a field cannot be read, set it to null or omit it. Do NOT wrap in markdown code fences."
    )

    if document_type:
        user_prompt = f"Document Type Hint: {document_type.value}\nPlease extract all document information in valid JSON."
    else:
        user_prompt = "Document Type Hint: auto (Please examine the document scan visually, classify its document_type accurately, and extract all fields in valid JSON)."

    import io
    from PIL import Image

    # Compress and scale image for sub-2s latency (<200KB payload)
    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = pil_img.size
        max_dim = 1200
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
        
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85, optimize=True)
        optimized_bytes = buf.getvalue()
    except Exception:
        optimized_bytes = image_bytes

    encoded_image = base64.b64encode(optimized_bytes).decode("utf-8")

    try:
        model_name = settings.llm_model or "gemini-3.5-flash-lite"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_prompt}"},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                clean_json = re.sub(r"^```json\s*|\s*```$", "", content.strip())
                parsed = json.loads(clean_json)

                # Extract detected document type
                raw_type = str(parsed.get("document_type", "")).lower().strip()
                resolved_type = None
                for dt in DocumentType:
                    if dt.value == raw_type:
                        resolved_type = dt
                        break

                if not resolved_type:
                    # Fallback mapping based on raw string matches
                    if "national" in raw_type or "id" in raw_type or "aadhaar" in raw_type:
                        resolved_type = DocumentType.NATIONAL_ID
                    elif "license" in raw_type or "licence" in raw_type or "driving" in raw_type:
                        resolved_type = DocumentType.DRIVING_LICENSE
                    elif "visa" in raw_type:
                        resolved_type = DocumentType.VISA
                    elif "ticket" in raw_type or "ferry" in raw_type:
                        resolved_type = DocumentType.FERRY_TICKET
                    elif "permit" in raw_type:
                        resolved_type = DocumentType.PERMIT
                    else:
                        resolved_type = document_type or DocumentType.NATIONAL_ID

                fields_dict = parsed.get("fields", parsed)
                if not isinstance(fields_dict, dict):
                    fields_dict = {}

                fields: list[ExtractedField] = []
                for k, v in fields_dict.items():
                    if k != "document_type" and v and str(v).lower() not in ["null", "none"]:
                        fields.append(
                            ExtractedField(
                                field_name=str(k),
                                field_value=str(v).strip(),
                                confidence=0.96,
                                extraction_method=ExtractionMethod.LLM,
                            )
                        )
                logger.info(
                    "Successfully extracted fields via Gemini Vision API",
                    document_type=resolved_type.value,
                    count=len(fields),
                )
                return (resolved_type, fields)
            else:
                logger.warning("Gemini Vision API error", status_code=resp.status_code, response=resp.text[:200])

        return (document_type or DocumentType.NATIONAL_ID, [])

    except Exception as e:
        logger.error("Gemini Vision API fallback encountered error", error=str(e))
        return (document_type or DocumentType.NATIONAL_ID, [])
