# Graph Report - BorderGuard-AI  (2026-08-29)

## Corpus Check
- 62 files · ~24,061 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 528 nodes · 965 edges · 26 communities (18 shown, 8 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5e21f2d4`
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
- backend
- ESLint Config
- Next Config
- PostCSS Config
- ExtractedField
- ExtractedField

## God Nodes (most connected - your core abstractions)
1. `run_pipeline()` - 36 edges
2. `RiskScoreResponse` - 19 edges
3. `RiskScoreRequest` - 17 edges
4. `compilerOptions` - 16 edges
5. `build_risk_response()` - 14 edges
6. `validate_document()` - 14 edges
7. `compute_risk_score()` - 13 edges
8. `extract_face_embedding()` - 13 edges
9. `Base` - 12 edges
10. `DocumentType` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_blacklist_engine_lookup()` --calls--> `ExtractedField`  [INFERRED]
  backend/tests/test_phase3.py → backend/orchestrator/db/models.py
- `check_blacklist()` --indirect_call--> `BlacklistEntry`  [INFERRED]
  backend/orchestrator/core/blacklist.py → backend/orchestrator/db/models.py
- `check_blacklist()` --references--> `ExtractedField`  [EXTRACTED]
  backend/orchestrator/core/blacklist.py → backend/orchestrator/db/models.py
- `run_pipeline()` --calls--> `check_blacklist()`  [EXTRACTED]
  backend/orchestrator/core/pipeline.py → backend/orchestrator/core/blacklist.py
- `run_pipeline()` --calls--> `build_risk_response()`  [EXTRACTED]
  backend/orchestrator/core/pipeline.py → backend/risk_engine/core/scoring.py

## Import Cycles
- None detected.

## Communities (26 total, 8 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.05
Nodes (33): lifespan(), FastAPI, Audit Ledger — hash-chained append-only event log., append_event(), Phase 4A stub — chain integrity verification. Full implementation in Phase 4., Phase 4A stub — ledger event append. Full implementation in Phase 4., verify_chain(), get_logger() (+25 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.06
Nodes (37): eslint, eslint-config-next, dependencies, next, react, react-dom, devDependencies, eslint (+29 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.06
Nodes (30): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+22 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.06
Nodes (78): Any, AsyncSession, DocumentType, Orchestration Pipeline — End-to-end execution of the document screening workflow, Execute the full end-to-end document screening pipeline., run_pipeline(), call_audit_ledger(), call_face_service() (+70 more)

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.22
Nodes (7): AsyncSession, Shared settings loaded from .env (or environment variables). Every service impor, Settings, get_db(), DB Session — async SQLAlchemy session factory.  CONCEPT: A "session" is a unit o, FastAPI dependency — yields a DB session for the duration of a request.      The, BaseSettings

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.07
Nodes (45): _bytes_to_numpy_image(), extract_fields(), extract_raw_ocr_lines(), get_ocr_reader(), ExtractedField, Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi, Extract structured fields from image bytes., Singleton lazy-loader for EasyOCR reader. (+37 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.08
Nodes (38): _compute_check_digit(), parse_mrz(), parse_mrz_from_text_lines(), MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.  Works, Parse MRZ from OCR text lines first, falling back to PassportEye if available., Compute ICAO 9303 check digit using repeating weights [7, 3, 1]., Return True if the computed check digit matches the expected one., Directly parse MRZ lines from extracted OCR text lines.     This guarantees 100% (+30 more)

### Community 7 - "TypeScript Project Config"
Cohesion: 0.06
Nodes (50): clear_in_memory_embeddings(), Any, 1:N Biometric Deduplication & Person Clustering Engine.  CONCEPT: A primary thre, Helper for testing: store an embedding in the temporary in-memory registry., Clear in-memory embeddings store., Search 1:N stored face embeddings for duplicate identity matches.      Args:, register_in_memory_embedding(), search_duplicates() (+42 more)

### Community 8 - "test_phase2.py"
Cohesion: 0.06
Nodes (46): analyze_photo_boundaries(), _compute_noise_variance(), get_face_cascade(), ndarray, Photo Boundary & Noise Analysis Engine.  CONCEPT: When a forger splices a differ, Compute local high-frequency noise variance using Laplacian operator., Analyze photo boundaries and noise consistency on a document scan.      Args:, compute_ela() (+38 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.50
Nodes (3): Deploy on Vercel, Getting Started, Learn More

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 13 - "App Configuration"
Cohesion: 0.24
Nodes (11): Image, _draw_mock_face(), _draw_stamp(), generate_all_samples(), generate_baseline_passport(), ndarray, Synthetic Tampered Document Generator.  CONCEPT: Generates synthetic identity do, Generate genuine and 3 categories of synthetic tampered documents. (+3 more)

### Community 15 - "Face Service Router"
Cohesion: 0.06
Nodes (58): check_blacklist(), AsyncSession, Blacklist Lookup Engine.  Checks extracted document fields (document number, nam, Check extracted fields against the blacklist database (and in-memory seed list)., BlacklistEntry, generate_reasons(), Reason Generator — Plain-language risk explanation for border officers.  CONCEPT, Generate a plain-language reasons list from all upstream module signals.      Ar (+50 more)

## Knowledge Gaps
- **53 isolated node(s):** `backend`, `Getting Started`, `Learn More`, `Deploy on Vercel`, `geistSans` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Docker Infrastructure Stack` to `Face Service Router`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `validate_document()` connect `File Icon Assets` to `Docker Infrastructure Stack`, `Next.js Branding Assets`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `RiskScoreResponse` connect `Docker Infrastructure Stack` to `Face Service Router`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `run_pipeline()` (e.g. with `ExtractionResponse` and `FullFaceVerificationResponse`) actually correct?**
  _`run_pipeline()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `RiskScoreResponse` (e.g. with `DecisionChoice` and `DecisionRequest`) actually correct?**
  _`RiskScoreResponse` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Blacklist Lookup Engine.  Checks extracted document fields (document number, nam`, `Check extracted fields against the blacklist database (and in-memory seed list).`, `Orchestration Pipeline — End-to-end execution of the document screening workflow` to the rest of the system?**
  _222 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.04846938775510204 - nodes in this community are weakly interconnected._