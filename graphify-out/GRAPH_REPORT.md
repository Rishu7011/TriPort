# Graph Report - BorderGuard-AI  (2026-08-29)

## Corpus Check
- 39 files · ~8,597 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 256 nodes · 367 edges · 24 communities (18 shown, 6 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `24a61959`
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
- PostCSS Config

## God Nodes (most connected - your core abstractions)
1. `DocumentType` - 18 edges
2. `ExtractedField` - 16 edges
3. `compilerOptions` - 16 edges
4. `validate_document()` - 14 edges
5. `Base` - 11 edges
6. `extract_document()` - 10 edges
7. `ValidationResponse` - 9 edges
8. `extract_fields()` - 8 edges
9. `ExtractionMethod` - 8 edges
10. `get_logger()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `extract_document()` --calls--> `parse_mrz()`  [EXTRACTED]
  backend/ocr_service/routers/extraction.py → backend/ocr_service/core/mrz_parser.py
- `RuleResult` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationRequest` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `ValidationResponse` --uses--> `DocumentType`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py
- `RuleResult` --uses--> `ExtractedField`  [INFERRED]
  backend/validation_service/schemas/validation.py → backend/ocr_service/schemas/extraction.py

## Import Cycles
- None detected.

## Communities (24 total, 6 thin omitted)

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
Cohesion: 0.07
Nodes (53): Any, extract_fields(), extract_raw_ocr_lines(), get_ocr_reader(), ExtractedField, Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi, Extract structured fields from image bytes., Singleton lazy-loader for EasyOCR reader. (+45 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.21
Nodes (13): _compute_check_digit(), parse_mrz(), parse_mrz_from_text_lines(), MRZ Parser — Robust MRZ line detection and ICAO 9303 checksum validation.  Works, Parse MRZ from OCR text lines first, falling back to PassportEye if available., Compute ICAO 9303 check digit using repeating weights [7, 3, 1]., Return True if the computed check digit matches the expected one., Directly parse MRZ lines from extracted OCR text lines.     This guarantees 100% (+5 more)

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

## Knowledge Gaps
- **54 isolated node(s):** `backend`, `Getting Started`, `Learn More`, `Deploy on Vercel`, `geistSans` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Are the 3 inferred relationships involving `DocumentType` (e.g. with `RuleResult` and `ValidationRequest`) actually correct?**
  _`DocumentType` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ExtractedField` (e.g. with `RuleResult` and `ValidationRequest`) actually correct?**
  _`ExtractedField` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Field Extractor — Robust document OCR using EasyOCR.  Extracts text boxes, confi`, `Singleton lazy-loader for EasyOCR reader.`, `Convert raw byte stream to RGB NumPy array.` to the rest of the system?**
  _114 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06970128022759602 - nodes in this community are weakly interconnected._
- **Should `Frontend Package Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.10476190476190476 - nodes in this community are weakly interconnected._
- **Should `TypeScript Compiler Config` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Should `Docker Infrastructure Stack` be split into smaller, more focused modules?**
  _Cohesion score 0.14761904761904762 - nodes in this community are weakly interconnected._