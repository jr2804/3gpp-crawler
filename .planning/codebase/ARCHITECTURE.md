<!-- refreshed: 2026-04-30 -->
# Architecture

**Analysis Date:** 2026-04-30

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                           CLI Layer (Typer)                              │
│  ┌─────────────────┬──────────────────────┬────────────────────────────┐ │
│  │   tdoc-app      │     spec-app         │      mgmt-app              │ │
│  │  TDocs/Meetings │  Specifications      │  Config/Workspace          │ │
│  └────────┬────────┴──────────┬───────────┴────────────┬───────────────┘ │
└─────────────┼──────────────────────────────────────────┼──────────────────┘
              │                                          │
         ┌────▼────────────────────────────────────────────────────┐
         │  CLI Commands & Configuration Management               │
         │  `src/tdoc_crawler/cli/`                                │
         │  - crawl, crawl-meetings, query, query-meetings         │
         │  - checkout, open                                       │
         │  - config init, validate, show                          │
         │  - workspace create, checkout, export                   │
         └────┬──────────────────────────────────────────────────┘
              │
    ┌─────────┴──────────────────────────────────────────────┐
    │  Core Domain Packages (Business Logic)                 │
    │  ┌──────────────┬───────────────┬────────────────────┐ │
    │  │ tdocs/       │ specs/        │ meetings/          │ │
    │  │ operations   │ operations    │ operations         │ │
    │  │ sources      │ sources       │                    │ │
    │  │ models       │ models        │ models             │ │
    │  └──────┬───────┴───────┬───────┴─────────┬──────────┘ │
    └─────────┼───────────────┼──────────────────┼───────────┘
              │               │                  │
    ┌─────────▼───────────────▼──────────────────▼───────────┐
    │  Unified Database Layer (SQLite via Oxyde ORM)        │
    │  - TDocDatabase, MeetingDatabase, SpecDatabase         │
    │  - TDocMetadata, MeetingMetadata, Specification models │
    │  `src/tdoc_crawler/database/`                          │
    └─────────┬──────────────────────────────────────────────┘
              │
    ┌─────────▼──────────────────────────────────────────────┐
    │  Extraction Pipeline & File Operations                │
    │  - convert_to_pdf, convert_to_markdown                 │
    │  - extract_document_structured_from_tdoc               │
    │  - fetch_tdoc_files, TDocFiles                         │
    │  `src/tdoc_crawler/extraction/`                        │
    └─────────┬──────────────────────────────────────────────┘
              │
    ┌─────────▼──────────────────────────────────────────────┐
    │  Parallel Execution & Workers                          │
    │  - pool_executors (serial, thread, process modes)      │
    │  - Subinterpreter workers (TDoc crawling)              │
    │  `src/tdoc_crawler/workers/`                           │
    │  `packages/pool_executors/`                            │
    └─────────┬──────────────────────────────────────────────┘
              │
    ┌─────────▼──────────────────────────────────────────────┐
    │  Cross-Cutting Concerns                                │
    │  - HTTP caching (hishel, niquests)                     │
    │  - Configuration management (pydantic)                 │
    │  - Logging (rich)                                      │
    │  - Parsing (BeautifulSoup, lxml)                       │
    │  `src/tdoc_crawler/config/`                            │
    │  `src/tdoc_crawler/utils/`                             │
    │  `src/tdoc_crawler/parsers/`                           │
    └─────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Location |
|-----------|----------------|----------|
| **TDocCrawler** | Orchestrate parallel workers for TDoc metadata extraction | `src/tdoc_crawler/tdocs/operations/crawl.py` |
| **TDocDatabase** | Upsert TDoc records, query with filters | `src/tdoc_crawler/database/tdocs.py` |
| **MeetingCrawler** | Fetch and store 3GPP meeting metadata | `src/tdoc_crawler/meetings/operations/crawl.py` |
| **SpecDatabase** | Manage specifications catalog, track downloads | `src/tdoc_crawler/database/specs.py` |
| **ExtractionPipeline** | Convert documents (PDF, Office, text formats) to markdown | `src/tdoc_crawler/extraction/convert.py` |
| **CacheManager** | Centralized path management (cache, checkout, database) | `src/tdoc_crawler/config/cache_manager.py` |
| **HTTP Client** | Session management with persistent caching (hishel) | External: `tdoc_crawler.http_client` |
| **Portal Parser** | Parse 3GPP portal HTML for TDoc metadata | `src/tdoc_crawler/parsers/portal.py` |
| **PortalClient** | EOL authentication, portal API calls | `src/tdoc_crawler/clients/portal.py` |

## Pattern Overview

**Overall:** Domain-driven architecture with layers:

**Key Characteristics:**
- **Three independent CLI entry points** — Each app is deployable separately (TDocs, Specs, Management)
- **Domain-oriented packages** — `tdocs/`, `specs/`, `meetings/` encapsulate domain logic
- **Unified database interface** — All domain data flows through Oxyde ORM to SQLite
- **Parallel worker pattern** — Subinterpreter and thread pool executors for crawling
- **Cross-cutting configuration** — CacheManager enforces centralized path management across all domains

## Layers

**CLI Layer:**
- Purpose: Typer command definitions, argument parsing, output formatting
- Location: `src/tdoc_crawler/cli/`
- Contains: Command handlers, formatters, arg validators
- Depends on: Config, domain operations, database
- Used by: User via command line

**Domain Layer:**
- Purpose: Business logic for TDocs, Specs, Meetings
- Location: `src/tdoc_crawler/tdocs/`, `src/tdoc_crawler/specs/`, `src/tdoc_crawler/meetings/`
- Contains: Data models, operations, sources (fetchers), utilities
- Depends on: Database, HTTP client, parsers
- Used by: CLI layer, operations orchestrators

**Database Layer:**
- Purpose: Persistent storage abstraction (SQLite via Oxyde ORM)
- Location: `src/tdoc_crawler/database/`
- Contains: Oxyde models, database class implementations, schema definitions
- Depends on: Models, utilities
- Used by: All domain layers, CLI commands

**Extraction Layer:**
- Purpose: Document format conversion and content extraction
- Location: `src/tdoc_crawler/extraction/`
- Contains: PDF conversion, Office format handling, markdown extraction
- Depends on: External tools (LibreOffice, OpenDataLoader)
- Used by: Workspace extraction pipeline

**Execution Layer:**
- Purpose: Parallel worker orchestration
- Location: `src/tdoc_crawler/workers/`, `packages/pool_executors/`
- Contains: Subinterpreter workers, executor factories
- Depends on: Domain models, pool_executors library
- Used by: Crawlers for parallel metadata fetching

**Infrastructure Layer:**
- Purpose: Shared utilities, configuration, logging
- Location: `src/tdoc_crawler/config/`, `src/tdoc_crawler/utils/`, `src/tdoc_crawler/parsers/`, `src/tdoc_crawler/clients/`
- Contains: HTTP caching, path management, date parsing, portal auth
- Depends on: External libraries (pydantic, hishel, BeautifulSoup)
- Used by: All layers

## Data Flow

### Primary TDoc Crawl Path

1. **User invokes**: `tdoc-crawler crawl --working-group SA` → [`src/tdoc_crawler/cli/tdoc_app.py:crawl_tdocs()`](src/tdoc_crawler/cli/tdoc_app.py#L70)
2. **CLI loads config** → `CacheManager` registers cache paths
3. **Meeting discovery**: Query `MeetingDatabase` for meetings matching WG filters
4. **Parallel TDoc fetch**: [`TDocCrawler.crawl()`](src/tdoc_crawler/tdocs/operations/crawl.py#L49) spawns subinterpreter workers
5. **Excel parsing**: Each worker fetches document list Excel file via `ExcelDocListSource`
6. **Metadata extraction**: Parse Excel rows → normalize TDoc IDs → create `TDocMetadata` models
7. **Database upsert**: `TDocDatabase.bulk_upsert_tdocs()` → SQLite (with duplicate checking on `.upper()`)
8. **Output**: `CrawlResult` → formatted table/JSON to stdout

### Specification Checkout Flow

1. **User invokes**: `spec-crawler checkout TS 26.444` → [`src/tdoc_crawler/cli/spec_app.py`](src/tdoc_crawler/cli/spec_app.py)
2. **Spec resolution**: Query `SpecDatabase` or fetch from WhatTheSpec API
3. **Source discovery**: [`build_default_spec_sources()`](src/tdoc_crawler/specs/operations/checkout.py) constructs threegpp/whatthespec sources
4. **File download**: HTTP session with caching to checkout directory
5. **Extraction (optional)**: Convert to markdown via `convert_tdoc_to_markdown()`

### Extraction Workspace Path

1. **Workspace created** with source TDocs and target format (markdown, text)
2. **Fetch TDoc files**: `fetch_tdoc_files()` → downloads binaries to temp
3. **Determine format**: Auto-detect or explicit (PDF, DOCX, etc.)
4. **Convert**: `convert_document_to_markdown()` or office format handler
5. **Extract metadata**: Structured extraction via LiteParser + OpenDataLoader
6. **Store**: Result written to workspace output directory

### Meeting Crawl Path

1. **User invokes**: `tdoc-crawler crawl-meetings` → [`crawl_meetings()`](src/tdoc_crawler/cli/crawl.py)
2. **3GPP portal login** (optional): EOL credentials via `PortalClient`
3. **Meeting list fetch**: Query portal or cached source
4. **Metadata parsing**: [`MeetingCrawler.crawl()`](src/tdoc_crawler/meetings/operations/crawl.py) → parse meeting pages
5. **Database upsert**: `MeetingDatabase.bulk_upsert_meetings()`

**State Management:**
- Configuration is immutable `@dataclass` instances loaded at app startup
- Database state is SQLite (persistent)
- HTTP cache is SQLite (persistent, TTL-based eviction)
- Crawl results are in-memory during execution, logged to database when complete

## Key Abstractions

**TDocCrawler:**
- Purpose: Configuration-driven orchestrator for parallel TDoc fetching
- Examples: `src/tdoc_crawler/tdocs/operations/crawl.py`
- Pattern: Async/await with subinterpreter workers via `pool_executors`
- Interface: `async def crawl(config: TDocCrawlConfig) → TDocCrawlResult`

**TDocSource (Protocol):**
- Purpose: Pluggable TDoc metadata source (Excel, Portal, WhatTheSpec)
- Examples: `src/tdoc_crawler/tdocs/sources/doclist.py`, `portal.py`, `whatthespec.py`
- Pattern: Abstract base class with concrete implementations
- Interface: `fetch_tdoc_metadata()` → `list[TDocMetadata]`

**Oxyde ORM Models:**
- Purpose: Database schema definition and type-safe record management
- Examples: `TDocMetadata`, `MeetingMetadata`, `Specification` in `src/tdoc_crawler/database/oxyde_models.py`
- Pattern: Pydantic dataclasses mapped to SQLite tables
- Interface: Async methods on database classes (`upsert`, `query`, `bulk_upsert`)

**ExtractionProfile:**
- Purpose: Configuration for document extraction (backend, format options)
- Examples: `src/tdoc_crawler/extraction/profiles.py`
- Pattern: Dataclass with converter backend and format specs
- Interface: Passed to `convert_document_to_markdown()`, `extract_document_structured_from_tdoc()`

**CacheManager:**
- Purpose: Singleton path resolver for cache, checkout, database
- Examples: `src/tdoc_crawler/config/cache_manager.py`
- Pattern: Registry pattern — register once, access globally
- Interface: `CacheManager(cache_dir).register()` then `resolve_cache_manager()` everywhere

## Entry Points

**TDoc App (`tdoc-crawler`):**
- Location: `src/tdoc_crawler/cli/tdoc_app.py:tdoc_app`
- Triggers: Command line: `tdoc-crawler crawl|crawl-meetings|query|query-meetings|open|checkout`
- Responsibilities: TDoc/Meeting crawling, querying, opening documents

**Spec App (`spec-crawler`):**
- Location: `src/tdoc_crawler/cli/spec_app.py:spec_app`
- Triggers: Command line: `spec-crawler crawl|query|checkout|open`
- Responsibilities: Specification discovery, download, checkout

**Management App (`3gpp-crawler`):**
- Location: `src/tdoc_crawler/cli/mgmt_app.py:mgmt_app`
- Triggers: Command line: `3gpp-crawler config|workspace`
- Responsibilities: Configuration validation/export, workspace management

## Architectural Constraints

- **Threading:** Single-threaded event loop (asyncio) with optional subinterpreter workers for CPU-bound TDoc parsing
- **Global state:** `CacheManager` is a singleton registered at CLI startup; HTTP session objects are created per-scope; database connections are async context managers
- **Circular imports:** Domain packages avoid re-exporting operations (explicit submodule imports required) to prevent circular dependencies at module load time
- **Database:** SQLite (Oxyde ORM) — no concurrent writers; transactions serialize writes; readers are concurrent
- **HTTP caching:** Via hishel middleware; TTL-based eviction; stored in SQLite at `{cache_dir}/http-cache.sqlite3`
- **Configuration:** Immutable dataclass instances; environment variables override file values; no runtime config changes

## Anti-Patterns

### Eager re-exports in domain packages

**What happens:** Domain `__init__.py` imports all operations, causing circular import chains at load time.

**Why it's wrong:** Python module initialization order becomes fragile; adding a new operation or model can break the entire package load chain.

**Do this instead:** Use explicit submodule imports in CLI and test code:
```python
# ✓ Correct
from tdoc_crawler.tdocs.operations import TDocCrawler

# ✗ Wrong
from tdoc_crawler.tdocs import TDocCrawler  # May fail if __init__.py has circular deps
```

See `src/tdoc_crawler/tdocs/__init__.py` for the pattern.

### Hardcoded cache/database paths

**What happens:** Code uses `~/.3gpp-crawler` or `./cache` directly instead of `CacheManager`.

**Why it's wrong:** Multiple deployment environments (dev, test, CI) collide on same paths; config overrides don't propagate.

**Do this instead:** Always use `CacheManager`:
```python
# ✓ Correct
from tdoc_crawler.config import resolve_cache_manager
cache_manager = resolve_cache_manager()
db_file = cache_manager.db_file

# ✗ Wrong
db_file = Path.home() / ".3gpp-crawler" / "database.sqlite3"
```

See `src/tdoc_crawler/config/cache_manager.py` for the implementation.

### Unvalidated HTTP requests

**What happens:** Raw `requests` or `niquests` calls without `create_cached_session()`.

**Why it's wrong:** HTTP cache is not utilized; credentials leaks in logs; timeouts/retries not configured consistently.

**Do this instead:** Always use `create_cached_session()`:
```python
# ✓ Correct
from tdoc_crawler.http_client import create_cached_session
with create_cached_session() as session:
    response = session.get(url)

# ✗ Wrong
import requests
response = requests.get(url)  # No caching, no config
```

See `src/tdoc_crawler/cli/crawl.py` for examples.

## Error Handling

**Strategy:** Async exceptions propagate to CLI layer; CLI layer formats errors for user display via `console.print()` or `typer.echo()`.

**Patterns:**
- Domain operations return `Result` dataclasses (e.g., `TDocCrawlResult(errors=[...])`) for non-fatal errors
- Fatal errors raise exceptions (e.g., `DatabaseError`, `ConfigLoadError`)
- CLI catches exceptions and calls `sys.exit(1)` with formatted message
- HTTP errors are retried per `config.http.max_retries` with exponential backoff

## Cross-Cutting Concerns

**Logging:** Via `get_logger(__name__)` (custom logger); verbosity set at app startup via `set_verbosity()`; output to stderr via `logging` module.

**Validation:** Pydantic models validate inputs at dataclass initialization; CLI args validated via typer options; config validated at load time via `_validate_config_values()`.

**Authentication:** EOL portal credentials stored locally in `~/.3gpp-crawler/.credentials.toml` (encrypted via pydantic-settings); API keys via environment variables.

---

*Architecture analysis: 2026-04-30*
