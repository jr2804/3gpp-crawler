# Codebase Structure

**Analysis Date:** 2026-05-03

## Directory Layout

```
3gpp-crawler/                         # Repository root
├── .agents/skills/                   # Agent skill definitions (3gpp-*, etc.)
├── .config/                          # IDE/editor config
├── .planning/                        # GSD planning artifacts
├── docs/                             # MkDocs documentation source
├── packages/                         # Workspace member packages
│   ├── 3gpp-ai/                      # AI processing package (separate)
│   ├── convert-lo/                   # LibreOffice document converter
│   └── pool_executors/              # Parallel executor abstractions
├── scripts/                          # Utility scripts
│   └── cache/                        # Cache management scripts
├── src/                              # Main source tree
│   └── tdoc_crawler/                 # Core library package
│       ├── cli/                      # CLI layer (Typer/Rich only)
│       ├── clients/                  # HTTP/API clients (PortalClient)
│       ├── config/                   # Configuration management
│       ├── constants/                # Shared URLs and patterns
│       ├── database/                 # SQLite persistence (Oxyde ORM)
│       ├── extraction/              # Document conversion pipeline
│       ├── http_client/             # HTTP session with caching
│       ├── logging/                  # Rich logging integration
│       ├── meetings/                # Meeting domain package
│       ├── models/                  # Shared data models
│       ├── parsers/                  # HTML/Excel parsing
│       ├── specs/                   # Spec domain package
│       ├── tdocs/                   # TDoc domain package
│       ├── utils/                    # Shared utilities
│       ├── workers/                 # Parallel crawl workers
│       └── workspaces/              # Workspace management
└── tests/                            # Test suite
    ├── config/                       # Config-specific tests
    ├── convert_lo/                   # convert-lo package tests
    ├── data/                         # Test fixtures/data
    └── pool_executor/                # Pool executor tests
```

## Directory Purposes

### `src/tdoc_crawler/cli/`
- Purpose: Typer CLI command definitions and Rich output formatting
- Contains: Three Typer apps (`tdoc_app`, `spec_app`, `mgmt_app`), shared args, formatting helpers
- Key files: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py`, `args.py`, `_workspace_commands.py`, `crawl.py`, `query.py`
- Scoped AGENTS.md: `cli/AGENTS.md` — defines CLI-only vs library code classification

### `src/tdoc_crawler/tdocs/`
- Purpose: TDoc domain — crawling, fetching, checkout, normalization
- Contains: Operations (crawl, fetch, checkout), sources (DocList, WhatTheSpec, Portal), models
- Key files: `operations/crawl.py` (`TDocCrawler`), `operations/fetch.py`, `operations/checkout.py`, `sources/base.py` (`TDocSource` protocol), `models.py`
- Scoped AGENTS.md: `tdocs/AGENTS.md` (at parent level `src/tdoc_crawler/AGENTS.md`)

### `src/tdoc_crawler/specs/`
- Purpose: Spec domain — crawling, downloading, version resolution
- Contains: Operations (checkout), sources (3GPP website, WhatTheSpec), models, downloads
- Key files: `operations/checkout.py`, `sources/threegpp.py`, `sources/whatthespec.py`, `models.py`, `downloads.py`

### `src/tdoc_crawler/meetings/`
- Purpose: Meeting domain — crawling meeting metadata
- Contains: Operations (crawl), sources (empty placeholder), models, utils
- Key files: `operations/crawl.py` (`MeetingCrawler`), `models.py`

### `src/tdoc_crawler/database/`
- Purpose: SQLite persistence using Oxyde ORM
- Contains: Base class, domain-specific DB classes, ORM models, error types, protocols
- Key files: `base.py` (`DocDatabase`), `tdocs.py` (`TDocDatabase`), `meetings.py` (`MeetingDatabase`), `specs.py` (`SpecDatabase`), `oxyde_models.py` (all ORM models), `errors.py`, `protocols.py` (`DatabaseFactory`)

### `src/tdoc_crawler/config/`
- Purpose: Configuration management (settings, paths, env vars, sources)
- Contains: CacheManager, pydantic-settings models, config file discovery, env var mappings, workspace registry, export
- Key files: `cache_manager.py`, `settings.py` (`ThreeGPPConfig`), `env_vars.py`, `sources.py`, `workspace_registry.py`
- Scoped AGENTS.md: `config/AGENTS.md`

### `src/tdoc_crawler/extraction/`
- Purpose: Document conversion pipeline for AI/LLM consumption
- Contains: Office→PDF conversion, OpenDataLoader integration, hybrid server management, metrics, profiles
- Key files: `convert.py` (main conversion), `conversion.py` (PDF backend), `profiles.py` (`ExtractionProfile`), `hybrid_server.py`, `metrics.py`, `fetch_tdoc.py`, `fetch_spec.py`

### `src/tdoc_crawler/workspaces/`
- Purpose: Workspace CRUD and member management
- Contains: Workspace lifecycle, member add/remove/list, utilities
- Key files: `crud.py`, `members.py`, `utils.py`

### `src/tdoc_crawler/models/`
- Purpose: Shared data models and reference data
- Contains: Base types (OutputFormat, PortalCredentials, SortOrder), WG/SubWG records, workspace models, crawl log
- Key files: `base.py`, `workspaces.py`, `working_groups.py`, `subworking_groups.py`, `crawl_log.py`

### `src/tdoc_crawler/http_client/`
- Purpose: HTTP session factory with caching
- Contains: Session creation, download helpers, SSL config, decompression
- Key files: `session.py` (`create_cached_session()`, `download_to_file()`)

### `src/tdoc_crawler/clients/`
- Purpose: API client wrappers
- Contains: Portal client for 3GPP EOL authentication
- Key files: `portal.py` (`PortalClient`)

### `src/tdoc_crawler/parsers/`
- Purpose: HTML and data format parsing
- Contains: Meeting page parser, portal page parser
- Key files: `meetings.py` (`MeetingParser`), `portal.py` (`PortalParser`)

### `src/tdoc_crawler/constants/`
- Purpose: Shared constants — URLs, regex patterns
- Key files: `urls.py` (all 3GPP URLs), `patterns.py` (TDoc ID patterns, date patterns)

### `src/tdoc_crawler/workers/`
- Purpose: Parallel crawl worker functions
- Contains: Subinterpreter worker for meeting document list fetching
- Key files: `tdoc_worker.py` (`fetch_meeting_document_list_subinterpreter`)

### `src/tdoc_crawler/logging/`
- Purpose: Logging configuration with Rich
- Key files: `__init__.py` (`get_logger()`, `set_verbosity()`, `configure_logger()`)

### `src/tdoc_crawler/utils/`
- Purpose: Shared utility functions
- Key files: `normalization.py` (TDoc/Spec ID normalization), `date_parser.py` (partial date parsing), `parse.py` (spec version parsing), `misc.py` (UTC now, etc.)

### `packages/`
- Purpose: Workspace-member packages (local dependencies)
- `convert-lo/`: LibreOffice document conversion wrapper
- `pool_executors/`: Serial/multiprocessing executor abstraction
- `3gpp-ai/`: AI processing package (workspace embeddings, RAG, graph)

### `tests/`
- Purpose: Test suite
- Scoped AGENTS.md: `tests/AGENTS.md`
- Key files: `conftest.py`, domain-specific test files (see TESTING.md)

### `docs/`
- Purpose: MkDocs documentation
- Key files: `development.md` (in-depth dev docs), `crawl.md`, `query.md`, `config.md`, etc.

## Key File Locations

### Entry Points
- `src/tdoc_crawler/cli/tdoc_app.py:tdoc_app`: `tdoc-crawler` CLI command
- `src/tdoc_crawler/cli/spec_app.py:spec_app`: `spec-crawler` CLI command
- `src/tdoc_crawler/cli/mgmt_app.py:mgmt_app`: `3gpp-crawler` CLI command
- `pyproject.toml` → `[project.scripts]`: Console script definitions

### Configuration
- `src/tdoc_crawler/config/cache_manager.py`: `CacheManager` — path single source of truth
- `src/tdoc_crawler/config/settings.py`: `ThreeGPPConfig` — pydantic-settings
- `src/tdoc_crawler/config/env_vars.py`: `ConfigEnvVar` enum — env var mappings
- `src/tdoc_crawler/config/sources.py`: Config file discovery and merging
- `src/tdoc_crawler/config/workspace_registry.py`: Workspace JSON persistence
- `ruff.toml`: Linting configuration
- `ty.toml`: Type checker configuration
- `pyproject.toml`: Build config, pytest, coverage

### Core Logic
- `src/tdoc_crawler/tdocs/operations/crawl.py`: `TDocCrawler` — parallel TDoc crawl orchestrator
- `src/tdoc_crawler/meetings/operations/crawl.py`: `MeetingCrawler` — meeting crawl orchestrator
- `src/tdoc_crawler/tdocs/operations/fetch.py`: `fetch_missing_tdocs()` — targeted TDoc fetch
- `src/tdoc_crawler/tdocs/operations/checkout.py`: `checkout_tdoc()` — download + extract
- `src/tdoc_crawler/specs/operations/checkout.py`: `checkout_spec()` — spec checkout + release resolution
- `src/tdoc_crawler/database/base.py`: `DocDatabase` — base DB with Oxyde ORM
- `src/tdoc_crawler/database/oxyde_models.py`: All ORM model definitions
- `src/tdoc_crawler/extraction/convert.py`: `convert_for_wiki()` — workspace extraction pipeline

### Database
- `src/tdoc_crawler/database/tdocs.py`: `TDocDatabase` — TDoc + Meeting queries
- `src/tdoc_crawler/database/meetings.py`: `MeetingDatabase` — Meeting queries
- `src/tdoc_crawler/database/specs.py`: `SpecDatabase` — Spec crawl + queries
- `src/tdoc_crawler/database/errors.py`: `DatabaseError` types
- `src/tdoc_crawler/database/protocols.py`: `DatabaseFactory` protocol

### Models
- `src/tdoc_crawler/models/base.py`: `OutputFormat`, `PortalCredentials`, `SortOrder`
- `src/tdoc_crawler/models/workspaces.py`: `Workspace`, `SourceKind`, extraction element models
- `src/tdoc_crawler/models/working_groups.py`: `WorkingGroupRecord`, WG reference data
- `src/tdoc_crawler/models/subworking_groups.py`: `SubWorkingGroupRecord`, SubWG reference data
- `src/tdoc_crawler/tdocs/models.py`: `TDocMetadata`, `TDocCrawlConfig`, `TDocQueryConfig`
- `src/tdoc_crawler/meetings/models.py`: `MeetingMetadata`, `MeetingCrawlConfig`, `MeetingQueryConfig`
- `src/tdoc_crawler/specs/models.py`: Spec query models

### Source Adapters
- `src/tdoc_crawler/tdocs/sources/base.py`: `TDocSource` protocol, `TDocSourceConfig`
- `src/tdoc_crawler/tdocs/sources/doclist.py`: `DocumentListSource` — batch FTP crawl
- `src/tdoc_crawler/tdocs/sources/whatthespec.py`: `WhatTheSpecSource` — single lookups
- `src/tdoc_crawler/tdocs/sources/portal.py`: `PortalSource` — authenticated portal
- `src/tdoc_crawler/specs/sources/base.py`: `SpecSource` protocol, `FunctionSpecSource`
- `src/tdoc_crawler/specs/sources/threegpp.py`: `fetch_threegpp_metadata()` — primary spec source
- `src/tdoc_crawler/specs/sources/whatthespec.py`: `fetch_whatthespec_metadata()` — fallback spec source

### HTTP & Clients
- `src/tdoc_crawler/http_client/session.py`: `create_cached_session()`, `download_to_file()`
- `src/tdoc_crawler/clients/portal.py`: `PortalClient` — EOL authentication

### Shared
- `src/tdoc_crawler/constants/urls.py`: All 3GPP URL constants
- `src/tdoc_crawler/constants/patterns.py`: Regex patterns (TDoc ID, date, etc.)
- `src/tdoc_crawler/utils/normalization.py`: TDoc/Spec ID normalization
- `src/tdoc_crawler/utils/date_parser.py`: Partial date parsing (YYYY, YYYY-MM, YYYY-MM-DD)
- `src/tdoc_crawler/utils/parse.py`: Spec version parsing
- `src/tdoc_crawler/logging/__init__.py`: `get_logger()`, `set_verbosity()`

### Testing
- `tests/conftest.py`: Shared fixtures
- `tests/test_crawler.py`: TDoc crawler tests
- `tests/test_database.py`: Database operation tests
- `tests/test_workspaces.py`: Workspace management tests
- `tests/test_cli.py`: CLI integration tests

## Naming Conventions

### Files
- CLI commands: `{domain}_app.py` for Typer apps (e.g., `tdoc_app.py`, `spec_app.py`, `mgmt_app.py`)
- Operations: `crawl.py`, `fetch.py`, `checkout.py` within `*/operations/`
- Sources: Named by provider within `*/sources/` (e.g., `doclist.py`, `whatthespec.py`, `portal.py`)
- Models: `models.py` at each domain package root
- Database: Domain names in `database/` (e.g., `tdocs.py`, `specs.py`, `meetings.py`)
- Tests: `test_{feature}.py` in `tests/`

### Directories
- Domain packages: Plural lowercase (e.g., `tdocs/`, `specs/`, `meetings/`)
- Each domain has: `operations/`, `sources/`, `models.py`
- Infrastructure: Singular lowercase (e.g., `config/`, `database/`, `extraction/`)
- CLI sub-apps: Named `*_app.py`

### Types
- Typer Annotated options: `{Name}Option` (e.g., `WorkingGroupOption`, `StartDateOption`)
- Typer Annotated arguments: `{Name}Argument` (e.g., `TDocIdArgument`, `SpecArgument`)
- Config models: `{Name}Config` (e.g., `PathConfig`, `HttpConfig`, `CrawlConfig`)
- Crawl results: `{Domain}CrawlResult` (e.g., `TDocCrawlResult`, `MeetingCrawlResult`)
- Protocols: `{Domain}Source` (e.g., `TDocSource`, `SpecSource`)
- Database classes: `{Domain}Database` (e.g., `TDocDatabase`, `SpecDatabase`)

## Where to Add New Code

### New TDoc CLI Command
- CLI definition: `src/tdoc_crawler/cli/tdoc_app.py` (or `crawl.py`/`query.py`)
- CLI args: `src/tdoc_crawler/cli/args.py`
- Core logic: `src/tdoc_crawler/tdocs/operations/` (new module)
- Tests: `tests/test_crawler.py` or new `tests/test_{feature}.py`

### New Spec CLI Command
- CLI definition: `src/tdoc_crawler/cli/spec_app.py`
- Core logic: `src/tdoc_crawler/specs/operations/` (new module)
- Tests: `tests/test_specs_*.py`

### New Workspace Command
- CLI definition: `src/tdoc_crawler/cli/_workspace_commands.py`
- Core logic: `src/tdoc_crawler/workspaces/` (crud.py or members.py)
- Tests: `tests/test_workspaces.py`

### New Data Source (e.g., new API)
- Protocol: Already defined in `src/tdoc_crawler/tdocs/sources/base.py` or `specs/sources/base.py`
- Implementation: New file in `*/sources/` (e.g., `tdocs/sources/newsource.py`)
- Register: Import from `*/sources/__init__.py`
- Use in operations: Import and call from relevant operation

### New Database Table/Model
- ORM model: `src/tdoc_crawler/database/oxyde_models.py`
- Register in `_ensure_tables_exist()`: `src/tdoc_crawler/database/base.py`
- Add to `_clear_tables()` map: `src/tdoc_crawler/database/base.py`
- Domain-specific DB class: Add methods to `database/tdocs.py`, `database/specs.py`, or `database/meetings.py`

### New Extraction Profile
- Profile enum: `src/tdoc_crawler/extraction/profiles.py`
- Conversion logic: `src/tdoc_crawler/extraction/convert.py`

### New Shared Utility
- Location: `src/tdoc_crawler/utils/` (new module or existing)
- Import from: `tdoc_crawler.utils.{module}`

### New CLI Option
- Type definition: `src/tdoc_crawler/cli/args.py`
- Use in command: Import and add as parameter

## Special Directories

### `packages/`
- Purpose: Workspace-member local packages
- Managed by: `uv workspace` (defined in `pyproject.toml [tool.uv.workspace]`)
- Committed: Yes
- Packages: `convert-lo` (LibreOffice wrapper), `pool_executors` (parallelism), `3gpp-ai` (AI pipeline)

### `.agents/skills/`
- Purpose: Agent skill definitions for AI-assisted development
- Contains: 3gpp domain skills, tool skills, workflow skills
- Committed: Yes
- Generated: No

### `.planning/`
- Purpose: GSD (Getting Stuff Done) planning artifacts
- Contains: Phase plans, codebase analysis documents
- Committed: Partially (codebase docs yes, transient plans maybe)

### `docs/`
- Purpose: MkDocs documentation source
- Committed: Yes
- Build: `mkdocs build` or `mkdocs serve`

### `tests/data/`
- Purpose: Test fixtures and sample data
- Committed: Yes

---

*Structure analysis: 2026-05-03*
