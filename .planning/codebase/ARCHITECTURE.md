<!-- refreshed: 2026-05-03 -->
# Architecture

**Analysis Date:** 2026-05-03

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                               CLI Layer (thin)                               │
├──────────────────────┬───────────────────────┬──────────────────────────────┤
│    tdoc-crawler       │     spec-crawler       │     3gpp-crawler             │
│  `cli/tdoc_app.py`    │  `cli/spec_app.py`     │  `cli/mgmt_app.py`           │
│  TDocs + Meetings     │  Specs only            │  Config + Workspaces         │
└──────────┬───────────┴───────────┬───────────┴──────────────┬───────────────┘
           │                       │                          │
           ▼                       ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Domain Operations Layer                               │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────┤
│ `tdocs/`     │ `meetings/`  │  `specs/`    │`extraction/` │ `workspaces/`   │
│  sources/    │  sources/    │  sources/    │  convert.py  │  crud.py        │
│  operations/ │  operations/ │  operations/ │  profiles.py │  members.py     │
│  models.py   │  models.py   │  models.py   │  fetch_*.py  │  utils.py       │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴────────┬────────┘
       │              │              │              │                │
       ▼              ▼              ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Infrastructure Layer                                │
├────────────────────┬───────────────────┬──────────────────┬─────────────────┤
│ `http_client/`     │  `config/`        │  `database/`     │  `clients/`     │
│  session.py        │  settings.py      │  base.py         │  portal.py      │
│  (hishel cache)    │  cache_manager.py │  tdocs.py        │                 │
│                    │  sources.py       │  meetings.py     │                 │
│                    │  (config files)   │  specs.py        │                 │
├────────────────────┴───────────────────┴──────────────────┴─────────────────┤
│ `models/`  `parsers/`  `utils/`  `workers/`  `constants/`  `logging/`      │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Storage                                                                     │
│  `~/.3gpp-crawler/`                                                          │
│  ├── 3gpp_crawler.db          (SQLite via Oxyde ORM)                         │
│  ├── http-cache.sqlite3        (hishel HTTP cache)                           │
│  ├── checkout/                 (raw downloaded docs)                          │
│  └── workspaces/              (processed artifacts)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `tdoc_app.py` | TDoc/Meeting CLI commands (crawl, query, checkout) | `src/tdoc_crawler/cli/tdoc_app.py` |
| `spec_app.py` | Spec CLI commands (crawl, query, checkout, open) | `src/tdoc_crawler/cli/spec_app.py` |
| `mgmt_app.py` | Config and workspace management CLI | `src/tdoc_crawler/cli/mgmt_app.py` |
| `CacheManager` | Singleton file-system path resolver | `src/tdoc_crawler/config/cache_manager.py` |
| `ThreeGPPConfig` | Pydantic-settings configuration hierarchy | `src/tdoc_crawler/config/settings.py` |
| `TDocDatabase` | TDoc/meeting persistence (extends MeetingDatabase) | `src/tdoc_crawler/database/tdocs.py` |
| `SpecDatabase` | Spec persistence | `src/tdoc_crawler/database/specs.py` |
| `MeetingDatabase` | Meeting persistence (extends DocDatabase) | `src/tdoc_crawler/database/meetings.py` |
| `DocDatabase` | Base database facade (Oxyde ORM lifecycle) | `src/tdoc_crawler/database/base.py` |
| `create_cached_session()` | Factory for hishel-cached HTTP sessions | `src/tdoc_crawler/http_client/session.py` |
| `TDocCrawler` | Parallel TDoc crawl orchestrator | `src/tdoc_crawler/tdocs/operations/crawl.py` |
| `TDocSource` | Protocol for TDoc metadata sources | `src/tdoc_crawler/tdocs/sources/base.py` |
| `SpecSource` | Protocol for spec metadata sources | `src/tdoc_crawler/specs/sources/base.py` |
| `WorkspaceRegistry` | JSON-backed workspace persistence | `src/tdoc_crawler/config/workspace_registry.py` |
| `HybridServerManager` | OpenDataLoader hybrid server lifecycle | `src/tdoc_crawler/extraction/hybrid_server.py` |

## Pattern Overview

**Overall:** Domain-Oriented Architecture with thin CLI wrappers

**Key Characteristics:**
- Three independent Typer CLI entry points sharing a common core library
- Domain modules (`tdocs/`, `meetings/`, `specs/`) each contain their own models, sources, and operations subdirectories
- Infrastructure (HTTP, config, database) is separated from domain logic
- Singleton `CacheManager` registered once at CLI startup, resolved everywhere via `resolve_cache_manager()`
- Protocol-based source abstraction allows multiple data sources per domain
- Oxyde ORM replaces pydantic-sqlite; database models are in `database/oxyde_models.py`
- UV workspace monorepo with two internal packages: `convert-lo` and `pool-executors`

## Layers

**CLI Layer:**
- Purpose: Typer command definitions, Rich console output, CLI argument parsing
- Location: `src/tdoc_crawler/cli/`
- Contains: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py`, `_workspace_commands.py`, `config_app.py`, `args.py`, `_shared.py`, `formatting.py`, `printing.py`
- Depends on: Domain operations, config, database
- Used by: End users via `tdoc-crawler`, `spec-crawler`, `3gpp-crawler` console scripts
- **Rule:** CLI is thin — all logic belongs in the core library. CLI only wraps Typer/Rich.

**Domain Operations Layer:**
- Purpose: Business logic for TDocs, Meetings, Specs, Workspaces, and document extraction
- Location: `src/tdoc_crawler/{tdocs,meetings,specs,workspaces,extraction}/`
- Contains: Domain models, source implementations (FTP, Portal, WhatTheSpec), crawl/checkout/fetch operations, document conversion pipeline
- Depends on: Infrastructure layer (config, database, HTTP client)
- Used by: CLI layer

**Infrastructure Layer:**
- Purpose: Cross-cutting technical concerns — HTTP caching, configuration, database persistence, portal authentication
- Location: `src/tdoc_crawler/{config,database,http_client,clients}/`
- Contains: `CacheManager`, `ThreeGPPConfig`, `DocDatabase`, `create_cached_session()`, `PortalClient`
- Depends on: External libraries (hishel, oxyde, niquests, pydantic-settings)
- Used by: Domain operations layer

**Shared/Support Layer:**
- Purpose: Shared models, parsing, normalization, constants, logging
- Location: `src/tdoc_crawler/{models,parsers,utils,constants,logging,workers}/`
- Contains: Base enums (`OutputFormat`, `SortOrder`), working group reference data, regex patterns, URL templates, date/time normalization, meeting/portal parsers, subinterpreter workers
- Depends on: minimal external dependencies
- Used by: Both domain and infrastructure layers

## Data Flow

### Primary TDoc Crawl Flow

1. CLI entry: `tdoc-crawler crawl --start-date 2016` → `tdoc_app.py:crawl_tdocs()` (`src/tdoc_crawler/cli/tdoc_app.py`)
2. CLI delegates to `cli/crawl.py:crawl_tdocs()` which orchestrates config loading, database opening, and crawl
3. Meeting crawl: `meetings/operations/crawl.py` → fetches meeting metadata via portal/Excel doclist
4. TDoc crawl: `TDocCrawler` in `tdocs/operations/crawl.py` → parallel workers via `pool_executors`
5. Each worker: `workers/tdoc_worker.py` → `fetch_meeting_document_list_subinterpreter()` → `tdocs/sources/doclist.py`
6. Source fetches Excel doclist from `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm` via `create_cached_session()`
7. Doclist parsed with pandas, TDocMetadata models created
8. Upsert to database: `TDocDatabase.upsert_tdoc()` → Oxyde ORM → SQLite (`~/.3gpp-crawler/3gpp_crawler.db`)

### Single TDoc Lookup Flow

1. CLI: `tdoc-crawler query S4-260109` → `cli/tdoc_app.py:query_tdocs()` → `cli/query.py`
2. Attempts primary source: `tdocs/sources/whatthespec.py:resolve_via_whatthespec()` — JSON API
3. Falls back to: `tdocs/sources/portal.py:PortalSource` — authenticated portal HTML parsing
4. Falls back to: `clients/portal.py:PortalClient` — direct portal AJAX endpoint
5. Result cached in database via `TDocDatabase`
6. Output formatted by `cli/formatting.py` or `cli/printing.py`

### Spec Crawl/Checkout Flow

1. CLI: `spec-crawler crawl` → `cli/spec_app.py` → `cli/crawl.py:crawl_specs()`
2. Sources resolved: `specs/sources/threegpp.py` (primary, portal dynareport) → `specs/sources/whatthespec.py` (fallback)
3. Metadata stored via `SpecDatabase` → Oxyde models (`Specification`, `SpecificationVersion`, `SpecificationSourceRecord`)
4. Checkout: `spec-crawler checkout 26260 --release 18` → `specs/operations/checkout.py:checkout_spec()`
5. Downloads from `https://www.3gpp.org/ftp/Specs/archive/{series}/{spec}/` via `SpecDownloads`
6. Release resolved to concrete 3-part version (e.g., `18.0.0`) via `resolve_spec_release()`

### Workspace Processing Flow

1. CLI: `3gpp-crawler workspace process --profile advanced` → `cli/_workspace_commands.py`
2. Workspace members iterated (TDocs + Specs) from `WorkspaceRegistry` JSON
3. Hybrid server pre-started if profile requires it: `extraction/hybrid_server.py`
4. For each member:
   - TDoc: `extraction/fetch_tdoc.py:fetch_tdoc_files()` → checkout/download → PDF conversion via `extraction/conversion.py` (LibreOffice or remote) → Markdown extraction via `extraction/convert.py:convert_document_to_markdown()` (OpenDataLoader hybrid)
   - Spec: `extraction/fetch_spec.py:fetch_spec_files()` → checkout/download → same conversion pipeline
5. Artifacts stored in `workspaces/{name}/sources/{doc-id}/` (never in checkout dirs)
6. Quality gates: `models/workspaces.py:ExtractionQualityStatus` (ok/partial/failed)

**State Management:**
- `CacheManager` — global singleton via class variable `_instance`; registered at CLI startup, resolved everywhere
- `WorkspaceRegistry` — JSON file (`workspaces.json`) in cache root; manages workspace definitions
- Database — SQLite via Oxyde ORM; async context managers (`async with database as db:`)

## Key Abstractions

**CacheManager:**
- Purpose: Single source of truth for all file-system paths
- Examples: `src/tdoc_crawler/config/cache_manager.py`
- Pattern: Singleton with explicit `.register()` / `resolve_cache_manager()`; raises `CacheManagerNotRegisteredError` if accessed before registration
- Provided paths: `root`, `db_file`, `http_cache_file`, `checkout_dir`, `workspaces_dir`
- **Rule:** Never hardcode `~/.3gpp-crawler`; always use `resolve_cache_manager()`

**ThreeGPPConfig:**
- Purpose: Type-safe hierarchical configuration (files + env vars + defaults)
- Examples: `src/tdoc_crawler/config/settings.py`
- Pattern: Pydantic-settings with nested models (`PathConfig`, `HttpConfig`, `CrawlConfig`, `CredentialsConfig`)
- Config discovery: 12 locations in precedence order (global → project → conf.d)
- **Precedence:** CLI args > Config file > Environment variables > Defaults

**Database Hierarchy:**
- Purpose: Domain-specific database operations with shared base
- Examples: `DocDatabase` → `MeetingDatabase` → `TDocDatabase` (in `database/base.py`, `database/meetings.py`, `database/tdocs.py`)
- Pattern: Async context managers (`__aenter__`/`__aexit__`) using Oxyde ORM
- Oxyde models in `database/oxyde_models.py`: `TDocMetadata`, `MeetingMetadata`, `Specification`, `SpecificationVersion`, `WorkingGroupRecord`, etc.

**Protocol-Based Sources:**
- Purpose: Abstract data sources behind protocols for polymorphism
- Examples: `tdocs/sources/base.py:TDocSource` (protocol), `specs/sources/base.py:SpecSource` (protocol)
- TDoc sources: `doclist.py` (Excel, batch), `whatthespec.py` (JSON API, single), `portal.py` (authenticated HTML, fallback)
- Spec sources: `threegpp.py` (portal dynareport, primary), `whatthespec.py` (JSON API, fallback)

**HTTP Caching:**
- Purpose: All HTTP requests cached via hishel SQLite backend
- Examples: `http_client/session.py:create_cached_session()`
- Pattern: Factory function → returns `niquests.Session` with `CacheAdapter` using `SyncSqliteStorage`
- **Rule:** ALL HTTP requests MUST use `create_cached_session()` — never raw `requests`/`niquests`

**Extraction Profiles:**
- Purpose: Three-tier document extraction pipeline
- Examples: `extraction/profiles.py:ExtractionProfile`
- Tiers: `pdf-only` → `default` (OpenDataLoader hybrid) → `advanced` (hybrid + AI descriptions)
- SourceKind branching: TDoc vs Spec path resolution differs (different checkout/fetch logic)

## Entry Points

**`tdoc-crawler` CLI:**
- Location: `pyproject.toml` → `tdoc_crawler.cli.tdoc_app:tdoc_app`
- Triggers: `tdoc-crawler <command>` from terminal
- Responsibilities: TDoc crawling, meeting crawling, TDoc querying, TDoc checkout/download

**`spec-crawler` CLI:**
- Location: `pyproject.toml` → `tdoc_crawler.cli.spec_app:spec_app`
- Triggers: `spec-crawler <command>` from terminal
- Responsibilities: Spec crawling, spec querying, spec checkout, spec open

**`3gpp-crawler` CLI:**
- Location: `pyproject.toml` → `tdoc_crawler.cli.mgmt_app:mgmt_app`
- Triggers: `3gpp-crawler <command>` from terminal
- Responsibilities: Config management (`config init/show/validate`), workspace management (`workspace create/delete/activate/deactivate/add/members/process`)

**Library import:**
- Location: `src/tdoc_crawler/__init__.py`
- Usage: `import tdoc_crawler` — provides `__version__`, `__author__`
- All submodules importable: `from tdoc_crawler.config import CacheManager`, `from tdoc_crawler.database import TDocDatabase`, etc.

## Architectural Constraints

- **Threading:** Subinterpreter-based parallelism via `aiointerpreters` for TDoc crawl workers (`workers/tdoc_worker.py`). Async/await for database operations (Oxyde async). LibreOffice conversions run sequentially (not thread-safe).
- **Global state:** `CacheManager._instance` — module-level singleton, registered once at CLI startup. `WorkspaceRegistry` — JSON file-backed state. Console singleton in `cli/_shared.py`.
- **Circular imports:** Avoided by design — `TYPE_CHECKING` discouraged; shared types extracted to `models/` neutral layer. Domain packages do not re-export operations.
- **Config immutability:** `ThreeGPPConfig` loaded once at CLI startup and passed via `ctx.obj`. Not mutated after initialization.
- **CLI-is-thin:** No business logic in `cli/`. All domain logic in core library. CLI only contains Typer command definitions, Rich formatting, and CLI-specific argument parsing.
- **SourceKind branching:** Functions like `convert_for_wiki()` must branch on `SourceKind` (TDoc vs Spec) — different fetch and file-resolution logic. Never assume all sources are TDocs.

## Anti-Patterns

### Hardcoded Paths

**What happens:** Using `Path.home() / ".3gpp-crawler"` or similar path construction outside `CacheManager`
**Why it's wrong:** Bypasses config overrides, breaks testability, violates DRY
**Do this instead:** Always use `resolve_cache_manager()` → `manager.root`, `manager.db_file`, etc.

### Defensive CacheManager Resolution

**What happens:** Wrapping `resolve_cache_manager()` in try/except fallbacks
**Why it's wrong:** Hides dev errors — if `CacheManager` is not registered before use, that is a structural defect that should fail fast
**Do this instead:** `manager = resolve_cache_manager()` — let it raise `CacheManagerNotRegisteredError`

### Raw HTTP Requests

**What happens:** Using `requests.get()` or `niquests.get()` directly without caching
**Why it's wrong:** No HTTP caching, rate-limiting risk, inconsistent behavior
**Do this instead:** Always use `create_cached_session()` from `tdoc_crawler.http_client`

### Duplicated Domain Logic in CLI

**What happens:** Reimplementing domain logic in `cli/` modules
**Why it's wrong:** Violates thin-CLI rule; leads to code duplication and inconsistency
**Do this instead:** Move logic to appropriate domain module, import in CLI

### Artifact Directories in Checkout Folders

**What happens:** Storing converted PDFs/markdown as subdirectories of checkout folders
**Why it's wrong:** Checkout folders are raw downloaded data; mixing artifacts causes naming collisions and cleanup problems
**Do this instead:** Store artifacts in `workspaces/<name>/sources/<doc-id>/`

### Ambiguous Release Selectors for Specs

**What happens:** Passing `"latest"` or `"18"` (unresolved) to fetch/convert functions
**Why it's wrong:** Shared checkout directory contains files from multiple releases; unresolved selectors can return wrong-release files
**Do this instead:** Resolve to concrete 3-part version (`"18.0.0"`) at workspace-add time via `resolve_spec_release()`

## Error Handling

**Strategy:** Fail fast with specific exceptions; no silent fallbacks or inconsistent return types

**Patterns:**
- Custom exception hierarchy: `AiError` → `TDocNotFoundError`, `ConversionError`, `LlmConfigError`, `WorkspaceNotFoundError` (in `models/workspaces.py`)
- Database errors: `DatabaseError` (in `database/errors.py`) with structured error codes
- Config errors: `ConfigLoadError` (in `config/sources.py`) with path + reason
- Cache errors: `CacheManagerNotRegisteredError` (in `config/cache_manager.py`)
- Portal errors: `PortalAuthenticationError`, `PortalParsingError` (in `clients/portal.py`, `parsers/portal.py`)
- Conversion errors propagate as `ConversionError`; quality gates produce structured status (`ExtractionQualityStatus` with reason codes)

## Cross-Cutting Concerns

**Logging:** Module-level `logging.getLogger(__name__)` via `tdoc_crawler.logging.get_logger()`. Verbosity controlled by `--verbosity` CLI option or `set_verbosity()`.
**Validation:** Pydantic validators on settings models (`config/settings.py`); field validators on Oxyde models; regex patterns in `constants/patterns.py`.
**Authentication:** EOL portal credentials via env vars (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`), config file, CLI params, or interactive prompt — resolved by `credentials.py:resolve_credentials()`.
**Caching:** Two cache tiers: SQLite HTTP cache (hishel, per-request dedup) and SQLite database (Oxyde, crawled metadata persistence).

---

*Architecture analysis: 2026-05-03*
