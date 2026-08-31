"""
Phase 6 Test Suite — Multi-Identity & Cross-Checkpoint Detection Engine (Module 5).

Covers:
  - Phase 6A: Cross-Checkpoint Face Graph & Anomaly Flags (name mismatch, doc number mismatch, impossible travel)
  - Phase 6B: Repeat-Offender Flagging & Risk Tier Escalation
  - Phase 6C: Central Aggregation Dossier & FastAPI Endpoints
  - Phase 6-7 Integration: Risk Engine Cross-Checkpoint Weighted Scoring & Reasons
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.cross_checkpoint_service.main import app as cross_checkpoint_app
from backend.cross_checkpoint_service.core.face_graph import (
    analyze_cluster,
    clear_cluster_registry,
    evaluate_cluster_graph,
    get_cluster_history,
    register_cluster_document,
)
from backend.cross_checkpoint_service.core.repeat_offender import (
    check_repeat_offender,
    create_repeat_offender_audit_event,
)
from backend.cross_checkpoint_service.schemas.cross_checkpoint import (
    ClusterAnalysisRequest,
    ClusterDocument,
    CrossCheckpointFlagType,
)
from backend.risk_engine.core.reasons import generate_reasons
from backend.risk_engine.core.scoring import compute_risk_score
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
def clean_registry():
    """Clear in-memory cluster registry before and after every test."""
    clear_cluster_registry()
    yield
    clear_cluster_registry()


# ===========================================================================
# 1. Phase 6A: Name Mismatch Across Cluster
# ===========================================================================
class TestNameMismatchAcrossCluster:
    def test_conflicting_names_trigger_flag(self):
        """Seeding two documents with the same face under different names triggers name_mismatch."""
        cluster_id = str(uuid.uuid4())
        doc1 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            checkpoint_name="Indira Gandhi International Airport",
            uploaded_at="2026-08-30T10:00:00Z",
            document_type="passport",
            name="Johnathan Smith",
            document_number="A12345678",
            nationality="USA",
            risk_band="low",
            risk_score=15.0,
        )
        doc2 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="land_border",
            checkpoint_name="Raxaul Land Border Checkpoint",
            uploaded_at="2026-08-30T18:00:00Z",
            document_type="passport",
            name="David Miller",
            document_number="B98765432",
            nationality="GBR",
            risk_band="low",
            risk_score=20.0,
        )

        flags, cc_risk, rep_hit, esc_tier, esc_band, summary = evaluate_cluster_graph(
            person_cluster_id=cluster_id,
            documents=[doc1, doc2],
        )

        flag_types = [f.flag_type for f in flags]
        assert CrossCheckpointFlagType.NAME_MISMATCH in flag_types
        assert cc_risk >= 0.70
        assert "Johnathan Smith" in summary or "MULTI-IDENTITY" in flags[0].detail

    def test_normalized_same_name_no_mismatch(self):
        """Same name with formatting differences (titles, case) should NOT trigger mismatch."""
        cluster_id = str(uuid.uuid4())
        doc1 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            uploaded_at="2026-08-30T10:00:00Z",
            name="MR. JOHN SMITH",
            document_number="P12345",
        )
        doc2 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            uploaded_at="2026-08-30T15:00:00Z",
            name="John Smith",
            document_number="P12345",
        )

        flags, cc_risk, _, _, _, _ = evaluate_cluster_graph(
            person_cluster_id=cluster_id,
            documents=[doc1, doc2],
        )

        flag_types = [f.flag_type for f in flags]
        assert CrossCheckpointFlagType.NAME_MISMATCH not in flag_types
        assert cc_risk == 0.0


# ===========================================================================
# 2. Phase 6A: Document Number Mismatch Across Cluster
# ===========================================================================
class TestDocumentNumberMismatch:
    def test_differing_doc_numbers_trigger_flag(self):
        """Same person holding multiple distinct passport numbers raises document_number_mismatch."""
        cluster_id = str(uuid.uuid4())
        doc1 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            uploaded_at="2026-08-25T10:00:00Z",
            name="Robert Johnson",
            document_number="US998877",
        )
        doc2 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="sea",
            uploaded_at="2026-08-29T10:00:00Z",
            name="Robert Johnson",
            document_number="UK112233",
        )

        flags, cc_risk, _, _, _, _ = evaluate_cluster_graph(
            person_cluster_id=cluster_id,
            documents=[doc1, doc2],
        )

        flag_types = [f.flag_type for f in flags]
        assert CrossCheckpointFlagType.DOCUMENT_NUMBER_MISMATCH in flag_types
        assert cc_risk >= 0.50


# ===========================================================================
# 3. Phase 6A: Impossible Travel Velocity Detection
# ===========================================================================
class TestImpossibleTravelVelocity:
    def test_rapid_cross_checkpoint_transit_triggers_flag(self):
        """Sightings at Airport and Land Border within 30 minutes triggers impossible_travel_detected."""
        cluster_id = str(uuid.uuid4())
        doc1 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            checkpoint_name="Delhi Airport",
            checkpoint_id="DEL-T3",
            uploaded_at="2026-08-30T10:00:00Z",
            name="Carlos Ruiz",
            document_number="CR1001",
        )
        doc2 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="land_border",
            checkpoint_name="Petrapole Border Checkpoint",
            checkpoint_id="PTP-LAND-1",
            uploaded_at="2026-08-30T10:35:00Z",  # 35 minutes later at distant border
            name="Carlos Ruiz",
            document_number="CR1001",
        )

        flags, cc_risk, _, _, _, _ = evaluate_cluster_graph(
            person_cluster_id=cluster_id,
            documents=[doc1, doc2],
        )

        flag_types = [f.flag_type for f in flags]
        assert CrossCheckpointFlagType.IMPOSSIBLE_TRAVEL in flag_types
        assert cc_risk >= 0.80

    def test_realistic_travel_window_clean(self):
        """Sightings 10 hours apart across checkpoints is physically plausible -> no flag."""
        cluster_id = str(uuid.uuid4())
        doc1 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            checkpoint_id="DEL-T3",
            uploaded_at="2026-08-30T08:00:00Z",
            name="Carlos Ruiz",
            document_number="CR1001",
        )
        doc2 = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="land_border",
            checkpoint_id="PTP-LAND-1",
            uploaded_at="2026-08-30T22:00:00Z",  # 14 hours later
            name="Carlos Ruiz",
            document_number="CR1001",
        )

        flags, _, _, _, _, _ = evaluate_cluster_graph(
            person_cluster_id=cluster_id,
            documents=[doc1, doc2],
        )

        flag_types = [f.flag_type for f in flags]
        assert CrossCheckpointFlagType.IMPOSSIBLE_TRAVEL not in flag_types


# ===========================================================================
# 4. Phase 6B: Repeat Offender Flagging & Band Escalation
# ===========================================================================
class TestRepeatOffenderAndEscalation:
    def test_prior_critical_score_triggers_escalation(self):
        """A cluster with a prior Critical score causes the current scan to escalate its risk band."""
        cluster_id = str(uuid.uuid4())
        prior_doc = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="airport",
            checkpoint_name="Mumbai International Airport",
            uploaded_at="2026-07-15T12:00:00Z",
            name="Alex Thorne",
            document_number="TX9988",
            risk_band="critical",
            risk_score=92.0,
        )
        current_doc = ClusterDocument(
            document_id=str(uuid.uuid4()),
            checkpoint_type="land_border",
            checkpoint_name="Raxaul Land Border",
            uploaded_at="2026-08-31T09:00:00Z",
            name="Alex Thorne",
            document_number="TX9988",
            risk_band="medium",
            risk_score=45.0,
        )

        (
            rep_hit,
            hp_band,
            hp_score,
            esc_tier,
            esc_band,
            prior_reasons,
        ) = check_repeat_offender(
            documents=[prior_doc, current_doc],
            current_document_id=current_doc.document_id,
            current_risk_band="medium",
        )

        assert rep_hit is True
        assert hp_band == "critical"
        assert hp_score == 92.0
        assert esc_tier is True
        assert esc_band == "high"  # Medium escalates to High
        assert len(prior_reasons) > 0

    def test_escalation_mapping_tiers(self):
        """Check tier escalation logic: low->medium, medium->high, high->critical, critical->critical."""
        doc_crit = ClusterDocument(
            document_id="d1",
            risk_band="critical",
            risk_score=88.0,
        )
        # Test low -> medium
        _, _, _, _, esc_low, _ = check_repeat_offender([doc_crit], current_document_id="d2", current_risk_band="low")
        assert esc_low == "medium"

        # Test medium -> high
        _, _, _, _, esc_med, _ = check_repeat_offender([doc_crit], current_document_id="d2", current_risk_band="medium")
        assert esc_med == "high"

        # Test high -> critical
        _, _, _, _, esc_high, _ = check_repeat_offender([doc_crit], current_document_id="d2", current_risk_band="high")
        assert esc_high == "critical"

        # Test critical -> critical
        _, _, _, _, esc_crit, _ = check_repeat_offender([doc_crit], current_document_id="d2", current_risk_band="critical")
        assert esc_crit == "critical"

    def test_clean_cluster_no_repeat_offender(self):
        """A cluster with only Low risk documents does not trigger repeat offender."""
        doc_low1 = ClusterDocument(document_id="d1", risk_band="low", risk_score=10.0)
        doc_low2 = ClusterDocument(document_id="d2", risk_band="low", risk_score=12.0)

        rep_hit, _, _, esc_tier, esc_band, _ = check_repeat_offender([doc_low1, doc_low2], current_document_id="d2", current_risk_band="low")
        assert rep_hit is False
        assert esc_tier is False
        assert esc_band == "low"

    def test_audit_event_creation(self):
        """Verify repeat offender audit event structure."""
        event = create_repeat_offender_audit_event(
            person_cluster_id="cluster-123",
            document_id="doc-456",
            prior_offense_count=2,
            highest_prior_band="critical",
            escalated_band="high",
            officer_id="officer-789",
        )
        assert event["event_type"] == "REPEAT_OFFENDER_FLAG"
        assert event["document_id"] == "doc-456"
        assert event["payload"]["flag"] == "repeat_offender_hit"
        assert event["payload"]["highest_prior_band"] == "critical"


# ===========================================================================
# 5. Phase 6C: Central Aggregation & FastAPI Endpoints
# ===========================================================================
class TestCrossCheckpointFastAPIEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(cross_checkpoint_app)

    def test_health_endpoint(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "cross-checkpoint-service"

    def test_seed_and_get_cluster_history(self, client):
        """GET /api/v1/clusters/{id} returns the full cross-checkpoint history."""
        cluster_id = str(uuid.uuid4())
        doc_id1 = str(uuid.uuid4())
        doc_id2 = str(uuid.uuid4())

        # Seed doc 1
        res1 = client.post(
            "/api/v1/clusters/seed",
            json={
                "person_cluster_id": cluster_id,
                "document": {
                    "document_id": doc_id1,
                    "checkpoint_type": "airport",
                    "checkpoint_name": "Terminal 1",
                    "name": "Maria Garcia",
                    "document_number": "MG1122",
                    "uploaded_at": "2026-08-30T10:00:00Z",
                    "risk_band": "low",
                    "risk_score": 15.0,
                },
            },
        )
        assert res1.status_code == 200

        # Seed doc 2 with different name (fraud simulation)
        res2 = client.post(
            "/api/v1/clusters/seed",
            json={
                "person_cluster_id": cluster_id,
                "document": {
                    "document_id": doc_id2,
                    "checkpoint_type": "land_border",
                    "checkpoint_name": "Border Gate 4",
                    "name": "Elena Rostova",
                    "document_number": "ER9988",
                    "uploaded_at": "2026-08-30T11:00:00Z",  # 1 hour later -> impossible travel + name mismatch
                    "risk_band": "high",
                    "risk_score": 75.0,
                },
            },
        )
        assert res2.status_code == 200

        # Query GET /api/v1/clusters/{cluster_id}
        history_res = client.get(f"/api/v1/clusters/{cluster_id}")
        assert history_res.status_code == 200
        history_data = history_res.json()

        assert history_data["person_cluster_id"] == cluster_id
        assert history_data["total_documents"] == 2
        assert len(history_data["documents"]) == 2
        assert history_data["cross_checkpoint_risk"] > 0.50
        assert history_data["repeat_offender_hit"] is True

        flag_types = [f["flag_type"] for f in history_data["flags"]]
        assert "name_mismatch_across_cluster" in flag_types
        assert "document_number_mismatch_across_cluster" in flag_types
        assert "impossible_travel_detected" in flag_types
        assert "repeat_offender_hit" in flag_types

    def test_analyze_cluster_endpoint(self, client):
        """POST /api/v1/clusters/analyze returns real-time fraud assessment."""
        cluster_id = str(uuid.uuid4())
        prior_doc = {
            "document_id": "doc-prior",
            "checkpoint_type": "airport",
            "name": "Viktor Vance",
            "document_number": "VV1234",
            "uploaded_at": "2026-08-20T10:00:00Z",
            "risk_band": "high",
            "risk_score": 72.0,
        }

        req = {
            "person_cluster_id": cluster_id,
            "current_document_id": "doc-current",
            "current_checkpoint_type": "land_border",
            "current_name": "Viktor Vance",
            "current_document_number": "VV9999",  # Different passport number
            "current_risk_band": "medium",
            "seed_documents": [prior_doc],
        }

        res = client.post("/api/v1/clusters/analyze", json=req)
        assert res.status_code == 200
        data = res.json()

        assert data["person_cluster_id"] == cluster_id
        assert data["repeat_offender_hit"] is True
        assert data["escalate_risk_tier"] is True
        assert data["original_risk_band"] == "medium"
        assert data["escalated_risk_band"] == "high"


# ===========================================================================
# 6. Integration: Risk Engine Cross-Checkpoint Scoring & Reasons
# ===========================================================================
class TestRiskEngineCrossCheckpointIntegration:
    def test_cross_checkpoint_weighting_formula(self):
        """Cross-checkpoint risk dedicates 0.10 weight and scales final score."""
        req = RiskScoreRequest(
            document_id="doc-test-1",
            validation=ValidationSubScore(total_rules=5, failed_rules=0),
            tampering=TamperingSubScore(overall_score=0.0, flagged=False),
            face=FaceSubScore(cosine_similarity=0.90),
            blacklist=BlacklistSubScore(hit=False),
            cross_checkpoint=CrossCheckpointSubScore(
                cross_checkpoint_risk=0.80,
                flags=["name_mismatch_across_cluster"],
                repeat_offender_hit=False,
            ),
        )

        score, band, breakdown = compute_risk_score(req)
        assert breakdown.cross_checkpoint_score == 0.80
        assert breakdown.weights["cross_checkpoint"] == 0.10
        # Contribution = 0.10 * 0.80 * 100 = 8.0 + baseline
        assert score >= 8.0

    def test_repeat_offender_escalation_in_risk_engine(self):
        """Risk engine automatically escalates band when repeat_offender_hit is True."""
        req = RiskScoreRequest(
            document_id="doc-test-2",
            validation=ValidationSubScore(total_rules=5, failed_rules=0),  # Clean
            tampering=TamperingSubScore(overall_score=0.0, flagged=False),  # Clean
            face=FaceSubScore(cosine_similarity=0.95),  # Clean
            blacklist=BlacklistSubScore(hit=False),  # Clean
            cross_checkpoint=CrossCheckpointSubScore(
                cross_checkpoint_risk=0.10,
                repeat_offender_hit=True,
                prior_critical_or_high_count=1,
            ),
        )

        score, band, breakdown = compute_risk_score(req)
        # Baseline score would be Low (0-30), escalated to Medium
        assert band == RiskBand.MEDIUM

    def test_reasons_generation_includes_cross_checkpoint_alerts(self):
        """Reasons list outputs plain-language explanations for all multi-identity signals."""
        req = RiskScoreRequest(
            document_id="doc-test-3",
            cross_checkpoint=CrossCheckpointSubScore(
                cross_checkpoint_risk=0.90,
                flags=[
                    "name_mismatch_across_cluster",
                    "document_number_mismatch_across_cluster",
                    "impossible_travel_detected",
                    "repeat_offender_hit",
                ],
                repeat_offender_hit=True,
                prior_critical_or_high_count=2,
            ),
        )

        _, _, breakdown = compute_risk_score(req)
        reasons = generate_reasons(req, breakdown)

        reasons_text = " ".join(reasons)
        assert "MULTI-IDENTITY" in reasons_text
        assert "MULTIPLE TRAVEL DOCUMENTS" in reasons_text
        assert "IMPOSSIBLE TRAVEL" in reasons_text
        assert "REPEAT OFFENDER" in reasons_text

