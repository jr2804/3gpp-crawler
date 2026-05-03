<!-- refreshed: 2026-05-03 -->
# Architecture

**Analysis Date:** 2026-05-03

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLI Layer (Typer)                              │
├───────────────────┬──────────────────┬──────────────────────────────────┤
│  tdoc-crawler     │  spec-crawler    │  3gpp-crawler                    │
│  `cli/tdoc_app`   │  `cli/spec_app`  │  `cli/mgmt_app`                  │
│  TDocs + Meetings │  Specs           │  Config + Workspaces             │
└────────┬──────────┴────────┬─────────┴──────────────┬───────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Operations Layer                                 │
├───────────────────┬──────────────────┬──────────────────────────────────┤
│  tdocs/operations │ meetings/ops     │ specs/operations                 │
│  crawl, fetch,    │ crawl            │ checkout                         │
│  checkout         │                  │                                  │
└────────┬──────────┴────────┬─────────┴──────────────┬───────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Source Adapters + Clients                           │
│  tdocs/sources/   │  meetings/       │  specs/sources/                 │
│  (DocList, WTS,   │  sources/        │  (3GPP, WTS)                    │
│   Portal)         │                  │                                  │
│                   │  clients/        │                                  │
│                   │  (PortalClient)  │                                  │
└────────┬──────────┴──────────────────┴──────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                               │
├──────────────────┬───────────────────┬──────────────────────────────────┤
│  database/       │  http_client/     │  config/                         │
│  (SQLite/Oxyde)  │  (niquests+       │  (CacheManager,                  │
│  DocDatabase →   │   hishel cache)   │   ThreeGPPConfig)                │
│  TDocDB,SpecDB,  │                   │                                  │
│  MeetingDB       │  parsers/         │  constants/                      │
│                  │  (HTML, Portal)   │  (URLs, patterns)                │
├──────────────────┼───────────────────┼──────────────────────────────────┤
│  extraction/     │  workspaces/      │  models/                         │
│  (PDF→MD,        │  (CRUD, members)  │  (WG records,                    │
│   OpenDataLoader)│                   │   base types)                    │
└──────────────────┴───────────────────┴──────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  External Services + Storage                            │
│  3GPP FTP      │  WhatTheSpec API  │  3GPP Portal (EOL auth)           │
│  LibreOffice    │  OpenDataLoader   │  PDF Remote Converter             │
│  SQLite DB      │  Filesystem cache │                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `tdoc_app` | TDoc/Meeting CLI entry point | `src/tdoc_crawler/cli/tdoc_app.py` |
| `spec_app` | Spec CLI entry point | `src/tdoc_crawler/cli/spec_app.py` |
| `mgmt_app` | Config + Workspace CLI entry point | `src/tdoc_crawler/cli/mgmt_app.py` |
| `TDocCrawler` | Orchestrates TDoc crawl via parallel workers | `src/tdoc_crawler/tdocs/operations/crawl.py` |
| `MeetingCrawler` | Orchestrates meeting crawl | `src/tdoc_crawler/meetings/operations/crawl.py` |
| `TDocDatabase` | All TDoc + Meeting DB operations | `src/tdoc_crawler/database/tdocs.py` |
| `SpecDatabase` | Spec DB + crawl-from-sources | `src/tdoc_crawler/database/specs.py` |
| `DocDatabase` | Base DB class (Oxyde ORM, schema init) | `src/tdoc_crawler/database/base.py` |
| `CacheManager` | Single source of truth for all paths | `src/tdoc_crawler/config/cache_manager.py` |
| `ThreeGPPConfig` | pydantic-settings configuration | `src/tdoc_crawler/config/settings.py` |
| `create_cached_session` | HTTP session factory with hishel caching | `src/tdoc_crawler/http_client/session.py` |
| `PortalClient` | 3GPP EOL portal authentication | `src/tdoc_crawler/clients/portal.py` |
| `ExtractionProfile` | PDF-only / default / advanced tiers | `src/tdoc_crawler/extraction/profiles.py` |
| `convert_for_wiki` | Workspace member extraction pipeline | `src/tdoc_crawler/extraction/convert.py` |
| `Workspace CRUD` | Workspace create/delete/list/activate | `src/tdoc_crawler/workspaces/crud.py` |
| `workspace members` | Member add/remove/list/deactivate | `src/tdoc_crawler/workspaces/members.py` |
| `WorkspaceRegistry` | JSON-based workspace persistence | `src/tdoc_crawler/config/workspace_registry.py` |
| `args` | Typer Annotated type definitions | `src/tdoc_crawler/cli/args.py` |

## Pattern Overview

**Overall:** Domain-oriented modular CLI application with thin CLI layer delegating to library packages.

**Key Characteristics:**
- Three separate CLI entry points sharing one core library
- Async database layer with async context managers (`async with`)
- Protocol-based source abstraction (`TDocSource`, `SpecSource`)
- Global singleton `CacheManager` for path resolution
- Parallel crawling via `pool-executors` (multiprocessing or serial)

## Layers

### CLI Layer
- Purpose: Typer command definitions, Rich output, argument parsing
- Location: `src/tdoc_crawler/cli/`
- Contains: Typer apps, Annotated option/argument types, output formatting
- Depends on: Operations layer, database, config, extraction
- Used by: End user via console entry points

**Critical rule:** CLI contains ONLY Typer/Rich wrappers. All logic belongs in the core library. Never duplicate core logic in CLI.

### Operations Layer
- Purpose: Domain-specific business logic (crawl, fetch, checkout)
- Location: `src/tdoc_crawler/tdocs/operations/`, `src/tdoc_crawler/meetings/operations/`, `src/tdoc_crawler/specs/operations/`
- Contains: Crawler orchestrators, fetch strategies, checkout workflows
- Depends on: Source adapters, database, config, HTTP client
- Used by: CLI layer

### Source Adapters
- Purpose: Abstract different data sources behind protocols
- Location: `src/tdoc_crawler/tdocs/sources/`, `src/tdoc_crawler/specs/sources/`
- Contains: `TDocSource` implementations (DocList, WhatTheSpec, Portal), `SpecSource` implementations
- Depends on: HTTP client, parsers, models
- Used by: Operations layer, workers

### Database Layer
- Purpose: SQLite persistence via Oxyde ORM
- Location: `src/tdoc_crawler/database/`
- Contains: `DocDatabase` base, `TDocDatabase`, `MeetingDatabase`, `SpecDatabase`, Oxyde models
- Depends on: Oxyde ORM, models
- Used by: Operations layer, CLI (for queries)

### Extraction Pipeline
- Purpose: Document conversion (Office→PDF→Markdown) for AI/LLM consumption
- Location: `src/tdoc_crawler/extraction/`
- Contains: LibreOffice conversion, OpenDataLoader PDF extraction, hybrid server management, metrics
- Depends on: `convert-lo` package, `opendataloader-pdf`, workspace models
- Used by: CLI workspace process command

### Workspace Management
- Purpose: Named collections of documents for batch extraction
- Location: `src/tdoc_crawler/workspaces/`
- Contains: Workspace CRUD, member management, workspace utils
- Depends on: Models, CacheManager, workspace registry (JSON file)
- Used by: CLI workspace commands

## Data Flow

### Primary Crawl Path (TDocs)

1. CLI `crawl_tdocs()` receives args (`src/tdoc_crawler/cli/crawl.py`)
2. `load_cli_config()` initializes `ThreeGPPConfig` (`src/tdoc_crawler/cli/config.py`)
3. `TDocDatabase` opens SQLite connection (`src/tdoc_crawler/database/tdocs.py`)
4. `TDocCrawler.crawl()` queries meetings, creates parallel workers (`src/tdoc_crawler/tdocs/operations/crawl.py`)
5. Workers fetch document lists from 3GPP FTP via `fetch_meeting_document_list_subinterpreter()` (`src/tdoc_crawler/workers/tdoc_worker.py`)
6. Results parsed into `TDocMetadata` models, bulk upserted to DB
7. Progress reported via Rich progress bar back to CLI

### Spec Crawl Path

1. CLI `crawl_specs()` receives args (`src/tdoc_crawler/cli/crawl.py`)
2. `SpecDatabase.crawl_from_sources()` orchestrates multi-source fetching (`src/tdoc_crawler/database/specs.py`)
3. Sources: `fetch_threegpp_metadata()` (primary, 3gpp.org), `fetch_whatthespec_metadata()` (fallback)
4. Spec records upserted, versions and source records stored

### Workspace Process Path

1. CLI `workspace_process()` resolves workspace name (`src/tdoc_crawler/cli/_workspace_commands.py`)
2. Lists active members via `list_workspace_members()` (`src/tdoc_crawler/workspaces/members.py`)
3. For each member: `convert_for_wiki()` orchestrates extraction (`src/tdoc_crawler/extraction/convert.py`)
4. Extraction: checkout files → ensure PDF → run OpenDataLoader → write Markdown/JSON artifacts
5. Artifacts stored under `{workspaces_dir}/{name}/sources/{member_id}/`

### TDoc Checkout Path

1. CLI `checkout()` normalizes TDoc IDs (`src/tdoc_crawler/cli/tdoc_app.py`)
2. `fetch_missing_tdocs()` checks DB, falls back to WhatTheSpec/Portal sources (`src/tdoc_crawler/tdocs/operations/fetch.py`)
3. `checkout_tdoc()` downloads ZIP, extracts main document (`src/tdoc_crawler/tdocs/operations/checkout.py`)
4. Files saved to `CacheManager.checkout_dir`

**State Management:**
- SQLite database for persistent metadata (TDocs, Meetings, Specs, Crawl Logs)
- JSON workspace registry file for workspace definitions and active workspace
- Filesystem cache for downloaded/extracted documents
- HTTP cache (SQLite via hishel) for web request caching

## Key Abstractions

**TDocSource Protocol:**
- Purpose: Abstract TDoc metadata fetching from different backends
- Definition: `src/tdoc_crawler/tdocs/sources/base.py`
- Implementations: `DocumentListSource`, `WhatTheSpecSource`, `PortalSource`
- Methods: `fetch_by_id()`, `fetch_by_meeting()`, `source_name`, `requires_authentication`

**SpecSource Protocol:**
- Purpose: Abstract spec metadata fetching from different backends
- Definition: `src/tdoc_crawler/specs/sources/base.py`
- Implementations: `FunctionSpecSource` wrapper around `fetch_threegpp_metadata`, `fetch_whatthespec_metadata`
- Method: `fetch(spec_number)`

**DocDatabase Hierarchy:**
- Purpose: Layered database access with inheritance
- Definition: `src/tdoc_crawler/database/base.py`
- Hierarchy: `DocDatabase` → `MeetingDatabase` → `TDocDatabase` (unified), separate `SpecDatabase(DocDatabase)`
- Pattern: Async context manager with Oxyde ORM

**CacheManager Singleton:**
- Purpose: Centralized path resolution, no hardcoded paths
- Definition: `src/tdoc_crawler/config/cache_manager.py`
- Pattern: Module-level singleton registered at app startup via `register()`
- Properties: `root`, `db_file`, `http_cache_file`, `checkout_dir`, `workspaces_dir`, `workspace_registry_file`

**ThreeGPPConfig (pydantic-settings):**
- Purpose: Type-safe configuration from files, env vars, defaults
- Definition: `src/tdoc_crawler/config/settings.py`
- Sub-models: `PathConfig`, `HttpConfig`, `CredentialsConfig`, `CrawlConfig`
- Alias: `TDocCrawlerConfig`

## Entry Points

**`tdoc-crawler` (TDoc/Meeting CLI):**
- Location: `src/tdoc_crawler/cli/tdoc_app.py:tdoc_app`
- Defined in: `pyproject.toml` → `[project.scripts]`
- Commands: crawl, crawl-meetings, query, query-meetings, open, checkout, stats

**`spec-crawler` (Spec CLI):**
- Location: `src/tdoc_crawler/cli/spec_app.py:spec_app`
- Defined in: `pyproject.toml` → `[project.scripts]`
- Commands: crawl, query, checkout, open

**`3gpp-crawler` (Management CLI):**
- Location: `src/tdoc_crawler/cli/mgmt_app.py:mgmt_app`
- Defined in: `pyproject.toml` → `[project.scripts]`
- Sub-apps: config (init, show), workspace (create, list, activate, deactivate, delete, members, add, process, clear-invalid)

## Architectural Constraints

- **Async model:** All database operations are async (`async with`, `await`). CLI bridges via `asyncio.run()`.
- **Global state:** `CacheManager` uses module-level singleton (`_instance` class variable). Registered once at startup, resolved everywhere via `resolve_cache_manager()`.
- **Circular imports:** Prevented by keeping domain packages (`tdocs/`, `meetings/`, `specs/`) from re-exporting operations. Shared types live in `models/` layer.
- **Threading:** Crawling uses `pool-executors` (multiprocessing or serial) via `concurrent.futures`. Workers run `fetch_meeting_document_list_subinterpreter()` in separate processes.
- **Import direction:** CLI → Core. Core submodules → Common layer (`models/`). Never Core → CLI.
- **HTTP caching:** All HTTP requests MUST use `create_cached_session()` from `tdoc_crawler.http_client`. Never use raw `requests` or `niquests` directly.

## Anti-Patterns

### Hardcoded Paths

**What happens:** Using `Path.home() / ".3gpp-crawler"` or similar hardcoded paths
**Why it's wrong:** Breaks testability, configurability, and the single-source-of-truth principle
**Do this instead:** Use `resolve_cache_manager()` from `src/tdoc_crawler/config/cache_manager.py` everywhere

### Logic in CLI

**What happens:** Business logic (DB queries, data transformation, HTTP calls) implemented in CLI command handlers
**Why it's wrong:** CLI is a thin wrapper. Logic can't be reused by library consumers or tested independently
**Do this instead:** Implement in core library (`tdocs/`, `specs/`, `database/`, etc.), import and call from CLI

### Inline Imports

**What happens:** `import` statements inside function bodies (PLC0415)
**Why it's wrong:** Violates project linting rules, hides dependency graph, degrades performance
**Do this instead:** All imports at module top level

### Code Duplication Across Domains

**What happens:** Similar patterns (normalization, validation, DB queries) copied between `tdocs/`, `specs/`, `meetings/`
**Why it's wrong:** Increases maintenance burden, leads to inconsistent behavior
**Do this instead:** Search before implementing. Refactor existing code in `utils/`, `models/`, or `database/` rather than duplicating.

## Error Handling

**Strategy:** Typed exceptions with structured error propagation.

**Patterns:**
- `DatabaseError` with machine-readable error codes (`src/tdoc_crawler/database/errors.py`)
- `AiError` hierarchy: `TDocNotFoundError`, `ConversionError`, `WorkspaceNotFoundError` (`src/tdoc_crawler/models/workspaces.py`)
- `PortalAuthenticationError` for EOL auth failures (`src/tdoc_crawler/clients/portal.py`)
- CLI catches exceptions and presents user-friendly Rich output with `[red]` styling
- Crawlers collect errors into lists, continue processing, report summary at end

## Cross-Cutting Concerns

**Logging:** Rich-based logging via `src/tdoc_crawler/logging/__init__.py`. `get_logger(__name__)` everywhere. Verbosity controlled by `--verbosity` CLI flag. Root logger configured with `RichHandler`.

**Validation:** Pydantic models for all data structures. Oxyde ORM models for DB persistence. Typer validates CLI args at entry. `normalize_tdoc_id()` ensures consistent TDoc ID casing (upper).

**Authentication:** EOL credentials via `TDC_EOL_USERNAME`/`TDC_EOL_PASSWORD` env vars, `--eol-username`/`--eol-password` CLI flags, or interactive prompt. Stored in `CredentialsConfig`. Applied via `set_credentials()` (`src/tdoc_crawler/credentials.py`).

**Configuration:** ThreeGPPConfig from pydantic-settings. Sources: TOML config files (discovered or explicit), env vars (`TDC_*` prefix), CLI flags. Precedence: CLI > config file > env vars > defaults.

**HTTP Caching:** hishel SQLite-backed cache. `create_cached_session()` returns context-managed `niquests.Session` with `CacheAdapter`. Configurable TTL, refresh-on-access, SSL verify.

---

*Architecture analysis: 2026-05-03*
