"""
Phase 9 — Global Multi-Language Passport OCR & Standard English ICAO Doc 9303 MRZ Tests

Tests cover:
  1. ICAO Doc 9303 Section 6 character transliteration (German umlauts, French/Spanish diacritics, Nordic)
  2. Non-Latin Indic script transliteration (Devanagari, Bengali)
  3. Regional numeral normalization (Devanagari, Bengali, Eastern Arabic-Indic)
  4. Script and language identification
  5. Country and nationality normalization (ISO 3166-1 alpha-3)
  6. Field extraction with multilingual anchors (German, Hindi, Bengali)
  7. Native script preservation in ExtractedField.native_value
  8. MRZ cross-check compatibility between accented VIZ and standard English ICAO MRZ
"""

import pytest
from backend.ocr_service.core.transliteration import (
    normalize_icao_transliteration,
    normalize_regional_numerals,
    detect_script,
    detect_languages_in_text,
    normalize_country_code,
)
from backend.ocr_service.core.field_extractor import (
    extract_fields,
    detect_multilingual_ocr_metadata,
)
from backend.ocr_service.schemas.extraction import DocumentType


# ===========================================================================
# 1. ICAO Doc 9303 Transliteration Tests
# ===========================================================================

def test_icao_transliteration_german_umlauts():
    """Verify German umlauts and eszett transliterate per ICAO Doc 9303 Section 6."""
    assert normalize_icao_transliteration("MÜLLER") == "MUELLER"
    assert normalize_icao_transliteration("JÖRG SCHRÖDER") == "JOERG SCHROEDER"
    assert normalize_icao_transliteration("STRAßE") == "STRASSE"
    assert normalize_icao_transliteration("BÄCKER") == "BAECKER"
    assert normalize_icao_transliteration("FÜRST") == "FUERST"


def test_icao_transliteration_french_spanish_nordic():
    """Verify Western European accents and Nordic characters transliterate correctly."""
    assert normalize_icao_transliteration("FRANÇOIS") == "FRANCOIS"
    assert normalize_icao_transliteration("PEÑA") == "PENA"
    assert normalize_icao_transliteration("HÅLAND") == "HAALAND"
    assert normalize_icao_transliteration("SØREN") == "SOEREN"
    assert normalize_icao_transliteration("BJÖRN") == "BJOERN"


def test_devanagari_and_bengali_transliteration():
    """Verify Devanagari and Bengali names transliterate to readable ASCII."""
    hindi_name = "अमित शर्मा"
    transliterated_hi = normalize_icao_transliteration(hindi_name)
    assert len(transliterated_hi) > 0
    # Should contain only Latin characters and spaces
    assert all(c.isalpha() or c.isspace() for c in transliterated_hi)

    bengali_name = "রাহুল সেন"
    transliterated_bn = normalize_icao_transliteration(bengali_name)
    assert len(transliterated_bn) > 0
    assert all(c.isalpha() or c.isspace() for c in transliterated_bn)


# ===========================================================================
# 2. Regional Numeral Normalization Tests
# ===========================================================================

def test_regional_numeral_normalization():
    """Verify Devanagari, Bengali, and Eastern Arabic numerals convert to ASCII digits."""
    # Devanagari digits: १२/०५/१९९० -> 12/05/1990
    devanagari_date = "१२/०५/१९९०"
    assert normalize_regional_numerals(devanagari_date) == "12/05/1990"

    # Bengali digits: ১২/০৫/১৯৯০ -> 12/05/1990
    bengali_date = "১২/০৫/১৯৯০"
    assert normalize_regional_numerals(bengali_date) == "12/05/1990"

    # Eastern Arabic digits: ١٢/٠٥/١٩٩٠ -> 12/05/1990
    arabic_date = "١٢/٠٥/١٩٩٠"
    assert normalize_regional_numerals(arabic_date) == "12/05/1990"


# ===========================================================================
# 3. Script and Language Identification Tests
# ===========================================================================

def test_script_detection():
    """Verify script identification for major travel document languages."""
    assert detect_script("John Smith") == "latin"
    assert detect_script("Müller") == "latin"
    assert detect_script("अमित शर्मा") == "devanagari"
    assert detect_script("রাহুল সেন") == "bengali"
    assert detect_script("محمد علي") == "arabic"
    assert detect_script("Иван Иванов") == "cyrillic"
    assert detect_script("สมชาย") == "thai"


def test_language_detection():
    """Verify language code detection from text."""
    langs_de = detect_languages_in_text("Bundesrepublik Deutschland Reisepass")
    assert "de" in langs_de

    langs_hi = detect_languages_in_text("भारत गणराज्य पासपोर्ट अमित शर्मा")
    assert "hi" in langs_hi


# ===========================================================================
# 4. Nationality and Country Code Normalization Tests
# ===========================================================================

def test_country_code_normalization():
    """Verify country and nationality strings map to ISO 3166-1 alpha-3 codes."""
    assert normalize_country_code("DEUTSCHLAND") == "DEU"
    assert normalize_country_code("DEUTSCH") == "DEU"
    assert normalize_country_code("FRANÇAIS") == "FRA"
    assert normalize_country_code("BHARAT") == "IND"
    assert normalize_country_code("INDIAN") == "IND"
    assert normalize_country_code("NEPALI") == "NPL"
    assert normalize_country_code("BANGLADESHI") == "BGD"


# ===========================================================================
# 5. Multilingual Field Extraction Tests
# ===========================================================================

def test_german_passport_extraction_with_umlaut_transliteration():
    """Verify German passport VIZ with umlauts extracts normalized + native values."""
    dummy_img = b"fake_bytes"
    raw_lines = [
        ("BUNDESREPUBLIK DEUTSCHLAND", 0.98),
        ("REISEPASS", 0.99),
        ("NAME / SURNAME", 0.95),
        ("MÜLLER", 0.96),
        ("VORNAMEN / GIVEN NAMES", 0.95),
        ("HANS", 0.97),
        ("STAATSANGEHÖRIGKEIT / NATIONALITY", 0.95),
        ("DEUTSCH", 0.98),
        ("GEBURTSDATUM / DATE OF BIRTH", 0.95),
        ("15.08.1985", 0.94),
        ("PASS-NR. / PASSPORT NO.", 0.95),
        ("C01X00T47", 0.97),
    ]

    fields = extract_fields(dummy_img, DocumentType.PASSPORT, raw_lines=raw_lines)
    fields_dict = {f.field_name: f for f in fields}

    # Verify Name extraction
    assert "name" in fields_dict
    name_field = fields_dict["name"]
    # field_value should be ICAO transliterated
    assert "MUELLER" in name_field.field_value
    assert "HANS" in name_field.field_value
    # native_value preserves original umlaut
    assert name_field.native_value is not None
    assert "MÜLLER" in name_field.native_value

    # Verify Nationality normalized to DEU
    assert "nationality" in fields_dict
    assert fields_dict["nationality"].field_value == "DEU"


def test_multilingual_metadata_detection():
    """Verify detect_multilingual_ocr_metadata detects non-Latin scripts alongside Latin."""
    # Mixed Hindi + English passport lines
    lines = [
        ("भारत गणराज्य", 0.95),
        ("REPUBLIC OF INDIA", 0.98),
        ("अमित शर्मा", 0.94),
        ("AMIT SHARMA", 0.97),
        ("Z1234567", 0.99),
    ]
    langs, primary_script, is_multilingual = detect_multilingual_ocr_metadata(lines)
    assert is_multilingual is True
    assert primary_script == "devanagari"
    assert "hi" in langs or "en" in langs


def test_are_names_equivalent_icao_cross_check():
    """Verify are_names_equivalent handles exact, ICAO transliterated, and fuzzy matches."""
    from backend.ocr_service.core.transliteration import are_names_equivalent

    # German passport: VIZ "MÜLLER, HANS" vs MRZ "MUELLER<<HANS"
    eq, reason = are_names_equivalent("HANS MÜLLER", "MUELLER<<HANS")
    assert eq is True
    assert "ICAO" in reason or "EXACT" in reason

    # French passport: VIZ "FRANÇOIS DUPONT" vs MRZ "DUPONT<<FRANCOIS"
    eq, reason = are_names_equivalent("FRANÇOIS DUPONT", "DUPONT<<FRANCOIS")
    assert eq is True

    # Hindi passport: VIZ "अमित शर्मा" vs MRZ "SHARMA<<AMIT"
    eq, reason = are_names_equivalent("अमित शर्मा", "SHARMA<<AMIT")
    assert eq is True

    # Genuine mismatch
    eq, reason = are_names_equivalent("JOHN SMITH", "DOE<<JANE")
    assert eq is False
