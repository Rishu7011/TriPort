"""
LLM Fallback — Pluggable Vision LLM interface for non-standard documents.

CONCEPT:
Driving licenses, state permits, Aadhaar cards, PAN cards, Voter ID cards, and ferry tickets
often lack standardized fonts or MRZ zones. This module provides a provider-agnostic fallback
interface that connects to Multimodal Vision LLMs (Google Gemini).

Phase 9 — Global Multi-Language Passport Support:
For passports written in Arabic, Russian Cyrillic, Burmese, Thai, Sinhala, or other scripts
not preloaded in local EasyOCR, Gemini Vision is used as the Layer 2 extraction fallback.
The prompt extracts both native_value (original script) and english_transliteration (ICAO ASCII)
for names, plus a detected_languages list for multilingual passport indicator.
"""

import base64
import json
import re
import time
from typing import Any
import httpx
from PIL import Image
import io

from backend.config import settings
from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import (
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)
from backend.ocr_service.core.transliteration import (
    normalize_icao_transliteration,
    detect_languages_in_text,
    detect_script,
)

logger = get_logger("ocr_service.llm_fallback")

# In-memory circuit breaker: after 429 quota exhaustion or auth errors, avoid hammering API
_cooldown_until: float = 0.0


def extract_fields_with_llm(
    image_bytes: bytes,
    document_type: DocumentType | None = None,
    mime_type: str = "image/jpeg",
) -> tuple[DocumentType, list[ExtractedField]]:
    """
    Multimodal Gemini Vision interface for all 8 document types.
    Auto-detects document type from visual layout if not specified or auto.

    Returns:
        (detected_document_type, list[ExtractedField])
    """
    global _cooldown_until
    if time.time() < _cooldown_until:
        logger.debug("Gemini Vision API in cooldown (quota/rate-limit); skipping vision fallback")
        return (document_type or DocumentType.NATIONAL_ID, [])

    api_key = settings.llm_api_key
    if not api_key or len(api_key.strip()) < 10:
        logger.debug("No valid Gemini API key configured; skipping vision LLM fallback")
        return (document_type or DocumentType.NATIONAL_ID, [])

    logger.info(
        "Executing Gemini vision document extraction",
        document_type=document_type.value if document_type else "auto",
        provider=settings.llm_provider,
    )

    system_prompt = (
        "You are an expert international border control and identity document OCR system for TriPort. "
        "Your task is to inspect the uploaded document scan, classify it accurately, and extract structured data.\n\n"
        "1. Identify the exact 'document_type' from these 8 supported options:\n"
        "   - 'passport': Standard international passports (P< MRZ).\n"
        "   - 'visa': Entry visas, tourist/business visas (V< MRZ).\n"
        "   - 'national_id': Indian Aadhaar Card (12-digit UID), Citizen ID, Civil ID, National Identity Cards.\n"
        "   - 'driving_license': Driving/Driver licenses, motor vehicle authority cards.\n"
        "   - 'permit': Border crossing permits, restricted area permits, movement passes.\n"
        "   - 'ferry_ticket': Sea boarding passes, ferry tickets, vessel disembarkation slips.\n"
        "   - 'pan_card': Indian Permanent Account Number (PAN Card) issued by Income Tax Department.\n"
        "   - 'voter_id': Indian Elector Identity Card (Voter ID / EPIC Card) issued by Election Commission of India.\n\n"
        "2. MULTILINGUAL SUPPORT: This document may contain text in Arabic, Russian Cyrillic, Burmese, Thai, \n"
        "   Sinhala, Chinese, Japanese, Hindi (Devanagari), or Bengali alongside English.\n"
        "   For ALL name fields, extract TWO values:\n"
        "   a) 'native_value': The name in its original native script (e.g. '\u0645\u062d\u0645\u062f', '\u0418\u0432\u0430\u043d\u043e\u0432', '\u0a86\u0ab9\u0ac0\u0aa8\u0abe').\n"
        "   b) 'english_transliteration': The standard ICAO/Latin romanization (e.g. 'MOHAMMED', 'IVANOV', 'AHINA').\n\n"
        "3. Extract all visible fields based on the matching schema:\n"
        "   - passport: passport_number, name, surname, given_names, nationality, date_of_birth, date_of_expiry, gender\n"
        "   - visa: visa_number, visa_type, passport_number, entry_validity, stay_duration, nationality\n"
        "   - national_id: id_number, name, date_of_birth, issuing_authority, validity_period, gender\n"
        "   - driving_license: license_number, name, date_of_birth, date_of_expiry, vehicle_class, issuing_authority\n"
        "   - permit: permit_number, name, permit_type, valid_until, issuing_authority\n"
        "   - ferry_ticket: ticket_number, name, route, travel_date, vessel_name\n"
        "   - pan_card: pan_number, name, father_name, date_of_birth, issuing_authority\n"
        "   - voter_id: voter_id_number, name, father_name, date_of_birth, gender, issuing_authority\n\n"
        "4. For dates: Always return in DD/MM/YYYY format. Convert any regional numerals to Arabic digits 0-9.\n"
        "   European dot-dates (DD.MM.YYYY) should be converted to DD/MM/YYYY.\n"
        "5. For nationality fields: Return the ICAO/ISO 3166-1 alpha-3 three-letter code (e.g. 'IND', 'DEU', 'ARE').\n\n"
        "Output ONLY valid JSON with keys:\n"
        "  'document_type' (string)\n"
        "  'detected_languages' (array of ISO 639-1 codes, e.g. ['ar', 'en'] or ['hi', 'en'])\n"
        "  'fields' (object mapping field name to string value for standard English fields)\n"
        "  'multilingual_fields' (object mapping field name to {'native_value': str, 'english_transliteration': str} for name fields with non-Latin scripts)\n"
    )

    user_prompt = (
        f"Document hint: {document_type.value if document_type else 'auto'}.\n"
        "Read this document carefully, identify its type, and return all fields in JSON format."
    )

    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        max_side = 1000
        w, h = pil_img.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
        out_buf = io.BytesIO()
        pil_img.save(out_buf, format="JPEG", quality=85)
        optimized_bytes = out_buf.getvalue()
    except Exception:
        optimized_bytes = image_bytes

    encoded_image = base64.b64encode(optimized_bytes).decode("utf-8")

    try:
        configured_model = settings.llm_model or "gemini-3.5-flash"
        candidate_models = [configured_model, "gemini-3.5-flash", "gemini-3.6-flash"]
        candidate_models = list(dict.fromkeys(candidate_models))

        resp = None
        for model_name in candidate_models:
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

            try:
                with httpx.Client(timeout=4.0) as client:
                    r = client.post(url, json=payload)
                    if r.status_code == 200:
                        resp = r
                        break
                    elif r.status_code in (429, 500, 503):
                        logger.warning("Gemini Vision API rate-limit/unavailable — engaging cooldown", model=model_name, status_code=r.status_code)
                        _cooldown_until = time.time() + 60.0
                        break
                    elif r.status_code in (401, 403):
                        logger.warning("Gemini Vision API auth failure — engaging cooldown", model=model_name, status_code=r.status_code)
                        _cooldown_until = time.time() + 300.0
                        break
                    else:
                        logger.warning("Gemini Vision API non-200", model=model_name, status_code=r.status_code)
            except Exception as exc:
                logger.warning("Gemini Vision API model attempt failed", model=model_name, error=str(exc))

        if resp and resp.status_code == 200:
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_json = re.sub(r"^```json\s*|\s*```$", "", content.strip())
            parsed = json.loads(clean_json)

            raw_type = str(parsed.get("document_type", "")).lower().strip()
            resolved_type = None
            for dt in DocumentType:
                if dt.value == raw_type:
                    resolved_type = dt
                    break
            final_type = resolved_type or document_type or DocumentType.NATIONAL_ID

            fields_dict = parsed.get("fields", {})
            multilingual_fields = parsed.get("multilingual_fields", {})

            # Phase 9: Parse detected_languages from Gemini response
            detected_langs: list[str] = parsed.get("detected_languages", [])
            if not isinstance(detected_langs, list):
                detected_langs = []

            extracted_fields: list[ExtractedField] = []
            if isinstance(fields_dict, dict):
                for k, v in fields_dict.items():
                    if v and str(v).strip():
                        field_key = str(k).strip()
                        field_val = str(v).strip()

                        # Phase 9: Check if multilingual data is available for this field
                        native_v: str | None = None
                        trans_v: str | None = None
                        lang_code: str | None = None

                        if field_key in multilingual_fields and isinstance(multilingual_fields[field_key], dict):
                            ml = multilingual_fields[field_key]
                            raw_native = ml.get("native_value", "") or ""
                            raw_trans = ml.get("english_transliteration", "") or ""
                            if raw_native and raw_native.strip():
                                native_v = raw_native.strip()
                                # Use the english_transliteration as the canonical field_value
                                if raw_trans and raw_trans.strip():
                                    trans_v = normalize_icao_transliteration(raw_trans.strip())
                                    field_val = trans_v
                                else:
                                    # Fallback: transliterate the native value ourselves
                                    trans_v = normalize_icao_transliteration(raw_native)
                                    field_val = trans_v
                                # Detect language code from native value
                                script = detect_script(native_v)
                                if script not in ("latin", "unknown"):
                                    langs = detect_languages_in_text(native_v)
                                    lang_code = langs[0] if langs else None
                        elif detected_langs:
                            # Use detected langs to annotate non-Latin fields
                            non_en = [l for l in detected_langs if l != "en"]
                            if non_en and field_key in ("name", "surname", "given_names"):
                                lang_code = non_en[0]

                        extracted_fields.append(
                            ExtractedField(
                                field_name=field_key,
                                field_value=field_val,
                                native_value=native_v,
                                transliterated_value=trans_v,
                                language=lang_code,
                                confidence=0.96,
                                extraction_method=ExtractionMethod.LLM,
                            )
                        )

            logger.info(
                "Extracted fields via Gemini Vision (Phase 9 multilingual)",
                count=len(extracted_fields),
                document_type=final_type.value,
                detected_languages=detected_langs,
            )
            return (final_type, extracted_fields)

    except Exception as exc:
        logger.warning("Gemini Vision extraction failed", error=str(exc))

    return (document_type or DocumentType.NATIONAL_ID, [])
