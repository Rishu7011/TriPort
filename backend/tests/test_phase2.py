"""
Phase 2 Unit & Integration Tests — Tampering Detection and Face Verification Services.
"""

import io
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

from backend.face_service.core.dedup_search import (
    clear_in_memory_embeddings,
    register_in_memory_embedding,
    search_duplicates,
)
from backend.face_service.core.embedding import extract_face_embedding
from backend.face_service.core.one_to_one import verify_one_to_one
from backend.tampering_service.core.boundary_analysis import analyze_photo_boundaries
from backend.tampering_service.core.ela import compute_ela
from backend.tampering_service.core.metadata_forensics import analyze_metadata
from backend.tampering_service.core.stamp_matcher import (
    compute_stamp_dhash,
    verify_stamps,
)

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


# ─── 1. Tampering Tests ──────────────────────────────────────────────────────

def test_ela_generates_heatmap_and_score(genuine_doc_bytes, textedit_doc_bytes):
    """Test ELA produces valid numeric score, heatmap PNG bytes, and explainable detail."""
    score, flagged, heatmap_png, detail = compute_ela(genuine_doc_bytes)
    assert 0.0 <= score <= 1.0
    assert isinstance(heatmap_png, bytes)
    assert len(heatmap_png) > 0
    assert "ELA" in detail

    # Tampered image with recompression should execute cleanly and return valid metrics
    t_score, t_flagged, t_heatmap, t_detail = compute_ela(textedit_doc_bytes)
    assert 0.0 <= t_score <= 1.0
    assert len(t_heatmap) > 0


def test_metadata_forensics_clean_vs_suspicious(genuine_doc_bytes):
    """Test metadata forensics flags editing software signatures."""
    score, flagged, flags, raw_meta, detail = analyze_metadata(genuine_doc_bytes)
    assert 0.0 <= score <= 1.0

    # Create image with injected Adobe Photoshop software tag
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    # In Pillow 10+, exif can be populated
    exif = img.getexif()
    exif[0x0131] = "Adobe Photoshop 2024 (Windows)"  # 0x0131 = Software
    img.save(buf, format="JPEG", exif=exif)
    forged_bytes = buf.getvalue()

    f_score, f_flagged, f_flags, _, f_detail = analyze_metadata(forged_bytes)
    assert f_flagged is True
    assert f_score >= 0.60
    assert any("Photoshop" in flag for flag in f_flags)


def test_boundary_analysis(genuine_doc_bytes, photoswap_doc_bytes):
    """Test photo region boundary discontinuity and noise variance analysis."""
    score, flagged, detail, meta = analyze_photo_boundaries(genuine_doc_bytes)
    assert 0.0 <= score <= 1.0
    assert "noise_ratio" in meta
    assert "photo_noise_variance" in meta

    # Spliced photo has higher noise variance ratio
    p_score, p_flagged, p_detail, p_meta = analyze_photo_boundaries(photoswap_doc_bytes)
    assert 0.0 <= p_score <= 1.0
    assert p_meta["noise_ratio"] >= 1.0


def test_stamp_verification_and_duplicate_hash(genuine_doc_bytes):
    """Test stamp ink detection and duplicate perceptual hash matching."""
    score, flagged, detected, conf, detail, meta = verify_stamps(genuine_doc_bytes)
    assert detected is True
    assert meta["stamp_count"] >= 1
    assert "dhash" in meta["stamps"][0]

    captured_hash = meta["stamps"][0]["dhash"]
    assert len(captured_hash) > 0

    # When scanning another document that reuses the exact same stamp hash:
    d_score, d_flagged, _, _, d_detail, d_meta = verify_stamps(
        genuine_doc_bytes, known_stamp_hashes={captured_hash}
    )
    assert d_flagged is True
    assert d_score >= 0.85
    assert "CRITICAL" in d_detail or "duplicate" in d_detail.lower()


# ─── 2. Face Verification Tests ──────────────────────────────────────────────

def test_face_embedding_extraction(genuine_doc_bytes):
    """Test face embedding generates 512-dim unit vector."""
    detected, embedding, count, detail = extract_face_embedding(genuine_doc_bytes)
    assert detected is True
    assert len(embedding) == 512
    # Verify unit length L2 norm
    import numpy as np
    norm = np.linalg.norm(embedding)
    assert pytest.approx(norm, abs=0.02) == 1.0


def test_one_to_one_face_verification(genuine_doc_bytes):
    """Test 1:1 face verification matching same face vs different faces."""
    _, emb1, _, _ = extract_face_embedding(genuine_doc_bytes)

    # Identical embedding verification (same person)
    matched, match_score, sim, detail = verify_one_to_one(
        doc_embedding=emb1,
        live_embedding=emb1,
    )
    assert matched is True
    assert sim >= 0.99
    assert match_score >= 0.95

    # Completely orthogonal/inverted embedding (different person)
    import numpy as np
    emb_diff = (-np.array(emb1)).tolist()
    diff_matched, diff_score, diff_sim, _ = verify_one_to_one(
        doc_embedding=emb1,
        live_embedding=emb_diff,
    )
    assert diff_matched is False
    assert diff_sim < 0.0


@pytest.mark.asyncio
async def test_dedup_search_and_clustering(genuine_doc_bytes):
    """Test 1:N deduplication matches identical person and creates new cluster for new person."""
    clear_in_memory_embeddings()
    _, emb1, _, _ = extract_face_embedding(genuine_doc_bytes)

    # Initially empty registry -> no duplicates
    has_dups, hits, cluster_1, detail = await search_duplicates(embedding=emb1)
    assert has_dups is False
    assert len(hits) == 0
    assert len(cluster_1) > 0

    # Register first identity
    register_in_memory_embedding(
        document_id="doc_first_001",
        embedding=emb1,
        person_cluster_id=cluster_1,
    )

    # Scan second document with the same face -> MUST flag duplicate and share cluster_1
    has_dups_2, hits_2, cluster_2, detail_2 = await search_duplicates(embedding=emb1)
    assert has_dups_2 is True
    assert len(hits_2) == 1
    assert hits_2[0].document_id == "doc_first_001"
    assert cluster_2 == cluster_1  # Reuses same cluster ID!
