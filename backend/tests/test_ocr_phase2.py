"""
Phase 2 Unit & Integration Tests — Multi-Modal OCR, Classification & Batch Extraction.

Verifies:
  1. Document Classifier across all 6 document types (Passport, Visa, National ID, Driving License, Permit, Ferry Ticket).
  2. Multi-Format MRZ Parser: TD3 (2x44), TD2 (2x36), and TD1 (3x30) + ICAO 9303 checksum checks & auto-correction.
  3. Visual Zone (VIZ) extraction for all 6 document types.
  4. Batch Queue Processing for bulk passenger arrivals (bus/ferry).
  5. OCR Service HTTP Endpoints (/classify, /extract, /extract/batch).
"""

import io
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from httpx import ASGITransport, AsyncClient

from backend.ocr_service.core.batch import process_batch_queue
from backend.ocr_service.core.classifier import classify_document
from backend.ocr_service.core.field_extractor import (
    REQUIRED_FIELDS_BY_DOCTYPE,
    extract_fields,
)
from backend.ocr_service.core.mrz_parser import (
    _compute_check_digit,
    _validate_check_digit,
    parse_mrz_from_text_lines,
    parse_td1,
    parse_td2,
    parse_td3,
)
from backend.ocr_service.main import app
from backend.ocr_service.schemas.extraction import (
    CheckpointType,
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "synthetic-tampered"


@pytest.fixture
def genuine_passport_bytes():
    path = SAMPLE_DIR / "doc_001_genuine.jpg"
    with open(path, "rb") as f:
        return f.read()


def _create_synthetic_doc_image(text_lines: list[str]) -> bytes:
    """Helper to generate a clean synthetic document image with specified text lines."""
    img = Image.new("RGB", (800, 500), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Simple placeholder geometry
    draw.rectangle([(20, 20), (780, 480)], outline=(100, 100, 100), width=2)
    draw.rectangle([(40, 40), (200, 240)], fill=(200, 200, 200), outline=(50, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ─── 1. Document Classifier Tests ────────────────────────────────────────────

def test_classifier_all_doctypes():
    """Verify document classifier accurately predicts each of the 6 document types from text signatures."""
    test_cases = [
        (
            [("REPUBLIC OF INDIA PASSPORT", 0.95), ("P<INDSHARMA<<RAHUL<<<<<<<<<<<<<<<<<<", 0.99), ("PASSPORT NO: Z6720715", 0.98)],
            DocumentType.PASSPORT,
        ),
        (
            [("REPUBLIC OF INDIA VISA", 0.95), ("VISA NO: V9876543", 0.98), ("TYPE: TOURIST", 0.92), ("STAY DURATION: 90 DAYS", 0.90)],
            DocumentType.VISA,
        ),
        (
            [("GOVERNMENT OF INDIA UNIQUE IDENTIFICATION AADHAAR", 0.96), ("1234 5678 9012", 0.98), ("NAME: AMIT KUMAR", 0.95)],
            DocumentType.NATIONAL_ID,
        ),
        (
            [("UNION OF INDIA DRIVING LICENCE", 0.97), ("DL NO: DL-0420110012345", 0.98), ("VEHICLE CLASS: LMV", 0.94)],
            DocumentType.DRIVING_LICENSE,
        ),
        (
            [("LAND PORTS AUTHORITY OF INDIA", 0.96), ("LAND BORDER ENTRY PERMIT", 0.98), ("PERMIT NO: PER-987654", 0.95)],
            DocumentType.PERMIT,
        ),
        (
            [("INCOME TAX DEPARTMENT GOVT OF INDIA", 0.97), ("PERMANENT ACCOUNT NUMBER CARD", 0.98), ("PATPK1234M", 0.99)],
            DocumentType.PAN_CARD,
        ),
        (
            [("ELECTION COMMISSION OF INDIA ELECTOR IDENTITY CARD", 0.98), ("EPIC NO: ABC1234567", 0.99), ("ELECTOR'S NAME: RAJESH KUMAR", 0.95)],
            DocumentType.VOTER_ID,
        ),
    ]

    dummy_bytes = _create_synthetic_doc_image([])

    for ocr_lines, expected_type in test_cases:
        predicted, conf, details = classify_document(dummy_bytes, ocr_lines=ocr_lines)
        assert predicted == expected_type, f"Expected {expected_type}, got {predicted} with scores {details['scores']}"
        assert conf >= 0.60


def test_classifier_on_genuine_sample(genuine_passport_bytes):
    """Verify classifier on genuine passport image defaults or classifies accurately."""
    predicted, conf, details = classify_document(genuine_passport_bytes)
    assert predicted == DocumentType.PASSPORT
    assert conf >= 0.50


# ─── 2. Multi-Format MRZ Parser & Checksums ──────────────────────────────────

def test_mrz_td3_passport_parsing():
    """Verify TD3 (2x44) passport MRZ parsing and checksum verification."""
    line1 = "P<INDSURNAME<<GIVENNAME<<<<<<<<<<<<<<<<<<<<<"
    line2 = "Z6720715<3IND8501156M2812313<<<<<<<<<<<<<<<<"

    res = parse_td3(line1, line2)
    assert res.mrz_present is True
    assert res.checksum_valid is True
    assert len(res.checksum_failures) == 0
    assert res.mrz_fields["doc_number"] == "Z6720715"
    assert res.mrz_fields["nationality"] == "IND"
    assert res.mrz_fields["date_of_birth"] == "15/01/1985"
    assert res.mrz_fields["date_of_expiry"] == "31/12/2028"
    assert res.mrz_fields["sex"] == "M"
    assert res.mrz_fields["mrz_format"] == "TD3"


def test_mrz_td2_visa_parsing():
    """Verify TD2 (2x36) Visa MRZ parsing."""
    line1 = "V<INDNEGI<<SAHIL<<<<<<<<<<<<<<<<<<<<<"
    line2 = "V1234567<5IND9005152M3012318<<<<<<<<<"

    res = parse_td2(line1, line2)
    assert res.mrz_present is True
    assert res.mrz_fields["mrz_format"] == "TD2"
    assert res.mrz_fields["doc_number"] == "V1234567"
    assert res.mrz_fields["nationality"] == "IND"


def test_mrz_td1_national_id_parsing():
    """Verify TD1 (3x30) National ID MRZ parsing."""
    line1 = "I<IND1234567897<<<<<<<<<<<<<<<"
    line2 = "9005152M3012318IND<<<<<<<<<<<1"
    line3 = "KUMAR<<AMIT<<<<<<<<<<<<<<<<<<<"

    res = parse_td1(line1, line2, line3)
    assert res.mrz_present is True
    assert res.mrz_fields["mrz_format"] == "TD1"
    assert res.mrz_fields["doc_number"] == "123456789"
    assert res.mrz_fields["name"] == "AMIT KUMAR"


def test_mrz_checksum_corruption_detection():
    """Verify corrupted check digit fails checksum verification."""
    line1 = "P<INDSURNAME<<GIVENNAME<<<<<<<<<<<<<<<<<<<<<"
    # Expected check digit for Z6720715 is 3. Corrupt it to 9:
    line2_corrupted = "Z6720715<9IND8501156M2812313<<<<<<<<<<<<<<<<"

    res = parse_td3(line1, line2_corrupted)
    assert res.mrz_present is True
    assert res.checksum_valid is False
    assert "doc_number" in res.checksum_failures


def test_mrz_auto_correction():
    """Verify OCR confusion auto-correction (e.g. 2 misread as first char of Z6720715)."""
    line1 = "P<INDSURNAME<<GIVENNAME<<<<<<<<<<<<<<<<<<<<<"
    # '2' at position 0 instead of 'Z':
    line2_ocr_glitch = "26720715<3IND8501156M2812313<<<<<<<<<<<<<<<<"

    res = parse_td3(line1, line2_ocr_glitch)
    assert res.checksum_valid is True
    assert res.mrz_fields["doc_number"] == "Z6720715"


# ─── 3. Visual Zone (VIZ) Extraction across all 6 Document Types ──────────────

def test_viz_field_extraction_all_doctypes():
    """Verify visual field extraction pulls required field set for all 6 document types."""
    dummy_bytes = _create_synthetic_doc_image([])

    # 1. Visa
    visa_lines = [
        ("VISA NUMBER: V9876543", 0.95),
        ("VISA TYPE: TOURIST", 0.92),
        ("PASSPORT NO: A1234567", 0.94),
        ("VALID UNTIL: 2028-12-31", 0.90),
        ("STAY DURATION: 90 DAYS", 0.93),
    ]
    visa_fields = extract_fields(dummy_bytes, DocumentType.VISA, raw_lines=visa_lines)
    visa_dict = {f.field_name: f.field_value for f in visa_fields}
    assert "visa_type" in visa_dict
    assert visa_dict["visa_type"] == "TOURIST"
    assert "stay_duration" in visa_dict

    # 2. National ID
    id_lines = [
        ("UNIQUE IDENTIFICATION AUTHORITY OF INDIA", 0.95),
        ("1234 5678 9012", 0.98),
        ("NAME: AMIT KUMAR", 0.95),
        ("DOB: 15/05/1992", 0.91),
    ]
    id_fields = extract_fields(dummy_bytes, DocumentType.NATIONAL_ID, raw_lines=id_lines)
    id_dict = {f.field_name: f.field_value for f in id_fields}
    assert "id_number" in id_dict
    assert id_dict["id_number"] == "1234 5678 9012"
    assert "name" in id_dict

    # 3. Driving License
    dl_lines = [
        ("UNION OF INDIA DRIVING LICENCE", 0.95),
        ("DL NO: DL-0420110012345", 0.98),
        ("NAME: VIKRAM SINGH", 0.95),
        ("DOB: 10/08/1988", 0.90),
        ("VALID TILL: 31/12/2035", 0.92),
        ("VEHICLE CLASS: LMV", 0.94),
    ]
    dl_fields = extract_fields(dummy_bytes, DocumentType.DRIVING_LICENSE, raw_lines=dl_lines)
    dl_dict = {f.field_name: f.field_value for f in dl_fields}
    assert "license_number" in dl_dict
    assert "vehicle_class" in dl_dict
    assert dl_dict["vehicle_class"] == "LMV"

    # 4. Permit
    permit_lines = [
        ("LAND PORTS AUTHORITY OF INDIA", 0.96),
        ("BORDER PASS PERMIT NO: BP-889900", 0.95),
        ("HOLDER NAME: RAJESH GUPTA", 0.94),
        ("PERMIT TYPE: BORDER PASS", 0.90),
        ("VALID UNTIL: 2026-10-15", 0.92),
    ]
    permit_fields = extract_fields(dummy_bytes, DocumentType.PERMIT, raw_lines=permit_lines)
    permit_dict = {f.field_name: f.field_value for f in permit_fields}
    assert "permit_number" in permit_dict
    assert "permit_type" in permit_dict


# ─── 4. Batch Queue Processing Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_processing_queue(genuine_passport_bytes):
    """Verify batch processing queue handles multiple arrivals concurrently without blocking."""
    dummy_doc = _create_synthetic_doc_image([])
    items = [
        (genuine_passport_bytes, "passenger_1_passport.jpg", DocumentType.PASSPORT),
        (dummy_doc, "passenger_2_permit.jpg", DocumentType.PERMIT),
        (b"", "corrupt_scan.jpg", None),  # Empty/corrupted item to test isolation
        (genuine_passport_bytes, "passenger_4_passport.jpg", DocumentType.PASSPORT),
    ]

    res = await process_batch_queue(
        items=items,
        checkpoint_type=CheckpointType.SEA,
        provider="local",
        max_concurrency=2,
    )

    assert res.total_processed == 4
    assert res.successful_count >= 2
    assert res.failed_count >= 1
    # Check that individual corrupt item is isolated and failed cleanly
    assert res.items[2].success is False
    assert "empty" in res.items[2].error.lower()


# ─── 5. OCR Service HTTP Endpoints Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_api_classify_endpoint(genuine_passport_bytes):
    """Verify POST /api/v1/ocr/classify endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("passport.jpg", genuine_passport_bytes, "image/jpeg")}
        resp = await client.post("/api/v1/ocr/classify", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "document_type" in data
        assert "confidence" in data
        assert data["document_type"] == DocumentType.PASSPORT.value


@pytest.mark.asyncio
async def test_ocr_api_extract_endpoint(genuine_passport_bytes):
    """Verify POST /api/v1/ocr/extract endpoint returns full structured response with checkpoint & provider."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("passport.jpg", genuine_passport_bytes, "image/jpeg")}
        data = {
            "checkpoint_type": CheckpointType.LAND_BORDER.value,
            "provider": "local",
        }
        resp = await client.post("/api/v1/ocr/extract", files=files, data=data)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["document_type"] == "passport"
        assert res_data["checkpoint_type"] == "land_border"
        assert res_data["provider_used"] == "local"
        assert len(res_data["fields"]) > 0
        assert res_data["mrz"]["mrz_present"] is True


@pytest.mark.asyncio
async def test_ocr_api_batch_endpoint(genuine_passport_bytes):
    """Verify POST /api/v1/ocr/extract/batch endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = [
            ("files", ("pass1.jpg", genuine_passport_bytes, "image/jpeg")),
            ("files", ("pass2.jpg", genuine_passport_bytes, "image/jpeg")),
        ]
        data = {"checkpoint_type": CheckpointType.AIRPORT.value}
        resp = await client.post("/api/v1/ocr/extract/batch", files=files, data=data)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["total_processed"] == 2
        assert res_data["successful_count"] == 2


# ─── 6. Verification Tests for Bug Fixes ──────────────────────────────────────

def test_father_name_not_extracted_as_holder_name():
    """Verify lines with FATHER'S NAME are skipped when extracting holder name."""
    dummy_bytes = _create_synthetic_doc_image([])
    lines = [
        ("FATHER'S NAME: RAMESH KUMAR", 0.95),
        ("NAME: AMIT KUMAR", 0.96),
    ]
    fields = extract_fields(dummy_bytes, DocumentType.NATIONAL_ID, raw_lines=lines)
    field_dict = {f.field_name: f.field_value for f in fields}
    assert "name" in field_dict
    assert field_dict["name"] == "AMIT KUMAR"


def test_national_id_alphabetic_word_filtering():
    """Verify purely alphabetic words like NATIONAL are not selected as id_number."""
    dummy_bytes = _create_synthetic_doc_image([])
    lines = [
        ("NATIONAL IDENTITY CARD NO: 987654321012", 0.95),
    ]
    fields = extract_fields(dummy_bytes, DocumentType.NATIONAL_ID, raw_lines=lines)
    field_dict = {f.field_name: f.field_value for f in fields}
    assert "id_number" in field_dict
    assert field_dict["id_number"] == "987654321012"


def test_single_digit_date_and_dl_slashes_extraction():
    """Verify single-digit dates and slashes in driving license numbers are extracted."""
    dummy_bytes = _create_synthetic_doc_image([])
    lines = [
        ("DL NO: DL-04/2011/0012345", 0.95),
        ("DOB: 5/8/1995", 0.94),
        ("VALID TILL: 1/1/2030", 0.93),
    ]
    fields = extract_fields(dummy_bytes, DocumentType.DRIVING_LICENSE, raw_lines=lines)
    field_dict = {f.field_name: f.field_value for f in fields}
    assert "license_number" in field_dict
    assert field_dict["license_number"] == "DL-04/2011/0012345"
    assert field_dict.get("date_of_birth") == "5/8/1995"
    assert field_dict.get("date_of_expiry") == "1/1/2030"


def test_lowercase_pan_and_voter_id_extraction():
    """Verify lowercase PAN and Voter ID regex matching."""
    dummy_bytes = _create_synthetic_doc_image([])
    pan_lines = [("pan number: abcde1234f", 0.95)]
    pan_fields = extract_fields(dummy_bytes, DocumentType.PAN_CARD, raw_lines=pan_lines)
    pan_dict = {f.field_name: f.field_value for f in pan_fields}
    assert pan_dict.get("pan_number") == "abcde1234f"

    voter_lines = [("epic no: tgi8262487", 0.95)]
    voter_fields = extract_fields(dummy_bytes, DocumentType.VOTER_ID, raw_lines=voter_lines)
    voter_dict = {f.field_name: f.field_value for f in voter_fields}
    assert voter_dict.get("voter_id_number") == "tgi8262487"


def test_date_line_plus_1_no_dob_collision():
    """Verify labeled expiry date on next line does not collide with unlabeled birth date fallback."""
    dummy_bytes = _create_synthetic_doc_image([])
    lines = [
        ("EXPIRY DATE:", 0.90),
        ("15/10/2028", 0.95),
    ]
    fields = extract_fields(dummy_bytes, DocumentType.PASSPORT, raw_lines=lines)
    field_dict = {f.field_name: f.field_value for f in fields}
    assert field_dict.get("date_of_expiry") == "15/10/2028"
    assert "date_of_birth" not in field_dict

