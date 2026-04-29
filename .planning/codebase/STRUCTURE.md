# Codebase Structure

**Analysis Date:** 2026-04-30

## Directory Layout

```
3gpp-crawler/
├── src/
│   ├── tdoc_crawler/                # Main library package
│   │   ├── __init__.py
│   │   ├── cli/                     # Typer CLI apps and commands
│   │   │   ├── __init__.py
│   │   │   ├── tdoc_app.py          # TDoc/Meetings CLI entry point
│   │   │   ├── spec_app.py          # Spec CLI entry point
│   │   │   ├── mgmt_app.py          # Management CLI entry point
│   │   │   ├── crawl.py             # crawl, crawl-meetings, crawl-specs handlers
│   │   │   ├── query.py             # query, query-meetings, query-specs handlers
│   │   │   ├── config_app.py        # config init, validate, show, docs
│   │   │   ├── specs.py             # checkout, open spec commands
│   │   │   ├── _workspace_commands.py # workspace create, checkout, export
│   │   │   ├── args.py              # Typer argument/option definitions
│   │   │   ├── config.py            # CLI config loading
│   │   │   ├── constants.py         # Help text, panels, messages
│   │   │   ├── formatting.py        # Output formatting (table, JSON, YAML, ISON)
│   │   │   ├── printing.py          # Table rendering helpers
│   │   │   ├── utils.py             # CLI utilities (open files, etc.)
│   │   │   └── _shared.py           # Shared resources (console, progress bars)
│   │   │
│   │   ├── config/                  # Configuration management
│   │   │   ├── __init__.py          # Exports public API
│   │   │   ├── settings.py          # Pydantic config models (ThreeGPPConfig, etc.)
│   │   │   ├── cache_manager.py     # CacheManager singleton
│   │   │   ├── sources.py           # Config file discovery/loading
│   │   │   ├── export.py            # Config export (TOML, docs)
│   │   │   ├── env_vars.py          # Environment variable mappings
│   │   │   ├── workspace_registry.py # Workspace discovery
│   │   │   └── AGENTS.md            # Config layer instructions
│   │   │
│   │   ├── database/                # SQLite database (Oxyde ORM)
│   │   │   ├── __init__.py          # Exports: TDocDatabase, MeetingDatabase, SpecDatabase
│   │   │   ├── base.py              # DocDatabase base class, schema
│   │   │   ├── tdocs.py             # TDocDatabase operations
│   │   │   ├── meetings.py          # MeetingDatabase operations
│   │   │   ├── specs.py             # SpecDatabase operations
│   │   │   ├── oxyde_models.py      # Oxyde ORM models (TDocMetadata, MeetingMetadata, Specification, etc.)
│   │   │   └── errors.py            # DatabaseError exception
│   │   │
│   │   ├── tdocs/                   # TDoc domain
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # TDocMetadata, TDocCrawlConfig, TDocQueryConfig
│   │   │   ├── utils.py             # TDoc utility functions
│   │   │   ├── operations/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── crawl.py         # TDocCrawler orchestrator
│   │   │   │   ├── fetch.py         # fetch_missing_tdocs utility
│   │   │   │   └── checkout.py      # checkout_tdocs, prepare_tdoc_file
│   │   │   └── sources/
│   │   │       ├── __init__.py
│   │   │       ├── base.py          # TDocSource abstract base
│   │   │       ├── doclist.py       # ExcelDocListSource
│   │   │       ├── portal.py        # PortalTDocSource (EOL-protected)
│   │   │       └── whatthespec.py   # WhatTheSpecSource
│   │   │
│   │   ├── specs/                   # Specification domain
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # Specification, SpecVersion, SpecQueryConfig
│   │   │   ├── downloads.py         # SpecDownloadManager
│   │   │   ├── operations/
│   │   │   │   ├── __init__.py
│   │   │   │   └── checkout.py      # checkout_specs, build_default_spec_sources
│   │   │   └── sources/
│   │   │       ├── __init__.py
│   │   │       ├── base.py          # SpecSource abstract base
│   │   │       ├── threegpp.py      # ThreeGPPSource (FTP)
│   │   │       └── whatthespec.py   # WhatTheSpecSource (API)
│   │   │
│   │   ├── meetings/                # Meeting domain
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig
│   │   │   ├── utils.py             # Meeting utility functions
│   │   │   ├── operations/
│   │   │   │   ├── __init__.py
│   │   │   │   └── crawl.py         # MeetingCrawler orchestrator
│   │   │   └── sources/
│   │   │       └── __init__.py      # (Placeholder for future sources)
│   │   │
│   │   ├── extraction/              # Document extraction pipeline
│   │   │   ├── __init__.py          # Exports all conversion functions
│   │   │   ├── convert.py           # convert_document_to_markdown, convert_tdoc_to_markdown
│   │   │   ├── conversion.py        # ConverterBackend, convert_to_pdf, office format handling
│   │   │   ├── fetch_tdoc.py        # fetch_tdoc_files, TDocFiles
│   │   │   ├── checkout.py          # Extraction workspace checkout
│   │   │   ├── profiles.py          # DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
│   │   │   ├── metrics.py           # MetricsTracker, performance monitoring
│   │   │   └── workspace_utils.py   # Workspace directory management
│   │   │
│   │   ├── workers/                 # Parallel execution workers
│   │   │   ├── __init__.py
│   │   │   └── tdoc_worker.py       # fetch_meeting_document_list_subinterpreter
│   │   │
│   │   ├── models/                  # Shared domain models
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # OutputFormat, PortalCredentials, SortOrder
│   │   │   ├── working_groups.py    # WorkingGroup enum (SA, RAN, CT, etc.)
│   │   │   ├── subworking_groups.py # SubWorkingGroup enum and SUBTB_INDEX
│   │   │   ├── workspaces.py        # Workspace model
│   │   │   └── crawl_log.py         # CrawlLogEntry
│   │   │
│   │   ├── parsers/                 # Metadata parsing
│   │   │   ├── __init__.py
│   │   │   ├── protocols.py         # Parser protocol definitions
│   │   │   ├── portal.py            # 3GPP portal HTML parser
│   │   │   └── meetings.py          # Meeting page parser
│   │   │
│   │   ├── clients/                 # External API clients
│   │   │   ├── __init__.py
│   │   │   └── portal.py            # PortalClient (EOL authentication, API calls)
│   │   │
│   │   ├── utils/                   # Shared utilities
│   │   │   ├── __init__.py
│   │   │   ├── normalization.py     # normalize_tdoc_id, normalize_spec_number, etc.
│   │   │   ├── parse.py             # parse_working_groups, parse_subgroups, collect_spec_numbers
│   │   │   ├── date_parser.py       # parse_partial_date
│   │   │   ├── security.py          # Secure credential handling
│   │   │   ├── misc.py              # Miscellaneous helpers (utc_now, etc.)
│   │   │
│   │   ├── http_client              # (Externally sourced module)
│   │   │   └── Used via: from tdoc_crawler.http_client import create_cached_session
│   │   │
│   │   ├── logging.py               # Logging setup (get_logger, set_verbosity)
│   │   ├── credentials.py           # Credential input/storage
│   │   └── __main__.py              # Entry point for `python -m tdoc_crawler`
│   │
│   └── AGENTS.md                    # Core library instructions
│
├── packages/
│   ├── pool_executors/              # Parallel executor library
│   │   ├── pool_executors/
│   │   │   ├── __init__.py          # Exports: create_executor
│   │   │   ├── types.py             # ExecutorMode, executor types
│   │   │   ├── factory.py           # Executor creation logic
│   │   │   ├── runner.py            # Task runner and submission
│   │   │   └── serial.py            # Serial executor implementation
│   │   └── pyproject.toml
│   │
│   └── convert-lo/                  # LibreOffice converter
│       ├── convert_lo/
│       │   ├── __init__.py
│       │   └── (LibreOffice integration)
│       └── pyproject.toml
│
├── tests/                           # Unit and integration tests
│   ├── __init__.py
│   ├── test_models.py               # Model tests
│   ├── test_normalization.py        # Normalization function tests
│   ├── test_whatthespec.py          # WhatTheSpec API tests
│   ├── test_portal_auth.py          # Portal authentication tests
│   ├── test_portal_client.py        # Portal client tests
│   ├── test_specs_*.py              # Spec-related tests (sources, downloads, database, CLI, etc.)
│   ├── test_specs_normalization.py  # Spec normalization
│   ├── test_targeted_fetch.py       # TDoc fetch tests
│   ├── test_workspaces.py           # Workspace tests
│   ├── test_new_cli_flags.py        # CLI argument tests
│   └── AGENTS.md                    # Test layer instructions
│
├── scripts/
│   └── demo.py                      # Demonstration scripts
│
├── .planning/
│   └── codebase/                    # (Generated documents directory)
│       ├── ARCHITECTURE.md          # (This file)
│       └── STRUCTURE.md             # (This file)
│
├── .config/
│   └── mise/
│       └── config.toml              # Task definitions
│
├── docs/
│   ├── development.md               # Development guide
│   └── (Other documentation)
│
├── pyproject.toml                   # Project metadata, dependencies, scripts
├── README.md                        # Project overview
└── .env.example                     # Example environment variables
```

## Directory Purposes

**`src/tdoc_crawler/cli/`:**
- Purpose: Typer command definitions and CLI interface
- Contains: Command handlers, output formatting, argument parsing
- Key files: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py` (entry points)

**`src/tdoc_crawler/config/`:**
- Purpose: Configuration management, path resolution, environment handling
- Contains: Pydantic config models, CacheManager singleton, config file discovery
- Key files: `cache_manager.py` (MANDATORY for all path operations), `settings.py`

**`src/tdoc_crawler/database/`:**
- Purpose: Data persistence abstraction (SQLite via Oxyde ORM)
- Contains: Database class implementations, Oxyde models, schema definitions
- Key files: `oxyde_models.py` (data models), `base.py` (schema), `tdocs.py`, `meetings.py`, `specs.py`

**`src/tdoc_crawler/tdocs/`, `src/tdoc_crawler/specs/`, `src/tdoc_crawler/meetings/`:**
- Purpose: Domain-specific business logic
- Contains: Models, operations (crawlers), sources (data fetchers)
- Pattern: Each domain is self-contained; operations are explicit imports only

**`src/tdoc_crawler/extraction/`:**
- Purpose: Document format conversion and content extraction
- Contains: PDF/Office format handlers, markdown extraction, metrics tracking
- Key files: `convert.py` (main conversion entry point), `conversion.py` (backends)

**`src/tdoc_crawler/workers/`:**
- Purpose: Parallel execution support
- Contains: Subinterpreter workers for TDoc parsing
- Key file: `tdoc_worker.py`

**`src/tdoc_crawler/parsers/`:**
- Purpose: HTML/XML parsing for metadata extraction
- Contains: Portal HTML parser, meeting page parser
- Key file: `portal.py`

**`src/tdoc_crawler/clients/`:**
- Purpose: External API clients
- Contains: Portal client with EOL authentication
- Key file: `portal.py`

**`src/tdoc_crawler/utils/`:**
- Purpose: Shared utility functions
- Contains: Normalization, date parsing, working group mapping, security
- Key files: `normalization.py`, `parse.py`

**`packages/pool_executors/`:**
- Purpose: Parallel executor library (serial, thread, process modes)
- Contains: Executor factory, task runner
- Dependency: Used by TDocCrawler for parallel workers

**`tests/`:**
- Purpose: Unit and integration tests
- Contains: Test files for each module, organized by concern (models, sources, database, CLI)
- Pattern: `test_*.py` files co-located conceptually with implementation

## Key File Locations

**Entry Points:**
- `src/tdoc_crawler/cli/tdoc_app.py`: TDoc/Meetings CLI (`tdoc-crawler` command)
- `src/tdoc_crawler/cli/spec_app.py`: Specification CLI (`spec-crawler` command)
- `src/tdoc_crawler/cli/mgmt_app.py`: Management CLI (`3gpp-crawler` command)

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, script entry points
- `src/tdoc_crawler/config/settings.py`: Pydantic config models
- `src/tdoc_crawler/config/cache_manager.py`: Path management

**Core Logic:**
- `src/tdoc_crawler/tdocs/operations/crawl.py`: TDocCrawler orchestrator
- `src/tdoc_crawler/meetings/operations/crawl.py`: MeetingCrawler orchestrator
- `src/tdoc_crawler/database/base.py`: Database schema and base operations
- `src/tdoc_crawler/extraction/convert.py`: Document conversion entry points

**Testing:**
- `tests/test_models.py`: Data model tests
- `tests/test_portal_auth.py`: Authentication tests
- `tests/test_specs_database.py`: Database operation tests
- `tests/test_whatthespec.py`: API integration tests

## Naming Conventions

**Files:**
- `*_app.py`: Typer CLI app definition
- `*_crawler.py`: Crawler class (orchestrates parallel workers)
- `*_database.py`: Database operations class
- `*_model*.py`: Data model definitions
- `*_source*.py`: Data source implementations
- `test_*.py`: Test files (pytest)
- `_*.py`: Private/internal modules (not meant for direct import)

**Directories:**
- `cli/`: All CLI-related code (Typer commands)
- `config/`: Configuration management
- `database/`: Database abstraction layer
- `{domain}/`: Domain packages (`tdocs`, `specs`, `meetings`)
- `{domain}/operations/`: Crawler orchestrators
- `{domain}/sources/`: Data source implementations
- `utils/`: Utility functions
- `parsers/`: Parsing logic
- `clients/`: External API clients
- `workers/`: Parallel execution workers

## Where to Add New Code

**New Feature (e.g., Add TDoc filter):**
- Primary code: `src/tdoc_crawler/tdocs/models.py` (add filter field), `src/tdoc_crawler/tdocs/operations/crawl.py` (implement filtering logic)
- CLI integration: `src/tdoc_crawler/cli/crawl.py` (add argument), `src/tdoc_crawler/cli/query.py` (add query option)
- Tests: `tests/test_targeted_fetch.py` or new `tests/test_tdoc_filters.py`

**New TDoc Source (e.g., Add custom Excel parser):**
- Implementation: `src/tdoc_crawler/tdocs/sources/custom.py` (inherit from `TDocSource`)
- Integration: `src/tdoc_crawler/tdocs/operations/crawl.py` (add to source selection logic)
- Tests: `tests/test_specs_sources.py` (or similar)

**New CLI Command (e.g., Export TDocs):**
- Command handler: `src/tdoc_crawler/cli/query.py` or new `src/tdoc_crawler/cli/export.py`
- Registration: Add to appropriate `*_app.py` via `@*_app.command()` decorator
- Output formatting: `src/tdoc_crawler/cli/formatting.py` (add format handler)
- Tests: `tests/test_specs_cli.py` (or `test_tdoc_cli.py`)

**New Database Operation (e.g., Add TDoc statistics):**
- Implementation: `src/tdoc_crawler/database/tdocs.py` (add async method)
- Tests: `tests/test_specs_database.py` (or `test_tdoc_database.py`)

**New Extraction Profile (e.g., Add custom markdown style):**
- Definition: `src/tdoc_crawler/extraction/profiles.py` (define profile)
- Implementation: `src/tdoc_crawler/extraction/convert.py` (handle in conversion logic)
- Integration: `src/tdoc_crawler/extraction/checkout.py` (pass profile through pipeline)
- Tests: `tests/test_specs_normalization.py` (or create `test_extraction_profiles.py`)

## Special Directories

**`src/tdoc_crawler/database/`:**
- Purpose: Oxyde ORM mapping to SQLite
- Generated: No
- Committed: Yes
- Note: All database operations go through this layer; never use `sqlite3` directly

**`.planning/codebase/`:**
- Purpose: Generated codebase documentation (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (via `/gsd-map-codebase`)
- Committed: Yes
- Note: These files guide future phase planning and implementation

**`packages/`:**
- Purpose: Vendored/local dependencies published separately
- Generated: No
- Committed: Yes
- Note: `pool_executors` is used by crawlers; `convert-lo` is used by extraction

**`tests/`:**
- Purpose: pytest test suite
- Generated: No
- Committed: Yes
- Pattern: Tests co-located with feature areas (e.g., `test_specs_*.py` for spec domain)

---

*Structure analysis: 2026-04-30*
