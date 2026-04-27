# Architecture

**Analysis Date:** 2026-04-27

## Pattern Overview

**Overall:** Layered CLI-first monorepo with domain modules and shared infrastructure services.

**Key Characteristics:**

- Command entrypoints are thin Typer adapters that delegate to domain operations in `src/tdoc_crawler/cli/tdoc_app.py`, `src/tdoc_crawler/cli/spec_app.py`, and `packages/3gpp-ai/threegpp_ai/cli.py`.
- Domain logic is split by business area (`tdocs`, `meetings`, `specs`) with consistent `models`/`operations`/`sources` separation under `src/tdoc_crawler/`.
- Persistence and transport are centralized in reusable layers (`src/tdoc_crawler/database/`, `src/tdoc_crawler/http_client/`, `src/tdoc_crawler/config/`).

## Layers

**CLI Layer:**

- Purpose: Parse options, configure runtime context, and render output.
- Location: `src/tdoc_crawler/cli/`, `packages/3gpp-ai/threegpp_ai/cli/`
- Contains: Typer apps, option aliases, output formatting adapters.
- Depends on: Domain models/operations, config loader, logging.
- Used by: Script entrypoints in `pyproject.toml` (`tdoc-crawler`, `spec-crawler`, `3gpp-ai`).

**Domain Operations Layer:**

- Purpose: Execute crawl/query/checkout workflows.
- Location: `src/tdoc_crawler/tdocs/operations/`, `src/tdoc_crawler/meetings/operations/`, `src/tdoc_crawler/specs/operations/`
- Contains: Orchestrators such as `TDocCrawler`, `MeetingCrawler`, and spec checkout orchestration.
- Depends on: Database facades, source adapters, parsers, utility normalization.
- Used by: CLI layer and package integrations (notably `packages/3gpp-ai/threegpp_ai/operations/`).

**Source/Client Layer:**

- Purpose: Fetch and normalize data from external systems.
- Location: `src/tdoc_crawler/tdocs/sources/`, `src/tdoc_crawler/specs/sources/`, `src/tdoc_crawler/clients/`, `src/tdoc_crawler/parsers/`
- Contains: Portal/WhatTheSpec/doclist source implementations and HTML parsing.
- Depends on: HTTP client and credential resolution.
- Used by: Domain operations.

**Infrastructure Layer:**

- Purpose: Provide shared runtime services (config, HTTP cache/session, logging, worker execution).
- Location: `src/tdoc_crawler/config/`, `src/tdoc_crawler/http_client/`, `src/tdoc_crawler/logging/`, `src/tdoc_crawler/workers/`, `packages/pool_executors/pool_executors/`
- Contains: `ThreeGPPConfig`, `CacheManager`, cached session factory, subinterpreter worker functions.
- Depends on: pydantic-settings, niquests/hishel, pool executor package.
- Used by: CLI and domain operations.

**Persistence Layer:**

- Purpose: Store and query crawler state and metadata.
- Location: `src/tdoc_crawler/database/`
- Contains: `DocDatabase` lifecycle, table management, and typed facades (`TDocDatabase`, `MeetingDatabase`, `SpecDatabase`).
- Depends on: Oxyde async ORM and model definitions in `src/tdoc_crawler/database/oxyde_models.py`.
- Used by: Domain operations and some CLI query paths.

## Data Flow

**TDoc Crawl Flow:**

1. User executes `tdoc-crawler crawl` (`src/tdoc_crawler/cli/tdoc_app.py` routes to `crawl_tdocs` in `src/tdoc_crawler/cli/crawl.py`).
2. CLI builds `TDocCrawlConfig`, opens `TDocDatabase`, and instantiates `TDocCrawler`.
3. `TDocCrawler.crawl()` loads meetings from DB and dispatches per-meeting worker tasks through `pool_executors.create_executor()` in `src/tdoc_crawler/tdocs/operations/crawl.py`.
4. Worker entrypoint `fetch_meeting_document_list_subinterpreter()` in `src/tdoc_crawler/workers/tdoc_worker.py` fetches doclists and returns JSON payloads.
5. Orchestrator normalizes/deduplicates metadata and persists via `TDocDatabase.bulk_upsert_tdocs()`.

**TDoc Query + On-Demand Fetch Flow:**

1. User executes `tdoc-crawler query` handled by `query_tdocs` in `src/tdoc_crawler/cli/query.py`.
2. CLI queries `TDocDatabase.query_tdocs()` with `TDocQueryConfig`.
3. Missing IDs are resolved by `fetch_missing_tdocs()` in `src/tdoc_crawler/tdocs/operations/fetch.py` using source strategy/fallback.
4. Output is rendered through `src/tdoc_crawler/cli/printing.py` and `src/tdoc_crawler/cli/formatting.py`.

**State Management:**

- Runtime state is file-backed and config-driven (`PathConfig` in `src/tdoc_crawler/config/settings.py`).
- Shared mutable runtime objects are minimized; DB and HTTP sessions are short-lived context-managed instances.
- Parallel crawl state exchange uses serialized JSON payloads between worker boundaries.

## Key Abstractions

**Configuration Abstraction (`ThreeGPPConfig` + `CacheManager`):**

- Purpose: Centralize config loading and path resolution.
- Examples: `src/tdoc_crawler/config/settings.py`, `src/tdoc_crawler/config/cache_manager.py`
- Pattern: Pydantic settings model + registered runtime path manager.

**Source Abstraction (`TDocSource` protocol):**

- Purpose: Hide source-specific fetch details behind a common interface.
- Examples: `src/tdoc_crawler/tdocs/sources/base.py`, `src/tdoc_crawler/tdocs/sources/portal.py`, `src/tdoc_crawler/tdocs/sources/whatthespec.py`
- Pattern: Protocol-driven adapters selected by fetch orchestrators.

**Database Facade Abstraction:**

- Purpose: Expose domain-friendly methods over Oxyde models and SQL lifecycle.
- Examples: `src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/database/tdocs.py`, `src/tdoc_crawler/database/specs.py`
- Pattern: Async facade classes inheriting shared lifecycle behavior.

## Entry Points

**TDoc/Meeting CLI:**

- Location: `src/tdoc_crawler/cli/tdoc_app.py`
- Triggers: `tdoc-crawler` script in root `pyproject.toml` and `python -m tdoc_crawler` via `src/tdoc_crawler/__main__.py`
- Responsibilities: Register command groups, initialize config/cache manager, dispatch to crawl/query/open/checkout paths.

**Spec CLI:**

- Location: `src/tdoc_crawler/cli/spec_app.py`
- Triggers: `spec-crawler` script in root `pyproject.toml`
- Responsibilities: Spec crawl/query/checkout/open workflows.

**AI Extension CLI:**

- Location: `packages/3gpp-ai/threegpp_ai/cli.py`
- Triggers: `3gpp-ai` script in `packages/3gpp-ai/pyproject.toml`
- Responsibilities: Workspace/document AI workflows reusing core crawler storage/query components.

## Error Handling

**Strategy:** Boundary-level exception handling with typed domain errors and CLI-friendly exit behavior.

**Patterns:**

- Database lifecycle wraps failures in `DatabaseError` in `src/tdoc_crawler/database/base.py`.
- Source/client fetch paths catch transport and parse exceptions and either return `None` or aggregate error messages (`src/tdoc_crawler/tdocs/operations/fetch.py`, `src/tdoc_crawler/clients/portal.py`).
- CLI commands convert validation/runtime failures to `typer.Exit` with user-facing Rich output (`src/tdoc_crawler/cli/config_app.py`, `src/tdoc_crawler/cli/query.py`).

## Cross-Cutting Concerns

**Logging:** `tdoc_crawler.logging` logger setup is consumed across core and AI package modules.
**Validation:** Pydantic models/settings validate CLI inputs, config, and metadata schemas.
**Authentication:** Credentials are resolved via `src/tdoc_crawler/credentials.py`; authenticated portal flows run through `PortalClient`.

---

*Architecture analysis: 2026-04-27*
