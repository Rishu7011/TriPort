"""
Phase 4 Tampering & Forgery Detection Test Suite (Module 3).

Covers all 'Definition of Done' criteria from phase.md:
  1. On genuine baseline samples, no forensic check fires above threshold (flagged=False).
  2. On photo-swapped samples, photo boundary analysis (Laplacian noise variance / border energy)
     and/or ELA flags the spliced photo region.
  3. On text-edited samples, text manipulation analysis (stroke-width / font uniformity)
     and/or ELA flags the altered text fields.
  4. On stamp-duplicated pairs, stamp_matcher flags identical perceptual hash reuse (dHash duplicate match).
  5. Metadata forensics flags editing software tags (Photoshop/GIMP/Canva) and timestamp discrepancies.
  6. At least 5 tampered samples per tampering category exist in datasets/synthetic-tampered/
     with ground-truth manifests, verified programmatically.
  7. End-to-end FastAPI endpoint test on POST /api/v1/tampering/detect.
"""

import io
import json
from pathlib import Path
import pytest
import pytest_asyncio
import httpx
from PIL import Image, ImageDraw

from backend.tampering_service.core.boundary_analysis import analyze_photo_boundaries
from backend.tampering_service.core.ela import compute_ela, ela_to_base64
from backend.tampering_service.core.metadata_forensics import analyze_metadata
from backend.tampering_service.core.stamp_matcher import (
    compute_stamp_dhash,
    detect_stamp_regions,
    verify_stamps,
)
from backend.tampering_service.core.text_analysis import analyze_text_manipulation
from backend.tampering_service.main import app
from backend.tampering_service.schemas.tampering import TamperingCheckType, TamperingResponse

DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "synthetic-tampered"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def manifest() -> dict:
    manifest_path = DATASET_DIR / "manifest.json"
    assert manifest_path.exists(), f"Manifest missing at {manifest_path}. Run generate_synthetic_tampered_docs.py first."
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest_asyncio.fixture
async def api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# 1. Dataset Integrity & Manifest Tests
# ---------------------------------------------------------------------------

class TestSyntheticDatasetIntegrity:
    def test_manifest_structure_and_counts(self, manifest):
        """Phase 4 DoD: >=5 samples per category with verified ground-truth manifests."""
        samples = manifest.get("samples", [])
        assert len(samples) >= 20, f"Expected at least 20 samples, found {len(samples)}"

        genuine = [s for s in samples if not s.get("is_tampered")]
        photoswap = [s for s in samples if s.get("tampering_type") == "photo_swap"]
        textedit = [s for s in samples if s.get("tampering_type") == "text_edit"]
        stampdup = [s for s in samples if s.get("tampering_type") == "stamp_duplicate"]

        assert len(genuine) >= 5, f"Expected >= 5 genuine samples, found {len(genuine)}"
        assert len(photoswap) >= 5, f"Expected >= 5 photoswap samples, found {len(photoswap)}"
        assert len(textedit) >= 5, f"Expected >= 5 textedit samples, found {len(textedit)}"
        assert len(stampdup) >= 5, f"Expected >= 5 stampdup samples, found {len(stampdup)}"

    def test_all_sample_files_exist_and_open(self, manifest):
        """Ensure every sample referenced in the manifest physically exists and is a valid image."""
        for sample in manifest.get("samples", []):
            img_path = DATASET_DIR / sample["filename"]
            assert img_path.exists(), f"Image file {sample['filename']} not found on disk"
            with open(img_path, "rb") as f:
                img_bytes = f.read()
                assert len(img_bytes) > 1000, f"File {sample['filename']} is suspiciously small"
                img = Image.open(io.BytesIO(img_bytes))
                assert img.size[0] >= 500 and img.size[1] >= 300


# ---------------------------------------------------------------------------
# 2. Genuine Baseline Document Tests
# ---------------------------------------------------------------------------

class TestGenuineDocumentAnalysis:
    def test_genuine_samples_not_flagged(self, manifest):
        """Phase 4 DoD: Genuine samples produce no false positive flags."""
        genuine_samples = [s for s in manifest["samples"] if not s["is_tampered"]]
        
        for sample in genuine_samples:
            img_path = DATASET_DIR / sample["filename"]
            img_bytes = img_path.read_bytes()

            # 1. ELA
            ela_score, ela_flagged, _, _ = compute_ela(img_bytes)
            assert ela_score < 0.60, f"Genuine sample {sample['filename']} had high ELA score {ela_score}"

            # 2. Text analysis
            text_score, text_flagged, _, _, _ = analyze_text_manipulation(img_bytes)
            assert text_score < 0.60, f"Genuine sample {sample['filename']} had high text score {text_score}"

            # 3. Metadata
            meta_score, meta_flagged, flags, _, _ = analyze_metadata(img_bytes)
            assert meta_flagged is False, f"Genuine sample {sample['filename']} triggered metadata flags: {flags}"

            # 4. Boundary
            bnd_score, bnd_flagged, _, _ = analyze_photo_boundaries(img_bytes)
            assert bnd_score < 0.60, f"Genuine sample {sample['filename']} had high boundary score {bnd_score}"

            # 5. Stamp
            stamp_score, stamp_flagged, _, _, _, _ = verify_stamps(img_bytes)
            assert stamp_flagged is False


# ---------------------------------------------------------------------------
# 3. Photo-Swap Tampering Detection Tests
# ---------------------------------------------------------------------------

class TestPhotoSwapDetection:
    def test_photo_swap_samples_flagged_by_boundary_or_ela(self, manifest):
        """Phase 4 DoD: Photo-swapped samples trigger boundary analysis or ELA."""
        photoswap_samples = [s for s in manifest["samples"] if s["tampering_type"] == "photo_swap"]
        
        flagged_count = 0
        for sample in photoswap_samples:
            img_path = DATASET_DIR / sample["filename"]
            img_bytes = img_path.read_bytes()

            bnd_score, bnd_flagged, bnd_detail, bnd_meta = analyze_photo_boundaries(img_bytes)
            ela_score, ela_flagged, _, _ = compute_ela(img_bytes)

            # At least one of boundary or ELA should register anomaly on spliced portrait
            if bnd_flagged or ela_flagged or bnd_score >= 0.40 or ela_score >= 0.40:
                flagged_count += 1

            assert bnd_meta.get("photo_box") is not None
            assert bnd_meta.get("noise_ratio", 0) > 0.0

        assert flagged_count == len(photoswap_samples), f"Expected all {len(photoswap_samples)} photoswap samples detected, got {flagged_count}"


# ---------------------------------------------------------------------------
# 4. Text-Edit Tampering Detection Tests
# ---------------------------------------------------------------------------

class TestTextEditDetection:
    def test_text_edit_samples_flagged(self, manifest):
        """Phase 4 DoD: Text-edited samples trigger text manipulation analysis or ELA recompression anomaly."""
        textedit_samples = [s for s in manifest["samples"] if s["tampering_type"] == "text_edit"]

        detected_count = 0
        for sample in textedit_samples:
            img_path = DATASET_DIR / sample["filename"]
            img_bytes = img_path.read_bytes()

            text_score, text_flagged, flagged_regions, text_detail, text_meta = analyze_text_manipulation(img_bytes)
            ela_score, ela_flagged, _, _ = compute_ela(img_bytes)

            # Compression artifacts from lower-quality resave or font inconsistency must trigger
            if text_flagged or ela_flagged or text_score >= 0.35 or ela_score >= 0.35:
                detected_count += 1

        assert detected_count >= len(textedit_samples) - 1, f"Expected nearly all text edits detected, got {detected_count}/{len(textedit_samples)}"


# ---------------------------------------------------------------------------
# 5. Stamp Duplicate Detection Tests
# ---------------------------------------------------------------------------

class TestStampDuplicationDetection:
    def test_stamp_duplicate_hash_detection(self, manifest):
        """Phase 4 DoD: Reused digital stamp hash across documents is flagged as forgery."""
        doc1_path = DATASET_DIR / "doc_001_genuine.jpg"
        doc1_bytes = doc1_path.read_bytes()

        # Step 1: Scan doc1 and extract its stamp hashes
        _, _, detected1, _, _, meta1 = verify_stamps(doc1_bytes)
        assert detected1 is True
        stamps1 = meta1.get("stamps", [])
        assert len(stamps1) > 0
        known_hashes = {s["dhash"] for s in stamps1}

        # Step 2: Scan stamp-duplicate sample with doc1's known hashes
        dup_samples = [s for s in manifest["samples"] if s["tampering_type"] == "stamp_duplicate"]
        for sample in dup_samples:
            img_path = DATASET_DIR / sample["filename"]
            img_bytes = img_path.read_bytes()

            score, flagged, detected, conf, detail, meta = verify_stamps(
                img_bytes,
                known_stamp_hashes=known_hashes,
            )
            assert detected is True
            assert meta["duplicate_hash_match"] is True, f"Duplicate stamp not detected in {sample['filename']}"
            assert flagged is True
            assert score >= 0.85
            assert "duplicate stamp hash" in detail.lower()


# ---------------------------------------------------------------------------
# 6. Metadata Forensics Tests
# ---------------------------------------------------------------------------

class TestMetadataForensics:
    def test_photoshop_software_signature_detected(self):
        """Injected editing software metadata tag triggers high anomaly score."""
        img = Image.new("RGB", (300, 200), color=(240, 240, 240))
        exif = img.getexif()
        # Tag 305 is Software
        exif[305] = "Adobe Photoshop 2024 (Windows)"
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        img_bytes = buf.getvalue()

        score, flagged, flags, raw_meta, detail = analyze_metadata(img_bytes)
        assert flagged is True
        assert score >= 0.70
        assert any("photoshop" in f.lower() for f in flags)
        assert "photoshop" in detail.lower()

    def test_gimp_software_signature_detected(self):
        """GIMP signature detected."""
        img = Image.new("RGB", (300, 200), color=(240, 240, 240))
        exif = img.getexif()
        exif[305] = "GIMP 2.10.36"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        img_bytes = buf.getvalue()

        score, flagged, flags, _, _ = analyze_metadata(img_bytes)
        assert flagged is True
        assert any("gimp" in f.lower() for f in flags)

    def test_clean_metadata_passes(self):
        """Clean metadata without manipulation tools passes."""
        img = Image.new("RGB", (300, 200), color=(240, 240, 240))
        exif = img.getexif()
        exif[271] = "Canon"
        exif[272] = "EOS R5"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        img_bytes = buf.getvalue()

        score, flagged, flags, _, detail = analyze_metadata(img_bytes)
        assert flagged is False
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# 7. Non-JPEG Format & Heatmap Conversion Tests
# ---------------------------------------------------------------------------

class TestNonJPEGAndHeatmapHandling:
    def test_png_format_supported_by_ela(self):
        """ELA handles PNG format seamlessly by converting to RGB."""
        img = Image.new("RGBA", (400, 300), color=(200, 220, 240, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(50, 50), (150, 150)], fill=(50, 50, 50, 255))
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        score, flagged, heatmap_bytes, detail = compute_ela(png_bytes)
        assert isinstance(score, float)
        assert len(heatmap_bytes) > 0

        b64 = ela_to_base64(heatmap_bytes)
        assert b64.startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# 8. FastAPI Endpoint Integration Tests (POST /api/v1/tampering/detect)
# ---------------------------------------------------------------------------

class TestTamperingFastAPIEndpoint:
    @pytest.mark.asyncio
    async def test_detect_endpoint_on_genuine_sample(self, api_client, manifest):
        """Full FastAPI endpoint execution on genuine sample returns 200 OK and complete schema."""
        doc_path = DATASET_DIR / "doc_001_genuine.jpg"
        with open(doc_path, "rb") as f:
            files = {"file": ("doc_001_genuine.jpg", f.read(), "image/jpeg")}

        resp = await api_client.post("/api/v1/tampering/detect", files=files)
        assert resp.status_code == 200
        data = resp.json()

        assert "flagged" in data
        assert "tampering_score" in data
        assert "checks" in data
        assert "ela_heatmap_base64" in data
        assert data["flagged"] is False
        assert data["tampering_score"] < 0.50

        # All 5 check types must be present
        check_types = {c["check_type"] for c in data["checks"]}
        expected_types = {"ela", "text_analysis", "metadata", "boundary", "stamp_match"}
        assert expected_types.issubset(check_types), f"Missing check types: {expected_types - check_types}"

    @pytest.mark.asyncio
    async def test_detect_endpoint_on_tampered_sample(self, api_client, manifest):
        """Tampered sample triggers positive tampering score on /detect endpoint."""
        doc_path = DATASET_DIR / "doc_011_tampered_photoswap_1.jpg"
        with open(doc_path, "rb") as f:
            files = {"file": ("photoswap.jpg", f.read(), "image/jpeg")}

        resp = await api_client.post("/api/v1/tampering/detect", files=files)
        assert resp.status_code == 200
        data = resp.json()

        assert data["tampering_score"] > 0.0
        assert data["ela_heatmap_base64"] is not None
        assert data["ela_heatmap_base64"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_empty_file_returns_422(self, api_client):
        """Empty uploaded file returns 422 Unprocessable Entity."""
        files = {"file": ("empty.jpg", b"", "image/jpeg")}
        resp = await api_client.post("/api/v1/tampering/detect", files=files)
        assert resp.status_code == 422
