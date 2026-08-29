"""
Phase 1 Smoke Tests — Validation Service & MRZ checksum testing.
"""

import pytest
from backend.ocr_service.core.mrz_parser import _compute_check_digit, _validate_check_digit
from backend.ocr_service.schemas.extraction import (
    DocumentType,
    ExtractedField,
    ExtractionMethod,
)
from backend.validation_service.core.rules_engine import validate_document


def test_icao_mrz_checksum_calculation():
    """
    Test ICAO 9303 checksum computation with standard test vectors.
    Example DOB: '850115' -> check digit 6
    """
    # 8*7 + 5*3 + 0*1 + 1*7 + 1*3 + 5*1 = 56 + 15 + 0 + 7 + 3 + 5 = 86 -> 86 % 10 = 6
    assert _compute_check_digit("850115") == 6
    assert _validate_check_digit("850115", "6") is True
    # If tampered: '860115' -> should fail against expected '6'
    assert _validate_check_digit("860115", "6") is False


def test_validation_engine_valid_passport():
    """Test valid passport fields passing all YAML rules."""
    fields = [
        ExtractedField(field_name="doc_number", field_value="A1234567", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="date_of_birth", field_value="1990-05-15", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="expiry_date", field_value="2030-12-31", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="nationality", field_value="IND", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
    ]

    response = validate_document(DocumentType.PASSPORT, fields)
    assert response.passed is True
    assert len(response.failed_rules) == 0


def test_validation_engine_ocr_field_names():
    """Test passport fields with visual zone naming (date_of_expiry, passport_number) passing all rules."""
    fields = [
        ExtractedField(field_name="passport_number", field_value="A1234567", confidence=0.95, extraction_method=ExtractionMethod.OCR),
        ExtractedField(field_name="date_of_birth", field_value="1990-05-15", confidence=0.95, extraction_method=ExtractionMethod.OCR),
        ExtractedField(field_name="date_of_expiry", field_value="2030-12-31", confidence=0.95, extraction_method=ExtractionMethod.OCR),
        ExtractedField(field_name="nationality", field_value="IND", confidence=0.95, extraction_method=ExtractionMethod.OCR),
    ]

    response = validate_document(DocumentType.PASSPORT, fields)
    assert response.passed is True
    assert len(response.failed_rules) == 0


def test_validation_engine_expired_passport():
    """Test expired passport failing expiry_not_passed rule."""
    fields = [
        ExtractedField(field_name="doc_number", field_value="A1234567", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="date_of_birth", field_value="1990-05-15", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="expiry_date", field_value="2018-01-01", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
        ExtractedField(field_name="nationality", field_value="IND", confidence=0.98, extraction_method=ExtractionMethod.MRZ),
    ]

    response = validate_document(DocumentType.PASSPORT, fields)
    assert response.passed is False
    assert "expiry_not_passed" in response.failed_rules


def test_mrz_parser_with_p_doc_number():
    """Test MRZ parser correctly handles document numbers starting with 'P' without line confusion."""
    from backend.ocr_service.core.mrz_parser import parse_mrz_from_text_lines
    lines = [
        "P<INDSURNAME<<GIVENNAME<<<<<<<<<<<<<<<<<<<<<",
        "P1234567<1IND8501156M2812313<<<<<<<<<<<<<<<<",
    ]
    res = parse_mrz_from_text_lines(lines)
    assert res.mrz_present is True
    assert res.checksum_valid is True
    assert res.mrz_fields["doc_number"] == "P1234567"
    assert res.mrz_fields["nationality"] == "IND"


def test_date_conditions_offset():
    """Test date condition evaluations including +/- offsets."""
    from backend.validation_service.core.date_logic import evaluate_date_condition
    passed, _ = evaluate_date_condition("1995-01-01", "< today - 18y")
    assert passed is True
    passed_future, _ = evaluate_date_condition("2020-01-01", "< today - 18y")
    assert passed_future is False

