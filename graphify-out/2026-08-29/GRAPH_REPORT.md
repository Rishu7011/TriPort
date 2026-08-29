# Graph Report - BorderGuard-AI  (2026-08-29)

## Corpus Check
- 51 files · ~16,594 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 391 nodes · 584 edges · 32 communities (24 shown, 8 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3e57bbe4`
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
- date_logic.py
- Audit Ledger Router
- App Layout
- App Configuration
- 001_initial_schema.py
- Face Service Router
- backend
- ESLint Config
- Next Config
- extraction.py
- PostCSS Config
- extract_document
- ExtractedField
- _validate_check_digit
- ExtractionResponse
- extract_fields_with_llm
- ExtractedField
- ExtractedField

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `validate_document()` - 14 edges
3. `extract_face_embedding()` - 13 edges
4. `DocumentType` - 12 edges
5. `detect_tampering()` - 11 edges
6. `ExtractedField` - 11 edges
7. `Base` - 11 edges
8. `extract_document()` - 10 edges
9. `search_duplicates()` - 9 edges
10. `verify_one_to_one()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `RuleResult` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationRequest` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationResponse` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `extract_document()` --calls--> `parse_mrz()`  [EXTRACTED]
  backend/ocr_service/routers/extraction.py → backend/ocr_service/core/mrz_parser.py
- `validate_document()` --calls--> `evaluate_date_condition()`  [EXTRACTED]
  backend/validation_service/core/rules_engine.py → backend/validation_service/core/date_logic.py

## Import Cycles
- None detected.

## Communities (32 total, 8 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.06
Nodes (23): AsyncSession, Shared settings loaded from .env (or environment variables). Every service impor, Settings, get_logger(), Shared structured logging setup. Call configure_logging() at service startup., LLM Fallback — Pluggable Vision LLM interface for non-standard documents.  CONCE, lifespan(), FastAPI (+15 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.10
Nodes (20): dependencies, next, react, react-dom, ignoreScripts, name, packageManager, private (+12 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.06
Nodes (30): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+22 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.15
Nodes (19): do_run_migrations(), get_url(), Alembic env.py — the bridge between Alembic and your SQLAlchemy models.  CONCEPT, Read DATABASE_URL from environment — never hardcode credentials., Offline mode: generate SQL scripts without connecting to DB.     Useful when you, Online mode: connect to DB and apply migrations directly.     This is the normal, run_migrations_offline(), run_migrations_online() (+11 more)

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+9 more)

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.22
Nodes (13): DocumentType, WHY Enum instead of plain str?     If a caller sends document_type="pasport" (ty, Validation Router — FastAPI endpoint for document validation.  Accepts extracted, Evaluate OCR-extracted fields against configured document rules (dates, formats,, validate_extracted_fields(), BaseModel, Pydantic Schemas for Validation Service.  Defines the structure for input valida, Result of evaluating a single rule. (+5 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.18
Nodes (14): _compute_check_digit(), parse_mrz(), parse_mrz_from_text_lines(), MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.  Works, Parse MRZ from OCR text lines first, falling back to PassportEye if available., Compute ICAO 9303 check digit using repeating weights [7, 3, 1]., Return True if the computed check digit matches the expected one., Directly parse MRZ lines from extracted OCR text lines.     This guarantees 100% (+6 more)

### Community 7 - "TypeScript Project Config"
Cohesion: 0.07
Nodes (47): clear_in_memory_embeddings(), Any, 1:N Biometric Deduplication & Person Clustering Engine.  CONCEPT: A primary thre, Helper for testing: store an embedding in the temporary in-memory registry., Clear in-memory embeddings store., Search 1:N stored face embeddings for duplicate identity matches.      Args:, register_in_memory_embedding(), search_duplicates() (+39 more)

### Community 8 - "test_phase2.py"
Cohesion: 0.06
Nodes (43): analyze_photo_boundaries(), _compute_noise_variance(), get_face_cascade(), ndarray, Photo Boundary & Noise Analysis Engine.  CONCEPT: When a forger splices a differ, Compute local high-frequency noise variance using Laplacian operator., Analyze photo boundaries and noise consistency on a document scan.      Args:, compute_ela() (+35 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.50
Nodes (3): Deploy on Vercel, Getting Started, Learn More

### Community 10 - "date_logic.py"
Cohesion: 0.21
Nodes (11): Test date condition evaluations including +/- offsets., test_date_conditions_offset(), evaluate_cross_document_dates(), evaluate_date_condition(), parse_date(), Date Logic — Parsing, Normalization, and Evaluation for Validation Rules.  CONCE, Cross-document check: A visa's valid stay/expiry must not exceed     the underly, Parse arbitrary date strings into a standard datetime.date object.      Handles: (+3 more)

### Community 11 - "Audit Ledger Router"
Cohesion: 0.22
Nodes (7): lifespan(), FastAPI, Audit Ledger — hash-chained append-only event log., append_event(), Phase 4A stub — chain integrity verification. Full implementation in Phase 4., Phase 4A stub — ledger event append. Full implementation in Phase 4., verify_chain()

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 13 - "App Configuration"
Cohesion: 0.24
Nodes (11): Image, _draw_mock_face(), _draw_stamp(), generate_all_samples(), generate_baseline_passport(), ndarray, Synthetic Tampered Document Generator.  CONCEPT: Generates synthetic identity do, Generate genuine and 3 categories of synthetic tampered documents. (+3 more)

### Community 15 - "Face Service Router"
Cohesion: 0.29
Nodes (5): lifespan(), FastAPI, Risk Engine — combines all module signals into a weighted risk score., Phase 3 stub — risk scoring. Full implementation in Phase 3., score()

### Community 22 - "extraction.py"
Cohesion: 0.32
Nodes (7): ExtractionMethod, Tracks HOW a field was extracted — critical for debugging and audit., Pydantic schemas for the Tampering Detection Service.  Defines schemas for Error, Types of forensic tampering checks performed., TamperingCheckType, Enum, str

### Community 24 - "extract_document"
Cohesion: 0.21
Nodes (11): _bytes_to_numpy_image(), extract_fields(), extract_raw_ocr_lines(), get_ocr_reader(), ExtractedField, Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi, Extract structured fields from image bytes., Singleton lazy-loader for EasyOCR reader. (+3 more)

### Community 25 - "ExtractedField"
Cohesion: 0.16
Nodes (17): extract_fields_with_llm(), Generic interface for vision-capable LLM document extraction.      Args:, Phase 1 Smoke Tests — Validation Service & MRZ checksum testing., Test valid passport fields passing all YAML rules., Test passport fields with visual zone naming (date_of_expiry, passport_number) p, Test expired passport failing expiry_not_passed rule., test_validation_engine_expired_passport(), test_validation_engine_ocr_field_names() (+9 more)

### Community 26 - "_validate_check_digit"
Cohesion: 0.50
Nodes (3): lifespan(), FastAPI, Face Service — 1:1 verification and 1:N deduplication using face embeddings.

### Community 27 - "ExtractionResponse"
Cohesion: 0.20
Nodes (14): extract_document(), Extraction Router — FastAPI endpoint for document OCR extraction.  FLOW:   1. Re, Extract structured fields and MRZ check digits from an uploaded document image., ExtractedField, ExtractionError, ExtractionResponse, MRZResult, BaseModel (+6 more)

## Knowledge Gaps
- **53 isolated node(s):** `backend`, `Getting Started`, `Learn More`, `Deploy on Vercel`, `geistSans` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `validate_document()` connect `ExtractedField` to `date_logic.py`, `Next.js Branding Assets`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `extract_face_embedding()` connect `TypeScript Project Config` to `test_phase2.py`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `DocumentType` (e.g. with `RuleResult` and `ValidationRequest`) actually correct?**
  _`DocumentType` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Audit Ledger — hash-chained append-only event log.`, `1:N Biometric Deduplication & Person Clustering Engine.  CONCEPT: A primary thre`, `Helper for testing: store an embedding in the temporary in-memory registry.` to the rest of the system?**
  _167 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06349206349206349 - nodes in this community are weakly interconnected._
- **Should `Frontend Package Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.10476190476190476 - nodes in this community are weakly interconnected._
- **Should `TypeScript Compiler Config` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._