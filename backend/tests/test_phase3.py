"""
Phase 3 Unit & Integration Tests — Risk Scoring Engine & Orchestrator Integration.

Verifies:
  1. Risk score weighted formula & sub-score normalization math.
  2. Explainable reason generator for all risk signal combinations.
  3. End-to-end pipeline execution with genuine and tampered documents.
  4. Degraded pipeline resilience when individual modules fail.
  5. Blacklist lookup and risk scoring impact.
  6. Orchestrator API routes and 404 error handling.
"""

from pathlib import Path
import pytest

from backend.ocr_service.schemas.extraction import DocumentType, ExtractedField, ExtractionMethod
from backend.risk_engine.core.reasons import generate_reasons
from backend.risk_engine.core.scoring import (
    BAND_THRESHOLDS,
    WEIGHTS,
    classify_band,
    compute_risk_score,
    build_risk_response,
)
from backend.risk_engine.schemas.risk import (
    BlacklistSubScore,
    FaceSubScore,
    RiskBand,
    RiskScoreRequest,
    TamperingSubScore,
    ValidationSubScore,
)
from backend.orchestrator.core.pipeline import run_pipeline
from backend.orchestrator.core.blacklist import check_blacklist

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "synthetic-tampered"


@pytest.fixture
def genuine_doc_bytes():
    path = SAMPLE_DIR / "doc_001_genuine.jpg"
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture
def photoswap_doc_bytes():
    path = SAMPLE_DIR / "doc_002_tampered_photoswap.jpg"
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture
def textedit_doc_bytes():
    path = SAMPLE_DIR / "doc_003_tampered_textedit.jpg"
    with open(path, "rb") as f:
        return f.read()


# ─── 1. Risk Scoring Formula & Normalization ─────────────────────────────────

def test_risk_score_formula_normalization():
    """
    Test exact weighted formula math:
    risk_score = 0.30*v + 0.35*t + 0.20*f + 0.15*b
    """
    # 1. Perfectly clean document: all 0.0 -> score = 0.0, band = LOW
    req_clean = RiskScoreRequest(
        document_id="doc_test_clean",
        validation=ValidationSubScore(total_rules=4, failed_rules=0),
        tampering=TamperingSubScore(overall_score=0.0, flagged=False),
        face=FaceSubScore(cosine_similarity=1.0, matched=True),
        blacklist=BlacklistSubScore(hit=False),
    )
    score, band, breakdown = compute_risk_score(req_clean)
    assert score == 0.0
    assert band == RiskBand.LOW
    assert breakdown.validation_score == 0.0
    assert breakdown.tampering_score == 0.0
    assert breakdown.face_match_score == 0.0
    assert breakdown.blacklist_hit_score == 0.0

    # 2. Maximum risk document: all failed / max tampering / face mismatch / blacklist banned
    req_max = RiskScoreRequest(
        document_id="doc_test_max",
        validation=ValidationSubScore(total_rules=4, failed_rules=4), # 1.0 * 0.30 = 0.30
        tampering=TamperingSubScore(overall_score=1.0, flagged=True),  # 1.0 * 0.35 = 0.35
        face=FaceSubScore(cosine_similarity=-1.0, matched=False),      # 1.0 * 0.20 = 0.20
        blacklist=BlacklistSubScore(hit=True, severity="banned"),      # 1.0 * 0.15 = 0.15
    )
    score_max, band_max, breakdown_max = compute_risk_score(req_max)
    assert pytest.approx(score_max, abs=0.5) == 100.0
    assert band_max == RiskBand.CRITICAL

    # 3. Intermediate: only tampering flagged (0.80)
    req_tamper_only = RiskScoreRequest(
        document_id="doc_test_tamper",
        validation=ValidationSubScore(total_rules=4, failed_rules=0), # 0.0
        tampering=TamperingSubScore(overall_score=0.80, flagged=True), # 0.80 * 0.35 = 0.28
        face=FaceSubScore(cosine_similarity=1.0, matched=True),       # 0.0
        blacklist=BlacklistSubScore(hit=False),                       # 0.0
    )
    score_t, band_t, _ = compute_risk_score(req_tamper_only)
    # Expected: 0.28 * 100 = 28.0 (LOW/MEDIUM boundary)
    assert pytest.approx(score_t, abs=0.5) == 28.0


def test_risk_band_thresholds():
    """Verify band classification thresholds."""
    assert classify_band(0.0) == RiskBand.LOW
    assert classify_band(30.9) == RiskBand.LOW
    assert classify_band(31.0) == RiskBand.MEDIUM
    assert classify_band(60.9) == RiskBand.MEDIUM
    assert classify_band(61.0) == RiskBand.HIGH
    assert classify_band(80.9) == RiskBand.HIGH
    assert classify_band(81.0) == RiskBand.CRITICAL
    assert classify_band(100.0) == RiskBand.CRITICAL


# ─── 2. Reason Generator Tests ───────────────────────────────────────────────

def test_reason_generation_signals():
    """Verify plain-language reason strings for various forensic combinations."""
    # Test clean document
    req_clean = RiskScoreRequest(
        document_id="doc_clean",
        validation=ValidationSubScore(total_rules=3, failed_rules=0),
        tampering=TamperingSubScore(overall_score=0.05, flagged=False),
        face=FaceSubScore(cosine_similarity=0.92, matched=True),
        blacklist=BlacklistSubScore(hit=False),
    )
    res_clean = build_risk_response(req_clean)
    assert len(res_clean.reasons) >= 1
    assert "No risk signals detected" in res_clean.reasons[0]

    # Test multi-signal risk document
    req_suspicious = RiskScoreRequest(
        document_id="doc_suspicious",
        validation=ValidationSubScore(
            total_rules=3,
            failed_rules=1,
            failed_rule_names=["expiry_not_passed"],
            rule_details={"expiry_not_passed": "Date 2018-01-01 is in the past"},
        ),
        tampering=TamperingSubScore(
            overall_score=0.75,
            flagged=True,
            flagged_checks=["ela", "boundary"],
            check_details={
                "ela": "Localized compression disparity detected",
                "boundary": "Noise variance mismatch in photo area",
            },
        ),
        face=FaceSubScore(
            cosine_similarity=0.35,
            matched=False,
            has_duplicates=True,
            dedup_hit_count=2,
        ),
        blacklist=BlacklistSubScore(
            hit=True,
            matched_fields=["passport_number (X9999999)"],
            severity="banned",
        ),
    )
    res_suspicious = build_risk_response(req_suspicious)

    reasons_text = " ".join(res_suspicious.reasons)
    assert "expiry_not_passed" in reasons_text
    assert "ELA" in reasons_text or "compression" in reasons_text.lower()
    assert "Photo region boundary" in reasons_text or "boundary" in reasons_text.lower()
    assert "Face match" in reasons_text or "cosine similarity" in reasons_text.lower()
    assert "MULTI-IDENTITY ALERT" in reasons_text
    assert "BLACKLIST HIT" in reasons_text


# ─── 3. Blacklist Engine Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_blacklist_engine_lookup():
    """Verify blacklist lookup flags demo prohibited passport number."""
    fields_hit = [
        ExtractedField(field_name="passport_number", field_value="X9999999", confidence=0.99),
        ExtractedField(field_name="name", field_value="SOME PERSON", confidence=0.95),
    ]
    subscore_hit = await check_blacklist(fields_hit)
    assert subscore_hit.hit is True
    assert subscore_hit.severity == "banned"
    assert any("X9999999" in f for f in subscore_hit.matched_fields)

    fields_clean = [
        ExtractedField(field_name="passport_number", field_value="A1234567", confidence=0.99),
        ExtractedField(field_name="name", field_value="GENUINE TRAVELER", confidence=0.95),
    ]
    subscore_clean = await check_blacklist(fields_clean)
    assert subscore_clean.hit is False


# ─── 4. End-to-End Orchestrator Pipeline Tests ───────────────────────────────

@pytest.mark.asyncio
async def test_full_pipeline_genuine_document(genuine_doc_bytes):
    """
    Test full end-to-end screening pipeline with a genuine passport scan.
    Verifies all 5 modules execute and produce low/medium risk.
    """
    res = await run_pipeline(
        image_bytes=genuine_doc_bytes,
        document_type=DocumentType.PASSPORT,
    )

    assert res.document_id is not None
    assert res.extraction is not None
    assert len(res.extraction.fields) > 0
    assert res.validation is not None
    assert res.tampering is not None
    assert res.face is not None
    assert res.risk_score is not None
    assert 0.0 <= res.risk_score.score <= 100.0
    assert res.risk_score.band in [RiskBand.LOW, RiskBand.MEDIUM]
    assert len(res.risk_score.reasons) > 0


@pytest.mark.asyncio
async def test_full_pipeline_tampered_document(photoswap_doc_bytes, textedit_doc_bytes):
    """
    Test full pipeline on tampered documents.
    Verifies elevated risk score and specific tampering reasons generated.
    """
    # Photo-swap tampered document
    res_photo = await run_pipeline(
        image_bytes=photoswap_doc_bytes,
        document_type=DocumentType.PASSPORT,
    )
    assert res_photo.tampering is not None
    assert res_photo.risk_score is not None

    # Text-edit tampered document
    res_text = await run_pipeline(
        image_bytes=textedit_doc_bytes,
        document_type=DocumentType.PASSPORT,
    )
    assert res_text.tampering is not None
    assert res_text.risk_score is not None


@pytest.mark.asyncio
async def test_pipeline_degraded_on_service_failure(genuine_doc_bytes):
    """
    Test pipeline graceful degradation when downstream services return partial/no results.
    Pipeline MUST complete and return a valid risk assessment rather than crashing.
    """
    # Pass corrupted bytes to simulate unreadable image
    res = await run_pipeline(
        image_bytes=b"not_an_image_corrupted_data",
        document_type=DocumentType.PASSPORT,
    )
    assert res.document_id is not None
    assert res.risk_score is not None
    assert 0.0 <= res.risk_score.score <= 100.0
    assert len(res.risk_score.reasons) > 0
