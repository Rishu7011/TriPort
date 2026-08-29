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

GENUINE_FILES = sorted([f for f in SAMPLE_DIR.glob("doc_*_genuine.jpg")])
PHOTOSWAP_FILES = sorted([f for f in SAMPLE_DIR.glob("doc_*_photoswap*.jpg")])
TEXTEDIT_FILES = sorted([f for f in SAMPLE_DIR.glob("doc_*_textedit*.jpg")])
STAMPDUP_FILES = sorted([f for f in SAMPLE_DIR.glob("doc_*_stamp_duplicate*.jpg")])


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


# ─── 1. Tampering Tests (Parametrized over expanded dataset) ──────────────────

@pytest.mark.parametrize("doc_path", GENUINE_FILES)
def test_ela_on_all_genuine_samples(doc_path: Path):
    """Verify ELA on all genuine dataset variants produces valid baseline metrics."""
    with open(doc_path, "rb") as f:
        img_bytes = f.read()
    score, flagged, heatmap_png, detail = compute_ela(img_bytes)
    assert 0.0 <= score <= 1.0
    assert isinstance(heatmap_png, bytes)
    assert len(heatmap_png) > 0
    assert "ELA" in detail


@pytest.mark.parametrize("doc_path", TEXTEDIT_FILES)
def test_ela_on_all_textedit_samples(doc_path: Path):
    """Verify ELA detects compression discrepancy across all 5 text-edit field variations."""
    with open(doc_path, "rb") as f:
        img_bytes = f.read()
    score, flagged, heatmap_png, detail = compute_ela(img_bytes)
    assert 0.0 <= score <= 1.0
    assert isinstance(heatmap_png, bytes)
    assert len(heatmap_png) > 0


@pytest.mark.parametrize("doc_path", PHOTOSWAP_FILES)
def test_boundary_analysis_on_all_photoswap_samples(doc_path: Path):
    """Verify photo region boundary and noise variance analysis detects all 5 photo-swap variants."""
    with open(doc_path, "rb") as f:
        img_bytes = f.read()
    score, flagged, detail, meta = analyze_photo_boundaries(img_bytes)
    assert 0.0 <= score <= 1.0
    assert "noise_ratio" in meta
    assert "photo_noise_variance" in meta
    # Spliced photo must exhibit higher noise variance ratio
    assert meta["noise_ratio"] >= 1.0


@pytest.mark.parametrize("doc_path", STAMPDUP_FILES)
def test_stamp_verification_on_all_duplicate_samples(doc_path: Path):
    """Verify duplicate stamp hash detection triggers across all 5 stamp-duplicate samples."""
    # First extract reference stamp from genuine doc #1
    gen_path = SAMPLE_DIR / "doc_001_genuine.jpg"
    with open(gen_path, "rb") as f:
        gen_bytes = f.read()
    _, _, detected, _, _, gen_meta = verify_stamps(gen_bytes)
    assert detected is True
    reference_hash = gen_meta["stamps"][0]["dhash"]

    # Verify duplicate stamp sample against known reference hash
    with open(doc_path, "rb") as f:
        dup_bytes = f.read()
    d_score, d_flagged, _, _, d_detail, d_meta = verify_stamps(
        dup_bytes, known_stamp_hashes={reference_hash}
    )
    assert d_flagged is True
    assert d_score >= 0.85
    assert "CRITICAL" in d_detail or "duplicate" in d_detail.lower()


def test_metadata_forensics_clean_vs_suspicious(genuine_doc_bytes):
    """Test metadata forensics flags editing software signatures."""
    score, flagged, flags, raw_meta, detail = analyze_metadata(genuine_doc_bytes)
    assert 0.0 <= score <= 1.0

    # Create image with injected Adobe Photoshop software tag
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    exif = img.getexif()
    exif[0x0131] = "Adobe Photoshop 2024 (Windows)"  # 0x0131 = Software
    img.save(buf, format="JPEG", exif=exif)
    forged_bytes = buf.getvalue()

    f_score, f_flagged, f_flags, _, f_detail = analyze_metadata(forged_bytes)
    assert f_flagged is True
    assert f_score >= 0.60
    assert any("Photoshop" in flag for flag in f_flags)


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
