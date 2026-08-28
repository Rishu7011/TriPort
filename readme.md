<div align="center">

# 🛡️ BorderGuard-AI

### *Next-Generation Autonomous Identity & Travel Document Verification System*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C.svg?logo=pytorch&logoColor=white)](https://pytorch.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Next.js](https://img.shields.io/badge/Next.js-14_App_Router-000000.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose_Ready-2496ED.svg?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  <b>High-precision, sub-second multimodal document screening, forensic tampering detection, biometric face clustering, and cryptographic audit ledgers for border checkpoints and immigration authorities.</b>
</p>

---

[Problem Overview](#-problem-overview) • [Key Features](#-key-features) • [System Architecture](#-system-architecture) • [Microservices](#-microservices-ecosystem) • [Security & Privacy](#-security--privacy)

---

</div>

## 📌 Problem Overview

Border control points handle thousands of complex identity and travel documents daily (Passports, Visas, National IDs, Permits). Human inspection faces severe challenges:
1. **Sophisticated Forgeries**: High-resolution image editing (Photoshop, face swapping, modified dates) invisible to the naked human eye.
2. **Global Language Barriers**: Non-standard regional scripts (Hindi, Chinese, Cyrillic, Arabic).
3. **Syndicate Multi-Identity Fraud**: The same criminal traveling under multiple distinct passports with different names and document numbers.
4. **Lack of Digital Evidentiary Trails**: Inability to mathematically prove tampering in legal/court proceedings.

**BorderGuard-AI** solves this with a **hybrid local-inference architecture** combining Optical Character Recognition, ICAO 9303 mathematical checksum verification, Computer Vision error-level forensics, vector biometrics, and immutable hash-chained ledgers.

---

## ⚡ Key Features

| Capability | Technical Mechanism | Benefit |
| :--- | :--- | :--- |
| **🔤 Multi-Zone OCR & MRZ Parsing** | EasyOCR + ICAO 9303 repeating `[7,3,1]` checksum engine | Extracts visual text & validates secret mathematical check digits on passports instantly. |
| **🔍 Forensic Tampering Detection** | Error Level Analysis (ELA) + Photo Boundary Edge Analysis | Generates thermal heatmaps highlighting edited JPEG compression artifacts & photo-swapping. |
| **👤 1:1 & 1:N Biometric Search** | DeepFace / Cosine Similarity + `pgvector` IVFFlat indexing | Verifies live traveler photo against document photo & detects duplicate faces across past passports. |
| **📋 Data-Driven Rules Engine** | Generic YAML business rule interpreter | Evaluates expiration, 6-month validity thresholds, format regexes & cross-document visa matching without code changes. |
| **🧠 Explainable Risk Engine** | Dynamic weighted scoring model (0–100) | Produces clear risk bands (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) with itemized human-readable reasons. |
| **🔗 Tamper-Evident Audit Ledger** | SHA-256 Hash-Chained sequential ledger | Cryptographically seals every scan, check, and officer decision into an immutable court-ready audit trail. |

---

## 🏗 System Architecture

```
                                  ┌──────────────────────────┐
                                  │   Next.js 14 Dashboard   │
                                  │    (Officer Interface)   │
                                  └─────────────┬────────────┘
                                                │ REST / Multipart
                                                ▼
                                  ┌──────────────────────────┐
                                  │   Orchestrator Gateway   │
                                  │     (FastAPI :8007)      │
                                  └─────────────┬────────────┘
                                                │
         ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
         │                  │                   │                   │                  │
         ▼                  ▼                   ▼                   ▼                  ▼
┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐
│   OCR Service   ││Validation Engine││Tampering Service││  Face Service   ││  Risk Engine    │
│  (:8001 / MRZ)  ││ (:8002 / YAML)  ││  (:8003 / ELA)  ││(:8004 / Vector) ││ (:8005 / Score) │
└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘
                                                │
                                                ▼
                                  ┌──────────────────────────┐
                                  │   Audit Ledger Engine    │
                                  │ (:8006 / SHA-256 Chain)  │
                                  └─────────────┬────────────┘
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
        ┌─────────────────────────────┐                   ┌─────────────────────────────┐
        │     PostgreSQL + pgvector   │                   │      MinIO Object Store     │
        │ (Documents, Embeddings, DB) │                   │  (Encrypted Scans, Heatmaps)│
        └─────────────────────────────┘                   └─────────────────────────────┘
```

---

## 📦 Microservices Ecosystem

All backend services run as isolated FastAPI microservices sharing a high-performance Python monorepo:

| Service | Port | Description | Core Libraries |
| :--- | :---: | :--- | :--- |
| **`ocr_service`** | `8001` | Reads text, parses MRZ lines, verifies ICAO check digits | `easyocr`, `Pillow`, `re`, `httpx` |
| **`validation_service`** | `8002` | Validates dates, formats, and cross-document validity | `PyYAML`, `pydantic` |
| **`tampering_service`** | `8003` | Generates ELA heatmaps, analyzes metadata and borders | `opencv-python`, `scikit-image`, `exifread` |
| **`face_service`** | `8004` | 1:1 face matching and 1:N duplicate cluster detection | `deepface`, `pgvector`, `numpy` |
| **`risk_engine`** | `8005` | Computes weighted risk score (0–100) and reasons | `pydantic` |
| **`audit_ledger`** | `8006` | Append-only sequential cryptographic hash chain | `hashlib`, `cryptography` |
| **`orchestrator`** | `8007` | Central pipeline coordination, auth, and database writes | `SQLAlchemy`, `asyncpg`, `alembic` |
| **`frontend`** | `3000` | Officer inspection dashboard and ledger explorer | `Next.js 14`, `TailwindCSS`, `shadcn/ui` |

---

## 🔒 Security & Privacy

* **Zero Cloud Lock-In**: Core inference runs 100% locally on-device without internet access.
* **Encrypted Storage**: Documents and extracted PII are secured at rest.
* **Immutable Audit Trail**: Sequential hashing prevents historical log tampering.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
