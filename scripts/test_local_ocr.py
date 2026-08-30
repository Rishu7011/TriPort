"""
Local OCR & Document Extraction Tester for TriPort.
Runs local classification, MRZ parsing & visual field extraction on sample documents.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ocr_service.core.classifier import classify_document
from backend.ocr_service.core.field_extractor import extract_fields, extract_raw_ocr_lines
from backend.ocr_service.core.mrz_parser import parse_mrz

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets" / "synthetic-tampered"


def test_document(sample_path: Path):
    print("=" * 70)
    print(f"📄 Testing Document: {sample_path.name}")
    print("=" * 70)

    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    # 1. OCR text lines
    raw_lines = extract_raw_ocr_lines(image_bytes)
    print(f"🔍 OCR Detected: {len(raw_lines)} text boxes/lines.")

    # 2. Document Classification
    doc_type, class_conf, details = classify_document(image_bytes, ocr_lines=raw_lines, provider="local")
    print(f"🏷️  Document Type: {doc_type.value.upper()} (Confidence: {class_conf * 100:.1f}%)")

    # 3. MRZ Parsing
    text_only = [t for t, _ in raw_lines]
    mrz_res = parse_mrz(image_bytes, ocr_text_lines=text_only)
    if mrz_res.mrz_present:
        status_sym = "✅ PASSED" if mrz_res.checksum_valid else "❌ CHECKSUM FAILED"
        print(f"🛂 MRZ Zone: {status_sym} (Format: {mrz_res.mrz_fields.get('mrz_format', 'TD3')})")
        print(f"   • Doc Number: {mrz_res.mrz_fields.get('doc_number')}")
        print(f"   • Holder Name: {mrz_res.mrz_fields.get('name')}")
        print(f"   • Nationality: {mrz_res.mrz_fields.get('nationality')}")
        print(f"   • DOB: {mrz_res.mrz_fields.get('date_of_birth')}")
        print(f"   • Expiry: {mrz_res.mrz_fields.get('date_of_expiry')}")
    else:
        print("🛂 MRZ Zone: Not Present (Visual Zone Extraction Only)")

    # 4. Visual Zone Extraction
    fields = extract_fields(image_bytes, doc_type, raw_lines=raw_lines)
    print(f"📋 Structured Fields Extracted ({len(fields)}):")
    for f in fields:
        conf_str = f"{f.confidence:.2f}" if f.confidence is not None else "N/A"
        print(f"   • {f.field_name}: '{f.field_value}' (conf: {conf_str})")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.exists():
            test_document(target)
        else:
            print(f"File not found: {target}")
    else:
        # Run across first 3 sample documents
        samples = sorted(list(DATASET_DIR.glob("doc_*.jpg")))[:3]
        for s in samples:
            test_document(s)
