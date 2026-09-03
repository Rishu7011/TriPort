<div align="center">

# 🌐 🛡️ TriPort
### *Autonomous Multi-Modal Document Screening & Biometric Identity Verification Platform*
**✈️ Airports • 🚗 Land Borders • 🚢 Passenger Seaports**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph_DAG-FF6F00.svg?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Next.js 16](https://img.shields.io/badge/Frontend-Next.js_16_Turbopack-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![AWS Rekognition](https://img.shields.io/badge/Biometrics-AWS_Rekognition_&_ArcFace-FF9900.svg?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/rekognition/)
[![Supabase](https://img.shields.io/badge/Cloud_Database-Supabase_PostgreSQL_+_pgvector-3ECF8E.svg?logo=supabase&logoColor=white)](https://supabase.com)
[![Google Stitch](https://img.shields.io/badge/Design-Google_Stitch_Tactical_HUD-C0F500.svg?logo=google&logoColor=black)](https://stitch.withgoogle.com)
[![Cryptography](https://img.shields.io/badge/Security-SHA--256_HashChain_&_AES--256-107C41.svg?logo=gnupg&logoColor=white)](https://cryptography.io)
[![Tests](https://img.shields.io/badge/Pytest-196_Passed_100%25-brightgreen.svg?logo=pytest&logoColor=white)](backend/tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  <b>⚡ Sub-second multi-modal OCR • 🔬 5-Layer forensic tampering (ELA) • 👤 Hybrid AWS Rekognition & InsightFace ArcFace biometrics • 🌐 Cross-checkpoint impossible-velocity face graphs • ⚖️ Automated frictionless clearance • 🔗 Immutable SHA-256 cryptographic audit ledger.</b>
</p>

---

[🌟 Executive Overview](#-executive-overview) • [✨ Key Capabilities](#-key-capabilities) • [👤 Hybrid Biometric Architecture](#-hybrid-biometric-architecture-aws--insightface) • [🖥️ Tactical Screening Console Flow](#️-tactical-screening-console-flow) • [📜 Multi-Document Forensic Engine](#-multi-document-forensic-engine) • [🏗️ System Architecture](#️-system-architecture) • [⚡ LangGraph Orchestration DAG](#-langgraph-orchestration-dag) • [📦 Unified Microservices](#-unified-microservices) • [🎯 Explainable Risk Engine](#-explainable-risk-engine-0100) • [🧪 Test Suite](#-test-suite--verification) • [🚀 Quick Start](#-quick-start)

---

</div>

## 📌 Executive Overview

Border checkpoints process tens of thousands of international travelers daily under strict operational time constraints. Immigration and border officers typically have an unforgiving **5 to 8 second inspection window** per traveler to detect sophisticated identity fraud:

* 🎭 **Digital Tampering & Splicing:** Digitally altered birth dates, forged visa stamps, erased security watermarks, and photo-swaps on legitimate booklets.
* 👥 **Syndicate Multi-Identity Fraud:** The same bad actor presenting different names, passports, and national IDs across separate checkpoints.
* ⚡ **High Queue Pressures:** Manual document inspection creates massive passenger bottlenecks across international terminals and land border gates.
* 📶 **Disconnected Outposts:** Remote land border crossings frequently suffer from cloud connectivity dropouts and require edge-resilient offline AI screening.
* ⚖️ **Legal Evidentiary Gaps:** Difficulty in providing mathematically tamper-proof audit trails for intercepted criminals in judicial proceedings.

**TriPort** solves this with a **Google Stitch Tactical HUD**, powered by an autonomous **LangGraph multi-agent pipeline**. It screens travelers in **~2 seconds**, detects pixel-level forgeries, compares live facial biometrics against encrypted chip photos, cross-references regional travel graphs for impossible velocity, and commits every decision to an append-only **SHA-256 cryptographic hash-chained ledger**.

---

## ✨ Key Capabilities

### ⚡ 1. Ultra-Fast Parallelized Screening Engine
* 🏎️ **Concurrent Fan-Out:** Dispatches OCR character extraction, Error Level Analysis (ELA), EXIF structure parsing, and facial embedding extraction concurrently.
* 🤖 **Gemini Multimodal LLM Fallback:** Low-contrast scans, torn corners, or complex non-standard credentials automatically trigger **Google Gemini Flash Vision** to extract full entity trees without officer intervention.

### 🔬 2. Five-Layer Forensic Tampering Detection
* 🔍 **Error Level Analysis (ELA):** Identifies differences in JPEG compression ratios to expose digitally pasted portraits, modified text, and erased watermarks.
* 🖼️ **Boundary & Sobel Discontinuity:** Detects photo border splicing, unnatural noise gradients, and synthetic edges around portrait zones.
* 📜 **EXIF & Software Signatures:** Scans for traces of manipulation software (*Photoshop, GIMP, Snapseed*) embedded within file headers.
* 🏷️ **Entry/Exit Stamp Perceptual Hash (dHash):** Matches travel stamps against authorized border control matrices.
* ✍️ **Font & Stroke Consistency:** Detects mismatched typographic weights and irregular kerning across text lines.

### 👤 3. Dual-Engine Biometrics & Automated Clearance
* 👁️ **Hybrid Cloud & Edge Biometrics:** Combines **AWS Rekognition CompareFaces** with on-device **InsightFace (RetinaFace 10G + ArcFace ResNet-50)** for instant, zero-downtime offline failover.
* 🚀 **Automated Clearance (Zero Human Friction):** When live camera face verification matches the document portrait ($\ge 90\%$), the console displays **`FACE RECOGNIZED — NO HUMAN VERIFICATION REQUIRED`** with an animated 3-second auto-clear timer!
* ⚠️ **Human Verification Escalation:** When a biometric discrepancy occurs, the console alerts **`HUMAN VERIFICATION REQUIRED`**, locking gate passage until an officer conducts an in-person physical inspection and logs signed audit notes.

### 🌐 4. Cross-Checkpoint Face Graph & Velocity Tracking
* 🧠 **`pgvector` 1:N Facial Deduplication:** High-dimensional 512-d vector indexing in PostgreSQL identifies whether a traveler’s face has ever been sighted under an alias name or alternate document number.
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

## 👤 Hybrid Biometric Architecture (AWS + InsightFace)

TriPort implements a **defense-in-depth, zero-downtime biometric verification pipeline** that combines cloud precision with edge offline survivability:

```
                          [ Incoming Biometric Verification ]
                                           │
                                           ▼
                       Is AWS Rekognition Online & Configured?
                                    /              \
                             YES   /                \  NO / TIMEOUT / OFFLINE
                                  ▼                  ▼
                     ┌──────────────────────┐   ┌──────────────────────┐
                     │   AWS REKOGNITION    │   │   INSIGHTFACE LOCAL  │
                     │  CompareFaces API    │   │  RetinaFace Detector │
                     │  (Cloud Precision)   │   │  + ArcFace W600K R50 │
                     └──────────┬───────────┘   └──────────┬───────────┘
                                │                          │
                                │                          ▼
                                │               512-d Unit Hypersphere
                                │               Cosine Similarity (sim)
                                │                          │
                                │                          ▼
                                │               AWS-Style Calibration:
                                │               • sim ≥ 0.35 → 91%–99.5%
                                │               • sim < 0.35 → 10%–65.0%
                                │                          │
                                └───────────┬──────────────┘
                                            ▼
                                [ Unified 0–100% Score ]
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
          Score ≥ 90.0% (MATCH)                         Score < 90.0% (MISMATCH)
    ┌─────────────────────────────────┐           ┌─────────────────────────────────┐
    │  FACE RECOGNIZED                │           │  MISMATCH DETECTED              │
    │  NO HUMAN VERIFICATION REQUIRED │           │  HUMAN VERIFICATION REQUIRED    │
    │  [3-Second Auto-Clear Timer]    │           │  [Officer Manual Review Modal]  │
    └─────────────────────────────────┘           └─────────────────────────────────┘
```

### 📐 The AWS-Style Calibration Formula for ArcFace
In deep learning, ArcFace vectors sit on a **512-dimensional unit hypersphere** where the mathematical decision boundary for a verified match is **`0.35`** (False Accept Rate $< 0.01\%$). To provide uniform clarity to officers, TriPort maps raw cosine scores to the standard 0–100% scale:

* **When Face is Recognized ($sim \ge 0.35$):**
  $$\text{Percentage} = 91.0\% + \left( \frac{sim - 0.35}{0.60 - 0.35} \right) \times 8.5\% \quad \implies \mathbf{91.0\% \text{ to } 99.5\% \text{ MATCH}}$$
* **When Face is Mismatched ($sim < 0.35$):**
  $$\text{Percentage} = 10.0\% + \left( \frac{sim}{0.35} \right) \times 50.0\% \quad \implies \mathbf{10.0\% \text{ to } 65.0\% \text{ MATCH}}$$

| Match Scenario | Raw Cosine Angle | Officer Display Score | Decision Protocol |
| :--- | :---: | :---: | :--- |
| **Completely Different Person** | `0.04` | **`15.7%`** | ❌ Mismatch $\rightarrow$ Officer Manual Review |
| **Random Stranger** | `0.13` | **`28.6%`** | ❌ Mismatch $\rightarrow$ Officer Manual Review |
| **Distant Lookalike / Sibling** | `0.22` | **`41.4%`** | ❌ Mismatch $\rightarrow$ Officer Manual Review |
| **Passing Cutoff** | `0.35` | **`91.0%`** | ✅ **Match $\rightarrow$ Auto-Clear (Zero Delay)** |
| **Real Document vs. Live Cam** | `0.37` | **`91.8%`** | ✅ **Match $\rightarrow$ Auto-Clear (Zero Delay)** |
| **High-Quality Clean Scan** | `0.45` | **`94.4%`** | ✅ **Match $\rightarrow$ Auto-Clear (Zero Delay)** |
| **Direct Digital Match** | `0.60+` | **`99.5%`** | ✅ **Match $\rightarrow$ Auto-Clear (Zero Delay)** |

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
* **Document Type Selector:** Multi-document selection (`Passport`, `National ID / Aadhaar`, `Driving License`, `Voter ID / EPIC`, `Visa`, `Permit`).
* **Checkpoint Station Selector:** Configurable between `Airport Terminal`, `Land Border Gate`, and `Passenger Seaport`.
* **Instant Local Preview:** Generates an in-memory client preview instantly so officers can verify visual clarity before cloud dispatch.

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

## 📜 Multi-Document Forensic Engine

TriPort features dedicated extraction parsers and YAML business rule validators across 6 international document categories:

| Document Type | Primary Identifiers & Format | Validation Checks Executed |
| :--- | :--- | :--- |
| 🛂 **International Passports** | ICAO 9303 TD3 standard (2 lines $\times$ 44 chars) | VIZ OCR vs. MRZ 5-column cross-check, check digit $[7,3,1]$ math, 6-month validity rule, issuing country SLTD query. |
| 🪪 **Indian Voter ID (EPIC)** | 3 Letters + 7 Digits (e.g. `TGI8262487`) | Bilingual Hindi/English parsing (`मतदाता का नाम`, `पिता का नाम`), assembly constituency validation, plastic card tampering heuristics. |
| 🆔 **Aadhaar / National ID** | 12-Digit Numeric Sequence (`XXXX-XXXX-XXXX`) | Verhoeff checksum algorithm, DOB chronology check, regional district validation, portrait boundary continuity. |
| 🚗 **Driving Licenses** | State Code + Year + Serial (15–16 chars) | Transport authority code validation, vehicle class endorsements (LMV, MCWG, HMV), license expiration check. |
| ✈️ **Visas** | 8–10 Alpha-Numeric Serial | Entry type quota (Single/Multiple), issuing consulate code, stay duration limits, passport number binding. |
| 📋 **Border Gate Permits** | Regional Outpost Permit ID | Valid transit corridor matching, border crossing time window (< 24h), carrier vehicle license validation. |

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │          💻 Next.js 16 Tactical Console UI             │
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

## 📦 Unified Microservices

All backend dependencies have been consolidated into a single manifest: [`backend/requirements.txt`](backend/requirements.txt).

| Service | Port | Responsibilities | Core Technologies |
| :--- | :---: | :--- | :--- |
| **`orchestrator`** | `8000` | LangGraph DAG pipeline coordination, Supabase DB pooling, auth, and routing | `LangGraph`, `FastAPI`, `SQLAlchemy`, `psycopg3` |
| **`ocr_service`** | `8001` | Multi-document OCR, ICAO-9303 MRZ parser, Gemini Flash LLM vision fallback | `EasyOCR`, `google-generativeai`, `Pillow`, `PyTorch` |
| **`validation_service`** | `8002` | YAML business rules (Passports, Voter ID, Aadhaar, License, Visas, Permits) | `PyYAML`, `pydantic`, `SQLAlchemy` |
| **`tampering_service`** | `8003` | Error Level Analysis (ELA), EXIF structure, Sobel boundary noise, stamp dHash | `opencv-python`, `scikit-image`, `numpy` |
| **`face_service`** | `8004` | AWS Rekognition, InsightFace ArcFace 512d vectors, pgvector 1:N deduplication | `boto3`, `insightface`, `onnxruntime`, `pgvector` |
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
* **Node.js 18+** or **Bun**
* **Supabase Project** (PostgreSQL with `pgvector` & Storage enabled)

### 2. Clone & Environment Setup
```bash
# Clone repository
git clone https://github.com/Rishu7011/TriPort.git
cd TriPort

# Setup Python virtual environment with uv (recommended)
uv venv --python 3.11 backend/.venv
source backend/.venv/bin/activate

# Install all dependencies with single unified manifest
uv pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

**Backend (`backend/.env`):**
```env
# Database & Supabase Storage
DATABASE_URL=postgresql+psycopg://postgres.[REF]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL=https://[REF].supabase.co
SUPABASE_SERVICE_ROLE_KEY=[YOUR_KEY]

# Biometric Mode (aws = Cloud with local fallback, local = 100% On-Device InsightFace)
FACE_VERIFICATION_PROVIDER=aws
AWS_ACCESS_KEY_ID=[YOUR_AWS_KEY]
AWS_SECRET_ACCESS_KEY=[YOUR_AWS_SECRET]
AWS_REGION=ap-south-1
AWS_FACE_SIMILARITY_THRESHOLD=90

# AI Vision Fallback
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
* **Biometric Cluster Graph:** `http://localhost:3000/command/clusters`
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
