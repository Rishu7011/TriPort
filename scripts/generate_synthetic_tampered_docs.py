"""
Synthetic Tampered Document Generator.

CONCEPT:
Generates synthetic identity documents and deliberate tampering variants
(photo-swaps, text edits with recompression artifacts, and duplicated digital stamps)
alongside a ground-truth manifest JSON.

This enables rigorous automated testing of Phase 2 tampering detection
without using any real citizens' personal data.
"""

import json
import os
import random
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "synthetic-tampered"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _draw_mock_face(size=(140, 180), seed=42) -> np.ndarray:
    """Generate a clean synthetic facial portrait image."""
    rng = random.Random(seed)
    w, h = size
    img = np.full((h, w, 3), 235, dtype=np.uint8)

    # Background gradient
    for y in range(h):
        img[y, :] = (210 + int(y * 0.15), 220 + int(y * 0.1), 240)

    # Face Oval
    center = (w // 2, int(h * 0.48))
    axes = (int(w * 0.32), int(h * 0.38))
    skin_color = (195 + rng.randint(0, 30), 210 + rng.randint(0, 20), 235 + rng.randint(0, 15))
    cv2.ellipse(img, center, axes, 0, 0, 360, skin_color, -1)

    # Hair
    hair_color = (30 + rng.randint(0, 20), 30 + rng.randint(0, 20), 40 + rng.randint(0, 20))
    cv2.ellipse(img, (w // 2, int(h * 0.28)), (int(w * 0.34), int(h * 0.20)), 0, 180, 360, hair_color, -1)

    # Eyes
    eye_y = int(h * 0.44)
    cv2.circle(img, (int(w * 0.38), eye_y), 5, (255, 255, 255), -1)
    cv2.circle(img, (int(w * 0.38), eye_y), 3, (30, 20, 10), -1)
    cv2.circle(img, (int(w * 0.62), eye_y), 5, (255, 255, 255), -1)
    cv2.circle(img, (int(w * 0.62), eye_y), 3, (30, 20, 10), -1)

    # Mouth
    mouth_y = int(h * 0.64)
    cv2.ellipse(img, (w // 2, mouth_y), (14, 6), 0, 0, 180, (120, 100, 160), 2)

    # Shirt / Shoulders
    cv2.ellipse(img, (w // 2, int(h * 1.1)), (int(w * 0.65), int(h * 0.45)), 0, 180, 360, (140, 80, 60), -1)

    return img


def _draw_stamp(size=100, color=(180, 40, 40)) -> np.ndarray:
    """Generate a mock circular immigration ink stamp."""
    img = np.zeros((size, size, 4), dtype=np.uint8)
    center = (size // 2, size // 2)
    radius = int(size * 0.42)

    # Outer double ring
    cv2.circle(img, center, radius, (*color, 210), 3)
    cv2.circle(img, center, radius - 6, (*color, 190), 1)

    # Stamp text
    cv2.putText(img, "SSB CHECKPOINT", (12, size // 2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (*color, 230), 1)
    cv2.putText(img, "ENTRY PERMIT", (16, size // 2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (*color, 230), 1)
    cv2.putText(img, "IMMIGRATION", (18, size // 2 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (*color, 200), 1)

    return img


def generate_baseline_passport(doc_id: str, surname: str, given_name: str, doc_num: str, seed: int = 100) -> Image.Image:
    """Create a high-resolution synthetic passport document image."""
    width, height = 700, 480
    img = Image.new("RGB", (width, height), color=(248, 245, 235))
    draw = ImageDraw.Draw(img)

    # Passport Header
    draw.rectangle([(20, 20), (width - 20, 70)], fill=(220, 215, 195))
    draw.text((30, 28), "PASSPORT / PASSEPORT", fill=(40, 40, 40))
    draw.text((30, 48), "REPUBLIC OF INDIA / RÉPUBLIQUE DE L'INDE", fill=(70, 70, 70))
    draw.text((width - 160, 35), "Type: P  Code: IND", fill=(50, 50, 50))

    # Photo Box
    photo_np = _draw_mock_face(size=(140, 180), seed=seed)
    photo_pil = Image.fromarray(photo_np)
    img.paste(photo_pil, (40, 90))
    draw.rectangle([(39, 89), (181, 271)], outline=(160, 150, 130), width=1)

    # Document Fields
    draw.text((210, 90), f"Passport No. / No du Passeport:\n{doc_num}", fill=(20, 20, 20))
    draw.text((210, 135), f"Surname / Nom:\n{surname}", fill=(20, 20, 20))
    draw.text((210, 180), f"Given Names / Prénoms:\n{given_name}", fill=(20, 20, 20))
    draw.text((210, 225), f"Nationality / Nationalité:\nINDIAN", fill=(20, 20, 20))

    draw.text((450, 90), "Date of Birth / Date de naissance:\n15/05/1990", fill=(20, 20, 20))
    draw.text((450, 135), "Sex / Sexe:\nM", fill=(20, 20, 20))
    draw.text((450, 180), "Date of Issue / Date de délivrance:\n01/01/2020", fill=(20, 20, 20))
    draw.text((450, 225), "Date of Expiry / Date d'expiration:\n31/12/2030", fill=(20, 20, 20))

    # Stamp overlay
    stamp_np = _draw_stamp(size=110, color=(190, 50, 50))
    stamp_pil = Image.fromarray(stamp_np)
    img.paste(stamp_pil, (540, 180), mask=stamp_pil.split()[3])

    # MRZ Zone at bottom
    draw.rectangle([(20, 380), (width - 20, 460)], fill=(238, 235, 225))
    line1 = f"P<IND{surname}<<{given_name}".ljust(44, "<")
    # doc check=1, dob check=6, exp check=3
    line2 = f"{doc_num}<1IND9005156M3012313<<<<<<<<<<<<<<0".ljust(44, "<")
    draw.text((35, 395), line1, fill=(10, 10, 10))
    draw.text((35, 425), line2, fill=(10, 10, 10))

    return img


def generate_all_samples():
    """Generate genuine and 3 categories of synthetic tampered documents."""
    manifest = {
        "dataset_name": "BorderGuard-AI Synthetic Tampered Dataset",
        "samples": [],
    }

    # 1. Genuine Baseline Document
    genuine_img = generate_baseline_passport("doc_001", "SINGH", "GURPREET", "A1234567", seed=101)
    genuine_path = OUTPUT_DIR / "doc_001_genuine.jpg"
    genuine_img.save(genuine_path, quality=95)
    manifest["samples"].append({
        "filename": "doc_001_genuine.jpg",
        "is_tampered": False,
        "tampering_type": "none",
        "details": "Clean genuine baseline passport scan",
    })

    # 2. Photo-Swap Tampered Document
    tampered_photo_img = generate_baseline_passport("doc_002", "SINGH", "GURPREET", "A1234567", seed=101)
    # Paste a completely different face with different noise/lighting onto the photo region
    different_face = _draw_mock_face(size=(140, 180), seed=999)
    # Add localized noise
    noise = np.random.normal(0, 15, different_face.shape).astype(np.uint8)
    different_face = cv2.add(different_face, noise)
    different_face_pil = Image.fromarray(different_face)
    tampered_photo_img.paste(different_face_pil, (40, 90))

    tampered_photo_path = OUTPUT_DIR / "doc_002_tampered_photoswap.jpg"
    tampered_photo_img.save(tampered_photo_path, quality=85)
    manifest["samples"].append({
        "filename": "doc_002_tampered_photoswap.jpg",
        "is_tampered": True,
        "tampering_type": "photo_swap",
        "tampered_region": {"x": 40, "y": 90, "w": 140, "h": 180},
        "details": "Substituted photo portrait with distinct noise profile and spliced boundary",
    })

    # 3. Text-Edit Tampered Document (Expiry date modified)
    tampered_text_img = generate_baseline_passport("doc_003", "SINGH", "GURPREET", "A1234567", seed=101)
    draw = ImageDraw.Draw(tampered_text_img)
    # White-out old date of expiry and overwrite with forged date
    draw.rectangle([(450, 240), (620, 260)], fill=(248, 245, 235))
    draw.text((450, 240), "31/12/2039", fill=(10, 10, 10))

    tampered_text_path = OUTPUT_DIR / "doc_003_tampered_textedit.jpg"
    # Resaving at quality 65 creates localized ELA artifact discrepancy
    tampered_text_img.save(tampered_text_path, quality=65)
    manifest["samples"].append({
        "filename": "doc_003_tampered_textedit.jpg",
        "is_tampered": True,
        "tampering_type": "text_edit",
        "tampered_region": {"x": 450, "y": 240, "w": 170, "h": 20},
        "details": "Date of expiry modified with altered compression artifacts",
    })

    # 4. Stamp Duplication Document
    stamp_dup_img = generate_baseline_passport("doc_004", "KUMAR", "RAJESH", "B9876543", seed=202)
    stamp_dup_path = OUTPUT_DIR / "doc_004_stamp_duplicate.jpg"
    stamp_dup_img.save(stamp_dup_path, quality=95)
    manifest["samples"].append({
        "filename": "doc_004_stamp_duplicate.jpg",
        "is_tampered": True,
        "tampering_type": "stamp_duplicate",
        "details": "Document with exact duplicate digital stamp impression from doc_001",
    })

    # Write manifest JSON
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(manifest['samples'])} synthetic samples into {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all_samples()
