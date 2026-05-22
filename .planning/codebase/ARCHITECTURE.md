<!-- refreshed: 2026-05-22 -->
# Architecture

**Analysis Date:** 2026-05-22

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLI Layer (Typer + Rich)                           │
├───────────────────┬───────────────────┬─────────────────────────────────────┤
│   tdoc_app.py     │   spec_app.py     │   mgmt_app.py                       │
│  `tdoc-crawler`   │  `spec-crawler`   │  `3gpp-crawler`                     │
│  crawl/query/     │  crawl/query/     │  config/workspace                   │
│  open/checkout    │  checkout/open    │                                     │
└────────┬──────────┴────────┬──────────┴──────────────┬──────────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Domain Operations Layer                                  │
├───────────────────┬───────────────────┬─────────────────────────────────────┤
│  tdocs/           │  meetings/        │  specs/                             │
│  operations/      │  operations/      │  operations/                        │
│  sources/         │  sources/         │  sources/                           │
│  models.py        │  models.py        │  models.py                          │
└────────┬──────────┴────────┬──────────┴──────────────┬──────────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                                     │
├──────────────┬─────────────────┬──────────────┬──────────────────────────────┤
│  database/   │  http_client/   │  extraction/ │  clients/                   │
│  Oxyde ORM   │  hishel+niquests│  Docling+LO  │  PortalClient               │
│  SQLite      │  HTTP cache     │  profiles    │  EOL auth                   │
└──────────────┴─────────────────┴──────────────┴──────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cross-Cutting: config/ · models/ · parsers/ · constants/ · utils/         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `tdoc_app` | TDoc-focused CLI: crawl, query, open, checkout, stats | `src/tdoc_crawler/cli/tdoc_app.py` |
| `spec_app` | Spec-focused CLI: crawl, query, checkout, open | `src/tdoc_crawler/cli/spec_app.py` |
| `mgmt_app` | Management CLI: config, workspace sub-apps | `src/tdoc_crawler/cli/mgmt_app.py` |
| `TDocDatabase` | TDoc CRUD, queries, bulk operations | `src/tdoc_crawler/database/tdocs.py` |
| `MeetingDatabase` | Meeting CRUD, queries, statistics | `src/tdoc_crawler/database/meetings.py` |
| `SpecDatabase` | Spec CRUD, version management | `src/tdoc_crawler/database/specs.py` |
| `DocDatabase` | Base class with shared DB helpers | `src/tdoc_crawler/database/base.py` |
| `CacheManager` | Single source of truth for all file paths | `src/tdoc_crawler/config/cache_manager.py` |
| `ThreeGPPConfig` | Type-safe settings from files/env vars | `src/tdoc_crawler/config/settings.py` |
| `TDocSource` | Protocol for TDoc metadata sources | `src/tdoc_crawler/tdocs/sources/base.py` |
| `SpecSource` | Protocol for spec metadata sources | `src/tdoc_crawler/specs/sources/base.py` |
| `PortalClient` | 3GPP EOL authenticated portal access | `src/tdoc_crawler/clients/portal.py` |
| `create_cached_session` | HTTP session factory with hishel cache | `src/tdoc_crawler/http_client/session.py` |
| `convert_for_wiki` | Document conversion for workspace ingestion | `src/tdoc_crawler/extraction/convert.py` |
| `WorkspaceRegistry` | Workspace metadata persistence (JSON) | `src/tdoc_crawler/config/workspace_registry.py` |

## Pattern Overview

**Overall:** Domain-oriented modular monolith with thin CLI shells over async core library.

**Key Characteristics:**
- Three separate CLI entry points sharing one core library (`tdoc_crawler`)
- Protocol-based source abstraction (`TDocSource`, `SpecSource`) with multiple implementations
- Async database layer using Oxyde ORM over SQLite
- Centralized path management via singleton `CacheManager`
- Pydantic `BaseModel` for validation-heavy configs; `dataclass` for pure data transfer; Oxyde `Model` for DB persistence

## Layers

### CLI Layer (`cli/`):
- Purpose: Typer command definitions, Rich console output, argument parsing
- Location: `src/tdoc_crawler/cli/`
- Contains: Typer `@app.command()` wrappers, `Annotated` option types, table formatting
- Depends on: Domain operations, config, database
- Used by: End users via `tdoc-crawler`, `spec-crawler`, `3gpp-crawler` scripts
- **Strict rule:** All business logic belongs in the core library. CLI is thin.

### Domain Operations Layer (`tdocs/`, `meetings/`, `specs/`):
- Purpose: Domain-specific crawl, fetch, and checkout operations
- Location: `src/tdoc_crawler/{tdocs,meetings,specs}/operations/`
- Contains: Crawler classes, fetch strategies, checkout logic
- Depends on: Sources, database, config, http_client
- Used by: CLI commands

### Domain Sources Layer (`sources/`):
- Purpose: Pluggable data source adapters following protocols
- Location: `src/tdoc_crawler/{tdocs,specs,meetings}/sources/`
- Contains: Protocol implementations for WhatTheSpec API, 3GPP Portal, Excel doc lists, 3GPP FTP
- Depends on: http_client, parsers, config
- Used by: Domain operations

### Database Layer (`database/`):
- Purpose: SQLite persistence via Oxyde ORM
- Location: `src/tdoc_crawler/database/`
- Contains: Oxyde models (`oxyde_models.py`), database facade classes, error types
- Depends on: Oxyde ORM, models layer for reference data
- Used by: Domain operations, CLI

### Extraction Layer (`extraction/`):
- Purpose: Document conversion pipeline (PDF, Markdown, structured JSON)
- Location: `src/tdoc_crawler/extraction/`
- Contains: Extraction profiles, Docling integration, LibreOffice conversion, metrics
- Depends on: config, http_client, external tools (LibreOffice, Docling)
- Used by: Workspace processing

### Infrastructure Layer:
- Purpose: HTTP caching, portal authentication, path management, configuration
- Location: `src/tdoc_crawler/{config,http_client,clients,constants}/`
- Contains: `CacheManager`, `ThreeGPPConfig`, `create_cached_session()`, `PortalClient`, URL constants
- Depends on: External libraries (hishel, niquests, pydantic-settings)
- Used by: All other layers

## Data Flow

### Primary Crawl Flow (TDocs)

1. User runs `tdoc-crawler crawl -w SA4` (`src/tdoc_crawler/cli/crawl.py:crawl_tdocs`)
2. CLI builds `TDocCrawlConfig`, opens `MeetingDatabase` + `TDocDatabase` (`src/tdoc_crawler/database/`)
3. `MeetingCrawler.crawl()` discovers meetings from 3GPP portal (`src/tdoc_crawler/meetings/operations/crawl.py`)
4. Per meeting: fetch TDoc list from Excel doc list (`src/tdoc_crawler/tdocs/sources/doclist.py`)
5. TDoc metadata parsed and upserted into SQLite via Oxyde ORM (`src/tdoc_crawler/database/tdocs.py`)
6. Progress displayed via Rich (`src/tdoc_crawler/cli/_shared.py`)

### Query Flow

1. User runs `tdoc-crawler query S4-250638` (`src/tdoc_crawler/cli/query.py:query_tdocs`)
2. CLI builds `TDocQueryConfig` with glob patterns and date filters (`src/tdoc_crawler/tdocs/models.py`)
3. Database queried via `TDocDatabase.query_tdocs()` (`src/tdoc_crawler/database/tdocs.py`)
4. Missing TDocs fetched on-demand from WhatTheSpec or Portal (`src/tdoc_crawler/tdocs/operations/fetch.py`)
5. Results formatted to table/JSON/ISON/TOON/YAML via `format_output()` (`src/tdoc_crawler/cli/formatting.py`)

### Workspace Processing Flow

1. User runs `3gpp-crawler workspace process` (`src/tdoc_crawler/cli/workspace/process.py`)
2. Workspace registry loaded from `workspaces.json` (`src/tdoc_crawler/config/workspace_registry.py`)
3. For each member: checkout document → convert per profile → output to wiki dir
4. Extraction profiles: `pdf-only`, `markdown-only`, `default`, `advanced` (`src/tdoc_crawler/extraction/profiles.py`)
5. Conversion uses Docling or pymupdf4llm depending on profile (`src/tdoc_crawler/extraction/convert.py`)

**State Management:**
- SQLite for all persistent domain data (TDocs, Meetings, Specs, Crawl Logs)
- JSON file (`workspaces.json`) for workspace registry metadata
- Filesystem for checkout artifacts and wiki output

## Key Abstractions

**Source Protocol Pattern:**
- Purpose: Pluggable data sources with uniform interface
- Examples: `src/tdoc_crawler/tdocs/sources/base.py` (`TDocSource`), `src/tdoc_crawler/specs/sources/base.py` (`SpecSource`)
- Pattern: `typing.Protocol` with `fetch()` methods; multiple implementations (Portal, WhatTheSpec, DocList, FTP)

**Config Pattern:**
- Purpose: Type-safe, layered configuration
- Examples: `src/tdoc_crawler/config/settings.py` (ThreeGPPConfig), `src/tdoc_crawler/tdocs/models.py` (TDocCrawlConfig)
- Pattern: `pydantic-settings` `BaseSettings` for app config; `pydantic` `BaseModel` for domain configs with `field_validator`s

**Database Facade Pattern:**
- Purpose: Async database access with context manager lifecycle
- Examples: `src/tdoc_crawler/database/base.py` (DocDatabase), `src/tdoc_crawler/database/tdocs.py` (TDocDatabase)
- Pattern: `async with Database(db_file) as db:` context manager; Oxyde ORM models registered via `auto_register=True`

**Extraction Profile Enum:**
- Purpose: Tiered document extraction with consistent CLI options
- Examples: `src/tdoc_crawler/extraction/profiles.py` (ExtractionProfile, FiguresMode, TablesMode, DeviceType)
- Pattern: `StrEnum` classes used directly as Typer option types for automatic validation

## Entry Points

**`tdoc-crawler` (TDoc-focused CLI):**
- Location: `src/tdoc_crawler/cli/tdoc_app.py:tdoc_app`
- Triggers: `pyproject.toml` script entry `tdoc-crawler = "tdoc_crawler.cli.tdoc_app:tdoc_app"`
- Responsibilities: crawl, query, open, checkout, stats commands for TDocs and meetings

**`spec-crawler` (Spec-focused CLI):**
- Location: `src/tdoc_crawler/cli/spec_app.py:spec_app`
- Triggers: `pyproject.toml` script entry `spec-crawler = "tdoc_crawler.cli.spec_app:spec_app"`
- Responsibilities: crawl, query, checkout, open commands for specifications

**`3gpp-crawler` (Management CLI):**
- Location: `src/tdoc_crawler/cli/mgmt_app.py:mgmt_app`
- Triggers: `pyproject.toml` script entry `3gpp-crawler = "tdoc_crawler.cli.mgmt_app:mgmt_app"`
- Responsibilities: config sub-app, workspace sub-app (create, list, activate, members, process)

## Architectural Constraints

- **Threading:** Async I/O via `asyncio.run()` wrapping `async with` database context managers. Worker pools use `ProcessPoolExecutor` or subinterpreters for parallel crawling. LibreOffice conversions run sequentially (not thread-safe).
- **Global state:** `CacheManager` uses a class-level `_instance` singleton registered once at CLI startup. `logging` module uses `@functools.cache` singletons for `Console` and `configure_logger()`.
- **Circular imports:** Domain packages (`tdocs/`, `meetings/`, `specs/`) do not re-export operations to avoid circular imports. Shared types extracted to `models/` layer.
- **HTTP/3 issue:** `www.3gpp.org` and `portal.3gpp.org` advertise HTTP/3 but cannot handle it. All `niquests.Session()` must use `disable_http3=True`. Cached sessions handle this via custom `_NiquetsCacheAdapter.init_poolmanager()`.
- **Async boundary:** The core library is async (database, network I/O). CLI bridges via `asyncio.run()`. No mixing of sync/async in the same call chain.

## Anti-Patterns

### Hardcoded Paths

**What happens:** Path strings like `~/.3gpp-crawler` are hardcoded in new code
**Why it's wrong:** Users can override via config/env. Hardcoded paths break tests and alternative installations.
**Do this instead:** Use `CacheManager` from `src/tdoc_crawler/config/cache_manager.py`:
```python
manager = resolve_cache_manager()
db_path = manager.db_file
```

### Raw HTTP Sessions Without Caching

**What happens:** Direct `requests.Session()` or `niquests.Session()` calls bypass caching and HTTP/3 mitigation
**Why it's wrong:** Wastes bandwidth, triggers HTTP/3 `MustDowngradeError` on 3gpp.org
**Do this instead:** Use `create_cached_session()` from `src/tdoc_crawler/http_client/session.py`:
```python
with create_cached_session() as session:
    response = session.get(url)
```

### Duplicate Models for Same Entity

**What happens:** Separate Pydantic and Oxyde models for the same database entity
**Why it's wrong:** Fields diverge, causing `AttributeError` at runtime
**Do this instead:** Single Oxyde model per entity in `src/tdoc_crawler/database/oxyde_models.py`. Import from there everywhere.

### Business Logic in CLI

**What happens:** Complex data processing implemented inside Typer command handlers
**Why it's wrong:** Cannot be reused by library consumers; violates CLI-is-thin rule
**Do this instead:** Move logic to domain operations (`tdocs/operations/`, `meetings/operations/`, `specs/operations/`), import in CLI.

## Error Handling

**Strategy:** Typed exceptions with domain-specific error classes.

**Patterns:**
- `DatabaseError` in `src/tdoc_crawler/database/errors.py` — wraps all DB failures
- `PortalAuthenticationError` in `src/tdoc_crawler/clients/portal.py` — auth failures
- `ConversionError` in `src/tdoc_crawler/models/workspaces.py` — document conversion failures
- `CacheManagerNotRegisteredError` in `src/tdoc_crawler/config/cache_manager.py` — missing registration
- `WorkspaceNotFoundError` in `src/tdoc_crawler/models/workspaces.py` — missing workspace
- CLI catches exceptions and reports via Rich console with `[red]` styling, then `raise typer.Exit(code=1)`

## Cross-Cutting Concerns

**Logging:** Rich-based logging via `src/tdoc_crawler/logging/__init__.py`. Use `get_logger(__name__)` everywhere. Verbosity controlled by `--verbosity` CLI flag. Singleton `Console` via `@functools.cache`.

**Validation:** Pydantic `field_validator` on all config and query models. Normalization happens at model construction time (TDoc IDs → uppercase, working groups → enum, subgroups → canonical form).

**Authentication:** Portal credentials managed via `src/tdoc_crawler/credentials.py` using `set_credentials()`. Supports env vars (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`), CLI flags, and interactive prompts.

**Configuration:** Layered config via `pydantic-settings`: CLI args > Config file (TOML) > Env vars (`TDC_*`) > Defaults. Discovery: global `~/.config/3gpp-crawler/config.toml`, project `3gpp-crawler.toml`, `.3gpp-crawler/config.toml`.

---

*Architecture analysis: 2026-05-22*
