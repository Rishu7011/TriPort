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
    """Generate 5+ genuine and 5+ samples per tampering category (photo-swap, text-edit, stamp-duplicate)."""
    manifest = {
        "dataset_name": "BorderGuard-AI Synthetic Tampered Dataset (Expanded)",
        "samples": [],
    }

    identities = [
        ("SINGH", "GURPREET", "A1234567", 101, "15/05/1990", "31/12/2030"),
        ("KUMAR", "RAJESH", "B9876543", 202, "20/08/1985", "15/06/2029"),
        ("SHARMA", "PRIYA", "Z5544332", 303, "10/11/1992", "22/04/2031"),
        ("PATEL", "AMIT", "K4433221", 404, "05/03/1988", "10/10/2028"),
        ("VERMA", "NEHA", "M8877665", 505, "18/09/1995", "01/01/2032"),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Genuine Baseline Documents (5 samples)
    # ─────────────────────────────────────────────────────────────────────────
    for idx, (surname, given_name, doc_num, seed, dob, exp) in enumerate(identities, 1):
        filename = f"doc_{idx:03d}_genuine.jpg"
        img = generate_baseline_passport(f"doc_{idx:03d}", surname, given_name, doc_num, seed=seed)
        path = OUTPUT_DIR / filename
        # Vary quality slightly
        quality = 90 + (idx % 3) * 3
        img.save(path, quality=quality)
        manifest["samples"].append({
            "filename": filename,
            "is_tampered": False,
            "tampering_type": "none",
            "document_number": doc_num,
            "surname": surname,
            "given_name": given_name,
            "quality": quality,
            "details": f"Clean genuine baseline passport scan #{idx}",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Photo-Swap Tampered Documents (5 samples)
    # ─────────────────────────────────────────────────────────────────────────
    for idx, (surname, given_name, doc_num, seed, _, _) in enumerate(identities, 1):
        filename = f"doc_{idx+10:03d}_tampered_photoswap_{idx}.jpg"
        base_img = generate_baseline_passport(f"doc_{idx+10:03d}", surname, given_name, doc_num, seed=seed)
        
        # Vary face size, replacement seed, noise level, and splice region
        w_crop = 135 + (idx * 2)
        h_crop = 175 + (idx * 2)
        diff_face = _draw_mock_face(size=(w_crop, h_crop), seed=900 + idx * 37)
        
        # Add localized gaussian noise with varying variance
        noise_sigma = 12.0 + idx * 3.0
        noise = np.random.normal(0, noise_sigma, diff_face.shape).astype(np.float32)
        noisy_face = np.clip(diff_face.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        
        # Splice with distinct border artifact
        x_pos = 38 + (idx % 3)
        y_pos = 88 + (idx % 3)
        diff_face_pil = Image.fromarray(noisy_face)
        base_img.paste(diff_face_pil, (x_pos, y_pos))
        
        draw = ImageDraw.Draw(base_img)
        draw.rectangle([(x_pos - 1, y_pos - 1), (x_pos + w_crop, y_pos + h_crop)], outline=(190 + idx * 10, 140, 110), width=1)

        path = OUTPUT_DIR / filename
        quality = 80 + idx * 2
        base_img.save(path, quality=quality)
        manifest["samples"].append({
            "filename": filename,
            "is_tampered": True,
            "tampering_type": "photo_swap",
            "tampered_region": {"x": x_pos, "y": y_pos, "w": w_crop, "h": h_crop},
            "noise_sigma": noise_sigma,
            "quality": quality,
            "details": f"Substituted portrait #{idx} with noise sigma {noise_sigma} and boundary splice",
        })

    # Legacy alias for backward compatibility with fixture names
    legacy_photo = OUTPUT_DIR / "doc_002_tampered_photoswap.jpg"
    if (OUTPUT_DIR / "doc_011_tampered_photoswap_1.jpg").exists():
        Image.open(OUTPUT_DIR / "doc_011_tampered_photoswap_1.jpg").save(legacy_photo, quality=85)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Text-Edit Tampered Documents (5 samples, varying fields altered)
    # ─────────────────────────────────────────────────────────────────────────
    text_tamper_configs = [
        # (field_name, box, fake_text, quality)
        ("date_of_expiry", [(450, 240), (620, 260)], "31/12/2039", 65),
        ("date_of_birth", [(450, 105), (620, 125)], "01/01/2005", 70),
        ("passport_number", [(210, 105), (380, 125)], "X9988776", 60),
        ("surname", [(210, 150), (380, 170)], "FORGERY", 75),
        ("nationality", [(210, 240), (380, 260)], "CANADIAN", 62),
    ]

    for idx, (field_name, box, fake_text, quality) in enumerate(text_tamper_configs, 1):
        filename = f"doc_{idx+20:03d}_tampered_textedit_{idx}.jpg"
        surname, given_name, doc_num, seed, _, _ = identities[idx - 1]
        base_img = generate_baseline_passport(f"doc_{idx+20:03d}", surname, given_name, doc_num, seed=seed)
        
        draw = ImageDraw.Draw(base_img)
        # White-out region with slight tone mismatch to trigger ELA
        draw.rectangle(box, fill=(244, 241, 230))
        draw.text((box[0][0] + 2, box[0][1] + 1), fake_text, fill=(5, 5, 5))

        path = OUTPUT_DIR / filename
        base_img.save(path, quality=quality)
        manifest["samples"].append({
            "filename": filename,
            "is_tampered": True,
            "tampering_type": "text_edit",
            "altered_field": field_name,
            "forged_value": fake_text,
            "tampered_region": {
                "x": box[0][0],
                "y": box[0][1],
                "w": box[1][0] - box[0][0],
                "h": box[1][1] - box[0][1],
            },
            "quality": quality,
            "details": f"Altered field {field_name} -> {fake_text} saved at JPEG quality {quality}",
        })

    # Legacy alias for backward compatibility
    legacy_text = OUTPUT_DIR / "doc_003_tampered_textedit.jpg"
    if (OUTPUT_DIR / "doc_021_tampered_textedit_1.jpg").exists():
        Image.open(OUTPUT_DIR / "doc_021_tampered_textedit_1.jpg").save(legacy_text, quality=65)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Stamp Duplication Documents (5 samples)
    # ─────────────────────────────────────────────────────────────────────────
    for idx in range(1, 6):
        filename = f"doc_{idx+30:03d}_stamp_duplicate_{idx}.jpg"
        surname, given_name, doc_num, seed, _, _ = identities[idx - 1]
        # Uses exact duplicate stamp impression from baseline
        base_img = generate_baseline_passport(f"doc_{idx+30:03d}", surname, given_name, doc_num, seed=seed)
        
        path = OUTPUT_DIR / filename
        quality = 92 + (idx % 2) * 3
        base_img.save(path, quality=quality)
        manifest["samples"].append({
            "filename": filename,
            "is_tampered": True,
            "tampering_type": "stamp_duplicate",
            "source_stamp_reference": "doc_001_genuine.jpg",
            "quality": quality,
            "details": f"Document #{idx} using identical reused digital stamp impression",
        })

    # Legacy alias for backward compatibility
    legacy_stamp = OUTPUT_DIR / "doc_004_stamp_duplicate.jpg"
    if (OUTPUT_DIR / "doc_031_stamp_duplicate_1.jpg").exists():
        Image.open(OUTPUT_DIR / "doc_031_stamp_duplicate_1.jpg").save(legacy_stamp, quality=95)

    # Write manifest JSON
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅ Generated {len(manifest['samples'])} synthetic samples into {OUTPUT_DIR}")
    print(f"   - Genuine: 5 samples")
    print(f"   - Photo-swap: 5 samples")
    print(f"   - Text-edit: 5 samples")
    print(f"   - Stamp-duplicate: 5 samples")


if __name__ == "__main__":
    generate_all_samples()
