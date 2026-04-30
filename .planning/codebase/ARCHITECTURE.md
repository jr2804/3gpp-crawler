# Architecture -- 3GPP Crawler

## Overview

A CLI tool for crawling the 3GPP FTP server, caching document metadata (TDocs, Specs, Meetings) in a local SQLite database, and querying structured data via JSON/YAML/YAML output. Written in Python 3.14, using Typer for CLI, Rich for output, Pydantic for models, Oxyde ORM for persistence, and hishel for HTTP caching.

## Layer Architecture

CLI Layer (cli/) -> Core Library (tdoc_crawler/) -> Shared Packages (packages/)

- CLI Layer: Typer command defs, Rich output, arg parsing only. Thin wrappers -- no business logic.
- Core Library: Domain modules (tdocs, meetings, specs), extraction, workspaces, workers, database, http_client, config, models, parsers, clients, utils.
- Shared Packages: convert-lo, pool-executors, toon-format.

Principle: CLI Is Thin. The cli/ directory contains only Typer command definitions and Rich formatting. All business logic lives in the core tdoc_crawler/ package. Import direction: CLI -> Core -> Models (only).

## Domain Modules

### tdocs/ -- Temporary Documents (Largest Domain)

- Crawling (operations/crawl.py): TDocCrawler orchestrates parallel subinterpreter workers (tdoc_worker.py) to fetch Excel document lists from the 3GPP FTP server for each meeting.
- Fetching (operations/fetch.py): Single-TDoc lookups via fetch_missing_tdocs() -- queries WhatTheSpec API or 3GPP Portal as fallback.
- Checkout (operations/checkout.py): Download, extract, and manage TDoc ZIP files.
- Sources (sources/): Protocol-based abstraction with three implementations:
  - doclist.py -- Excel DocList (batch, no auth) -- primary batch source
  - whatthespec.py -- WhatTheSpec API (single, no auth) -- primary single source
  - portal.py -- 3GPP Portal (single, auth required) -- authenticated fallback
- Models (models.py): TDocMetadata, TDocCrawlConfig, TDocQueryConfig, TDocStatus enum

### meetings/ -- Meeting Metadata

- operations/crawl.py: MeetingCrawler -- fetches meeting listings from the 3GPP portal, requires EOL credentials.
- models.py: MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig

### specs/ -- Technical Specifications

- sources/: SpecSource protocol with whatthespec.py and threegpp.py implementations.
- operations/checkout.py: Spec download and extraction.
- models.py: Specification, SpecificationSourceRecord, SpecificationVersion, SpecificationDownload, SpecQueryFilters
- Crawling is embedded in database/specs.py (not a separate operations module).

### extraction/ -- Document Conversion

- conversion.py: ConverterBackend enum (LIBREOFFICE, REMOTE, AUTO), convert_to_pdf(), ensure_pdf() -- converts Office documents to PDF via local LibreOffice or remote API.
- convert.py: Integration with OpenDataLoader for markdown extraction.
- fetch_tdoc.py: Download TDoc files from FTP.
- metrics.py: MetricsTracker, TimedOperationResult -- timing and performance tracking.
- profiles.py: ExtractionProfile -- configurable extraction behavior.

### workspaces/ -- AI/RAG Workspace Management

- crud.py: CRUD operations for workspaces.
- members.py: Add/remove workspace members (TDocs/Specs).
- utils.py: Checkout TDocs/Specs to workspace directories.
- Models in models/workspaces.py: Workspace, DocumentClassification, ExtractedTableElement, ExtractedFigureElement, SummarizeResult.

### workers/ -- Parallel Execution Workers

- tdoc_worker.py: fetch_meeting_document_list_subinterpreter() -- single function designed to run in Python subinterpreters for parallel TDoc crawling.

## Database Layer (Oxyde ORM)

Location: database/

### Inheritance Hierarchy

DocDatabase (base.py) -- Abstract base, lifecycle management
  |-- MeetingDatabase (meetings.py) -- Meeting CRUD + query
  |     |-- TDocDatabase (tdocs.py) -- TDoc CRUD + query + stats
  |-- SpecDatabase (specs.py) -- Spec CRUD + crawl + query

- DocDatabase (base.py): Async context manager, table creation, reference data seeding, crawl logging.
- MeetingDatabase (meetings.py): Meeting upsert/query, statistics gathering.
- TDocDatabase (tdocs.py): Extends MeetingDatabase (dual TDoc + Meeting ops). Bulk upsert, filtered queries with glob patterns.
- SpecDatabase (specs.py): Spec crawling (multiple sources), query with filters, version management.

### ORM Models (database/oxyde_models.py)

All models use Oxyde ORM Model class. Tables: working_groups (WorkingGroupRecord), subworking_groups (SubWorkingGroupRecord), crawl_log (CrawlLogEntry), meetings (MeetingMetadata), tdocs (TDocMetadata), specs (Specification), spec_source_records (SpecificationSourceRecord), spec_versions (SpecificationVersion), spec_downloads (SpecificationDownload).

### Error Handling (database/errors.py)

DatabaseError (extends RuntimeError) with code+detail pattern. Factory method: DatabaseError.connection_not_open().

## CLI Layer

### Entry Points (pyproject.toml)

- tdoc-crawler = tdoc_crawler.cli.tdoc_app:tdoc_app (Main app)
- spec-crawler = tdoc_crawler.cli.spec_app:spec_app (Spec-only app)
- 3gpp-crawler = tdoc_crawler.cli.mgmt_app:mgmt_app (Management app)

### CLI Module Structure

| File | Purpose |
|------|---------|
| tdoc_app.py | TDoc/Meeting Typer commands, callback registration |
| spec_app.py | Spec Typer commands |
| mgmt_app.py | Config + workspace Typer commands |
| crawl.py | Crawl command implementations |
| query.py | Query command implementations |
| args.py | Reusable Annotated[..] type aliases |
| printing.py | Table and output formatting |
| formatting.py | Structured output utilities |
| config.py | load_cli_config() startup loading |
| config_app.py | config init and config show subcommands |
| _workspace_commands.py | Workspace management subcommands |
| _shared.py | Shared console, progress_bar, clear options |
| constants.py | Help panel group constants |
| utils.py | launch_file() helper |

## Configuration System

### ThreeGPPConfig (pydantic-settings)

config/settings.py -- Type-safe configuration with nested models: PathConfig, HttpConfig, CredentialsConfig, CrawlConfig.

Config discovery order (later overrides earlier):
1. Global: ~/.config/3gpp-crawler/config.toml
2. Project: 3gpp-crawler.toml, .3gpp-crawler.toml, .3gpp-crawler/config.toml
3. Config dir: .config/.3gpp-crawler/conf.d/*.toml

Precedence: CLI args > Config file > Env vars > Defaults

### CacheManager (Runtime Path Singleton)

config/cache_manager.py -- Centralized path management. Register at startup, resolve everywhere.
Provides: root, db_file, http_cache_file, checkout_dir, workspace_registry_file, llm_wiki_dir.

Rule: Never hardcode paths like ~/.3gpp-crawler. Always use CacheManager.

### Environment Variables (config/env_vars.py)

ConfigEnvVar StrEnum maps env var names to TOML config paths.
Prefixes: TDC_ (most), HTTP_CACHE_ (HTTP cache), TDC_EOL_ (portal credentials).

## HTTP Client Layer

http_client/ -- Cached HTTP session factory using hishel.
session.py: create_cached_session() with SQLite-backed HTTP cache, SSL verification, retry support.
protocols.py: DefaultHttpClientProvider -- reusable session with cache file.

All HTTP requests MUST use create_cached_session() (project rule).

## Key Design Patterns

### SpecSource Protocol

Protocol-based abstraction over spec data sources. Implemented by specs/sources/whatthespec.py and specs/sources/threegpp.py. Adapters via FunctionSpecSource.

### TDocSource Protocol

Protocol-based abstraction for TDoc metadata sources (doclist, WhatTheSpec, Portal). Defines fetch_by_id() and fetch_by_meeting().

### Pipeline / Progress Callback Pattern

Crawlers accept progress_callback: Callable[[float, float], None] | None to decouple progress reporting from crawl logic.

### DatabaseFactory Protocol

@runtime_checkable protocol with DefaultDatabaseFactory for dependency injection.

### Workspace Registry

config/workspace_registry.py -- JSON-file-backed registry tracking wiki build health, page counts, build timestamps.

## Data Flow

### Crawl Path

1. CLI (crawl.py) builds TDocCrawlConfig.
2. CLI calls asyncio.run() to enter async context.
3. TDocDatabase opened via async context manager.
4. TDocCrawler.crawl() called:
   a. Query meetings from database (MeetingQueryConfig).
   b. Apply meeting limits (count, per-subwg, subwg count).
   c. For each meeting, submit to subinterpreter workers (pool-executors).
   d. Workers call fetch_meeting_document_list() to download Excel files.
   e. Parse Excel into list of TDocMetadata JSON.
   f. Return serialized JSON to main process.
   g. Deserialize, deduplicate, apply filters.
5. Collected TDocs -> bulk_upsert_tdocs() -> TDocDatabase.upsert_tdoc().
6. Crawl logged via CrawlLogEntry.
7. Results displayed (processed, inserted, updated, errors).

### Query Path

1. CLI (query.py) builds TDocQueryConfig with filters.
2. TDocDatabase.query_tdocs():
   a. Read all TDocMetadata from Oxyde ORM.
   b. Join with MeetingMetadata for working group resolution.
   c. Apply filters: TDoc ID -> WG -> date -> glob patterns.
   d. Sort by date_retrieved, apply limit.
3. Optional: fetch_missing_tdocs() for IDs not in database.
4. Optional: checkout_tdocs() to download files.
5. Format output: Rich table, JSON, YAML, ISON, or TOON.

## Async/Sync Boundary

Core database operations are async (Oxyde ORM). CLI is synchronous (Typer). Boundary crossed via asyncio.run().

The run_async() helper in utils/async_helpers.py handles both sync and async calling contexts by running in a background thread if a loop is already active.

For parallel crawl workers: subinterpreter workers run as separate Python interpreters, communicating via JSON.

## Error Handling Patterns

### Application-Specific Exceptions

- DatabaseError (database/errors.py): DB constraint/connection failures
- ConversionError (models/workspaces.py): Document conversion failures
- TDocNotFoundError (models/workspaces.py): TDoc not in DB/no files
- WorkspaceNotFoundError (models/workspaces.py): Workspace missing from registry
- CacheManagerNotRegisteredError (config/cache_manager.py): Access before registration
- PortalAuthenticationError (clients/portal.py): EOL portal auth failure
- PortalParsingError (parsers/portal.py): Portal HTML parse failure
- ConfigLoadError (config/sources.py): Config file load/parse failure

### Error Convention

DatabaseError uses code+detail pattern. CLI errors use typer.Exit(code=1) with Rich console messages.

## Recent Changes

- --cache-dir removed: No longer a CLI option; CacheManager uses config instead.
- run_async() helper added: Safe async-from-sync helper for both loop-present and loop-absent contexts.
- Exception narrowing: Replaced broad except Exception with specific types.
- Spec crawl parallelism: Multiple spec sources queried in parallel.
- Dead code removed: Legacy AiStorage references, unused CLI flags.

## Naming Conventions

Files: snake_case. Classes: PascalCase. Functions: snake_case. Path variables: _dir/_file suffix. Private methods: _ prefix. Type-only imports: TYPE_CHECKING guard. Private CLI modules: _ prefix (e.g., _shared.py).

## Test Architecture

- Framework: pytest with pytest-asyncio.
- Fixtures: conftest.py provides test_cache_dir, test_db_path, sample_tdocs, sample_meetings, populated_db.
- Isolation: _reset_cache_manager fixture clears singleton before each test.
- Database: In-memory SQLite via Oxyde ORM in temp directories.
- Coverage target: >90% for core modules.
