<div align="center">

# 🌐 🛡️ TriPort
### *Next-Generation Autonomous Border Screening & Multi-Modal Identity Verification Platform*
**✈️ Airports • 🚗 Land Borders • 🚢 Passenger Seaports**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph_DAG-FF6F00.svg?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Next.js 15](https://img.shields.io/badge/Frontend-Next.js_15_Turbopack-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![AWS Rekognition](https://img.shields.io/badge/Biometrics-AWS_Rekognition_&_ArcFace-FF9900.svg?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/rekognition/)
[![Supabase](https://img.shields.io/badge/Cloud_Database-Supabase_PostgreSQL_+_pgvector-3ECF8E.svg?logo=supabase&logoColor=white)](https://supabase.com)
[![Google Stitch](https://img.shields.io/badge/Design-Google_Stitch_Tactical_HUD-C0F500.svg?logo=google&logoColor=black)](https://stitch.withgoogle.com)
[![Cryptography](https://img.shields.io/badge/Security-SHA--256_HashChain_&_AES--256-107C41.svg?logo=gnupg&logoColor=white)](https://cryptography.io)
[![Tests](https://img.shields.io/badge/Pytest-196_Passed_100%25-brightgreen.svg?logo=pytest&logoColor=white)](backend/tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  <b>⚡ Sub-second multi-modal OCR • 🔬 5-Layer ELA pixel forensics • 👤 AWS Rekognition biometric matching • 🌐 Cross-checkpoint impossible-velocity face graphs • ⚖️ Automated clearance with zero human friction • 🔗 Immutable SHA-256 cryptographic audit ledger.</b>
</p>

---

[🌟 Executive Overview](#-executive-overview) • [✨ Key Capabilities](#-key-capabilities) • [🖥️ Tactical Screening Console Flow](#️-tactical-screening-console-flow) • [🏗️ System Architecture](#️-system-architecture) • [⚡ LangGraph Orchestration DAG](#-langgraph-orchestration-dag) • [📦 Core Microservices](#-core-microservices) • [🎯 Explainable Risk Engine](#-explainable-risk-engine-0100) • [🧪 Test Suite](#-test-suite--verification) • [🚀 Quick Start](#-quick-start)

---

</div>

## 📌 Executive Overview

Modern border security checkpoints process tens of thousands of travelers daily under intense operational pressure. Officers typically have an unforgiving **5 to 8 second inspection window** to detect increasingly sophisticated fraud:

* 🎭 **Digital Forgery & Splicing:** Laser-printed counterfeits, swapped photo pages, altered birth dates, and forged visas on authentic booklets.
* 👥 **Syndicate Identity Swapping:** The same bad actor presenting different names, passports, and national IDs across separate checkpoints.
* ⚡ **High Queue Congestion:** Manual human inspection creates massive bottleneck delays at high-throughput airport terminals and land borders.
* ⚖️ **Evidentiary Gaps:** Difficulty in providing mathematically tamper-proof audit trails for intercepted criminals in judicial proceedings.

**TriPort** solves this with a **Google Stitch Tactical HUD**, powered by an autonomous **LangGraph multi-agent pipeline**. It screens travelers in **~2 seconds**, detects pixel-level forgeries, compares live facial biometrics against encrypted chip photos, cross-references regional travel graphs for impossible velocity, and commits every decision to an append-only **SHA-256 cryptographic hash-chained ledger**.

---

## ✨ Key Capabilities

### ⚡ 1. Ultra-Fast Parallelized Screening Engine
* 🏎️ **Concurrent Fan-Out:** Dispatches OCR character extraction, Error Level Analysis (ELA), EXIF structure parsing, and facial embedding extraction in parallel.
* 🤖 **Gemini Multimodal LLM Fallback:** Low-contrast scans, torn corners, or complex non-ICAO documents automatically trigger **Google Gemini Flash Vision** to extract full entity trees without officer intervention.

### 🔬 2. Five-Layer Forensic Tampering Detection
* 🔍 **Error Level Analysis (ELA):** Identifies differences in JPEG compression ratios to expose digitally pasted portraits, modified text, and erased watermarks.
* 🖼️ **Boundary & Sobel Discontinuity:** Detects photo border splicing, unnatural noise gradients, and synthetic edges around portrait zones.
* 📜 **EXIF & Software Signatures:** Scans for traces of manipulation software (*Photoshop, GIMP, Snapseed*) embedded within file headers.
* 🏷️ **Entry/Exit Stamp Perceptual Hash (dHash):** Matches travel stamps against authorized border control matrices.

### 👤 3. Dual-Engine Biometrics & Automated Clearance
* 👁️ **AWS Rekognition CompareFaces & ArcFace 512-d:** Precision 1:1 matching between live checkpoint video capture and extracted eMRTD document portraits ($90\%$ threshold).
* 🚀 **Automated Biometric Clearance (No Human Verification Needed):** When a live traveler matches the document photo, the system grants **Instant Automated Clearance** with an automated 3-second auto-clear timer—eliminating unnecessary human verification friction!
* ⚠️ **Human Verification Escalation:** When a biometric discrepancy occurs, the console alerts **`HUMAN VERIFICATION REQUIRED`**, locking the flow until an officer conducts an in-person physical inspection and logs signed audit notes.

### 🌐 4. Cross-Checkpoint Face Graph & Velocity Tracking
* 🧠 **`pgvector` 1:N Facial Deduplication:** High-dimensional vector indexing in PostgreSQL identifies whether a traveler’s face has ever been sighted under an alias name or alternate document number.
* ⏱️ **Impossible Travel Velocity:** Flags sightings of the same individual across geographically distant border gates within physically impossible transit windows ($< 2$ hours).
* 🚨 **Repeat Offender Auto-Escalation:** Dynamically increases threat tiers by $+1$ band for individuals linked to prior border violations.

### 📜 5. Multi-Document & Regional Compatibility
* 🛂 **International Passports:** Full ICAO 9303 dual-zone cross-verification (**VIZ OCR vs. MRZ check digits** with `[7,3,1]` mathematical validation).
* 🪪 **Indian Voter ID (EPIC):** Full-system integration for Election Commission voter identity cards (`TGI8262487`), bilingual Hindi/English label parsing (`मतदाता का नाम`), and regional series validation.
* 🆔 **National ID & Aadhaar:** 12-digit Aadhaar Verhoeff checksum validation and date-of-birth chronology checks.
* 🚗 **Driving Licenses & Visas:** State authority format parsing, vehicle class validation, visa entry quotas, and permit validity windows.

### 🔒 6. Cryptographic SHA-256 Audit Ledger
* ⛓️ **Sequential Block Chaining:** `Block[N] = SHA256(Payload[N] || PrevHash || Timestamp)`.
* 🛡️ **Mathematically Provable Immutability:** Any retroactive modification to historical screening logs breaks the cryptographic chain immediately.
* 🗄️ **Supabase Cloud Storage:** Stores document scans and live selfie frames with secure signed URLs and zero PII leakage.

---

## 🖥️ Tactical Screening Console Flow

Built with the **Google Stitch Design System**, the screening console delivers a sleek, high-contrast, tactical cyber-command interface styled with acid lime accents (`#C0F500`), tactical reticles, and monospaced typography:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE TRIPORT WORKFLOW                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
       1. UPLOAD & DISPATCH        ▶       2. FORENSIC AUDIT RESULTS
   Select Document (Passport, Voter ID,     50/50 Split: Extracted Entity Data &
   Aadhaar, License) + Checkpoint Station   Dual-Zone Passport OCR vs MRZ Cross-Check
   + Instant File Preview                   + 280px High-Contrast Visual Scans
                                                           │
                                                           ▼
       4. IMMUTABLE CONFIRMATION   ◀       3. BIOMETRIC VERIFICATION
   Authorized Entry Badge + SHA-256 Ledger  Live Webcam Viewfinder + AWS Rekognition
   Sequence Hash + Next Traveler Dispatch   Match + AUTOMATED CLEARANCE (No Human
                                            Verification Needed on Recognized Match!)
```

### 📸 Screen 1: Document Upload & Checkpoint Dispatcher
* **Document Type Selector:** Real-time multi-document selection (`Passport`, `National ID / Aadhaar`, `Driving License`, `Voter ID / EPIC`, `Visa`, `Permit`).
* **Checkpoint Station Selector:** Configurable between `Airport Terminal`, `Land Border Gate`, and `Passenger Seaport`.
* **Immediate Local Visual Confirmation:** Shows the uploaded card instantly on screen so officers can confirm readability before cloud submission.

### 🔬 Screen 2: Deep Forensic Results (50/50 Balanced Split)
* **Passport Dual-Zone Cross-Verification:** Specialized 5-column table directly cross-referencing visual text (**VIZ OCR**) against the machine-readable lines (**ICAO 9303 MRZ**) with real-time `✔ MATCH` or `✖ MISMATCH` alerts.
* **Compact Visual Confidence Meters:** Subtle, unobtrusive confidence bars that highlight OCR clarity without dominating the screen.
* **Universal Multi-Document Suspicious Advisory Box:** When any document is flagged, a prominent tactical advisory details the exact failure reasons (ICAO formats, 12-digit Aadhaar Verhoeff, EPIC format, DOB conflicts, or ELA tampering scores) with clear officer action guidance.
* **Dual 280px Visual Scans:** High-contrast document scan viewer and extracted biometric chip photo with tactical corner reticles.
* **Four Security Feature Engines:** MRZ Checksum, ELA Pixel Forensics, Boundary & EXIF Analysis, and Rules Integrity.

### 👤 Screen 3: Dual-Source Live Biometric Verification
* **Dual-Source View:** Source A (Document eMRTD Portrait) vs. Source B (Live Camera Stream with alignment oval).
* **AWS Rekognition Score Meter:** Dynamic comparison evaluated against the official $90.0\%$ threshold.
* **Automated Clearance When Recognized:** Displays **`FACE RECOGNIZED • NO HUMAN VERIFICATION REQUIRED`** with an automated 3-second countdown to clear the traveler directly.
* **Human Verification Required Mode:** Discrepancies alert **`HUMAN VERIFICATION REQUIRED`**, enforcing manual inspection and signed override notes.

### 🛡️ Screen 4: Cryptographic Decision Confirmation
* **Clearance Seal:** High-contrast animated entry approval seal (`ENTRY APPROVED` or `ENTRY REJECTED`).
* **Traveler Summary:** Full name, document UUID, assigned checkpoint, UTC timestamp, and final risk band.
* **Ledger Hash Sequence:** Cryptographic proof logged permanently into the SHA-256 ledger.

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │          💻 Next.js 15 Tactical Console UI             │
                                  │    (Google Stitch HUD • Camera Viewfinder • Alerts)    │
                                  └───────────────────────────┬────────────────────────────┘
                                                              │ REST / Multipart Upload
                                                              ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │         ⚡ Orchestrator Gateway (FastAPI :8000)        │
                                  │       (LangGraph StateGraph DAG • Auth • Routing)      │
                                  └─────┬──────────────┬──────────────┬──────────────┬─────┘
                                        │              │              │              │
              ┌─────────────────────────┼──────────────┼──────────────┼──────────────┴────────────────────────┐
              ▼                         ▼              ▼              ▼                                       ▼
  ┌───────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐ ┌────────────────────────┐
  │     OCR Service       │ │  Tampering Service   │ │     Face Service     │ │   Validation Service   │ │Cross-Checkpoint Service│
  │     (Port :8001)      │ │     (Port :8003)     │ │     (Port :8004)     │ │      (Port :8002)      │ │      (Port :8008)      │
  │ • EasyOCR Engine      │ │ • Error Level (ELA)  │ │ • AWS Rekognition    │ │ • YAML Rules Engine  │ │ • Face Graph Clusters  │
  │ • ICAO MRZ Checksums  │ │ • EXIF Metadata      │ │ • ArcFace 512d Vector│ │ • Regional Rules (6) │ │ • Impossible Velocity  │
  │ • Gemini Flash Vision │ │ • Sobel Boundary     │ │ • pgvector 1:N Dedup │ │ • Voter ID / Aadhaar │ │ • Repeat Offender Band │
  │ • Multilingual Parser │ │ • Stamp dHash Match  │ │ • Liveness Detection │ │ • SLTD Watchlists    │ │ • Sybil Ring Detector  │
  └───────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘ └───────────┬────────────┘ └───────────┬────────────┘
              │                        │                        │                         │                          │
              └────────────────────────┴───────────────┬────────┴─────────────────────────┴──────────────────────────┘
                                                       ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │          🧠 Explainable Risk Engine (Port :8005)       │
                                  │  (Dynamic Composite Formula 0-100 • Explainable Bands) │
                                  └───────────────────────────┬────────────────────────────┘
                                                              │
                                                              ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │          🔗 SHA-256 Audit Ledger (Port :8006)          │
                                  │   (Tamper-Evident Hash Chaining • Zero Mutation Proof) │
                                  └───────────────────────────┬────────────────────────────┘
                                                              │
                                  ┌───────────────────────────┴────────────────────────────┐
                                  ▼                                                        ▼
                    ┌───────────────────────────┐                            ┌───────────────────────────┐
                    │   Supabase PostgreSQL     │                            │     Supabase Storage      │
                    │ (pgvector, Docs, Clusters)│                            │(Signed URLs for JPG Scans)│
                    └───────────────────────────┘                            └───────────────────────────┘
```

---

## ⚡ LangGraph Orchestration DAG

The screening workflow is modeled as an autonomous **LangGraph StateGraph**:

```mermaid
graph TD
    START([📄 Document Uploaded]) --> FANOUT{⚡ Parallel Fan-Out}

    FANOUT -->|Async Task| S3[Supabase Storage Signed Upload]
    FANOUT -->|Async Task| OCR[OCR Service & ICAO MRZ Parser]
    FANOUT -->|Async Task| TAMP[5-Layer Tampering Forensics]
    FANOUT -->|Async Task| FACE[Face Service & pgvector 1:N Dedup]

    OCR --> COND_OCR{"OCR Conf < 0.60 or Complex?"}
    COND_OCR -->|Yes| LLM[🤖 Google Gemini Flash Vision]
    COND_OCR -->|No / Clean| VAL[📜 Validation Rules Engine]
    LLM --> VAL

    OCR --> BL[🚨 Interpol SLTD & Watchlists]
    FACE --> CC[🌐 Cross-Checkpoint Face Graph]

    VAL --> FANIN{🔄 Fan-In Aggregate}
    BL --> FANIN
    TAMP --> FANIN
    CC --> FANIN
    S3 --> FANIN

    FANIN --> RISK[🎯 Composite Risk Scoring 0-100]

    RISK --> COND_THREAT{"Risk >= 61 or Watchlist Hit?"}
    COND_THREAT -->|Yes| SECONDARY[⚠️ Secondary Inspection Queue]
    COND_THREAT -->|No| CLEAR[✅ Standard Clearance]

    SECONDARY --> AUDIT[🔗 SHA-256 Audit Ledger Commit]
    CLEAR --> AUDIT
    AUDIT --> DB_PERSIST[(💾 PostgreSQL State Commit)]
    DB_PERSIST --> END([🏁 Complete & Dispatched])
```

---

## 📦 Core Microservices

| Service | Port | Responsibilities | Core Technologies |
| :--- | :---: | :--- | :--- |
| **`orchestrator`** | `8000` | LangGraph DAG pipeline coordination, Supabase DB pooling, auth, and routing | `LangGraph`, `FastAPI`, `SQLAlchemy`, `psycopg3` |
| **`ocr_service`** | `8001` | Multi-document OCR, ICAO-9303 MRZ parser, Gemini Flash LLM vision fallback | `EasyOCR`, `google-generativeai`, `Pillow`, `PyTorch` |
| **`validation_service`** | `8002` | YAML business rules (Passports, Voter ID, Aadhaar, License, Visas, Permits) | `PyYAML`, `pydantic`, `SQLAlchemy` |
| **`tampering_service`** | `8003` | Error Level Analysis (ELA), EXIF structure, Sobel boundary noise, stamp dHash | `opencv-python`, `scikit-image`, `numpy` |
| **`face_service`** | `8004` | AWS Rekognition CompareFaces, ArcFace 512d vectors, pgvector 1:N deduplication | `boto3` (AWS), `InsightFace`, `MediaPipe`, `pgvector` |
| **`cross_checkpoint_service`**| `8008`| Multi-identity cluster intelligence, name mismatch, impossible travel velocity | `FastAPI`, `networkx`, `pydantic` |
| **`risk_engine`** | `8005` | Dynamic weighted composite risk scoring (0 to 100) with explainable reasons | `pydantic`, `FastAPI` |
| **`audit_ledger`** | `8006` | Sequential SHA-256 hash chaining, AES-256-GCM encryption, integrity CLI | `cryptography`, `hashlib`, `SQLAlchemy` |

---

## 🎯 Explainable Risk Engine (0–100)

Composite risk is computed from dynamic weighted subscores and mapped to operational clearance bands:

$$\text{Risk Score} = (w_{\text{val}} \times S_{\text{val}}) + (w_{\text{tamper}} \times S_{\text{tamper}}) + (w_{\text{face}} \times S_{\text{face}}) + (w_{\text{blacklist}} \times S_{\text{blacklist}}) + (w_{\text{graph}} \times S_{\text{graph}})$$

| Risk Tier | Score Range | Operational Protocol |
| :--- | :---: | :--- |
| 🟢 **LOW** | `0.0 – 30.0` | **Standard Clearance:** Automated passage. |
| 🟡 **MEDIUM** | `31.0 – 60.0` | **Officer Review:** Inspect near-expiry documents or regional visa requirements. |
| 🟠 **HIGH** | `61.0 – 80.0` | **Secondary Inspection:** Supervisor forensic inspection for potential tampering. |
| 🔴 **CRITICAL** | `81.0 – 100.0` | **Immediate Intercept:** Watchlist hit, ICAO checksum failure, photo splice, or repeat offender. |

---

## 🧪 Test Suite & Verification

TriPort includes a comprehensive suite of **196 automated tests** covering all phases:

```bash
cd backend
.venv/bin/pytest tests/ -v
```

```
================================================================================
TOTAL BACKEND TESTS: 196 PASSED | 0 FAILED | 0 ERRORS in 65.29s (100%)
================================================================================
✓ Phase 1 & 2: OCR classification, EasyOCR, MRZ parsing & batch queues (46 tests)
✓ Phase 3: YAML rules, regional rules & SLTD database checks (38 tests)
✓ Phase 4: ELA heatmaps, EXIF metadata, boundary Sobel & stamp dHash (37 tests)
✓ Phase 5: ArcFace embeddings, 1:1 match, EAR liveness & pgvector dedup (36 tests)
✓ Phase 6: Face graph, name mismatch, impossible travel & repeat offenders (15 tests)
✓ Phase 7: LangGraph StateGraph, conditional routing, SHA-256 audit ledger (12 tests)
✓ API Integration & End-to-End Chains (12 tests)
```

---

## 🚀 Quick Start

### 1. Prerequisites
* **Python 3.11+**
* **Node.js 18+** / **Bun**
* **Supabase Project** (PostgreSQL with `pgvector` & Storage enabled)

### 2. Clone & Environment Setup
```bash
# Clone the repository
git clone https://github.com/Rishu7011/TriPort.git
cd TriPort

# Setup Python virtual environment
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-core.txt -r backend/requirements-ml.txt
```

### 3. Configure Environment Variables

**Backend (`backend/.env`):**
```env
DATABASE_URL=postgresql+psycopg://postgres.[REF]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL=https://[REF].supabase.co
SUPABASE_SERVICE_ROLE_KEY=[YOUR_KEY]
AWS_ACCESS_KEY_ID=[YOUR_AWS_KEY]
AWS_SECRET_ACCESS_KEY=[YOUR_AWS_SECRET]
AWS_REGION=ap-south-1
FACE_VERIFICATION_PROVIDER=aws
GEMINI_API_KEY=[YOUR_GEMINI_KEY]
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://[REF].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=[YOUR_ANON_KEY]
```

### 4. Launch Backend Orchestrator
```bash
cd backend
source .venv/bin/activate
uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Swagger OpenAPI Docs:** `http://localhost:8000/docs`

### 5. Launch Tactical Frontend Console
```bash
cd frontend
bun install   # or npm install
bun run dev   # or npm run dev
```
* **Officer Screening Console:** `http://localhost:3000`
* **Command Governance Hub:** `http://localhost:3000/command`
* **Audit Ledger Verification:** `http://localhost:3000/audit`

### 6. Verify Ledger Cryptographic Integrity
Run the standalone CLI tool to prove mathematical zero-mutation hash chaining:
```bash
python scripts/verify_ledger_integrity.py

# Simulate a simulated tampering attack and confirm detection:
python scripts/verify_ledger_integrity.py --corrupt-test
```

---

## 🔒 Security & Compliance

* 🛡️ **Zero-Trust Storage:** All sensitive document scans are stored in private Supabase Storage buckets accessible only via ephemeral, short-lived signed URLs.
* 🔐 **Cryptographic Immutability:** Audit records are cryptographically bound via SHA-256 hash chains, providing legally defensible evidence in court.
* 👥 **Role-Based Access Control (RBAC):** Distinct cryptographic JWT scopes for `officer`, `supervisor`, and `auditor`.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

<div align="center">
  <sub>Built for border security officers safeguarding international crossings worldwide. 🌐✈️</sub>
</div>
