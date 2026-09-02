"""
TriPort Pipeline Latency Profiler — Sub-Step Granular Profiling.

Measures the exact latency of every sub-step in Stage 1 and Stage 2:
- Image decode & preprocessing
- EasyOCR inference
- MRZ parsing
- 5 Tampering sub-engines (ELA, Boundary, Text, Metadata, Stamp)
- Validation rules engine
- Blacklist / watchlist DB check
- Face crop extraction
- Supabase storage uploads (doc + crop)
- Database persistence (save_scan)
- Audit ledger hash-chain append
- AWS Rekognition CompareFaces network round-trip
- Cross-checkpoint pgvector clustering
- Risk engine scoring & reasons
"""

import asyncio
import time
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.orchestrator.main import app
from backend.orchestrator.auth.security import create_access_token
from backend.orchestrator.db.session import get_db
from backend.ocr_service.core.field_extractor import _bytes_to_numpy_image, extract_raw_ocr_lines, extract_fields
from backend.ocr_service.core.mrz_parser import parse_mrz
from backend.ocr_service.schemas.extraction import DocumentType, CheckpointType
from backend.tampering_service.core.ela import compute_ela
from backend.tampering_service.core.metadata_forensics import analyze_metadata
from backend.tampering_service.core.boundary_analysis import analyze_photo_boundaries
from backend.tampering_service.core.stamp_matcher import verify_stamps
from backend.tampering_service.core.text_analysis import analyze_text_manipulation
from backend.validation_service.core.rules_engine import validate_document
from backend.orchestrator.core.blacklist import check_blacklist
from backend.orchestrator.core.service_clients import call_risk_engine
from backend.face_service.core.embedding import extract_face_crop_bytes
from backend.face_service.core.aws_rekognition import aws_compare_faces
from backend.orchestrator.storage import supabase_storage
from backend.audit_ledger.core.hash_chain import append_event
from backend.orchestrator.core import scan_store
from backend.cross_checkpoint_service.core.face_graph import analyze_cluster
from backend.orchestrator.core.service_clients import call_cross_checkpoint_service


async def profile_single_run(doc_path: Path, live_path: Path, run_idx: int) -> dict:
    doc_bytes = doc_path.read_bytes()
    live_bytes = live_path.read_bytes()

    token = create_access_token({
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "officer@borderguard.gov",
        "role": "officer",
        "badge_number": "BG-7492",
        "checkpoint_id": "00000000-0000-0000-0000-000000000010",
    })
    headers = {"Authorization": f"Bearer {token}"}
    metrics = {}

    print(f"\n==================== RUN {run_idx} ====================")

    # ─────────────────────────────────────────────────────────────
    # STAGE 1 SUB-STEP BENCHMARKS
    # ─────────────────────────────────────────────────────────────
    # 1. Image decode / preprocessing
    t0 = time.perf_counter()
    img_array = _bytes_to_numpy_image(doc_bytes)
    metrics["s1_img_decode_ms"] = (time.perf_counter() - t0) * 1000

    # 2. EasyOCR raw inference
    t0 = time.perf_counter()
    raw_lines = extract_raw_ocr_lines(doc_bytes)
    metrics["s1_easyocr_ms"] = (time.perf_counter() - t0) * 1000

    # 3. MRZ parsing
    t0 = time.perf_counter()
    text_lines = [t for t, _ in raw_lines]
    mrz_res = parse_mrz(doc_bytes, ocr_text_lines=text_lines)
    metrics["s1_mrz_parser_ms"] = (time.perf_counter() - t0) * 1000

    # Field extraction regex mapping
    t0 = time.perf_counter()
    fields = extract_fields(doc_bytes, DocumentType.PASSPORT, raw_lines=raw_lines)
    metrics["s1_field_mapping_ms"] = (time.perf_counter() - t0) * 1000

    # 4. Tampering 5 sub-engines individually
    t0 = time.perf_counter()
    compute_ela(doc_bytes)
    metrics["s1_tampering_ela_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    analyze_photo_boundaries(doc_bytes)
    metrics["s1_tampering_boundary_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    analyze_text_manipulation(doc_bytes)
    metrics["s1_tampering_text_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    analyze_metadata(doc_bytes)
    metrics["s1_tampering_metadata_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    verify_stamps(doc_bytes)
    metrics["s1_tampering_stamp_ms"] = (time.perf_counter() - t0) * 1000

    metrics["s1_tampering_total_serial_ms"] = (
        metrics["s1_tampering_ela_ms"]
        + metrics["s1_tampering_boundary_ms"]
        + metrics["s1_tampering_text_ms"]
        + metrics["s1_tampering_metadata_ms"]
        + metrics["s1_tampering_stamp_ms"]
    )

    # 5. Validation rules
    t0 = time.perf_counter()
    val_res = validate_document(DocumentType.PASSPORT, fields)
    metrics["s1_validation_rules_ms"] = (time.perf_counter() - t0) * 1000

    # 6. Watchlist DB check
    async for db in get_db():
        t0 = time.perf_counter()
        bl_res = await check_blacklist(fields, db=db)
        metrics["s1_blacklist_check_ms"] = (time.perf_counter() - t0) * 1000
        break

    # 7. Face crop extraction
    t0 = time.perf_counter()
    crop_bytes, found = extract_face_crop_bytes(doc_bytes)
    metrics["s1_face_crop_ms"] = (time.perf_counter() - t0) * 1000

    # 8. Supabase Storage uploads
    t0 = time.perf_counter()
    doc_url = await supabase_storage.upload_document_image(doc_bytes, "benchmark-test-doc")
    metrics["s1_storage_doc_upload_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    crop_url = await supabase_storage.upload_face_crop_image(crop_bytes or doc_bytes, "benchmark-test-doc")
    metrics["s1_storage_crop_upload_ms"] = (time.perf_counter() - t0) * 1000
    metrics["s1_storage_total_serial_ms"] = metrics["s1_storage_doc_upload_ms"] + metrics["s1_storage_crop_upload_ms"]

    # Full Stage 1 End-to-End API request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("passport.jpg", doc_bytes, "image/jpeg")}
        data = {
            "document_type": "passport",
            "checkpoint_type": "airport",
            "checkpoint_id": "00000000-0000-0000-0000-000000000010",
        }
        t0 = time.perf_counter()
        resp = await client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
        metrics["stage1_total_api_ms"] = (time.perf_counter() - t0) * 1000
        doc_id = resp.json().get("document_id")

    # 9. Audit ledger append
    async for db in get_db():
        t0 = time.perf_counter()
        await append_event(
            event_type="document_screened",
            payload={"test": True},
            document_id=doc_id,
            officer_id="00000000-0000-0000-0000-000000000001",
            db=db,
        )
        metrics["s1_audit_ledger_ms"] = (time.perf_counter() - t0) * 1000
        break

    # ─────────────────────────────────────────────────────────────
    # STAGE 2 SUB-STEP BENCHMARKS
    # ─────────────────────────────────────────────────────────────
    # 1. Live image decode
    t0 = time.perf_counter()
    live_array = _bytes_to_numpy_image(live_bytes)
    metrics["s2_live_img_decode_ms"] = (time.perf_counter() - t0) * 1000

    # 2. Live face crop / detection
    t0 = time.perf_counter()
    live_crop_bytes, live_found = extract_face_crop_bytes(live_bytes)
    metrics["s2_live_face_detect_ms"] = (time.perf_counter() - t0) * 1000

    # 3. AWS Rekognition CompareFaces network call
    t0 = time.perf_counter()
    matched, sim, conf, detail, meta = aws_compare_faces(crop_bytes or doc_bytes, live_bytes)
    metrics["s2_aws_rekognition_ms"] = (time.perf_counter() - t0) * 1000

    # 4. Cross-checkpoint clustering query
    t0 = time.perf_counter()
    cc_res = await call_cross_checkpoint_service(person_cluster_id="cluster-001")
    metrics["s2_cross_checkpoint_clustering_ms"] = (time.perf_counter() - t0) * 1000

    # 5. Risk engine composite scoring
    t0 = time.perf_counter()
    from backend.risk_engine.schemas.risk import RiskScoreRequest
    risk_req = RiskScoreRequest(
        document_id=doc_id,
        document_type=DocumentType.PASSPORT,
        checkpoint_type=CheckpointType.AIRPORT,
    )
    from backend.risk_engine.core.scoring import build_risk_response
    r_resp = build_risk_response(risk_req)
    metrics["s2_risk_engine_ms"] = (time.perf_counter() - t0) * 1000

    # 6. Full Stage 2 End-to-End API request
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        live_file = {"file": ("live.jpg", live_bytes, "image/jpeg")}
        t0 = time.perf_counter()
        resp2 = await client.post(f"/api/v1/documents/{doc_id}/verify-live-face", files=live_file, headers=headers)
        metrics["stage2_total_api_ms"] = (time.perf_counter() - t0) * 1000

    return metrics


async def main():
    doc_path = Path("datasets/synthetic-tampered/doc_001_genuine.jpg")
    live_path = Path("datasets/synthetic-tampered/test_realface_live.jpg")

    runs = []
    for i in range(1, 4):
        m = await profile_single_run(doc_path, live_path, i)
        runs.append(m)

    # Print Summary Table
    print("\n" + "=" * 80)
    print("                HONEST GRANULAR LATENCY PROFILING (3 RUNS)")
    print("=" * 80)
    keys = list(runs[0].keys())

    header = f"{'Sub-Step Component':<38} | {'Run 1 (ms)':<10} | {'Run 2 (ms)':<10} | {'Run 3 (ms)':<10} | {'Avg (ms)':<10}"
    print(header)
    print("-" * 80)

    for k in keys:
        r1, r2, r3 = runs[0][k], runs[1][k], runs[2][k]
        avg = (r1 + r2 + r3) / 3.0
        if "total_api" in k:
            print("-" * 80)
            print(f"👉 {k.upper():<35} | {r1:<10.1f} | {r2:<10.1f} | {r3:<10.1f} | {avg:<10.1f}")
            print("-" * 80)
        else:
            print(f"{k:<38} | {r1:<10.1f} | {r2:<10.1f} | {r3:<10.1f} | {avg:<10.1f}")

if __name__ == "__main__":
    asyncio.run(main())
