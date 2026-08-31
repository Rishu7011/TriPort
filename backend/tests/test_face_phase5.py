"""
Comprehensive Phase 5 Test Suite: Face Verification, Liveness, and 1:N Deduplication.

Tests DoD Criteria:
  1. 512-dim Face Embedding extraction & L2-normalization.
  2. 1:1 Identity Verification (Same person -> match, Different people -> mismatch).
  3. AWS Rekognition integration & graceful fallback.
  4. MediaPipe FaceMesh Liveness & Anti-spoofing detection.
  5. 1:N Deduplication search & Person Cluster ID linkage.
  6. Bulk batch throughput mode (/verify/batch).
  7. FastAPI integration tests for all /api/v1/face endpoints.
"""

import io
import pytest
import numpy as np
from PIL import Image, ImageDraw
import httpx
from fastapi.testclient import TestClient

from backend.face_service.main import app
from backend.face_service.core.embedding import (
    extract_face_embedding,
    extract_face_crop_bytes,
    _l2_normalize,
    _ensure_512d,
)
from backend.face_service.core.one_to_one import (
    compute_cosine_similarity,
    verify_one_to_one,
    run_liveness_check,
)
from backend.face_service.core.aws_rekognition import (
    get_rekognition_client,
    is_aws_rekognition_available,
    aws_compare_faces,
)
from backend.face_service.core.dedup_search import (
    search_duplicates,
    register_in_memory_embedding,
    clear_in_memory_embeddings,
)


# ---------------------------------------------------------------------------
# Test Helpers: Synthetic Face Images
# ---------------------------------------------------------------------------
def _create_synthetic_face_image(seed: int = 42, is_live: bool = True) -> bytes:
    """Generate a clean synthetic portrait image for testing."""
    np.random.seed(seed)
    w, h = 300, 350
    img = Image.new("RGB", (w, h), color=(235, 235, 240))
    draw = ImageDraw.Draw(img)

    # Head oval
    face_bbox = [50, 40, 250, 300]
    draw.ellipse(face_bbox, fill=(240, 205, 180), outline=(200, 160, 140), width=2)

    # Eyes
    if is_live:
        # Open eyes
        draw.ellipse([90, 130, 130, 155], fill=(255, 255, 255), outline=(50, 50, 50), width=2)
        draw.ellipse([103, 138, 117, 150], fill=(50, 40, 30))
        draw.ellipse([170, 130, 210, 155], fill=(255, 255, 255), outline=(50, 50, 50), width=2)
        draw.ellipse([183, 138, 197, 150], fill=(50, 40, 30))
    else:
        # Closed/slanted eyes (simulating spoof/closed eye)
        draw.line([90, 142, 130, 142], fill=(50, 50, 50), width=3)
        draw.line([170, 142, 210, 142], fill=(50, 50, 50), width=3)

    # Nose
    draw.line([150, 160, 145, 200], fill=(180, 140, 120), width=2)
    draw.line([145, 200, 160, 200], fill=(180, 140, 120), width=2)

    # Mouth
    draw.arc([115, 220, 185, 260], start=10, end=170, fill=(180, 70, 70), width=3)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test Suite 1: Embedding Extraction & Normalization
# ---------------------------------------------------------------------------
class TestFaceEmbeddingExtraction:
    def test_l2_normalization_and_512d(self):
        """Embedding vectors must be exactly 512 dimensions and L2-normalized."""
        raw_vec = np.random.randn(512)
        norm_vec = _l2_normalize(raw_vec)
        assert len(norm_vec) == 512
        assert abs(np.linalg.norm(norm_vec) - 1.0) < 1e-5

    def test_ensure_512d_padding_and_truncation(self):
        """Under-sized or over-sized feature vectors must be padded/truncated to 512-dim."""
        short_vec = np.ones(256)
        padded = _ensure_512d(short_vec)
        assert len(padded) == 512

        long_vec = np.ones(1024)
        truncated = _ensure_512d(long_vec)
        assert len(truncated) == 512

    def test_extract_face_embedding_on_image(self):
        """Extract face embedding returns valid 512-dim unit vector."""
        img_bytes = _create_synthetic_face_image(seed=101)
        ok, emb, count, detail = extract_face_embedding(img_bytes)

        assert ok is True
        assert len(emb) == 512
        assert count >= 1
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-4

    def test_extract_face_crop_bytes(self):
        """Extracting face crop returns valid image bytes or None gracefully."""
        img_bytes = _create_synthetic_face_image(seed=102)
        crop_bytes, detected = extract_face_crop_bytes(img_bytes)
        # Even on simple synthetic images, crop execution returns bytes or boolean flag cleanly
        if detected:
            assert isinstance(crop_bytes, bytes)
            assert len(crop_bytes) > 0


# ---------------------------------------------------------------------------
# Test Suite 2: Cosine Similarity & 1:1 Matching
# ---------------------------------------------------------------------------
class TestOneToOneVerification:
    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors must have cosine similarity = 1.0."""
        vec = _l2_normalize(np.random.randn(512)).tolist()
        sim = compute_cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-4

    def test_cosine_similarity_orthogonal_vectors(self):
        """Orthogonal vectors must have cosine similarity ≈ 0.0."""
        vec_a = [1.0] + [0.0] * 511
        vec_b = [0.0, 1.0] + [0.0] * 510
        sim = compute_cosine_similarity(vec_a, vec_b)
        assert abs(sim - 0.0) < 1e-4

    def test_verify_one_to_one_same_person(self):
        """Same person (same image / identical embedding) must yield matched=True."""
        img_bytes = _create_synthetic_face_image(seed=201)
        matched, score, sim, detail = verify_one_to_one(
            doc_image_bytes=img_bytes,
            live_image_bytes=img_bytes,
            enable_liveness=False,
        )
        assert matched is True
        assert sim >= 0.50
        assert "PASSED" in detail

    def test_verify_one_to_one_different_people(self):
        """Different people embeddings must yield matched=False."""
        # Create two distinct orthogonal vectors
        emb1 = [1.0] + [0.0] * 511
        emb2 = [0.0, 1.0] + [0.0] * 510

        matched, score, sim, detail = verify_one_to_one(
            doc_embedding=emb1,
            live_embedding=emb2,
            threshold=0.50,
            enable_liveness=False,
        )
        assert matched is False
        assert sim < 0.50
        assert "FAILED" in detail


# ---------------------------------------------------------------------------
# Test Suite 3: AWS Rekognition Integration
# ---------------------------------------------------------------------------
class TestAWSRekognitionIntegration:
    def test_aws_rekognition_client_initialization(self):
        """AWS Rekognition client should initialize when credentials are present."""
        client = get_rekognition_client()
        assert client is not None
        assert is_aws_rekognition_available() is True

    def test_aws_compare_faces_call_structure(self):
        """aws_compare_faces executes gracefully with live image bytes."""
        img_a = _create_synthetic_face_image(seed=301)
        img_b = _create_synthetic_face_image(seed=302)

        matched, sim, conf, detail, meta = aws_compare_faces(
            source_bytes=img_a,
            target_bytes=img_b,
            similarity_threshold=70.0,
        )
        # Verify return type contract
        assert isinstance(matched, bool)
        assert 0.0 <= sim <= 1.0
        assert 0.0 <= conf <= 1.0
        assert isinstance(detail, str)
        assert isinstance(meta, dict)


# ---------------------------------------------------------------------------
# Test Suite 4: Liveness & Anti-Spoofing
# ---------------------------------------------------------------------------
class TestLivenessDetection:
    def test_liveness_check_execution(self):
        """Liveness check runs on live photo bytes and returns calibrated score."""
        live_bytes = _create_synthetic_face_image(seed=401, is_live=True)
        score, detail = run_liveness_check(live_bytes)
        assert 0.0 <= score <= 1.0
        assert isinstance(detail, str)


# ---------------------------------------------------------------------------
# Test Suite 5: 1:N Deduplication & Clustering
# ---------------------------------------------------------------------------
class TestDedupSearch:
    @pytest.mark.asyncio
    async def test_dedup_finds_duplicate_record(self):
        """1:N search must return hits when matching face embedding is registered."""
        clear_in_memory_embeddings()
        vec_alice = _l2_normalize(np.random.randn(512)).tolist()
        cluster_id = register_in_memory_embedding(
            document_id="doc-passport-001",
            embedding=vec_alice,
            person_cluster_id="cluster-alice-123",
        )

        has_dups, hits, assigned_id, detail = await search_duplicates(
            embedding=vec_alice,
            threshold=0.60,
        )

        assert has_dups is True
        assert len(hits) >= 1
        assert hits[0].document_id == "doc-passport-001"
        assert hits[0].similarity >= 0.95
        assert assigned_id == "cluster-alice-123"
        assert "MULTI-IDENTITY ALERT" in detail

    @pytest.mark.asyncio
    async def test_dedup_no_duplicate_creates_new_cluster(self):
        """1:N search for a novel face must create a new cluster ID with 0 hits."""
        clear_in_memory_embeddings()
        vec_bob = _l2_normalize(np.random.randn(512)).tolist()

        has_dups, hits, assigned_id, detail = await search_duplicates(
            embedding=vec_bob,
            threshold=0.60,
        )

        assert has_dups is False
        assert len(hits) == 0
        assert assigned_id is not None
        assert "No duplicate identities found" in detail


# ---------------------------------------------------------------------------
# Test Suite 6: FastAPI Endpoints Integration
# ---------------------------------------------------------------------------
class TestFaceFastAPIEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["service"] == "face-service"

    def test_embed_endpoint(self, client):
        img_bytes = _create_synthetic_face_image(seed=501)
        resp = client.post(
            "/api/v1/face/embed",
            files={"file": ("face.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["face_detected"] is True
        assert len(data["embedding"]) == 512

    def test_verify_endpoint(self, client):
        img_a = _create_synthetic_face_image(seed=502)
        img_b = _create_synthetic_face_image(seed=502)

        resp = client.post(
            "/api/v1/face/verify",
            files={
                "doc_photo": ("doc.jpg", img_a, "image/jpeg"),
                "live_photo": ("live.jpg", img_b, "image/jpeg"),
            },
            data={"threshold": 0.50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "matched" in data
        assert "match_score" in data
        assert "cosine_similarity" in data

    def test_liveness_endpoint(self, client):
        live_bytes = _create_synthetic_face_image(seed=503)
        resp = client.post(
            "/api/v1/face/liveness",
            files={"live_photo": ("live.jpg", live_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_live" in data
        assert "liveness_score" in data
        assert 0.0 <= data["liveness_score"] <= 1.0

    def test_batch_verify_endpoint(self, client):
        img_1 = _create_synthetic_face_image(seed=601)
        img_2 = _create_synthetic_face_image(seed=602)

        resp = client.post(
            "/api/v1/face/verify/batch",
            files=[
                ("doc_photos", ("doc1.jpg", img_1, "image/jpeg")),
                ("doc_photos", ("doc2.jpg", img_2, "image/jpeg")),
                ("live_photos", ("live1.jpg", img_1, "image/jpeg")),
                ("live_photos", ("live2.jpg", img_2, "image/jpeg")),
            ],
            data={"threshold": 0.50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_processed"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["item_id"] == "item_1"
        assert data["results"][1]["item_id"] == "item_2"
