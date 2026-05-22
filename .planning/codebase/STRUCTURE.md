# Codebase Structure

**Analysis Date:** 2026-05-22

## Directory Layout

```
3gpp-crawler/
├── .agents/                  # Agent skills (3gpp-*, coding-*, etc.)
├── .planning/                # GSD planning artifacts
├── docs/                     # MkDocs documentation
├── packages/                 # Workspace-member packages
│   ├── convert-lo/           # LibreOffice conversion helpers
│   └── pool_executors/       # Executor pool extensions
├── scripts/                  # Utility scripts and cache tools
├── src/
│   └── tdoc_crawler/         # Main package
│       ├── cli/              # Thin CLI layer (Typer + Rich)
│       │   ├── crawl/        # Crawl commands (tdocs, meetings, specs)
│       │   ├── query/        # Query commands (tdocs, meetings, specs)
│       │   └── workspace/    # Workspace commands (create, process, members)
│       ├── clients/          # External API clients (Portal)
│       ├── config/           # Configuration and path management
│       ├── constants/        # Shared constants (URLs, patterns)
│       ├── database/         # Database layer (Oxyde ORM + SQLite)
│       ├── extraction/       # Document extraction pipeline
│       │   └── docling/      # Docling integration
│       ├── http_client/      # HTTP session factory with caching
│       ├── logging/          # Rich-based logging
│       ├── meetings/         # Meeting domain
│       │   ├── operations/   # Crawl operations
│       │   └── sources/      # Portal source
│       ├── models/           # Cross-domain shared models
│       ├── parsers/          # HTML/portal data parsers
│       ├── specs/            # Specification domain
│       │   ├── operations/   # Checkout operations
│       │   └── sources/      # 3GPP, WhatTheSpec sources
│       ├── tdocs/            # TDoc domain
│       │   ├── operations/   # Crawl, fetch, checkout operations
│       │   └── sources/      # DocList, Portal, WhatTheSpec sources
│       ├── utils/            # Shared utilities
│       ├── workers/          # Parallel execution workers
│       └── workspaces/       # Workspace CRUD and member management
└── tests/                    # Test suite
    ├── config/               # Config tests
    ├── convert_lo/           # convert-lo package tests
    ├── data/                 # Test fixtures and data
    └── pool_executor/        # pool-executors package tests
```

## Directory Purposes

**`src/tdoc_crawler/cli/`:**
- Purpose: Typer command definitions, Rich console output, CLI argument types
- Contains: App definitions, crawl/query/workspace subcommands, formatting, printing
- Key files: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py`, `args.py`, `formatting.py`

**`src/tdoc_crawler/cli/crawl/`:**
- Purpose: Crawl command implementations for all three domains
- Contains: `meetings.py`, `specs.py`, `tdocs.py`, `_helpers.py`
- Key files: All domain-specific crawl commands

**`src/tdoc_crawler/cli/query/`:**
- Purpose: Query command implementations for all three domains
- Contains: `meetings.py`, `specs.py`, `tdocs.py`, `_helpers.py`
- Key files: All domain-specific query commands

**`src/tdoc_crawler/cli/workspace/`:**
- Purpose: Workspace management CLI commands
- Contains: `create.py`, `lifecycle.py`, `members.py`, `process.py`
- Key files: `process.py` (main extraction orchestration)

**`src/tdoc_crawler/tdocs/`:**
- Purpose: TDoc domain — core crawling, fetching, checkout operations
- Contains: `operations/` (crawl, fetch, checkout), `sources/` (doclist, portal, whatthespec), `models.py`
- Key files: `operations/fetch.py`, `operations/crawl.py`, `operations/checkout.py`, `sources/doclist.py`, `models.py`

**`src/tdoc_crawler/meetings/`:**
- Purpose: Meeting domain — crawl operations and portal source
- Contains: `operations/` (crawl), `sources/` (portal), `models.py`, `utils.py`
- Key files: `operations/crawl.py`, `sources/portal.py`, `models.py`

**`src/tdoc_crawler/specs/`:**
- Purpose: Specification domain — checkout, sources for metadata
- Contains: `operations/` (checkout), `sources/` (threegpp, whatthespec, base), `models.py`, `downloads.py`
- Key files: `operations/checkout.py`, `sources/threegpp.py`, `sources/whatthespec.py`

**`src/tdoc_crawler/database/`:**
- Purpose: SQLite persistence via Oxyde ORM
- Contains: Oxyde model definitions, database facade classes, protocols, errors
- Key files: `oxyde_models.py` (all ORM models), `base.py` (DocDatabase), `tdocs.py`, `meetings.py`, `specs.py`

**`src/tdoc_crawler/config/`:**
- Purpose: Configuration management and centralized path resolution
- Contains: `CacheManager`, `ThreeGPPConfig`, env vars, config discovery, workspace registry
- Key files: `cache_manager.py`, `settings.py`, `workspace_registry.py`, `env_vars.py`, `sources.py`

**`src/tdoc_crawler/extraction/`:**
- Purpose: Document conversion and extraction pipeline
- Contains: Profile definitions, Docling integration, LibreOffice conversion, metrics, fetch helpers
- Key files: `profiles.py`, `convert.py`, `docling/pipeline.py`, `docling/converter.py`, `checkout.py`

**`src/tdoc_crawler/http_client/`:**
- Purpose: HTTP session factory with hishel caching and HTTP/3 mitigation
- Contains: Session creation, download helpers, protocol definitions
- Key files: `session.py`, `protocols.py`

**`src/tdoc_crawler/clients/`:**
- Purpose: External API clients (3GPP Portal authentication)
- Key files: `portal.py` (PortalClient, PortalAuthenticationError)

**`src/tdoc_crawler/parsers/`:**
- Purpose: HTML and data format parsers
- Key files: `portal.py` (PortalParser, parse_tdoc_portal_page)

**`src/tdoc_crawler/models/`:**
- Purpose: Cross-domain shared models, reference data, enumerations
- Key files: `base.py` (OutputFormat, SortOrder), `working_groups.py`, `subworking_groups.py`, `workspaces.py`, `crawl_log.py`

**`src/tdoc_crawler/constants/`:**
- Purpose: Shared constants (URLs, regex patterns)
- Key files: `urls.py`, `patterns.py`

**`src/tdoc_crawler/utils/`:**
- Purpose: Shared utilities
- Key files: `normalization.py`, `date_parser.py`, `version_types.py`, `security.py`, `misc.py`, `parse.py`

**`src/tdoc_crawler/logging/`:**
- Purpose: Rich-based logging setup
- Key files: `__init__.py` (get_logger, set_verbosity, configure_logger, get_console)

**`src/tdoc_crawler/workspaces/`:**
- Purpose: Workspace CRUD and member management logic
- Key files: `crud.py`, `members.py`, `utils.py`

**`src/tdoc_crawler/workers/`:**
- Purpose: Parallel execution workers for subinterpreter-based crawling
- Key files: `tdoc_worker.py`

**`packages/convert-lo/`:**
- Purpose: LibreOffice headless CLI conversion library
- Key files: `converter.py`, `locator.py`, `formats.py`

**`packages/pool_executors/`:**
- Purpose: Lightweight executor pool extensions (serial execution support)

**`docs/`:**
- Purpose: MkDocs documentation source
- Key files: `development.md`, `workspace.md`, `crawl.md`, `query.md`

## Key File Locations

### Entry Points:
- `src/tdoc_crawler/cli/tdoc_app.py`: `tdoc-crawler` CLI (TDocs, meetings, open, checkout, stats)
- `src/tdoc_crawler/cli/spec_app.py`: `spec-crawler` CLI (specs, crawl, query, checkout, open)
- `src/tdoc_crawler/cli/mgmt_app.py`: `3gpp-crawler` CLI (config, workspace management)
- `src/tdoc_crawler/__main__.py`: Python module execution entry

### Configuration:
- `pyproject.toml`: Project metadata, dependencies, build config, CLI scripts
- `src/tdoc_crawler/config/settings.py`: `ThreeGPPConfig` with nested models (PathConfig, HttpConfig, CredentialsConfig, CrawlConfig)
- `src/tdoc_crawler/config/cache_manager.py`: `CacheManager` singleton for all file paths
- `src/tdoc_crawler/config/env_vars.py`: `ConfigEnvVar` enum for all env var names
- `src/tdoc_crawler/config/sources.py`: Config file discovery and loading
- `ruff.toml`: Linting configuration
- `ty.toml`: Type checker configuration

### Core Logic:
- `src/tdoc_crawler/database/oxyde_models.py`: All Oxyde ORM models (TDocMetadata, MeetingMetadata, Specification, etc.)
- `src/tdoc_crawler/tdocs/operations/fetch.py`: TDoc fetch orchestration with source selection
- `src/tdoc_crawler/tdocs/operations/crawl.py`: TDocCrawler class for batch crawling
- `src/tdoc_crawler/tdocs/operations/checkout.py`: TDoc download and extraction
- `src/tdoc_crawler/meetings/operations/crawl.py`: MeetingCrawler class
- `src/tdoc_crawler/specs/operations/checkout.py`: Spec download and conversion
- `src/tdoc_crawler/extraction/convert.py`: Document conversion pipeline (Docling, pymupdf4llm, LibreOffice)
- `src/tdoc_crawler/extraction/profiles.py`: ExtractionProfile, FiguresMode, TablesMode, DeviceType enums

### CLI Types:
- `src/tdoc_crawler/cli/args.py`: All Typer `Annotated` option/argument types
- `src/tdoc_crawler/cli/formatting.py`: Output formatting (table, JSON, ISON, TOON, YAML)
- `src/tdoc_crawler/cli/printing.py`: Rich table rendering for TDocs, meetings, specs
- `src/tdoc_crawler/cli/_shared.py`: Shared console and progress bar helpers
- `src/tdoc_crawler/cli/constants.py`: Help panel names

### Domain Models (non-DB):
- `src/tdoc_crawler/tdocs/models.py`: TDocCrawlConfig, TDocQueryConfig, TDocStatus
- `src/tdoc_crawler/meetings/models.py`: MeetingCrawlConfig, MeetingQueryConfig
- `src/tdoc_crawler/specs/models.py`: SpecQueryFilters, SpecQueryResult (dataclasses)
- `src/tdoc_crawler/models/workspaces.py`: Workspace, SourceKind, DocumentClassification, extraction element models

### Testing:
- `tests/conftest.py`: Shared test fixtures
- `tests/test_database.py`: Database layer tests
- `tests/test_models.py`: Model validation tests
- `tests/test_portal_client.py`: Portal client tests
- `tests/test_workspaces.py`: Workspace management tests
- `tests/test_specs_database.py`: Spec database tests

## Naming Conventions

### Files:
- Python modules use `snake_case.py`: `cache_manager.py`, `tdoc_app.py`, `crawl.py`
- Test files use `test_` prefix: `test_database.py`, `test_portal_client.py`
- Private helpers use `_` prefix: `_shared.py`, `_helpers.py`
- Package init files: `__init__.py` with explicit `__all__`

### Directories:
- Domain packages: `tdocs/`, `meetings/`, `specs/` — each with `operations/` and `sources/` subdirectories
- Infrastructure: `config/`, `database/`, `http_client/`, `clients/`, `extraction/`
- Cross-cutting: `models/`, `constants/`, `utils/`, `parsers/`, `logging/`

### Classes:
- Database classes: `<Domain>Database` (e.g., `TDocDatabase`, `MeetingDatabase`, `SpecDatabase`)
- Crawler classes: `<Domain>Crawler` (e.g., `TDocCrawler`, `MeetingCrawler`)
- Config models: `<Domain>CrawlConfig`, `<Domain>QueryConfig` (Pydantic BaseModel)
- ORM models: Direct entity names (e.g., `TDocMetadata`, `MeetingMetadata`, `Specification`)
- Protocols: `<Domain>Source` (e.g., `TDocSource`, `SpecSource`)
- CLI option types: `<Name>Option` or `<Name>Argument` as `Annotated` types in `args.py`

### Functions:
- Public API: `snake_case` with verbs (`crawl_meetings`, `fetch_missing_tdocs`, `checkout_tdoc`)
- Private helpers: `_snake_case` prefix
- Async functions: Same naming, always `async def`
- Factory functions: `create_*` pattern (`create_cached_session`, `create_source`)

## Where to Add New Code

### New Domain Feature (e.g., new TDoc operation):
- Operations: `src/tdoc_crawler/tdocs/operations/new_operation.py`
- CLI command: `src/tdoc_crawler/cli/crawl/tdocs.py` or `src/tdoc_crawler/cli/query/tdocs.py`
- Register command in: `src/tdoc_crawler/cli/tdoc_app.py`

### New Data Source (e.g., new API):
- Implement `TDocSource` or `SpecSource` protocol in: `src/tdoc_crawler/<domain>/sources/<name>.py`
- Register in source factory: `src/tdoc_crawler/tdocs/operations/fetch.py` (`create_source()`)

### New Database Table/Model:
- Add Oxyde model to: `src/tdoc_crawler/database/oxyde_models.py`
- Add to `__all__` in: `src/tdoc_crawler/database/__init__.py`
- Add to `_table_to_model` in: `src/tdoc_crawler/database/base.py`
- Create domain-specific database class if needed: `src/tdoc_crawler/database/<domain>.py`

### New CLI Option:
- Define as `Annotated` type in: `src/tdoc_crawler/cli/args.py`
- Use `StrEnum` for multi-value options (never bare `str` with manual validation)
- Add env var to: `src/tdoc_crawler/config/env_vars.py` (`ConfigEnvVar` enum)

### New Extraction Profile:
- Add to `ExtractionProfile` enum in: `src/tdoc_crawler/extraction/profiles.py`
- Handle in conversion logic: `src/tdoc_crawler/extraction/convert.py`

### New Workspace Feature:
- Core logic: `src/tdoc_crawler/workspaces/<feature>.py`
- CLI command: `src/tdoc_crawler/cli/workspace/<feature>.py`
- Register in: `src/tdoc_crawler/cli/workspace/__init__.py`

### New Utility/Shared Code:
- Shared helpers: `src/tdoc_crawler/utils/<name>.py`
- Constants/URLs: `src/tdoc_crawler/constants/urls.py` or `src/tdoc_crawler/constants/patterns.py`
- Shared models: `src/tdoc_crawler/models/<name>.py`

### Tests:
- Unit tests: `tests/test_<feature>.py`
- Integration tests: `tests/test_<feature>.py` with `@pytest.mark.integration`
- Test data: `tests/data/`
- Config tests: `tests/config/`

## Special Directories

**`.agents/skills/`:**
- Purpose: Agent skill definitions (3gpp-basics, 3gpp-tdocs, etc.)
- Generated: No
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning artifacts and codebase analysis
- Generated: Yes (by GSD commands)
- Committed: Yes

**`packages/`:**
- Purpose: UV workspace member packages (convert-lo, pool_executors)
- Generated: No
- Committed: Yes

**`docs/`:**
- Purpose: MkDocs documentation source
- Generated: No
- Committed: Yes

**`src/tdoc_crawler/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes
- Committed: No (via .gitignore)

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (by `uv`)
- Committed: No

## CLI Entry Points (from pyproject.toml)

| Command | Entry Point | Purpose |
|---------|-------------|---------|
| `tdoc-crawler` | `tdoc_crawler.cli.tdoc_app:tdoc_app` | TDocs + meetings: crawl, query, open, checkout, stats |
| `spec-crawler` | `tdoc_crawler.cli.spec_app:spec_app` | Specs: crawl, query, checkout, open |
| `3gpp-crawler` | `tdoc_crawler.cli.mgmt_app:mgmt_app` | Management: config, workspace |

## Model Type Decision Guide

| Use When | Tool | Location |
|----------|------|----------|
| Persisting to SQLite | Oxyde `Model` | `src/tdoc_crawler/database/oxyde_models.py` |
| Passing data, no DB | `dataclass` | Domain module (e.g., `specs/models.py`) |
| Pydantic validators/serializers | Pydantic `BaseModel` | Domain module (e.g., `tdocs/models.py`) |

---

*Structure analysis: 2026-05-22*
