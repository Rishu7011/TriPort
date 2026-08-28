# Graph Report - .  (2026-08-28)

## Corpus Check
- Corpus is ~2,589 words - fits in a single context window. You may not need a graph.

## Summary
- 249 nodes · 237 edges · 60 communities (53 shown, 7 thin omitted)
- Extraction: 89% EXTRACTED · 10% INFERRED · 1% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

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
- Window Icon Assets
- Audit Ledger Router
- App Layout
- App Configuration
- Vercel Branding
- Face Service Router
- OCR Extraction Router
- Tampering Router
- Agent Rules Docs
- ESLint Config
- Next Config
- Next Env Types
- PostCSS Config

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `orchestrator` - 12 edges
3. `Shared Backend Requirements` - 10 edges
4. `FastAPI Microservices Backend` - 9 edges
5. `get_logger()` - 8 edges
6. `configure_logging()` - 7 edges
7. `include` - 7 edges
8. `scripts` - 5 edges
9. `Path Shape Element` - 5 edges
10. `Wireframe Globe Icon` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Shared Backend venv` --semantically_similar_to--> `Shared Backend Docker Image`  [INFERRED] [semantically similar]
  backend/requirements.txt → docker-compose.yml
- `JWT and Password Auth Stack` --conceptually_related_to--> `orchestrator`  [AMBIGUOUS]
  backend/requirements.txt → docker-compose.yml
- `Next.js Officer Dashboard` --semantically_similar_to--> `Next.js Project`  [INFERRED] [semantically similar]
  docker-compose.yml → frontend/README.md
- `FastAPI Web Framework Stack` --conceptually_related_to--> `FastAPI Microservices Backend`  [INFERRED]
  backend/requirements.txt → docker-compose.yml
- `Inter-Service HTTP Client` --conceptually_related_to--> `orchestrator`  [INFERRED]
  backend/requirements.txt → docker-compose.yml

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **FastAPI Backend Microservices** — docker_compose_yml_ocr_service, docker_compose_yml_validation_service, docker_compose_yml_tampering_service, docker_compose_yml_face_service, docker_compose_yml_risk_engine, docker_compose_yml_audit_ledger, docker_compose_yml_orchestrator [EXTRACTED 1.00]
- **Phased Backend Capabilities** — backend_requirements_txt_ocr_phase_1, backend_requirements_txt_tampering_phase_2, backend_requirements_txt_face_phase_2, backend_requirements_txt_encryption_phase_4 [EXTRACTED 1.00]
- **Orchestrator Service Coordination Flow** — docker_compose_yml_orchestrator, docker_compose_yml_ocr_service, docker_compose_yml_validation_service, docker_compose_yml_tampering_service, docker_compose_yml_face_service, docker_compose_yml_risk_engine, docker_compose_yml_audit_ledger, docker_compose_yml_postgres, docker_compose_yml_minio [EXTRACTED 1.00]
- **SVG Document Structure** — frontend_public_globe_globe_svg, frontend_public_globe_globe_path, frontend_public_globe_svg_clip_path [EXTRACTED 1.00]
- **Next.js Branding Identity** — frontend_public_next_nextjs_wordmark, frontend_public_next_nextjs_framework, frontend_public_next_branding_logo_purpose [INFERRED 0.85]
- **Window Icon Visual Composition** — frontend_public_window_browser_window_icon, frontend_public_window_window_frame, frontend_public_window_content_dots, frontend_public_window_gray_monochrome_style [EXTRACTED 0.95]

## Communities (60 total, 7 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.08
Nodes (14): Audit Ledger — hash-chained append-only event log., Face Service — 1:1 verification and 1:N deduplication using face embeddings., configure_logging(), get_logger(), Shared structured logging setup. Call configure_logging() at service startup., OCR Service — extracts structured fields from identity documents., Risk Engine — combines all module signals into a weighted risk score., Phase 3 stub — risk scoring. Full implementation in Phase 3. (+6 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.10
Nodes (20): dependencies, next, react, react-dom, ignoreScripts, name, packageManager, private (+12 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.10
Nodes (21): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+13 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.18
Nodes (20): Shared Backend Requirements, JWT and Password Auth Stack, PostgreSQL Database Stack, Encryption Phase 4, Face Verification Phase 2, Inter-Service HTTP Client, MinIO Object Storage Client, OCR and Document Processing Phase 1 (+12 more)

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+9 more)

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.21
Nodes (11): Homepage Header Branding Logo, create-next-app Default Starter Asset, Fill Color #000, Next.js Framework Brand, Next.js Wordmark Logo, Primary Path Shape (NEXT Letters), Secondary Path Shape (.js Suffix), Frontend Public Static Asset (+3 more)

### Community 6 - "File Icon Assets"
Cohesion: 0.20
Nodes (10): Document File Icon, Fill Color #666, Folded Corner Detail, Path Shape Element, Frontend Public Static Asset, SVG Document Root, SVG Namespace (xmlns), Text Line Indicators (+2 more)

### Community 7 - "TypeScript Project Config"
Cohesion: 0.20
Nodes (9): exclude, include, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts (+1 more)

### Community 8 - "Project Overview Docs"
Cohesion: 0.25
Nodes (9): Shared Backend venv, Docker Compose Stack, frontend, Next.js Officer Dashboard, Shared Backend Docker Image, Frontend README, create-next-app Bootstrap, Next.js Project (+1 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.28
Nodes (8): Earth / World Symbol, Gray Fill (#666), Globe Path Geometry, Internationalization UI Purpose, Static Public Asset, SVG Clip Path, 16×16 ViewBox, Wireframe Globe Icon

### Community 10 - "Window Icon Assets"
Cohesion: 0.29
Nodes (7): Next.js Public Static Assets Directory, 16x16 ViewBox Icon Size, Browser Window Icon, Three Horizontal Content Dots, Gray Monochrome Fill (#666), Next.js Create-Next-App Starter Icon, Rounded Window Frame

### Community 11 - "Audit Ledger Router"
Cohesion: 0.40
Nodes (4): append_event(), Phase 4A stub — chain integrity verification. Full implementation in Phase 4., Phase 4A stub — ledger event append. Full implementation in Phase 4., verify_chain()

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 13 - "App Configuration"
Cohesion: 0.50
Nodes (3): Shared settings loaded from .env (or environment variables). Every service impor, Settings, BaseSettings

### Community 14 - "Vercel Branding"
Cohesion: 0.67
Nodes (3): White upward-pointing triangle, Vercel Logomark, Vercel deployment platform

### Community 18 - "Agent Rules Docs"
Cohesion: 0.67
Nodes (3): Next.js Agent Rules, Next.js Breaking Changes Warning, Claude Agent Rules

## Ambiguous Edges - Review These
- `JWT and Password Auth Stack` → `orchestrator`  [AMBIGUOUS]
  backend/requirements.txt · relation: conceptually_related_to
- `Encryption Phase 4` → `audit-ledger`  [AMBIGUOUS]
  backend/requirements.txt · relation: conceptually_related_to
- `Wireframe Globe Icon` → `Internationalization UI Purpose`  [AMBIGUOUS]
  frontend/public/globe.svg · relation: conceptually_related_to

## Knowledge Gaps
- **74 isolated node(s):** `geistSans`, `geistMono`, `metadata`, `eslintConfig`, `nextConfig` (+69 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `JWT and Password Auth Stack` and `orchestrator`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Encryption Phase 4` and `audit-ledger`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Wireframe Globe Icon` and `Internationalization UI Purpose`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `devDependencies` connect `Dev Tooling Dependencies` to `Frontend Package Dependencies`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Why does `compilerOptions` connect `TypeScript Compiler Config` to `TypeScript Project Config`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `Audit Ledger — hash-chained append-only event log.`, `Phase 4A stub — ledger event append. Full implementation in Phase 4.`, `Phase 4A stub — chain integrity verification. Full implementation in Phase 4.` to the rest of the system?**
  _91 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.0773109243697479 - nodes in this community are weakly interconnected._