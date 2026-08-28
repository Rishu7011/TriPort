# Graph Report - BorderGuard-AI  (2026-08-29)

## Corpus Check
- 24 files · ~2,005 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 141 nodes · 144 edges · 19 communities (14 shown, 5 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a7b1e22a`
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
- Audit Ledger Router
- App Layout
- App Configuration
- Face Service Router
- ESLint Config
- Next Config
- PostCSS Config

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `get_logger()` - 8 edges
3. `configure_logging()` - 7 edges
4. `include` - 7 edges
5. `scripts` - 5 edges
6. `lib` - 4 edges
7. `ignoreScripts` - 3 edges
8. `trustedDependencies` - 3 edges
9. `append_event()` - 2 edges
10. `verify_chain()` - 2 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (19 total, 5 thin omitted)

### Community 0 - "FastAPI Service Layer"
Cohesion: 0.11
Nodes (11): Face Service — 1:1 verification and 1:N deduplication using face embeddings., configure_logging(), get_logger(), Shared structured logging setup. Call configure_logging() at service startup., OCR Service — extracts structured fields from identity documents., extract_fields(), Phase 1A stub — OCR extraction. Full implementation in Phase 1., Tampering Service — ELA, metadata forensics, boundary analysis, stamp matching. (+3 more)

### Community 1 - "Frontend Package Dependencies"
Cohesion: 0.16
Nodes (13): ignoreScripts, name, packageManager, private, scripts, build, dev, lint (+5 more)

### Community 2 - "TypeScript Compiler Config"
Cohesion: 0.10
Nodes (21): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+13 more)

### Community 3 - "Docker Infrastructure Stack"
Cohesion: 0.29
Nodes (3): Risk Engine — combines all module signals into a weighted risk score., Phase 3 stub — risk scoring. Full implementation in Phase 3., score()

### Community 4 - "Dev Tooling Dependencies"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+9 more)

### Community 5 - "Next.js Branding Assets"
Cohesion: 0.29
Nodes (3): Validation Service — evaluates extracted fields against document rules., Phase 1B stub — rules validation. Full implementation in Phase 1., validate()

### Community 6 - "File Icon Assets"
Cohesion: 0.29
Nodes (7): dependencies, next, react, react-dom, next, react, react-dom

### Community 7 - "TypeScript Project Config"
Cohesion: 0.20
Nodes (9): exclude, include, **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts (+1 more)

### Community 9 - "Globe Icon Assets"
Cohesion: 0.50
Nodes (3): Deploy on Vercel, Getting Started, Learn More

### Community 11 - "Audit Ledger Router"
Cohesion: 0.22
Nodes (5): Audit Ledger — hash-chained append-only event log., append_event(), Phase 4A stub — chain integrity verification. Full implementation in Phase 4., Phase 4A stub — ledger event append. Full implementation in Phase 4., verify_chain()

### Community 12 - "App Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 13 - "App Configuration"
Cohesion: 0.50
Nodes (3): Shared settings loaded from .env (or environment variables). Every service impor, Settings, BaseSettings

## Knowledge Gaps
- **53 isolated node(s):** `Getting Started`, `Learn More`, `Deploy on Vercel`, `geistSans`, `geistMono` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `Dev Tooling Dependencies` to `Frontend Package Dependencies`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `compilerOptions` connect `TypeScript Compiler Config` to `TypeScript Project Config`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `get_logger()` connect `FastAPI Service Layer` to `Docker Infrastructure Stack`, `Audit Ledger Router`, `Next.js Branding Assets`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `Audit Ledger — hash-chained append-only event log.`, `Phase 4A stub — ledger event append. Full implementation in Phase 4.`, `Phase 4A stub — chain integrity verification. Full implementation in Phase 4.` to the rest of the system?**
  _68 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.11067193675889328 - nodes in this community are weakly interconnected._
- **Should `TypeScript Compiler Config` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Should `Dev Tooling Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._