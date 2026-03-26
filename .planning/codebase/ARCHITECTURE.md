# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Domain-Oriented Modular Architecture with Source Abstraction

**Key Characteristics:**
- Domain-oriented packages (tdocs, meetings, specs) with consistent internal structure
- Source abstraction pattern for data fetching (Protocol-based)
- Layered database with inheritance (DocDatabase → MeetingDatabase → TDocDatabase)
- Centralized configuration via CacheManager singleton
- CLI as thin orchestration layer over core library

## Layers

**CLI Layer:**
- Purpose: Command definitions, argument parsing, user interaction
- Location: `src/tdoc_crawler/cli/`
- Contains: Typer commands, Rich console output, argument types
- Depends on: Core library (tdocs, meetings, specs, database)
- Used by: End users via `tdoc-crawler` command

**Domain Layer:**
- Purpose: Business logic for 3GPP entities (TDocs, Meetings, Specs)
- Location: `src/tdoc_crawler/{tdocs,meetings,specs}/`
- Contains: Operations, sources, models, utilities per domain
- Depends on: Database layer, config, http_client, parsers
- Used by: CLI layer

**Database Layer:**
- Purpose: Persistent storage and query operations
- Location: `src/tdoc_crawler/database/`
- Contains: Database classes with upsert/query operations
- Depends on: Models layer, pydantic-sqlite
- Used by: Domain layer operations

**Models Layer:**
- Purpose: Data structures and validation
- Location: `src/tdoc_crawler/models/`, `src/tdoc_crawler/{domain}/models.py`
- Contains: Pydantic models for metadata, configs, query parameters
- Depends on: Pydantic
- Used by: All layers

**Infrastructure Layer:**
- Purpose: Cross-cutting concerns (HTTP, caching, logging, config)
- Location: `src/tdoc_crawler/{config,http_client,logging,clients,utils}/`
- Contains: CacheManager, HTTP session factory, logging setup
- Depends on: hishel, httpx, requests
- Used by: All layers

**Parsers Layer:**
- Purpose: Data extraction from various formats (HTML, Excel, portal)
- Location: `src/tdoc_crawler/parsers/`
- Contains: HTML/Excel parsers for 3GPP data
- Depends on: beautifulsoup4, lxml, xlsxwriter
- Used by: Domain sources

## Data Flow

**TDoc Crawl Flow:**

1. CLI `crawl-tdocs` command receives arguments
2. Creates `TDocCrawlConfig` from parsed arguments
3. `CacheManager` registered with paths
4. `TDocCrawler.crawl()` orchestrates:
   - Query meetings from database
   - For each meeting, download Excel document list
   - Parse Excel via `DocumentListSource`
   - Upsert TDoc metadata to database
5. Results displayed via Rich console

**TDoc Query Flow:**

1. CLI `query-tdocs` creates `TDocQueryConfig`
2. `TDocDatabase.query_tdocs()` filters by:
   - TDoc IDs (exact match)
   - Working groups (via meeting join)
   - Date ranges (retrieved date, meeting date)
   - Glob patterns (source, title, agenda)
3. Returns list of `TDocMetadata`
4. Output formatted via Rich tables or JSON/YAML

**TDoc Fetch Flow (Missing TDocs):**

1. `fetch_missing_tdocs()` receives requested IDs not in DB
2. Creates appropriate source (`PortalSource` or `WhatTheSpecSource`)
3. Source fetches metadata via HTTP
4. Upserts to database
5. Falls back to WhatTheSpec if portal fails

**Spec Crawl Flow:**

1. CLI `crawl-specs` collects spec numbers
2. `SpecDatabase.crawl_specs()` iterates sources
3. Each `SpecSource.fetch()` retrieves metadata
4. Results stored and optionally checked out

**State Management:**
- SQLite database stores all persistent state
- HTTP cache (hishel) prevents redundant network requests
- `CacheManager` provides single source of truth for paths
- No in-memory state between commands

## Key Abstractions

**CacheManager:**
- Purpose: Central path management for all file operations
- Examples: `src/tdoc_crawler/config/__init__.py`
- Pattern: Singleton registry with name-based resolution
- Properties: `root`, `db_file`, `http_cache_file`, `checkout_dir`, `ai_cache_dir`
- Usage: `resolve_cache_manager(name)` returns registered instance

**TDocSource Protocol:**
- Purpose: Abstract interface for TDoc metadata sources
- Examples: `src/tdoc_crawler/tdocs/sources/base.py`
- Pattern: Protocol-based abstraction
- Implementations: `DocumentListSource`, `PortalSource`, `WhatTheSpecSource`
- Methods: `fetch_by_id()`, `fetch_by_meeting()`, `source_name`, `requires_authentication`

**SpecSource Protocol:**
- Purpose: Abstract interface for specification metadata sources
- Examples: `src/tdoc_crawler/specs/sources/base.py`
- Pattern: Protocol-based abstraction
- Implementations: `ThreeGppSpecSource`, `WhatTheSpecSpecSource`
- Methods: `name`, `fetch()`

**Database Inheritance:**
- Purpose: Layered database operations with shared base
- Pattern: Inheritance chain
- Hierarchy: `DocDatabase` → `MeetingDatabase` → `TDocDatabase`
- Shared: Connection management, table operations, crawl logging
- Specialized: Domain-specific queries and upserts

**Crawler Pattern:**
- Purpose: Orchestrate crawling operations with progress tracking
- Examples: `src/tdoc_crawler/tdocs/operations/crawl.py`, `src/tdoc_crawler/meetings/operations/crawl.py`
- Pattern: Class with `crawl()` method taking config
- Returns: `TDocCrawlResult` with processed/inserted/updated/error counts

**BaseConfigModel:**
- Purpose: Shared configuration base with HTTP cache and cache manager
- Examples: `src/tdoc_crawler/models/base.py`
- Pattern: Pydantic model with common fields
- Subclasses: `TDocCrawlConfig`, `TDocQueryConfig`, `MeetingCrawlConfig`, `MeetingQueryConfig`

## Entry Points

**CLI Main Entry:**
- Location: `src/tdoc_crawler/cli/app.py`
- Triggers: `tdoc-crawler` command
- Responsibilities: Register commands, global options, cache manager setup

**Domain Crawler Entry:**
- Location: `src/tdoc_crawler/{domain}/operations/crawl.py`
- Triggers: CLI crawl commands
- Responsibilities: Orchestrate domain-specific crawling

**Database Entry:**
- Location: `src/tdoc_crawler/database/{domain}.py`
- Triggers: Domain operations
- Responsibilities: CRUD operations, queries, upserts

## Error Handling

**Strategy:** Layered exception handling with domain-specific errors

**Patterns:**
- `DatabaseError` with typed error codes (connection_not_open, etc.)
- `PortalParsingError` for HTML extraction failures
- `ConversionError` hierarchy in convert-lo package
- Validation errors via Pydantic field validators
- Graceful fallbacks (Portal → WhatTheSpec)

## Cross-Cutting Concerns

**Logging:** 
- Module: `src/tdoc_crawler/logging/`
- Pattern: `get_logger(__name__)` returns configured logger
- Levels controlled via `--verbosity` CLI flag

**Validation:**
- Via Pydantic validators in models
- Field validators for normalization (uppercase IDs, enum conversion)
- Model validators for relationship integrity

**Authentication:**
- Portal credentials via environment variables or CLI flags
- `resolve_credentials()` for centralized credential access
- Sources declare `requires_authentication` property

**HTTP Caching:**
- Module: `src/tdoc_crawler/http_client/`
- Pattern: `create_cached_session()` with hishel
- Configuration via `HttpCacheConfig` (TTL, refresh on access)

## Package Architecture

**3gpp-ai Package:**
- Location: `packages/3gpp-ai/threegpp_ai/`
- Purpose: AI-powered document processing (LightRAG integration)
- Key modules: `lightrag/`, `operations/`
- Uses: CacheManager for paths, environment for LLM config

**convert-lo Package:**
- Location: `packages/convert-lo/convert_lo/`
- Purpose: LibreOffice headless document conversion
- Key class: `Converter` with `convert()` method

**pool_executors Package:**
- Location: `packages/pool_executors/pool_executors/`
- Purpose: Serial/parallel execution utilities
- Key classes: `SerialPoolExecutor`, `Runner`, `create_executor()`

---

*Architecture analysis: 2026-03-26*
