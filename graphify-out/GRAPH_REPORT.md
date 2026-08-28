# Graph Report - BorderGuard-AI  (2026-08-29)

## Corpus Check
- 39 files · ~8,597 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 258 nodes · 364 edges · 31 communities (24 shown, 7 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cd3b6a40`
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
- Project Overview Docs
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

## God Nodes (most connected - your core abstractions)
1. `DocumentType` - 16 edges
2. `compilerOptions` - 16 edges
3. `ExtractedField` - 15 edges
4. `validate_document()` - 14 edges
5. `Base` - 11 edges
6. `extract_document()` - 10 edges
7. `ValidationResponse` - 9 edges
8. `extract_fields()` - 8 edges
9. `get_logger()` - 8 edges
10. `extract_raw_ocr_lines()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `RuleResult` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationRequest` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationResponse` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `RuleResult` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationRequest` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py

## Import Cycles
- None detected.

## Communities (31 total, 7 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.07
Nodes (16): Audit Ledger — hash-chained append-only event log., Face Service — 1:1 verification and 1:N deduplication using face embeddings., Phase 2B stub — face verification. Full implementation in Phase 2., verify(), configure_logging(), get_logger(), Shared structured logging setup. Call configure_logging() at service startup., OCR Service — extracts structured fields from identity documents. (+8 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.10
Nodes (20): dependencies, next, react, react-dom, ignoreScripts, name, packageManager, private (+12 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.10
Nodes (21): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+13 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.15
Nodes (19): do_run_migrations(), get_url(), Alembic env.py — the bridge between Alembic and your SQLAlchemy models.  CONCEPT, Read DATABASE_URL from environment — never hardcode credentials., Offline mode: generate SQL scripts without connecting to DB.     Useful when you, Online mode: connect to DB and apply migrations directly.     This is the normal, run_migrations_offline(), run_migrations_online() (+11 more)

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+9 more)

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.16
Nodes (18): Any, load_rules_for_doctype(), ExtractedField, Rules Engine — Generic YAML-driven rule interpreter for document validation.  CO, Dynamically load YAML rule configuration for a document type.     Re-reading on, Evaluate all YAML-configured rules against extracted document fields., validate_document(), Validation Router — FastAPI endpoint for document validation.  Accepts extracted (+10 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.36
Nodes (7): parse_mrz(), parse_mrz_from_text_lines(), MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.  Works, Parse MRZ from OCR text lines first, falling back to PassportEye if available., Directly parse MRZ lines from extracted OCR text lines.     This guarantees 100%, MRZResult, The MRZ (Machine Readable Zone) is the two-line `<<<` block at the     bottom of

### Community 7 - "TypeScript Project Config"
Cohesion: 0.20
Nodes (9): exclude, include, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts (+1 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.50
Nodes (3): Deploy on Vercel, Getting Started, Learn More

### Community 10 - "date_logic.py"
Cohesion: 0.28
Nodes (8): evaluate_cross_document_dates(), evaluate_date_condition(), parse_date(), Date Logic — Parsing, Normalization, and Evaluation for Validation Rules.  CONCE, Cross-document check: A visa's valid stay/expiry must not exceed     the underly, Parse arbitrary date strings into a standard datetime.date object.      Handles:, Evaluate condition string against a parsed date.      Supported conditions:, date

### Community 11 - "Audit Ledger Router"
Cohesion: 0.40
Nodes (4): append_event(), Phase 4A stub — chain integrity verification. Full implementation in Phase 4., Phase 4A stub — ledger event append. Full implementation in Phase 4., verify_chain()

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 13 - "App Configuration"
Cohesion: 0.22
Nodes (7): AsyncSession, Shared settings loaded from .env (or environment variables). Every service impor, Settings, get_db(), DB Session — async SQLAlchemy session factory.  CONCEPT: A "session" is a unit o, FastAPI dependency — yields a DB session for the duration of a request.      The, BaseSettings

### Community 15 - "Face Service Router"
Cohesion: 0.67
Nodes (3): _bytes_to_numpy_image(), Convert raw byte stream to RGB NumPy array., ndarray

### Community 22 - "extraction.py"
Cohesion: 0.25
Nodes (10): Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi, LLM Fallback — Pluggable Vision LLM interface for non-standard documents.  CONCE, Extraction Router — FastAPI endpoint for document OCR extraction.  FLOW:   1. Re, DocumentType, ExtractionMethod, Pydantic schemas for the OCR Service.  CONCEPT: Pydantic schemas serve two purpo, WHY Enum instead of plain str?     If a caller sends document_type="pasport" (ty, Tracks HOW a field was extracted — critical for debugging and audit. (+2 more)

### Community 24 - "extract_document"
Cohesion: 0.22
Nodes (10): extract_fields(), extract_raw_ocr_lines(), get_ocr_reader(), ExtractedField, Extract structured fields from image bytes., Singleton lazy-loader for EasyOCR reader., Extract raw text lines and confidences using EasyOCR., extract_document() (+2 more)

### Community 25 - "ExtractedField"
Cohesion: 0.32
Nodes (7): ExtractedField, One extracted field from a document.     e.g. {"field_name": "date_of_expiry", ", Phase 1 Smoke Tests — Validation Service & MRZ checksum testing., Test valid passport fields passing all YAML rules., Test expired passport failing expiry_not_passed rule., test_validation_engine_expired_passport(), test_validation_engine_valid_passport()

### Community 26 - "_validate_check_digit"
Cohesion: 0.40
Nodes (6): _compute_check_digit(), Compute ICAO 9303 check digit using repeating weights [7, 3, 1]., Return True if the computed check digit matches the expected one., _validate_check_digit(), Test ICAO 9303 checksum computation with standard test vectors.     Example DOB:, test_icao_mrz_checksum_calculation()

### Community 27 - "ExtractionResponse"
Cohesion: 0.40
Nodes (5): ExtractionError, ExtractionResponse, BaseModel, The complete response from POST /extract.      WHY include extraction_method at, WHY a typed error response?     The orchestrator needs to distinguish between:

### Community 28 - "extract_fields_with_llm"
Cohesion: 0.50
Nodes (4): extract_fields_with_llm(), Generic interface for vision-capable LLM document extraction.      Args:, DocumentType, ExtractedField

## Knowledge Gaps
- **54 isolated node(s):** `backend`, `Getting Started`, `Learn More`, `Deploy on Vercel`, `geistSans` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DocumentType` connect `extraction.py` to `extract_document`, `ExtractedField`, `Next.js Branding Assets`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `ExtractedField` connect `ExtractedField` to `extract_document`, `ExtractionResponse`, `Next.js Branding Assets`, `extraction.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `DocumentType` (e.g. with `RuleResult` and `ValidationRequest`) actually correct?**
  _`DocumentType` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ExtractedField` (e.g. with `RuleResult` and `ValidationRequest`) actually correct?**
  _`ExtractedField` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Shared settings loaded from .env (or environment variables). Every service impor`, `LLM Fallback — Pluggable Vision LLM interface for non-standard documents.  CONCE`, `Generic interface for vision-capable LLM document extraction.      Args:` to the rest of the system?**
  _114 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06970128022759602 - nodes in this community are weakly interconnected._
- **Should `Frontend Package Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.10476190476190476 - nodes in this community are weakly interconnected._