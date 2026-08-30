<div align="center">

# 🌐 TriPort
### *AI-Based Fake Identity & Document Screening System for Border Checkpoints*
**Airport • Land Port • Sea Port (Passenger)**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C.svg?logo=pytorch&logoColor=white)](https://pytorch.org)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-3.5_Flash_Vision-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Next.js](https://img.shields.io/badge/Next.js-14_App_Router-000000.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose_Ready-2496ED.svg?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  <b>Sub-second multimodal document extraction, forensic tampering detection (ELA), biometric 1:1/1:N face clustering, and cryptographically verifiable SHA-256 audit ledgers for high-throughput border control and immigration authorities.</b>
</p>

---

[Problem Statement](#-problem-statement) • [Checkpoint Domains](#-three-checkpoint-domains) • [System Architecture](#-system-architecture) • [6 Core Modules](#-the-6-core-modules) • [Microservices Ecosystem](#-microservices-ecosystem) • [Quick Start](#-quick-start)

---

</div>

## 📌 Problem Statement

Border checkpoints process thousands of identity and travel documents daily — **Passports, Visas, National IDs (Aadhaar/Citizen Cards), Driving Licenses, and Land Border Crossing Permits**. Manual inspection is slow, error-prone, and struggles against sophisticated modern fraud:

* **High-Precision Forgeries**: Digital manipulation (photoshop editing, modified birth/expiry dates, altered visa stamps).
* **Identity Impersonation & Photo Swapping**: Physical or digital face replacement on genuine documents.
* **Syndicate Multi-Identity Fraud**: The same individual crossing borders under multiple synthetic identities.
* **Infrastructure Disparity**: Current trusted traveler programs (such as India's FTI-TTP) only cover select airports for pre-vetted citizens. No automated screening exists for **Land Ports** (bus/vehicle crossings) or **Sea Ports** (passenger terminals).
* **Evidentiary Gaps**: Inability to mathematically prove tampering or audit decisions in legal/court proceedings.

**TriPort** solves this with a unified, high-performance edge/cloud architecture combining deep learning OCR, ICAO 9303 checksum mathematics, computer vision forensics, vector biometrics, and immutable hash-chained audit ledgers.

---

## 🗺️ Three Checkpoint Domains

| Checkpoint Domain | Typical Traveler Profile | Primary Documents | Operational Environment |
| :--- | :--- | :--- | :--- |
| ✈️ **Airport** | Pre-vetted + international travelers | Passports, Visas, Boarding Passes | Fixed infrastructure, controlled lighting, high connectivity |
| 🚗 **Land Port** | Walk-in travelers, bulk bus arrivals | Passports, National IDs (Aadhaar), Border Permits, Driving Licenses | Variable lighting, bulk queues, low/moderate connectivity |
| 🚢 **Sea Port** | Passenger ferries, cruise travelers | Passports, Visas, National IDs | Bulk disembarkation, dockside conditions |

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
│  (:8001 / MRZ)  ││ (:8002 / Rules) ││  (:8003 / ELA)  ││(:8004 / Vector) ││ (:8005 / Score) │
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

## ⚙️ The 6 Core Modules

### 1. 🔤 Multi-Modal OCR & Document Classification (`ocr_service` — Port 8001)
* **Dynamic Classifier**: Auto-identifies document type (`passport`, `visa`, `national_id`, `driving_license`, `permit`) in <50ms.
* **Dual Inference Engines**:
  * **Local Engine**: Offline EasyOCR with CRNN neural text detection + ICAO 9303 `[7,3,1]` mathematical checksum verification and OCR error auto-correction (TD1, TD2, TD3).
  * **Cloud Vision API**: Google Gemini 3.5 Flash-Lite multimodal extraction with optimized payload compression (<2.5s end-to-end latency).
* **Multi-Format Ingestion**: Supports JPEG, PNG, TIFF, and native multi-page PDF documents via PyMuPDF rendering.
* **Concurrent Queue Worker**: Fault-isolated batch processing for multi-passenger queue bursts.

### 2. 📋 Cross-Field Validation & Consistency Rules (`validation_service` — Port 8002)
* **MRZ vs VIZ Cross-Validation**: Catches name, date, and document number discrepancies between the visual zone and machine-readable zone.
* **Chronological Validity Checks**: Validates expiration dates, 6-month validity rules, issuing dates, and age sanity (e.g., adult vs minor).
* **Watchlist & Blacklist Matching**: Instant in-memory and database screening against stolen document registries and INTERPOL alert lists.

### 3. 🔍 Forensic Tampering Detection (`tampering_service` — Port 8003)
* **Error Level Analysis (ELA)**: Detects compression rate differences across JPEG blocks, highlighting Photoshop edits and digital splices as glowing heatmaps.
* **Photo Boundary & Edge Forensics**: Analyzes Laplacian gradient discontinuities around photo borders to identify glued or swapped headshots.
* **Metadata & Copy-Move Forensics**: Scans EXIF structures for editing software signatures and detects cloned text/stamp regions.

### 4. 👤 Biometric Face Matching & Clustering (`face_service` — Port 8004)
* **1:1 Live-to-Document Verification**: Compares live checkpoint webcam capture against the photo extracted from the travel document (Cosine distance < 0.40 threshold).
* **1:N Syndicate & Duplicate Detection**: Uses 512-d embeddings indexed with PostgreSQL `pgvector` (IVFFlat) to detect if the same face has traveled under different names or synthetic IDs.

### 5. 🧠 Explainable Risk Engine (`risk_engine` — Port 8005)
* **Dynamic Weighted Scoring (0–100)**: Evaluates signals from OCR, Validation, Tampering, and Biometrics into a composite risk score.
* **Risk Categorization**:
  * 🟢 **LOW (0–29)**: Normal processing. Fast-track automated gate clearance.
  * 🟡 **MEDIUM (30–59)**: Minor discrepancy (e.g., near-expiry document). Secondary officer check.
  * 🟠 **HIGH (60–79)**: Significant anomaly (e.g., ELA tampering hotspot or watchlist flag). Mandatory physical inspection.
  * 🔴 **CRITICAL (80–100)**: Definitive fraud (e.g., failed ICAO checksum, photo-swap detected, blacklisted ID). Immediate supervisor intercept.
* **Officer Explainability**: Generates clear, itemized human-readable reasons for every alert.

### 6. 🔗 Tamper-Evident SHA-256 Audit Ledger (`audit_ledger` — Port 8006)
* **Cryptographic Hash Chaining**: Every verification event, biometric match, and officer disposition is appended to a sequentially chained SHA-256 ledger (`Block_N = Hash(Block_{N-1} || EventData)`).
* **Court-Ready Evidentiary Integrity**: Enables mathematically proving that historical records have never been altered or deleted.

---

## 📦 Microservices Ecosystem

All backend services run as isolated FastAPI microservices sharing a high-performance Python monorepo:

| Service | Port | Primary Purpose | Core Libraries |
| :--- | :---: | :--- | :--- |
| **`ocr_service`** | `8001` | Document classification, MRZ parsing, Gemini Vision API | `easyocr`, `Pillow`, `httpx`, `PyMuPDF` |
| **`validation_service`** | `8002` | Cross-field consistency, date chronology, blacklist checks | `pydantic`, `PyYAML`, `fastapi` |
| **`tampering_service`** | `8003` | Error Level Analysis (ELA), edge analysis, clone detection | `opencv-python`, `scikit-image`, `numpy` |
| **`face_service`** | `8004` | 1:1 face matching, 1:N duplicate detection via pgvector | `deepface`, `pgvector`, `torch` |
| **`risk_engine`** | `8005` | Composite 0–100 risk scoring with explainability rules | `pydantic`, `fastapi` |
| **`audit_ledger`** | `8006` | Append-only sequential SHA-256 cryptographic hash chain | `hashlib`, `cryptography` |
| **`orchestrator`** | `8007` | Central pipeline coordination, auth, and database writes | `SQLAlchemy`, `asyncpg`, `alembic` |
| **`frontend`** | `3000` | Officer inspection dashboard and ledger explorer | `Next.js 14`, `TailwindCSS`, `Lucide` |

---

## 🚀 Quick Start

### 1. Clone & Environment Setup
```bash
git clone https://github.com/Rishu7011/BorderGuard-AI.git
cd BorderGuard-AI

# Create virtual environment
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and configure your Google Gemini API Key:
# LLM_API_KEY=your_gemini_api_key_here
```

### 3. Run Microservices (e.g. OCR Service)
```bash
backend/.venv/bin/uvicorn backend.ocr_service.main:app --port 8001 --reload
```
Interactive Swagger API documentation will be available at: **`http://localhost:8001/docs`**

### 4. Run Test Suite
```bash
cd backend
.venv/bin/pytest tests/ -v
```

---

## 🔒 Security & Privacy

* **Edge Inference First**: Core OCR and forensics can execute 100% locally on-device without internet access.
* **Data Encryption**: All PII and scanned images are encrypted at rest with AES-256.
* **Cryptographic Verification**: Tamper-proof audit logs guarantee chain of custody.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
