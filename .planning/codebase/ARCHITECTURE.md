# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Domain-oriented layered architecture with a thin CLI facade over a standalone Python library.

**Key Characteristics:**

- CLI is an optional thin layer — the core `tdoc_crawler` package works as a standalone library
- Domain packages (`tdocs/`, `meetings/`, `specs/`) each encapsulate their own models, operations, and data sources with consistent internal structure (`models.py`, `operations/`, `sources/`, `utils.py`)
- Single registered `CacheManager` singleton provides all file paths — never hardcoded
- HTTP caching via `hishel` (SQLite-backed) is mandatory for all external requests
- Pydantic models serve dual purpose: data validation and ORM (via `pydantic-sqlite`)
- Sub-packages under `packages/` are independent uv workspace packages with their own `pyproject.toml`
- Multiple CLI entry points: unified `tdoc-crawler`, TDoc-only `tdoc_crawler.cli.tdoc_app`, spec-only `spec-crawler`, and AI `3gpp-ai`

## Layers

**CLI Layer:**

- Purpose: Typer command definitions, argument parsing, Rich console output, user interaction
- Location: `src/tdoc_crawler/cli/`
- Contains: `app.py` (unified app), `tdoc_app.py` (TDoc/meeting focused), `spec_app.py` (spec focused), `crawl.py`, `query.py`, `args.py`, `printing.py`, `_shared.py`, `specs.py`
- Depends on: All core domain packages, `config.CacheManager`, `http_client.create_cached_session`
- Used by: End users via entry points (`tdoc-crawler`, `spec-crawler`, `3gpp-ai`)
- Rule: NEVER duplicate core library logic in CLI — import from core instead

**Domain Layer:**

- Purpose: Business logic for each 3GPP document domain (TDocs, meetings, specifications)
- Location: `src/tdoc_crawler/tdocs/`, `src/tdoc_crawler/meetings/`, `src/tdoc_crawler/specs/`
- Contains: Domain models, crawl operations, fetch operations, checkout operations, data sources, domain utilities
- Each domain has internal structure: `models.py`, `operations/`, `sources/`, `utils.py`
- Depends on: `models/` (shared types), `database/`, `http_client/`, `parsers/`, `config/`, `constants/`
- Used by: CLI layer, AI sub-package

**Data Layer:**

- Purpose: SQLite database access via pydantic-sqlite, schema management, query execution
- Location: `src/tdoc_crawler/database/`
- Contains: `base.py` (DocDatabase facade), `tdocs.py` (TDocDatabase), `meetings.py` (MeetingDatabase), `specs.py` (SpecDatabase), `protocols.py`, `errors.py`
- Depends on: Pydantic models from domain packages and `models/`, `config/` for path resolution
- Used by: All domain crawlers, CLI query commands
- Pattern: Context manager pattern (`with TDocDatabase(path) as db:`), inheritance chain `DocDatabase` → `MeetingDatabase` → `TDocDatabase`

**Models Layer:**

- Purpose: Shared Pydantic models, enums, configuration dataclasses, reference data
- Location: `src/tdoc_crawler/models/`
- Contains: `base.py` (BaseConfigModel, HttpCacheConfig, OutputFormat, SortOrder, PortalCredentials), `crawl_limits.py`, `crawl_log.py`, `working_groups.py`, `subworking_groups.py`
- Depends on: `config.CacheManager` (for path resolution in BaseConfigModel)
- Used by: Domain layer, CLI layer, database layer
- Design: Neutral layer — both `database/` and domain packages import from here to avoid circular imports. Circular imports are resolved by extracting shared types here.

**Infrastructure Layer:**

- Purpose: Cross-cutting concerns — HTTP caching, path management, logging, credentials, constants
- Location: `src/tdoc_crawler/config/`, `src/tdoc_crawler/http_client/`, `src/tdoc_crawler/logging/`, `src/tdoc_crawler/credentials.py`, `src/tdoc_crawler/constants/`
- Contains: CacheManager singleton + ConfigService, cached session factory, logging setup, credential resolution, URL/pattern constants
- Depends on: `hishel`, `requests`, environment variables
- Used by: All layers above

**Parsing Layer:**

- Purpose: HTML and Excel parsing, extracting structured data from 3GPP pages
- Location: `src/tdoc_crawler/parsers/`
- Contains: `meetings.py` (meeting page parsing), `portal.py` (portal page parsing), `protocols.py`
- Depends on: `beautifulsoup4`, `lxml`, `python-calamine`
- Used by: Domain operations (crawlers), `clients/portal.py`

**AI Extension Layer (Workspace Sub-package):**

- Purpose: AI-powered document processing — embeddings, knowledge graphs, RAG, summarization, workspace management
- Location: `packages/3gpp-ai/threegpp_ai/`
- Contains: `lightrag/` (LightRAG integration: config, RAG, processor, metadata, seeding), `operations/` (classify, extract, convert, summarize, chunk, workspace management, metrics, figure descriptions), `models.py`, `config.py`, `cli.py`
- Depends on: `tdoc_crawler.config` (CacheManager), `convert-lo`, `lightrag-hku`, `litellm`, `kreuzberg`, `doc2txt`, `pydantic-settings`
- Used by: CLI via `tdoc-crawler ai` commands, standalone via `3gpp-ai` CLI entry point
- Design: Follows SSOT principle — all config from env vars, all paths from CacheManager

## Data Flow

**Crawl Flow (TDocs):**

1. CLI command (`crawl-tdocs`) registers `CacheManager` with `CacheManager(cache_dir).register()`, builds `TDocCrawlConfig`
1. `TDocCrawler.crawl()` resolves meetings from database via `MeetingQueryConfig`, then iterates per-subworking-group
1. For each meeting: downloads Excel document list via `create_cached_session()` (hishel SQLite cache)
1. Parses Excel rows → normalizes TDoc IDs (`.upper()`) → creates `TDocMetadata` Pydantic models
1. Upserts into SQLite via `TDocDatabase` (pydantic-sqlite `DataBase.add()`)
1. Logs crawl start/end to `crawl_log` table with item counts and error tracking
1. Optional: checkout phase downloads ZIP files from 3GPP FTP to `checkout_dir`

**Crawl Flow (Meetings):**

1. CLI command (`crawl-meetings`) resolves EOL credentials via `resolve_credentials()`, registers `CacheManager`
1. `MeetingCrawler.crawl()` fetches meeting list pages from 3GPP portal via `create_cached_session()`
1. Parses HTML meeting pages via `parse_meeting_page()` → normalizes meeting metadata → creates `MeetingMetadata` models
1. Stores in SQLite via `MeetingDatabase`
1. Reference data (working groups, subworking groups) auto-populated on database open

**Fetch Flow (Targeted TDoc Lookup):**

1. Query database first → find existing records or gaps
1. For missing TDocs: `fetch_missing_tdocs()` tries sources via strategy pattern
1. Source resolution: `create_source()` returns appropriate source based on config
1. Source priority: WhatTheSpec API (fast, no auth) → 3GPP Portal (authenticated fallback)
1. Full metadata fetched and stored; results returned to caller

**Checkout Flow:**

1. Given TDoc metadata records, download ZIP files from 3GPP FTP
1. Extract to `checkout_dir` following directory convention: `TSG_{TSG}/WG{n}_{CODE}/TSGS4_{nnn}/Docs/{tdoc_id}/`
1. Uses `download_to_file()` from `http_client/session.py` with streaming (`iter_content(chunk_size=8192)`)

**AI Processing Flow:**

1. Workspace created (JSON registry file at `ai_workspace_file` via `WorkspaceRegistry`)
1. Members (TDocs/specs) added to workspace with resolved checkout paths via `resolve_tdoc_checkout_path()` / `resolve_spec_release_from_db()`
1. `TDocProcessor` or `TDocRAG` processes documents:
   - Convert document formats (via `convert-lo`/LibreOffice, `kreuzberg`, `doc2txt`)
   - Extract text, classify, chunk
   - Ingest into LightRAG (embeddings, knowledge graph, vector store)
1. Query via `TDocRAG.query()` for semantic/graph-RAG search

**State Management:**

- SQLite database is the single source of truth for crawled metadata
- HTTP responses cached in separate SQLite file via hishel (default TTL: 7200s)
- AI state (workspaces, embeddings, graphs) stored under `ai_cache_dir` (default `~/.3gpp-crawler/lightrag/`)
- Checkout files are mutable local copies (can be deleted/recreated on demand)
- No in-memory state persists between CLI invocations

## Key Abstractions

**CacheManager (Singleton Registry):**

- Purpose: Single source of truth for all filesystem paths
- Implementation: `src/tdoc_crawler/config/__init__.py` — module-level `_cache_managers: dict[str, CacheManager]`
- Pattern: Registered once at CLI entry via `.register()`, resolved everywhere else via `resolve_cache_manager()`
- Properties: `root`, `db_file`, `http_cache_file`, `checkout_dir`, `ai_cache_dir`, `ai_workspace_file`, `ai_embed_dir(model)`
- Environment override: `TDC_CACHE_DIR`, `TDC_AI_STORE_PATH`
- Name-based: supports multiple managers with `name` parameter (default: `"default"`)

**Domain Database Facades:**

- Purpose: Typed database access per domain
- Examples: `TDocDatabase`, `MeetingDatabase`, `SpecDatabase` (all extend `DocDatabase`)
- Pattern: Context manager with auto-schema creation, inherits shared CRUD from `DocDatabase`
- Location: `src/tdoc_crawler/database/`
- Hierarchy: `DocDatabase` (shared: connection management, table ops, crawl logging, reference data) → domain-specific databases (specialized queries/upserts)

**TDoc Sources (Strategy/Protocol Pattern):**

- Purpose: Abstract over different TDoc metadata sources
- Protocol: `src/tdoc_crawler/tdocs/sources/base.py`
- Implementations: `DoclistSource` (Excel batch), `WhatTheSpecSource` (API single), `PortalSource` (authenticated single)
- Factory: `create_source()` in `src/tdoc_crawler/tdocs/sources/__init__.py`
- Location: `src/tdoc_crawler/tdocs/sources/`

**Spec Sources (Strategy/Protocol Pattern):**

- Purpose: Abstract over different specification metadata sources
- Protocol: `src/tdoc_crawler/specs/sources/base.py`
- Implementations: `ThreeGppSpecSource`, `WhatTheSpecSpecSource`
- Location: `src/tdoc_crawler/specs/sources/`

**CrawlResult Dataclasses:**

- Purpose: Standardized result reporting for all crawl operations
- Pattern: Frozen dataclass with `processed`, `inserted`, `updated`, `errors` fields
- Examples: `TDocCrawlResult`, `MeetingCrawlResult`
- Location: `src/tdoc_crawler/tdocs/operations/crawl.py`, `src/tdoc_crawler/meetings/operations/crawl.py`

**ConfigService:**

- Purpose: Unified configuration access combining CacheManager + HttpCacheConfig + CrawlLimits
- Location: `src/tdoc_crawler/config/service.py`
- Pattern: Lazy property resolution from environment variables, `from_env()` classmethod

**BaseConfigModel:**

- Purpose: Shared configuration base for all crawl/query config models
- Location: `src/tdoc_crawler/models/base.py`
- Fields: `cache_manager_name`, `http_cache` (HttpCacheConfig)
- Subclasses: `TDocCrawlConfig`, `TDocQueryConfig`, `MeetingCrawlConfig`, `MeetingQueryConfig`

## Entry Points

**`tdoc-crawler` CLI (Primary — Unified):**

- Location: `src/tdoc_crawler/cli/app.py` → `app` (Typer instance)
- Script entry: `tdoc-crawler = "tdoc_crawler.cli.app:app"` in `pyproject.toml`
- Commands: `crawl-tdocs`, `crawl-meetings`, `crawl-specs`, `query-tdocs`, `query-meetings`, `query-specs`, `open`, `checkout`, `checkout-spec`, `open-spec`, `stats`
- Aliases: `ct`, `cm`, `qt`, `qm` (hidden shortcuts)

**`tdoc-crawler` CLI (TDoc-only variant):**

- Location: `src/tdoc_crawler/cli/tdoc_app.py` → `app`
- Script entry: `tdoc-crawler = "tdoc_crawler.cli.tdoc_app:app"` (alternate)
- Subset: TDocs, meetings, open, checkout, stats commands only

**`spec-crawler` CLI (Spec-only):**

- Location: `src/tdoc_crawler/cli/spec_app.py` → `spec_app`
- Script entry: `spec-crawler = "tdoc_crawler.cli.spec_app:spec_app"`
- Commands: `crawl-specs`, `query-specs`, `checkout-spec`, `open-spec`

**`3gpp-ai` CLI (AI sub-package):**

- Location: `packages/3gpp-ai/threegpp_ai/cli.py`
- Script entry: `3gpp-ai = "threegpp_ai.cli:app"`
- Commands: AI workspace management, RAG queries, document processing

**`__main__` entry:**

- Location: `src/tdoc_crawler/__main__.py`
- Allows `python -m tdoc_crawler` — imports `cli.app:app`

## Error Handling

**Strategy:** Fail fast with clear exceptions. No defensive try-except wrapping. Let errors propagate to the caller.

**Patterns:**

- Custom `DatabaseError` with typed error codes in `src/tdoc_crawler/database/errors.py` (e.g., `connection_not_open`)
- Crawl results carry `errors: list[str]` — non-fatal issues logged as warnings, crawl continues
- CLI catches specific exceptions and prints user-friendly messages via Rich console
- `typer.Exit(code=1)` for user-facing errors, `typer.Exit(code=2)` for invalid arguments
- Portal authentication failures return `None` credentials (graceful degradation — WhatTheSpec fallback)

**Philosophy (from AGENTS.md):**

- Functions have consistent return types — no encoding logic into return values
- `None` in arguments is prohibited (use proper type constraints, not `str | None` for required params)
- Boilerplate error handling is an antipattern — "let it burn if not registered"
- Never use `try/except` to encode control flow or return different types on different code paths

## Cross-Cutting Concerns

**Logging:**

- Framework: Python `logging` module (configured in `src/tdoc_crawler/logging/__init__.py`)
- Pattern: `get_logger(__name__)` for module-level loggers, `get_console()` for Rich console
- Console output: Rich console singleton in `src/tdoc_crawler/cli/_shared.py`
- Levels controlled via `--verbosity` CLI flag (`set_verbosity()`)
- NEVER use `print()` — always use `logging`

**Validation:**

- All data validated via Pydantic models (`BaseModel` with `str_strip_whitespace=True`)
- TDoc IDs normalized to `.upper()` before storage and lookup (case-insensitive)
- CLI arguments use Typer's built-in type validation plus custom `Annotated` types in `cli/args.py`
- Working group/subworking group parsing via `utils/parse.py` helper functions

**Authentication:**

- EOL (ETSI Online) credentials resolved from: CLI args → env vars (`TDC_EOL_USERNAME`/`TDC_EOL_PASSWORD`) → interactive prompt
- Implementation: `src/tdoc_crawler/credentials.py` — `set_credentials()` stores in env, `resolve_credentials()` reads with fallback chain
- Sources declare `requires_authentication` property
- Portal client: `src/tdoc_crawler/clients/portal.py`

**HTTP Caching (Mandatory):**

- Implementation: `create_cached_session()` in `src/tdoc_crawler/http_client/session.py`
- Backend: hishel `SyncSqliteStorage` with configurable TTL (default: 7200s, refresh on access)
- Pool configuration: `PoolConfig` dataclass (max connections, per-host limit, connection timeout, retry strategy)
- Download utility: `download_to_file()` for streaming file downloads with optional session reuse
- Env vars: `HTTP_CACHE_ENABLED`, `HTTP_CACHE_TTL`, `HTTP_CACHE_REFRESH_ON_ACCESS`

**Configuration:**

- Primary: `CacheManager` (file paths), environment variables (credentials, HTTP cache, AI config)
- Secondary: CLI arguments (Typer options with `envvar=` parameter for env var fallbacks)
- AI config: `LightRAGConfig.from_env()` reads `TDC_AI_*` environment variables for LLM/embedding model settings
- ConfigService: `src/tdoc_crawler/config/service.py` provides unified lazy access to all config

**Dependency Direction (Strict):**

- CLI → Core library (never reverse)
- Domain packages → Shared `models/` (neutral layer to avoid circular imports)
- Domain packages → `database/`, `http_client/`, `parsers/`, `config/`
- Sub-packages (`packages/`) → `tdoc_crawler.config` (CacheManager only)

______________________________________________________________________

*Architecture analysis: 2026-03-27*
