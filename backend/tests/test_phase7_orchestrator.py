"""
Phase 7 Test Suite — LangGraph Pipeline, Orchestrator, Audit Ledger & Offline Infrastructure.

Covers:
  - Phase 7A: Risk Scoring Engine Weighted Formula & Plain-Language Reasons
  - Phase 7B: LangGraph StateGraph Execution & Conditional Routing (Standard vs Secondary Queue)
  - Phase 7C: Audit Ledger SHA-256 Hash Chaining, Cryptographic Verification & Tamper Detection
  - Phase 7D: Field-Level AES-256-GCM Encryption & PII Redaction
  - Phase 7E: Edge Inference Packaging & Local Heuristics
  - Phase 7F: Offline Sync SQLite Buffering & Reconciliation
"""

import io
import json
import uuid
import pytest
from PIL import Image

from backend.audit_ledger.core.encryption import (
    decrypt_bytes,
    decrypt_text,
    encrypt_bytes,
    encrypt_text,
    mask_pii,
)
from backend.audit_ledger.core.hash_chain import (
    _IN_MEMORY_CHAIN,
    append_event,
    clear_in_memory_chain,
    compute_payload_hash,
    compute_record_hash,
    verify_chain,
)
from backend.edge_inference.core.runner import EdgeModelRunner
from backend.ocr_service.schemas.extraction import (
    CheckpointType,
    DocumentType,
    ExtractedField,
    ExtractionMethod,
    ExtractionResponse,
    MRZResult,
)
from backend.orchestrator.core.langgraph_pipeline import (
    ScreeningState,
    build_screening_graph,
    check_ocr_quality,
    route_by_threat_level,
    run_langgraph_pipeline,
)
from backend.orchestrator.core.offline_sync import OrchestratorOfflineStore
from backend.risk_engine.core.reasons import generate_reasons
from backend.risk_engine.core.scoring import classify_band, compute_risk_score
from backend.risk_engine.schemas.risk import (
    BlacklistSubScore,
    CrossCheckpointSubScore,
    FaceSubScore,
    RiskBand,
    RiskScoreRequest,
    TamperingSubScore,
    ValidationSubScore,
)


@pytest.fixture(autouse=True)
def clean_ledger():
    """Clear ledger state before each test."""
    clear_in_memory_chain()
    yield
    clear_in_memory_chain()


def create_sample_passport_image_bytes() -> bytes:
    """Generate a clean synthetic passport image."""
    img = Image.new("RGB", (600, 420), color=(240, 244, 248))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ===========================================================================
# 1. Phase 7B: LangGraph Pipeline StateGraph & Conditional Routing
# ===========================================================================
class TestLangGraphPipelineExecution:
    def test_state_graph_compilation(self):
        """Verify LangGraph compiles all nodes and conditional edges successfully."""
        graph = build_screening_graph()
        assert graph is not None

    def test_ocr_quality_conditional_router(self):
        """Test conditional routing to LLM vision fallback on low confidence."""
        # 1. High confidence OCR -> continue
        state_good = {
            "document_type": DocumentType.PASSPORT,
            "extraction": ExtractionResponse(
                document_type=DocumentType.PASSPORT,
                checkpoint_type=CheckpointType.AIRPORT,
                provider_used="local",
                extraction_method=ExtractionMethod.OCR,
                fields=[
                    ExtractedField(field_name="name", field_value="John Doe", confidence=0.95),
                    ExtractedField(field_name="passport_number", field_value="P12345", confidence=0.90),
                ],
                mrz=MRZResult(mrz_present=True, checksum_valid=True, checksum_failures=[], mrz_fields={}),
                warnings=[],
            ),
        }
        assert check_ocr_quality(state_good) == "continue"

        # 2. Low confidence OCR -> route to fallback
        state_poor = {
            "document_type": DocumentType.PASSPORT,
            "extraction": ExtractionResponse(
                document_type=DocumentType.PASSPORT,
                checkpoint_type=CheckpointType.AIRPORT,
                provider_used="local",
                extraction_method=ExtractionMethod.OCR,
                fields=[
                    ExtractedField(field_name="name", field_value="???", confidence=0.30),
                ],
                mrz=MRZResult(mrz_present=False, checksum_valid=None, checksum_failures=[], mrz_fields={}),
                warnings=[],
            ),
        }
        assert check_ocr_quality(state_poor) == "fallback"

    def test_threat_level_conditional_router(self):
        """Test conditional routing between Standard Clearance and Secondary Inspection."""
        from backend.risk_engine.schemas.risk import RiskScoreResponse, SubScoreBreakdown

        clean_sub_scores = SubScoreBreakdown(
            validation_score=0.0,
            tampering_score=0.0,
            face_match_score=0.0,
            blacklist_hit_score=0.0,
            cross_checkpoint_score=0.0,
        )

        # Clean scan -> clearance
        state_clean = {
            "risk_score": RiskScoreResponse(
                document_id="doc-1",
                score=15.0,
                band=RiskBand.LOW,
                reasons=["Valid"],
                sub_scores=clean_sub_scores,
            ),
            "blacklist": BlacklistSubScore(hit=False),
            "cross_checkpoint": CrossCheckpointSubScore(repeat_offender_hit=False),
        }
        assert route_by_threat_level(state_clean) == "clearance"

        # High risk -> secondary inspection
        state_high_risk = {
            "risk_score": RiskScoreResponse(
                document_id="doc-high",
                score=75.0,
                band=RiskBand.HIGH,
                reasons=["Tampered"],
                sub_scores=clean_sub_scores,
            ),
            "blacklist": BlacklistSubScore(hit=False),
            "cross_checkpoint": CrossCheckpointSubScore(repeat_offender_hit=False),
        }
        assert route_by_threat_level(state_high_risk) == "secondary"


        # Blacklist hit -> secondary inspection
        state_blacklist = {
            "blacklist": BlacklistSubScore(hit=True, severity="banned"),
        }
        assert route_by_threat_level(state_blacklist) == "secondary"

        # Repeat offender hit -> secondary inspection
        state_repeat = {
            "cross_checkpoint": CrossCheckpointSubScore(repeat_offender_hit=True),
        }
        assert route_by_threat_level(state_repeat) == "secondary"


    @pytest.mark.asyncio
    async def test_full_langgraph_pipeline_execution(self):
        """Execute end-to-end LangGraph screening pipeline on document image."""
        img_bytes = create_sample_passport_image_bytes()
        result = await run_langgraph_pipeline(
            image_bytes=img_bytes,
            document_type=DocumentType.PASSPORT,
            checkpoint_type=CheckpointType.AIRPORT,
            provider="local",
        )

        assert result.document_id is not None
        assert result.service_statuses.ocr.available is True
        assert result.service_statuses.tampering.available is True
        assert result.service_statuses.face.available is True
        assert result.risk_score is not None
        assert result.risk_score.score >= 0.0
        assert len(result.risk_score.reasons) > 0

    @pytest.mark.asyncio
    async def test_stage1_and_stage2_pipeline_execution(self):
        """Execute Stage 1 and Stage 2 split pipelines independently."""
        from backend.orchestrator.core.langgraph_pipeline import (
            run_stage1_pipeline,
            run_stage2_pipeline,
        )
        img_bytes = create_sample_passport_image_bytes()
        live_bytes = create_sample_passport_image_bytes()

        # ── Stage 1: Document Screening (OCR + Tampering + Rules)
        stage1_res, meta1 = await run_stage1_pipeline(
            image_bytes=img_bytes,
            document_type=DocumentType.PASSPORT,
            checkpoint_type=CheckpointType.AIRPORT,
            provider="local",
        )
        assert stage1_res.document_id is not None
        assert stage1_res.extraction is not None
        assert stage1_res.tampering is not None
        assert stage1_res.validation is not None
        assert stage1_res.face is None
        assert meta1["inspection_status"] == "pending_biometric"
        assert meta1["duration_ms"] >= 0

        # ── Stage 2: Biometric Verification & Risk Scoring
        stage2_res, meta2 = await run_stage2_pipeline(
            doc_image_bytes=img_bytes,
            live_image_bytes=live_bytes,
            document_id=stage1_res.document_id,
            stage1_result=stage1_res,
            document_type=DocumentType.PASSPORT,
            checkpoint_type=CheckpointType.AIRPORT,
            blacklist_sub=meta1["blacklist"],
            provider="local",
        )
        assert stage2_res.document_id == stage1_res.document_id
        assert stage2_res.face is not None
        assert stage2_res.risk_score is not None
        assert meta2["inspection_status"] in ["standard_clearance", "secondary_inspection"]
        assert meta2["duration_ms"] >= 0



# ===========================================================================
# 2. Phase 7C: Audit Ledger Cryptographic Hash Chain & Tamper Catch
# ===========================================================================
class TestAuditLedgerHashChaining:
    @pytest.mark.asyncio
    async def test_ledger_append_and_verify_clean_chain(self):
        """Verify sequential append of events and mathematical validation."""
        for i in range(1, 6):
            await append_event(
                event_type="scan" if i == 1 else "officer_decision",
                payload={"step": i, "status": "approved", "score": 10.0 + i},
                document_id="00000000-0000-0000-0000-000000000001",
                officer_id="00000000-0000-0000-0000-000000000099",
            )

        report = await verify_chain()
        assert report.valid is True
        assert report.total_events == 5
        assert report.first_invalid_sequence is None

    @pytest.mark.asyncio
    async def test_ledger_catches_retroactive_data_tampering(self):
        """Deliberately modify a historical block payload and confirm verify_chain catches it."""
        for i in range(1, 6):
            await append_event(
                event_type="scan",
                payload={"step": i, "score": 15.0},
                document_id="00000000-0000-0000-0000-000000000001",
            )

        # Attack: Corrupt sequence #3 in the chain
        _IN_MEMORY_CHAIN[2]["payload_hash"] = "00" * 32

        report = await verify_chain()
        assert report.valid is False
        assert report.first_invalid_sequence == 3
        assert "tampering detected" in report.detail.lower() or "broken" in report.detail.lower()


# ===========================================================================
# 3. Phase 7D: AES-256-GCM Encryption & PII Redaction
# ===========================================================================
class TestFieldLevelEncryption:
    def test_encrypt_decrypt_text(self):
        """AES-256-GCM string encryption and decryption round-trip."""
        secret_passport = "P987654321"
        encrypted = encrypt_text(secret_passport)
        assert encrypted != secret_passport
        decrypted = decrypt_text(encrypted)
        assert decrypted == secret_passport

    def test_encrypt_decrypt_raw_bytes(self):
        """AES-256-GCM binary payload encryption."""
        raw = b"\x00\x01\x02\x03\x04\x05SECRET_DATA"
        encrypted = encrypt_bytes(raw)
        assert encrypted != raw
        decrypted = decrypt_bytes(encrypted)
        assert decrypted == raw

    def test_pii_masking(self):
        """Verify partial masking of sensitive traveller fields for UI display."""
        assert mask_pii("U5691319", visible_prefix=4) == "U569****"
        assert mask_pii("SMITH", visible_prefix=2) == "SM***"
        assert mask_pii("AB", visible_prefix=4) == "**"


# ===========================================================================
# 4. Phase 7E: Edge Inference Packaging
# ===========================================================================
class TestEdgeInferenceRunner:
    def test_edge_classifier_heuristic(self):
        """Test lightweight edge model runner aspect ratio classification."""
        runner = EdgeModelRunner()
        img_bytes = create_sample_passport_image_bytes()
        doc_type, conf, method = runner.classify_document(img_bytes)
        assert doc_type in [DocumentType.PASSPORT, DocumentType.NATIONAL_ID]
        assert conf > 0.60
        assert "edge" in method

    def test_edge_tampering_prediction(self):
        """Test edge ELA compression score calculation."""
        runner = EdgeModelRunner()
        img_bytes = create_sample_passport_image_bytes()
        score, flagged = runner.predict_tampering_score(img_bytes)
        assert 0.0 <= score <= 1.0


# ===========================================================================
# 5. Phase 7F: Offline Sync Mechanism
# ===========================================================================
class TestOfflineSyncStore:
    def test_buffer_offline_screenings(self, tmp_path):
        """Buffer screening results in SQLite during network disconnects."""
        db_file = tmp_path / "test_offline.db"
        store = OrchestratorOfflineStore(db_path=db_file)

        store.record_offline_screening(
            document_id="offline-doc-001",
            checkpoint_type="land_border",
            result_payload={"risk_score": 18.5, "band": "low"},
        )

        pending = store.get_pending_screenings()
        assert len(pending) == 1
        assert pending[0]["document_id"] == "offline-doc-001"
        assert pending[0]["payload"]["risk_score"] == 18.5

        # Mark as synced
        store.mark_synced([pending[0]["id"]])
        assert len(store.get_pending_screenings()) == 0
