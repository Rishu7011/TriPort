# BorderGuard-AI — System Architecture & Technical Specification

**Problem Statement ID:** 26188  
**Organization:** Ministry of Home Affairs — Sashastra Seema Bal (SSB), Police II Division  
**Theme:** Blockchain & Cybersecurity  

---

## 1. Executive Summary & Architecture Paradigm

BorderGuard-AI transforms manual identity document inspection into an automated, explainable, and cryptographically tamper-evident pipeline operating under **5 seconds** per traveler. 

### Core Architectural Decisions:
1. **Hybrid Edge-Local Inference with Central Sync:** The AI inference pipeline (OCR, forensic tampering detection, and biometric face verification) runs entirely on the local checkpoint kiosk/edge node without requiring active internet connectivity. Audit logs and watchlists sync to central headquarters when connectivity permits.
2. **Python Monorepo with Microservice Topology:** All backend microservices live in `backend/` sharing a unified Python virtual environment, Docker image, and dependencies, while isolating execution into separate FastAPI processes communicating over internal HTTP REST APIs.
3. **Defense-in-Depth AI Ensemble:** Combines explainable deterministic computer vision (ELA, EXIF analysis, boundary noise variance, ICAO check digits) with deep neural embeddings (InsightFace ArcFace, RetinaFace, Google MediaPipe FaceMesh) and multi-model consensus voting.

---

## 2. High-Level System Architecture

```
                          ┌─────────────────────────────────────────┐
                          │     Officer Dashboard (Web UI)          │
                          │     Next.js 14 + TypeScript + Tailwind   │
                          └────────────────────┬────────────────────┘
                                               │ HTTPS (REST + JWT Bearer)
                          ┌────────────────────▼────────────────────┐
                          │   Orchestrator Gateway (Port 8007)       │
                          │   Pipeline Engine + RBAC Auth Guard     │
                          └───────┬────────────┬────────────┬───────┘
                                  │            │            │
         ┌────────────────────────┼────────────┼────────────┼────────────────────────┐
         │                        │            │            │                        │
 ┌───────▼──────┐         ┌───────▼──────┐ ┌───▼────────┐ ┌─▼────────────┐   ┌───────▼──────┐
 │ OCR Service  │         │ Validation   │ │ Tampering  │ │ Face Service │   │ Risk Scoring │
 │ (Module 1)   │         │ Service (M2) │ │ Detection  │ │ (Module 4)   │   │ Engine (M5)  │
 │ Port: 8001   │         │ Port: 8002   │ │ Port: 8003 │ │ Port: 8004   │   │ Port: 8005   │
 └───────┬──────┘         └───────┬──────┘ └───┬────────┘ └─┬────────────┘   └───────┬──────┘
         │                        │            │            │                        │
         └────────────────────────┴────────────┴────────────┴────────────────────────┘
                                               │
                               ┌───────────────▼───────────────┐
                               │ Audit Ledger Service (Module 6)│
                               │ Port: 8006 (SHA-256 Chained)  │
                               └───────────────┬───────────────┘
                                               │
                      ┌────────────────────────┴────────────────────────┐
                      │                                                 │
              ┌───────▼───────────────┐                       ┌─────────▼─────────┐
              │ PostgreSQL + pgvector │                       │ MinIO S3 Storage  │
              │ Structured Records,   │                       │ Raw scans &       │
              │ Watchlist & Vectors   │                       │ ELA heatmaps      │
              └───────────────────────┘                       └───────────────────┘
```

---

## 3. Microservice Specifications

### Module 1: OCR Extraction Service (`ocr_service` — Port 8001)
- **Primary Engine:** PaddleOCR / EasyOCR for multi-language printed text extraction.
- **MRZ Parser:** PassportEye for ICAO 9303 Machine Readable Zone parsing. Computes check digits (Doc number, DOB, Expiry, Composite).
- **Fallback Engine:** Claude Vision LLM fallback for unformatted, damaged, or non-standard documents.

### Module 2: Document Validation Service (`validation_service` — Port 8002)
- **Rule Engine:** Declarative YAML rules engine (`backend/validation_service/rules/`).
- **Rule Sets:** `passport_rules.yaml`, `visa_rules.yaml`, `national_id_rules.yaml`.
- **Logic:** Date continuity checks (issue < expiry, age validity), regex schema conformance, and MRZ checksum cross-checks.

### Module 3: Tampering Detection Service (`tampering_service` — Port 8003)
- **Error Level Analysis (ELA):** JPEG resaving compression-error delta to pinpoint localized digital retouching.
- **EXIF Metadata Forensics:** Analyzes editing software signatures (Photoshop, GIMP), timestamp anomalies, and metadata stripping.
- **Photo-Region Boundary Analysis:** Edge discontinuity and noise variance ratio ($SNR_{\text{photo}} / SNR_{\text{background}}$) to catch photo swaps.
- **Stamp & Seal Matcher:** 64-bit difference perceptual hashing (`dhash`) and template matching to catch counterfeit stamps and stamp reuse across documents.

### Module 4: Face Verification & Biometrics (`face_service` — Port 8004)
- **Cropping & 5-pt Alignment:** InsightFace (RetinaFace) locates portrait box and standardizes eye-line alignment.
- **Live Anti-Spoofing & Liveness:** Google MediaPipe FaceMesh tracks 468 3D landmarks, measuring Eye Aspect Ratio (EAR) and head pose variance to block printout/screen replay attacks.
- **Biometric Embeddings:** InsightFace ArcFace W600K ResNet-50 producing 512-dimensional L2-normalized unit vectors.
- **Borderline Multi-Model Voter:** DeepFace consensus voting (VGG-Face, ArcFace, SFace) for ambiguous cosine similarity scores ($0.55 \le \text{sim} \le 0.65$).
- **1:N Deduplication:** PostgreSQL `pgvector` cosine similarity search ($\ge 0.65$) to detect multi-identity fraud.

### Module 5: Explainable Risk Scoring Engine (`risk_engine` — Port 8005)
- **Formula:**
  $$\text{Risk} = 100 \times \left( 0.30 \cdot S_{\text{val}} + 0.35 \cdot S_{\text{tamp}} + 0.20 \cdot S_{\text{face}} + 0.15 \cdot S_{\text{blacklist}} \right)$$
- **Bands:** Low ($< 30$), Medium ($30–59$), High ($60–79$), Critical ($\ge 80$).
- **Explainability:** Emits plain-language root-cause explanations for every triggered flag.

### Module 6: Cryptographic Audit Ledger (`audit_ledger` — Port 8006)
- **Hash Chaining:** SHA-256 Merkle-style sequential linking:
  $$\text{record\_hash}_n = \text{SHA256}(\text{payload\_hash}_n \parallel \text{record\_hash}_{n-1} \parallel \text{timestamp}_n)$$
- **Integrity Verification:** Endpoint `/api/v1/audit/events/verify` re-computes and asserts every link from genesis block to head.
- **Encryption at Rest:** AES-256-GCM symmetric encryption for document assets and PII data masking.

---

## 4. Container Deployment & Docker Architecture

All backend services share a single base image build defined in `backend/Dockerfile` with entry points overridden in `docker-compose.yml`:

| Service Name | Container Port | Host Port | Entry Point |
|---|---|---|---|
| `orchestrator` | 8007 | 8007 | `uvicorn backend.orchestrator.main:app` |
| `ocr-service` | 8001 | 8001 | `uvicorn backend.ocr_service.main:app` |
| `validation-service` | 8002 | 8002 | `uvicorn backend.validation_service.main:app` |
| `tampering-service` | 8003 | 8003 | `uvicorn backend.tampering_service.main:app` |
| `face-service` | 8004 | 8004 | `uvicorn backend.face_service.main:app` |
| `risk-engine` | 8005 | 8005 | `uvicorn backend.risk_engine.main:app` |
| `audit-ledger` | 8006 | 8006 | `uvicorn backend.audit_ledger.main:app` |
| `frontend` | 3000 | 3000 | Next.js Standalone Server |
| `postgres` | 5432 | 5432 | PostgreSQL 16 + pgvector |
| `minio` | 9000 | 9000 | MinIO S3 Object Storage |
