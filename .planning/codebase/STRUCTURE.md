# Codebase Structure

**Analysis Date:** 2026-03-27

## Directory Layout

```
3gpp-crawler/
├── src/tdoc_crawler/              # Core library (installable package)
│   ├── __init__.py                # Package metadata (__version__, __author__)
│   ├── __main__.py                # python -m tdoc_crawler entry
│   ├── credentials.py             # EOL credential resolution helpers
│   ├── cli/                       # CLI commands (Typer/Rich)
│   │   ├── app.py                 # Unified CLI app (all commands)
│   │   ├── tdoc_app.py            # TDoc-focused CLI app
│   │   ├── spec_app.py            # Spec-focused CLI app
│   │   ├── crawl.py               # crawl-tdocs, crawl-meetings, crawl-specs
│   │   ├── query.py               # query-tdocs, query-meetings, query-specs
│   │   ├── args.py                # Shared Typer Annotated types
│   │   ├── printing.py            # Rich table/output formatting
│   │   ├── _shared.py             # Console singleton, progress bar, clear helpers
│   │   ├── specs.py               # Spec checkout/open CLI commands
│   │   └── utils.py               # CLI helpers (e.g., launch_file)
│   ├── clients/                   # External API clients
│   │   └── portal.py              # 3GPP portal HTTP client
│   ├── config/                    # Path management and configuration
│   │   ├── __init__.py            # CacheManager singleton, resolve_cache_manager()
│   │   └── service.py             # ConfigService (unified config access)
│   ├── constants/                 # Shared constants
│   │   ├── patterns.py            # Regex patterns for 3GPP identifiers
│   │   └── urls.py                # 3GPP base URLs, browser headers
│   ├── database/                  # SQLite database layer (pydantic-sqlite)
│   │   ├── __init__.py            # Facade exports (DocDatabase, TDocDatabase, etc.)
│   │   ├── base.py                # DocDatabase base (shared CRUD, crawl logging)
│   │   ├── tdocs.py               # TDocDatabase (TDoc queries/upserts)
│   │   ├── meetings.py            # MeetingDatabase (meeting queries/upserts)
│   │   ├── specs.py               # SpecDatabase (spec queries/upserts)
│   │   ├── protocols.py           # Database protocol interfaces
│   │   └── errors.py              # DatabaseError with typed codes
│   ├── http_client/               # HTTP session factory (hishel caching)
│   │   ├── __init__.py            # Exports create_cached_session, download_to_file
│   │   ├── session.py             # create_cached_session(), download_to_file(), PoolConfig
│   │   └── protocols.py           # HTTP client protocol interfaces
│   ├── logging/                   # Logging configuration
│   │   └── __init__.py            # get_logger(), get_console(), set_verbosity()
│   ├── meetings/                  # Meeting domain package
│   │   ├── __init__.py
│   │   ├── models.py              # MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig
│   │   ├── operations/
│   │   │   ├── crawl.py           # MeetingCrawler class
│   │   │   └── __init__.py
│   │   ├── sources/
│   │   │   └── __init__.py        # (portal-based, inline)
│   │   └── utils.py               # Meeting utility functions
│   ├── models/                    # Shared Pydantic models and reference data
│   │   ├── __init__.py            # Re-exports all models
│   │   ├── base.py                # BaseConfigModel, HttpCacheConfig, OutputFormat, SortOrder, PortalCredentials
│   │   ├── crawl_limits.py        # CrawlLimits dataclass
│   │   ├── crawl_log.py           # CrawlLogEntry model
│   │   ├── working_groups.py      # WorkingGroup enum + WORKING_GROUP_RECORDS
│   │   └── subworking_groups.py   # SubWorkingGroupRecord + SUBWORKING_GROUP_RECORDS + SUBTB_INDEX
│   ├── parsers/                   # HTML/Excel/portal parsing
│   │   ├── __init__.py
│   │   ├── meetings.py            # parse_meeting_page() — HTML meeting list parsing
│   │   ├── portal.py              # Portal page parsing helpers
│   │   └── protocols.py           # Parser protocol interfaces
│   ├── specs/                     # Specification domain package
│   │   ├── __init__.py
│   │   ├── models.py              # Specification, SpecQueryFilters, SpecificationVersion, etc.
│   │   ├── downloads.py           # Spec download tracking
│   │   ├── operations/
│   │   │   ├── __init__.py
│   │   │   └── checkout.py        # checkout_specs(), build_default_spec_sources()
│   │   └── sources/
│   │       ├── __init__.py
│   │       ├── base.py            # SpecSource protocol
│   │       ├── threegpp.py        # ThreeGppSpecSource
│   │       └── whatthespec.py     # WhatTheSpecSpecSource
│   ├── tdocs/                     # TDoc domain package (largest domain)
│   │   ├── __init__.py
│   │   ├── models.py              # TDocMetadata, TDocCrawlConfig, TDocQueryConfig, FetchMissingResult
│   │   ├── operations/
│   │   │   ├── __init__.py        # Re-exports all operations
│   │   │   ├── crawl.py           # TDocCrawler class, TDocCrawlResult
│   │   │   ├── fetch.py           # fetch_missing_tdocs(), create_source(), FetchMethod
│   │   │   └── checkout.py        # checkout_tdoc(), checkout_tdocs(), prepare_tdoc_file()
│   │   ├── sources/
│   │   │   ├── __init__.py        # create_source() factory
│   │   │   ├── base.py            # TDocSource protocol
│   │   │   ├── doclist.py         # DoclistSource (Excel batch crawling)
│   │   │   ├── portal.py          # PortalSource (authenticated single fetch)
│   │   │   └── whatthespec.py     # WhatTheSpecSource (API single fetch)
│   │   └── utils.py               # TDoc utility functions
│   ├── utils/                     # Shared utility functions
│   │   ├── __init__.py
│   │   ├── date_parser.py         # parse_partial_date() — flexible date parsing
│   │   ├── misc.py                # Miscellaneous utilities
│   │   ├── normalization.py       # ID/text normalization helpers
│   │   └── parse.py               # parse_subgroups(), parse_working_groups(), collect_spec_numbers()
│   └── workers/                   # Parallel execution workers
│       ├── __init__.py
│       └── tdoc_worker.py         # TDoc processing worker
├── packages/                      # UV workspace sub-packages
│   ├── 3gpp-ai/                   # AI/RAG extension package
│   │   ├── pyproject.toml         # Independent package config
│   │   ├── AGENTS.md              # AI-specific agent guidelines
│   │   └── threegpp_ai/
│   │       ├── __init__.py        # Re-exports all public API
│   │       ├── cli.py             # 3gpp-ai CLI entry point
│   │       ├── config.py          # AI-specific configuration
│   │       ├── models.py          # SourceKind, SummarizeResult
│   │       ├── args.py            # CLI argument definitions
│   │       ├── lightrag/          # LightRAG integration layer
│   │       │   ├── __init__.py    # Re-exports LightRAG components
│   │       │   ├── config.py      # LightRAGConfig, LLMConfig, EmbeddingConfig, DatabaseConfig
│   │       │   ├── rag.py         # TDocRAG class (workspace-level retrieval)
│   │       │   ├── processor.py   # TDocProcessor (per-document ingestion)
│   │       │   ├── metadata.py    # RAGMetadata, create_metadata_from_dict
│   │       │   ├── cli.py         # LightRAG CLI commands
│   │       │   ├── seeder.py      # Data seeding utilities
│   │       │   ├── migration.py   # Schema migration support
│   │       │   ├── pg0_manager.py # PostgreSQL backend manager
│   │       │   └── shared_storage.py # Shared embedding storage
│   │       └── operations/        # AI processing operations
│   │           ├── __init__.py
│   │           ├── classify.py    # Document classification
│   │           ├── extraction.py  # Content extraction
│   │           ├── conversion.py  # Format conversion orchestration
│   │           ├── convert.py     # Document conversion helpers
│   │           ├── chunking.py    # Text chunking strategies
│   │           ├── summarize.py   # LLM summarization
│   │           ├── llm_client.py  # LiteLLM client wrapper
│   │           ├── fetch_tdoc.py  # TDoc fetching for AI pipeline
│   │           ├── figure_descriptor.py # Vision-based figure description
│   │           ├── metrics.py     # Processing metrics tracking
│   │           ├── extraction_result.py # Extraction result models
│   │           ├── workspace_names.py # Workspace name utilities
│   │           ├── workspace_registry.py # WorkspaceRegistry (JSON file)
│   │           └── workspaces.py  # Workspace CRUD, member management
│   ├── convert-lo/                # LibreOffice document conversion
│   │   ├── pyproject.toml
│   │   ├── AGENTS.md
│   │   └── convert_lo/
│   │       ├── __init__.py
│   │       ├── converter.py       # Converter class (headless soffice)
│   │       ├── exceptions.py      # ConversionError hierarchy
│   │       ├── formats.py         # Supported format definitions
│   │       └── locator.py         # LibreOffice binary locator
│   └── pool_executors/            # Serial/parallel executor utilities
│       ├── pyproject.toml
│       └── pool_executors/
│           ├── __init__.py
│           ├── factory.py         # create_executor() factory
│           ├── runner.py          # Runner class (aiointerpreters-compatible API)
│           ├── serial.py          # SerialPoolExecutor, SerialFuture
│           ├── types.py           # Type definitions
│           └── py.typed           # PEP 561 marker
├── tests/                         # Test suite
│   ├── AGENTS.md                  # Test-specific agent guidelines
│   ├── conftest.py                # Shared pytest fixtures
│   ├── data/                      # Test fixture files
│   ├── ai/                        # AI package tests
│   │   ├── conftest.py            # AI-specific fixtures
│   │   ├── data/                  # AI test data
│   │   ├── test_ai_*.py           # AI operation tests
│   │   ├── test_lightrag_config.py
│   │   ├── test_chunking.py
│   │   ├── test_cli_aggregator.py
│   │   └── test_integration.py
│   ├── convert_lo/                # convert-lo package tests
│   ├── pool_executor/             # pool_executors package tests
│   ├── test_*.py                  # Core library tests
│   └── test-cache/                # Test database/cache (gitignored)
├── docs/                          # Documentation (MkDocs)
│   ├── index.md                   # Documentation homepage
│   ├── crawl.md                   # Crawling documentation
│   ├── query.md                   # Query documentation
│   ├── ai.md                      # AI/RAG documentation
│   ├── development.md             # Developer guide
│   └── skills-reference.md        # Agent skills reference
├── scripts/                       # Utility scripts
│   ├── demo.py                    # Demo script
│   └── cache/                     # Cache management scripts
├── .agents/skills/                # Agent skill definitions
│   ├── 3gpp-*/                    # 3GPP domain skills
│   └── *.md                       # General skills
├── pyproject.toml                 # Main project configuration (Python 3.14, deps, scripts)
├── uv.lock                        # Dependency lockfile
├── ruff.toml                      # Ruff linter configuration
├── ty.toml                        # ty (LSP) configuration
├── AGENTS.md                      # Root agent guidelines
├── .env.example                   # Environment variable template
├── mkdocs.yml                     # MkDocs site configuration
└── tox.ini                        # Multi-environment test runner
```

## Directory Purposes

**`src/tdoc_crawler/cli/`:**

- Purpose: CLI commands, argument definitions, Rich console output, user interaction
- Contains: Typer command definitions, `Annotated` argument/option types, table printing, progress bars
- Key files: `app.py` (unified CLI), `tdoc_app.py` (TDoc variant), `spec_app.py` (spec variant), `crawl.py`, `query.py`, `args.py`
- AGENTS.md: `src/tdoc_crawler/cli/AGENTS.md` — CLI-only conventions, classification rules, circular import resolution

**`src/tdoc_crawler/tdocs/`:**

- Purpose: TDoc domain — the largest and most complex domain
- Contains: TDoc metadata models, crawl/fetch/checkout operations, multiple data sources
- Key files: `models.py` (TDocMetadata, crawl/query configs), `operations/crawl.py` (TDocCrawler), `operations/fetch.py` (fetch_missing_tdocs), `operations/checkout.py`, `sources/` (doclist, whatthespec, portal)

**`src/tdoc_crawler/meetings/`:**

- Purpose: Meeting domain — crawling meeting metadata from 3GPP portal
- Contains: Meeting models, MeetingCrawler, portal source
- Key files: `models.py` (MeetingMetadata, MeetingCrawlConfig), `operations/crawl.py` (MeetingCrawler)

**`src/tdoc_crawler/specs/`:**

- Purpose: Specification domain — metadata from 3GPP and WhatTheSpec
- Contains: Spec models, spec sources, checkout operations
- Key files: `models.py` (Specification, SpecQueryFilters), `sources/threegpp.py`, `operations/checkout.py`

**`src/tdoc_crawler/database/`:**

- Purpose: SQLite database abstraction via pydantic-sqlite
- Contains: Database facades with context manager pattern, shared base class
- Key files: `base.py` (DocDatabase — shared CRUD, crawl logging, reference data), `tdocs.py`, `meetings.py`, `specs.py`, `errors.py`

**`src/tdoc_crawler/models/`:**

- Purpose: Shared Pydantic models, enums, reference data (neutral layer for circular import prevention)
- Contains: Base config models, output formats, sort orders, crawl limits, working group records
- Key files: `base.py` (BaseConfigModel, HttpCacheConfig, PortalCredentials), `working_groups.py`, `subworking_groups.py`

**`src/tdoc_crawler/config/`:**

- Purpose: Centralized path management and configuration service
- Contains: CacheManager singleton registry, ConfigService
- Key files: `__init__.py` (CacheManager, `register_cache_manager()`, `resolve_cache_manager()`), `service.py` (ConfigService)

**`src/tdoc_crawler/http_client/`:**

- Purpose: HTTP session factory with hishel SQLite caching, file download utility
- Contains: Cached session creation, pool configuration, download helper
- Key files: `session.py` (`create_cached_session()`, `download_to_file()`, `PoolConfig`)

**`src/tdoc_crawler/parsers/`:**

- Purpose: HTML and Excel parsing for 3GPP data extraction
- Contains: Meeting page parser, portal page parser
- Key files: `meetings.py` (`parse_meeting_page()`), `portal.py`

**`src/tdoc_crawler/utils/`:**

- Purpose: Shared utility functions (domain-agnostic)
- Contains: Date parsing, normalization, argument parsing helpers
- Key files: `date_parser.py`, `parse.py`, `normalization.py`

**`packages/3gpp-ai/threegpp_ai/`:**

- Purpose: AI-powered document processing (LightRAG, embeddings, RAG, summarization)
- Contains: LightRAG integration layer, document processing operations, workspace management
- Key files: `lightrag/rag.py` (TDocRAG), `lightrag/processor.py` (TDocProcessor), `lightrag/config.py` (LightRAGConfig), `operations/workspaces.py`
- AGENTS.md: `packages/3gpp-ai/AGENTS.md` — SSOT principle, LightRAG patterns, path management

**`packages/convert-lo/convert_lo/`:**

- Purpose: LibreOffice headless document conversion
- Contains: Converter class, format definitions, exception hierarchy
- Key files: `converter.py` (Converter), `formats.py`, `locator.py`

**`packages/pool_executors/pool_executors/`:**

- Purpose: Serial/parallel execution utilities (aiointerpreters-compatible)
- Contains: SerialPoolExecutor, Runner factory
- Key files: `factory.py` (`create_executor()`), `serial.py`, `runner.py`

## Key File Locations

**Entry Points:**

- `src/tdoc_crawler/__main__.py`: `python -m tdoc_crawler` entry
- `src/tdoc_crawler/cli/app.py`: Primary unified Typer app (`tdoc-crawler` command)
- `src/tdoc_crawler/cli/tdoc_app.py`: TDoc-focused Typer app (alternate)
- `src/tdoc_crawler/cli/spec_app.py`: Spec-only Typer app (`spec-crawler` command)
- `packages/3gpp-ai/threegpp_ai/cli.py`: AI CLI (`3gpp-ai` command)
- `pyproject.toml` lines 63-65: Script entry point definitions

**Configuration:**

- `src/tdoc_crawler/config/__init__.py`: CacheManager, `resolve_cache_manager()`, path constants
- `src/tdoc_crawler/config/service.py`: ConfigService (unified config access)
- `src/tdoc_crawler/models/base.py`: BaseConfigModel, HttpCacheConfig, OutputFormat, SortOrder
- `src/tdoc_crawler/constants/urls.py`: 3GPP base URLs, browser headers
- `src/tdoc_crawler/constants/patterns.py`: Regex patterns for 3GPP identifiers
- `src/tdoc_crawler/credentials.py`: EOL credential resolution
- `.env.example`: Environment variable templates

**Core Logic:**

- `src/tdoc_crawler/tdocs/operations/crawl.py`: TDocCrawler (batch Excel crawling)
- `src/tdoc_crawler/tdocs/operations/fetch.py`: fetch_missing_tdocs() (targeted API/portal fetch)
- `src/tdoc_crawler/tdocs/operations/checkout.py`: checkout_tdoc(), prepare_tdoc_file()
- `src/tdoc_crawler/meetings/operations/crawl.py`: MeetingCrawler (portal HTML crawling)
- `src/tdoc_crawler/specs/operations/checkout.py`: checkout_specs(), build_default_spec_sources()
- `src/tdoc_crawler/specs/sources/`: Spec metadata sources

**Database:**

- `src/tdoc_crawler/database/base.py`: DocDatabase (shared base — connection, reference data, crawl logging)
- `src/tdoc_crawler/database/tdocs.py`: TDocDatabase (TDoc-specific queries/upserts)
- `src/tdoc_crawler/database/meetings.py`: MeetingDatabase (meeting queries/upserts, statistics)
- `src/tdoc_crawler/database/specs.py`: SpecDatabase (spec queries/upserts, crawl_specs)
- `src/tdoc_crawler/database/errors.py`: DatabaseError with typed codes

**Testing:**

- `tests/conftest.py`: Shared pytest fixtures
- `tests/test_crawler.py`: Core crawler integration tests
- `tests/test_database.py`: Database layer tests
- `tests/test_http_client.py`: HTTP caching tests
- `tests/test_cli.py`: CLI command tests
- `tests/test_checkout.py`: Checkout operation tests
- `tests/ai/`: AI package tests (classification, extraction, workspaces, chunking, integration)

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` (e.g., `tdoc_app.py`, `http_client/session.py`)
- Test files: `test_*.py` (e.g., `test_crawler.py`, `test_ai_workspaces.py`)
- AGENTS.md: `AGENTS.md` (scoped to directories — loaded by closest-match precedence)
- Config files: `pyproject.toml`, `ruff.toml`, `ty.toml`, `mkdocs.yml`

**Directories:**

- Domain packages: `{domain}/` (e.g., `tdocs/`, `meetings/`, `specs/`)
- Domain internal structure: `{domain}/operations/`, `{domain}/sources/`, `{domain}/models.py`, `{domain}/utils.py`
- Infrastructure: `config/`, `http_client/`, `logging/`, `clients/`, `constants/`
- Shared: `models/`, `parsers/`, `utils/`, `database/`, `workers/`
- CLI: `cli/`
- Sub-packages: `packages/{name}/{import_name}/` (e.g., `packages/3gpp-ai/threegpp_ai/`)

**Classes:**

- PascalCase: `TDocMetadata`, `MeetingCrawler`, `CacheManager`, `TDocRAG`, `TDocProcessor`
- Config models: `{Entity}{Purpose}Config` (e.g., `TDocCrawlConfig`, `MeetingQueryConfig`)
- Result types: `{Entity}CrawlResult`, `{Entity}Result`
- Database classes: `{Entity}Database` (e.g., `TDocDatabase`, `MeetingDatabase`)
- Source classes: `{Description}Source` (e.g., `WhatTheSpecSource`, `PortalSource`, `ThreeGppSpecSource`)

**Functions:**

- snake_case: `fetch_missing_tdocs`, `checkout_specs`, `parse_meeting_page`, `create_cached_session`
- Factory functions: `create_source()`, `create_executor()`, `build_default_spec_sources()`
- Resolver functions: `resolve_cache_manager()`, `resolve_credentials()`

**Variables:**

- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CACHE_DIR`, `HELP_PANEL_CRAWLING`)
- Private: `_cache_managers`, `_logger`
- Booleans: `is_*`, `has_*`, `requires_*` (e.g., `requires_authentication`)

**Type Hints:**

- Union: `T | None` (not `Optional[T]`)
- Imports: Top-level only — never use `typing.TYPE_CHECKING` to hide circular imports

## Where to Add New Code

**New Domain (e.g., Change Requests):**

- Create domain package:
  ```
  src/tdoc_crawler/change_requests/
  ├── __init__.py
  ├── models.py           # ChangeRequestMetadata, ChangeRequestCrawlConfig, ChangeRequestQueryConfig
  ├── sources/            # CR metadata sources
  │   ├── __init__.py
  │   └── portal.py       # PortalCRSource
  └── operations/         # CR operations
      ├── __init__.py     # Re-export all operations
      └── crawl.py        # ChangeRequestCrawler
  ```
- Add database: `src/tdoc_crawler/database/change_requests.py` (extends `DocDatabase`)
- Export: Add to `src/tdoc_crawler/database/__init__.py`
- CLI: Add commands in `src/tdoc_crawler/cli/crawl.py` or new file, register in `cli/app.py`
- Arguments: Define new `Annotated` types in `src/tdoc_crawler/cli/args.py`

**New Source for Existing Domain:**

- Add to: `src/tdoc_crawler/{domain}/sources/`
- Implement: Appropriate protocol (`TDocSource` or `SpecSource`)
- Register: Export from `sources/__init__.py`, wire into `create_source()` factory if applicable

**New CLI Command:**

- Add function to: `src/tdoc_crawler/cli/crawl.py` or `cli/query.py` (or new file)
- Register: In `src/tdoc_crawler/cli/app.py` via `app.command("name", rich_help_panel=...)`
- Arguments: Define `Annotated` types in `src/tdoc_crawler/cli/args.py`
- Output: Add formatting in `src/tdoc_crawler/cli/printing.py` if needed

**New Parser:**

- Add to: `src/tdoc_crawler/parsers/`
- Export: From `parsers/__init__.py`
- Use: In domain source files (e.g., `tdocs/sources/`)

**New AI Operation:**

- Add to: `packages/3gpp-ai/threegpp_ai/operations/`
- Export: From `operations/__init__.py` and `threegpp_ai/__init__.py`
- CLI: Add command to `packages/3gpp-ai/threegpp_ai/cli.py`

**New Utility Function:**

- Add to: `src/tdoc_crawler/utils/` in appropriate module
- Create new module for new category (e.g., `utils/html.py`)
- Keep general-purpose and domain-agnostic

**New Shared Model:**

- Add to: `src/tdoc_crawler/models/`
- Export: From `models/__init__.py`
- Both `database/` and domain packages can safely import from here

## Special Directories

**`~/.3gpp-crawler/` (Default cache location — never hardcoded):**

- Purpose: User cache directory for all persistent data
- Contains: `3gpp_crawler.db` (metadata DB), `http-cache.sqlite3` (HTTP cache), `checkout/` (downloaded docs), `lightrag/` (AI data)
- Generated: Yes (created by `CacheManager.ensure_paths()`)
- Configurable: Via `TDC_CACHE_DIR` env var
- Access: Always via `resolve_cache_manager()` — NEVER use `Path.home() / ".3gpp-crawler"`

**`tests/test-cache/`:**

- Purpose: Test database and cache files (isolated from real cache)
- Contains: Test SQLite database (`tdoc_crawler.db`)
- Generated: Yes (by tests)
- Committed: No (gitignored)

**`.agents/skills/`:**

- Purpose: Agent skill definitions for AI coding assistants
- Contains: `3gpp-basics/`, `3gpp-tdocs/`, `3gpp-specifications/`, etc.
- Generated: No
- Committed: Yes

**`.planning/codebase/`:**

- Purpose: Planning and analysis documents for GSD workflow
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `CONCERNS.md`
- Generated: Yes (by `/gsd-map-codebase` command)
- Committed: Optional

**`docs/`:**

- Purpose: MkDocs documentation site
- Contains: User-facing documentation (crawl, query, AI, development guides)
- Generated: No (source markdown)
- Built: Via `mkdocs` to static site

## AGENTS.md Scoped Files

| File | Coverage | Precedence |
|------|----------|------------|
| `AGENTS.md` (root) | Global defaults, CacheManager pattern, boundaries, antipatterns | Lowest |
| `src/tdoc_crawler/AGENTS.md` | Import patterns, HTTP caching mandate, anti-duplication, DB schema | Core library |
| `src/tdoc_crawler/cli/AGENTS.md` | CLI classification rules, circular import resolution, module responsibilities | CLI code |
| `tests/AGENTS.md` | Test organization, fixture locations, pool executor coverage | Test code |
| `packages/3gpp-ai/AGENTS.md` | SSOT principle, LightRAG patterns, path management, deprecated APIs | AI package |
| `packages/convert-lo/AGENTS.md` | Conversion-specific conventions | Convert-lo package |

**Rule:** Closest `AGENTS.md` to the file being edited wins. Root holds global defaults only.

______________________________________________________________________

*Structure analysis: 2026-03-27*
