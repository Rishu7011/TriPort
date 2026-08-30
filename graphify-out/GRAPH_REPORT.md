# Graph Report - BorderGuard-AI  (2026-08-30)

## Corpus Check
- 91 files · ~47,846 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 785 nodes · 1283 edges · 58 communities (39 shown, 19 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fdf2e15c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- FastAPI Service Layer
- Frontend Package Dependencies
- TypeScript Compiler Config
- Docker Infrastructure Stack
- Dev Tooling Dependencies
- Next.js Branding Assets
- File Icon Assets
- TypeScript Project Config
- test_phase2.py
- Globe Icon Assets
- Audit Ledger Router
- App Layout
- App Configuration
- 001_initial_schema.py
- Face Service Router
- main.py
- backend
- Home Page
- ESLint Config
- Next Config
- models.py
- PostCSS Config
- test_phase2.py
- service_clients.py
- extract_face_embedding
- run_pipeline
- validation.py
- ExtractedField
- ExtractedField
- 3. Microservice Specifications
- one_to_one.py
- field_extractor.py
- RiskScoreRequest
- test_phase3.py
- 3. Document Screening Endpoints
- 3. Threat Vectors & Mitigations
- logging_config.py
- rules_engine.py
- minio_client.py
- ⏱️ Minute-by-Minute Demo Flow
- main.py
- reasons.py
- dedup_search.py
- main.py
- main.py
- main.py
- main.py
- Settings
- ExtractedField
- ndarray
- ReasonsPanel.tsx
- Step3VerificationResult.tsx
- ndarray
- AsyncSession
- DocumentType

## God Nodes (most connected - your core abstractions)
1. `RiskScoreResponse` - 18 edges
2. `append_event()` - 16 edges
3. `compilerOptions` - 16 edges
4. `extract_face_embedding()` - 15 edges
5. `RiskScoreRequest` - 15 edges
6. `validate_document()` - 14 edges
7. `compute_risk_score()` - 13 edges
8. `verify_chain()` - 12 edges
9. `run_pipeline()` - 12 edges
10. `Base` - 12 edges

## Surprising Connections (you probably didn't know these)
- `extract_fields()` --calls--> `ExtractedField`  [EXTRACTED]
  backend/ocr_service/core/field_extractor.py → frontend/components/ExtractedFieldsTable.tsx
- `seed_data()` --calls--> `append_event()`  [EXTRACTED]
  scripts/seed_demo_data.py → backend/audit_ledger/core/hash_chain.py
- `main()` --calls--> `append_event()`  [EXTRACTED]
  scripts/verify_ledger_integrity.py → backend/audit_ledger/core/hash_chain.py
- `main()` --calls--> `verify_chain()`  [EXTRACTED]
  scripts/verify_ledger_integrity.py → backend/audit_ledger/core/hash_chain.py
- `check_blacklist()` --indirect_call--> `BlacklistEntry`  [INFERRED]
  backend/orchestrator/core/blacklist.py → backend/orchestrator/db/models.py

## Import Cycles
- None detected.

## Communities (58 total, 19 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.07
Nodes (28): BorderGuardDashboard(), DEMO_CREDENTIALS, getApiBases(), PRESETS, safeApiFetch(), AdminScanQueue(), AdminScanQueueProps, INITIAL_QUEUE (+20 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.05
Nodes (43): clsx, eslint, eslint-config-next, dependencies, clsx, lucide-react, next, react (+35 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.06
Nodes (30): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+22 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.22
Nodes (7): Orchestration Pipeline — End-to-end execution of the document screening workflow, DecisionChoice, str, Orchestrator Pydantic Schemas — Pipeline requests and responses.  These schemas, Pydantic schemas for the Tampering Detection Service.  Defines schemas for Error, Types of forensic tampering checks performed., TamperingCheckType

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.15
Nodes (25): AsyncSession, get_db(), DB Session — async SQLAlchemy session factory.  CONCEPT: A "session" is a unit o, FastAPI dependency — yields a DB session for the duration of a request.      The, extract_face_crop(), get_document_audit_trail(), get_document_extraction(), get_document_face() (+17 more)

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.17
Nodes (19): extract_document(), Extraction Router — FastAPI endpoint for document OCR extraction.  FLOW:   1. Re, Extract structured fields and MRZ check digits from an uploaded document image., DocumentType, ExtractedField, ExtractionError, ExtractionMethod, ExtractionResponse (+11 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.06
Nodes (47): _compute_check_digit(), _mrz_date_to_dmy(), parse_mrz(), parse_mrz_from_text_lines(), MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.  Works, Parse MRZ from OCR text lines first, falling back to PassportEye if available., Compute ICAO 9303 check digit using repeating weights [7, 3, 1]., Return True if the computed check digit matches the expected one. (+39 more)

### Community 7 - "TypeScript Project Config"
Cohesion: 0.16
Nodes (18): dedup_check(), generate_embedding(), UploadFile, Face Router — FastAPI endpoints for Face Embedding, 1:1 Verification, and 1:N De, Check face against historical vector index for duplicate identities., Extract a 512-dimensional facial embedding vector from an uploaded face image., Compare document portrait against live checkpoint capture., verify_faces() (+10 more)

### Community 8 - "test_phase2.py"
Cohesion: 0.07
Nodes (37): analyze_photo_boundaries(), _compute_noise_variance(), get_face_cascade(), ndarray, Photo Boundary & Noise Analysis Engine.  CONCEPT: When a forger splices a differ, Compute local high-frequency noise variance using Laplacian operator., Analyze photo boundaries and noise consistency on a document scan.      Args:, compute_ela() (+29 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.50
Nodes (3): Deploy on Vercel, Getting Started, Learn More

### Community 11 - "Audit Ledger Router"
Cohesion: 0.09
Nodes (37): get_current_user(), get_current_user_or_demo(), FastAPI Security & RBAC Dependencies (Phase 4B).  Enforces:   - Valid JWT Bearer, Extract and validate the current authenticated user from Bearer Token.     Raise, Optional helper: fallback to demo officer if no credentials provided (for dev co, RBAC dependency factory that asserts the current user possesses one of allowed_r, require_roles(), create_access_token() (+29 more)

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): jetbrainsMono, metadata, plusJakartaSans

### Community 13 - "App Configuration"
Cohesion: 0.24
Nodes (11): Image, _draw_mock_face(), _draw_stamp(), generate_all_samples(), generate_baseline_passport(), ndarray, Synthetic Tampered Document Generator.  CONCEPT: Generates synthetic identity do, Generate 5+ genuine and 5+ samples per tampering category (photo-swap, text-edit (+3 more)

### Community 15 - "Face Service Router"
Cohesion: 0.05
Nodes (70): check_blacklist(), AsyncSession, Blacklist Lookup Engine.  Checks extracted document fields (document number, nam, Check extracted fields against the blacklist database (and in-memory seed list)., call_risk_engine(), Invoke Risk Engine via HTTP or fallback to internal scoring logic., DecisionRequest, DecisionResponse (+62 more)

### Community 16 - "main.py"
Cohesion: 0.05
Nodes (63): decrypt_bytes(), decrypt_text(), encrypt_bytes(), encrypt_text(), _get_encryption_key(), mask_pii(), Field-Level & Scan AES-256-GCM Symmetric Encryption (Phase 4).  Features:   - AE, Derive deterministic 256-bit (32-byte) key from configuration secret. (+55 more)

### Community 19 - "Home Page"
Cohesion: 0.33
Nodes (4): ExtractedField, ExtractedFieldsTableProps, MRZDetails, ValidationCheck

### Community 22 - "models.py"
Cohesion: 0.10
Nodes (27): call_ocr_service(), call_validation_service(), DocumentType, Invoke Document Validation via HTTP or fallback to core engine., Invoke OCR extraction via HTTP or fallback to core pipeline., do_run_migrations(), get_url(), Alembic env.py — the bridge between Alembic and your SQLAlchemy models.  CONCEPT (+19 more)

### Community 24 - "test_phase2.py"
Cohesion: 0.12
Nodes (16): Phase 2 Unit & Integration Tests — Tampering Detection and Face Verification Ser, Test metadata forensics flags editing software signatures., Test face embedding generates 512-dim unit vector., Test 1:N deduplication matches identical person and creates new cluster for new, Verify ELA on all genuine dataset variants produces valid baseline metrics., Verify ELA detects compression discrepancy across all 5 text-edit field variatio, Verify photo region boundary and noise variance analysis detects all 5 photo-swa, Verify duplicate stamp hash detection triggers across all 5 stamp-duplicate samp (+8 more)

### Community 25 - "service_clients.py"
Cohesion: 0.18
Nodes (10): Any, call_audit_ledger(), call_face_service(), call_tampering_service(), Typed Async HTTP Service Clients for Downstream Microservices.  Features: - Conf, Invoke Tampering Detection via HTTP or fallback to core forensics., Invoke Face verification (1:1 and 1:N) via HTTP or fallback to core., Append event to the tamper-evident audit ledger (safe call; never raises). (+2 more)

### Community 26 - "extract_face_embedding"
Cohesion: 0.22
Nodes (17): _bytes_to_numpy_rgb(), _compute_fallback_embedding(), deepface_multi_model_vote(), _ensure_512d(), _extract_arcface_embedding(), _extract_deepface_facenet512(), extract_face_embedding(), _l2_normalize() (+9 more)

### Community 27 - "run_pipeline"
Cohesion: 0.14
Nodes (14): Any, AsyncSession, DocumentType, Execute the full end-to-end document screening pipeline., run_pipeline(), _safe_uuid(), Test full end-to-end screening pipeline with a genuine passport scan.     Verifi, Test full pipeline on tampered documents.     Verifies elevated risk score and s (+6 more)

### Community 28 - "validation.py"
Cohesion: 0.28
Nodes (8): BaseModel, Pydantic Schemas for Validation Service.  Defines the structure for input valida, Result of evaluating a single rule., Validation request body.     Accepts the extracted fields from OCR and an option, Overall document validation report., RuleResult, ValidationRequest, ValidationResponse

### Community 31 - "3. Microservice Specifications"
Cohesion: 0.15
Nodes (12): 1. Executive Summary & Architecture Paradigm, 2. High-Level System Architecture, 3. Microservice Specifications, 4. Container Deployment & Docker Architecture, BorderGuard-AI — System Architecture & Technical Specification, Core Architectural Decisions:, Module 1: OCR Extraction Service (`ocr_service` — Port 8001), Module 2: Document Validation Service (`validation_service` — Port 8002) (+4 more)

### Community 33 - "one_to_one.py"
Cohesion: 0.24
Nodes (9): _compute_ear(), 1:1 Face Verification Engine — Production-Grade with MediaPipe Liveness.  FULL P, MediaPipe FaceMesh liveness detector.      Checks:       1. EAR (Eye Aspect Rati, Perform 1:1 face verification between document portrait and live capture.      F, Eye Aspect Ratio (EAR) — Soukupova & Čech 2016.     EAR ≈ 0.30 for open eye; dro, run_liveness_check(), verify_one_to_one(), Test 1:1 face verification matching same face vs different faces. (+1 more)

### Community 34 - "field_extractor.py"
Cohesion: 0.21
Nodes (11): _bytes_to_numpy_image(), extract_fields(), extract_raw_ocr_lines(), get_ocr_reader(), DocumentType, ndarray, Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi, Extract structured fields from image bytes using contextual OCR line analysis. (+3 more)

### Community 35 - "RiskScoreRequest"
Cohesion: 0.40
Nodes (3): AuditLedgerViewerProps, LedgerEvent, VerificationReport

### Community 37 - "3. Document Screening Endpoints"
Cohesion: 0.17
Nodes (11): 1. Authentication & Security Model, 2. Authentication Endpoints, 3. Document Screening Endpoints, BorderGuard-AI — API Contracts & Specification, `GET /api/v1/audit/{document_id}`, `GET /api/v1/audit/events/verify`, `GET /api/v1/auth/me`, `POST /api/v1/auth/login` (+3 more)

### Community 38 - "3. Threat Vectors & Mitigations"
Cohesion: 0.20
Nodes (9): 1. System Overview & Scope, 2. Trust Boundaries & Architecture, 3.1 Document Forgery & Digital Manipulation, 3.2 Biometric Spoofing & Identity Clustering, 3.3 Insider Threat & Audit Log Tampering, 3.4 Data-at-Rest & In-Transit Interception, 3. Threat Vectors & Mitigations, 4. Known Hackathon Limitations & Production Roadmap (+1 more)

### Community 39 - "logging_config.py"
Cohesion: 0.14
Nodes (9): Shared settings loaded from .env (or environment variables). Every service impor, Settings, get_logger(), Shared structured logging setup. Call configure_logging() at service startup., extract_fields_with_llm(), LLM Fallback — Pluggable Vision LLM interface for non-standard documents.  CONCE, Generic interface for vision-capable LLM document extraction.      Args:, BaseSettings (+1 more)

### Community 41 - "minio_client.py"
Cohesion: 0.32
Nodes (7): get_document_image_url(), get_minio_client(), MinIO Object Storage Client Wrapper.  Handles uploading document scans and retri, Lazy initialize MinIO client., Upload document image bytes to MinIO.      Returns:         object_key: The stor, Generate presigned URL for viewing document scan from MinIO., upload_document_image()

### Community 42 - "⏱️ Minute-by-Minute Demo Flow"
Cohesion: 0.25
Nodes (7): [0:00 - 1:00] Ingestion & Genuine Baseline, [1:00 - 2:15] Advanced Digital Forgery Detection (Photo-Swap & Text-Edit), [2:15 - 3:15] Watchlist & Multi-Identity Biometric Deduplication, [3:15 - 4:30] The Cryptographic Audit Ledger & Live Tampering Catch (The Climax), [4:30 - 5:00] Summary & Architecture Wrap-Up, BorderGuard-AI — Live Demo & Presentation Script (5-Minute Walkthrough), ⏱️ Minute-by-Minute Demo Flow

### Community 43 - "main.py"
Cohesion: 0.28
Nodes (7): extract_face_crop_bytes(), _get_insightface_app(), Detect and crop the face photo from a passport/ID document image.      Uses a ca, Lazy-load InsightFace FaceAnalysis singleton (RetinaFace + ArcFace)., lifespan(), FastAPI, Face Service — 1:1 verification and 1:N deduplication using face embeddings.

### Community 45 - "dedup_search.py"
Cohesion: 0.18
Nodes (12): clear_in_memory_embeddings(), Any, 1:N Biometric Deduplication & Person Clustering Engine.  CONCEPT: A primary thre, Helper for testing: store an embedding in the temporary in-memory registry., Clear in-memory embeddings store., Search 1:N stored face embeddings for duplicate identity matches.      Args:, register_in_memory_embedding(), search_duplicates() (+4 more)

### Community 46 - "main.py"
Cohesion: 0.50
Nodes (3): lifespan(), FastAPI, Audit Ledger — hash-chained append-only event log.

### Community 47 - "main.py"
Cohesion: 0.50
Nodes (3): lifespan(), FastAPI, OCR Service — extracts structured fields from identity documents.

### Community 48 - "main.py"
Cohesion: 0.50
Nodes (3): lifespan(), FastAPI, Risk Engine — combines all module signals into a weighted risk score.

## Knowledge Gaps
- **117 isolated node(s):** `plusJakartaSans`, `jetbrainsMono`, `metadata`, `DEMO_CREDENTIALS`, `PRESETS` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `extract_fields()` connect `field_extractor.py` to `Home Page`, `Next.js Branding Assets`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `run_pipeline()` connect `run_pipeline` to `Docker Infrastructure Stack`, `File Icon Assets`, `Face Service Router`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `RiskScoreResponse` connect `Face Service Router` to `service_clients.py`, `Docker Infrastructure Stack`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `RiskScoreResponse` (e.g. with `DecisionChoice` and `DecisionRequest`) actually correct?**
  _`RiskScoreResponse` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Face Embedding Extraction Engine — Production-Grade Multi-Model Pipeline.  MODEL`, `Convert raw image bytes to an RGB NumPy array.`, `L2-normalize a vector to unit length. Returns zero vector if degenerate.` to the rest of the system?**
  _339 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.07301587301587302 - nodes in this community are weakly interconnected._
- **Should `Frontend Package Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.04756871035940803 - nodes in this community are weakly interconnected._