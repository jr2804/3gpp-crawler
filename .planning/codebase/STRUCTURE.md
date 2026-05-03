# Codebase Structure

**Analysis Date:** 2026-05-03

## Directory Layout

```
3gpp-crawler/
├── src/                        # Main library source
│   └── tdoc_crawler/           # Core Python package
│       ├── __init__.py         # Package identity (version, author)
│       ├── __main__.py         # `python -m tdoc_crawler` entry
│       ├── cli/                # Typer CLI apps (thin layer)
│       ├── clients/            # External API clients (portal auth)
│       ├── config/             # Configuration system
│       ├── constants/          # URL templates, regex patterns
│       ├── credentials.py      # Credential resolution
│       ├── database/           # SQLite/Oxyde ORM persistence
│       ├── extraction/         # Document conversion pipeline
│       ├── http_client/        # Cached HTTP session factory
│       ├── logging/            # Logging configuration
│       ├── meetings/           # Meeting domain (models, sources, operations)
│       ├── models/             # Shared models and enums
│       ├── parsers/            # HTML/portal parsing
│       ├── specs/              # Spec domain (models, sources, operations)
│       ├── tdocs/              # TDoc domain (models, sources, operations)
│       ├── utils/              # Shared utilities
│       ├── workers/            # Parallel crawl workers
│       └── workspaces/         # Workspace CRUD and management
├── packages/                   # UV workspace internal packages
│   ├── convert-lo/             # LibreOffice document conversion
│   └── pool_executors/         # Lightweight executor pools
├── tests/                      # Test suite (pytest)
├── docs/                       # MkDocs documentation
├── .agents/                    # Agent skills and tooling
│   └── skills/                 # Domain-specific agent skills
├── .planning/                  # GSD planning artifacts (generated)
│   └── codebase/               # Codebase analysis documents
├── .beads/                     # BEADS tracking
├── .config/                    # Project-local config
├── .grepai/                    # GrepAI semantic index config
├── .opencode/                  # OpenCode IDE config
├── .sisyphus/                  # Sisyphus task tracking
├── .vscode/                    # VS Code settings
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # UV lockfile (committed)
├── ruff.toml                   # Ruff linter config
├── ty.toml                     # Ty type checker config
├── tox.ini                     # Tox test runner config
├── mkdocs.yml                  # MkDocs documentation config
├── codecov.yaml                # Codecov coverage config
├── .pre-commit-config.yaml     # Pre-commit hooks
├── .env.example                # Environment variable template
├── demo.bat                    # Demo script (Windows)
├── AGENTS.md                   # Project-wide agent instructions
├── PLAN.md                     # Project plan
├── README.md                   # Project readme
├── LICENSE                     # License
└── skills-lock.json            # Skills version lock
```

## Directory Purposes

**`src/tdoc_crawler/`:**
- Purpose: Core Python library — all domain logic, database, HTTP, config
- Contains: Python source modules organized by domain
- Key files: `__init__.py`, `__main__.py`

**`src/tdoc_crawler/cli/`:**
- Purpose: Thin Typer CLI wrappers — command definitions, Rich output formatting
- Contains: `tdoc_app.py` (TDoc CLI), `spec_app.py` (Spec CLI), `mgmt_app.py` (Management CLI), `args.py` (Typer argument types), `_shared.py` (shared CLI utilities), `config_app.py` (config subcommands), `_workspace_commands.py` (workspace subcommands), `formatting.py`, `printing.py`, `constants.py`, `utils.py`
- Key files: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py`, `args.py`, `_workspace_commands.py`
- **Rule:** NO business logic — only Typer/Rich wrapping. All logic in core library.

**`src/tdoc_crawler/config/`:**
- Purpose: Two complementary systems: `ThreeGPPConfig` (pydantic-settings) and `CacheManager` (runtime paths)
- Contains: `settings.py` (config models), `cache_manager.py` (path singleton), `sources.py` (config file discovery/loading), `env_vars.py` (env var mapping), `export.py` (config export), `workspace_registry.py` (workspace JSON store)
- Key files: `settings.py`, `cache_manager.py`, `sources.py`

**`src/tdoc_crawler/database/`:**
- Purpose: Oxyde ORM persistence layer — all database operations
- Contains: `base.py` (DocDatabase lifecycle), `tdocs.py` (TDocDatabase), `meetings.py` (MeetingDatabase), `specs.py` (SpecDatabase), `oxyde_models.py` (ORM model definitions), `protocols.py` (DatabaseFactory), `errors.py` (DatabaseError)
- Key files: `base.py`, `tdocs.py`, `specs.py`, `oxyde_models.py`
- Inheritance chain: `DocDatabase` → `MeetingDatabase` → `TDocDatabase`

**`src/tdoc_crawler/tdocs/`:**
- Purpose: TDoc domain — crawling, fetching, checkout, models
- Contains: `models.py` (TDocStatus, TDocMetadata, TDocQueryConfig), `sources/` (doclist.py, portal.py, whatthespec.py, base.py), `operations/` (crawl.py, checkout.py, fetch.py), `utils.py`
- Key files: `models.py`, `sources/doclist.py`, `operations/crawl.py`, `operations/checkout.py`

**`src/tdoc_crawler/meetings/`:**
- Purpose: Meeting domain — meeting metadata crawling
- Contains: `models.py` (MeetingMetadata, MeetingQueryConfig), `sources/` (empty — meeting data comes via portal/doclist), `operations/` (crawl.py), `utils.py`
- Key files: `models.py`, `operations/crawl.py`

**`src/tdoc_crawler/specs/`:**
- Purpose: Spec domain — crawling, checkout, download, models
- Contains: `models.py` (SpecQueryFilters, SpecQueryResult), `sources/` (threegpp.py, whatthespec.py, base.py), `operations/` (checkout.py), `downloads.py`
- Key files: `sources/threegpp.py`, `operations/checkout.py`, `downloads.py`

**`src/tdoc_crawler/extraction/`:**
- Purpose: Document conversion pipeline (PDF/Markdown/structured extraction)
- Contains: `convert.py` (OpenDataLoader Markdown extraction), `conversion.py` (LibreOffice/remote PDF conversion), `profiles.py` (ExtractionProfile enum), `hybrid_server.py` (server lifecycle), `fetch_tdoc.py` (TDoc file fetch), `fetch_spec.py` (Spec file fetch), `workspace_utils.py`, `metrics.py`
- Key files: `convert.py`, `conversion.py`, `profiles.py`, `hybrid_server.py`

**`src/tdoc_crawler/http_client/`:**
- Purpose: Cached HTTP session management (hishel + niquests)
- Contains: `session.py` (factory, decompression, download), `protocols.py`
- Key files: `session.py` — exports `create_cached_session()`, `download_to_file()`, `PoolConfig`

**`src/tdoc_crawler/models/`:**
- Purpose: Shared domain-neutral models and enums
- Contains: `base.py` (OutputFormat, SortOrder, PortalCredentials), `workspaces.py` (SourceKind, workspace errors, ExtractionQualityStatus), `working_groups.py`, `subworking_groups.py`, `crawl_log.py`
- Key files: `base.py`, `workspaces.py`

**`src/tdoc_crawler/workspaces/`:**
- Purpose: Workspace CRUD and member management
- Contains: `crud.py` (create, delete, list, activate/deactivate), `members.py` (add, list members), `utils.py` (checkout path resolution, artifact cleanup)
- Key files: `crud.py`, `members.py`, `utils.py`

**`src/tdoc_crawler/utils/`:**
- Purpose: Shared utility functions
- Contains: `normalization.py` (TDoc IDs, spec numbers, releases), `parse.py` (agenda items, spec versions), `date_parser.py` (partial date parsing), `misc.py` (utc_now, etc.)
- Key files: `normalization.py`, `parse.py`

**`src/tdoc_crawler/parsers/`:**
- Purpose: HTML/portal content parsing
- Contains: `meetings.py` (meeting page parsing), `portal.py` (portal HTML parsing), `protocols.py`
- Key files: `meetings.py`, `portal.py`

**`src/tdoc_crawler/workers/`:**
- Purpose: Parallel crawl worker implementation (subinterpreter-based)
- Contains: `tdoc_worker.py` — `fetch_meeting_document_list_subinterpreter()`
- Key files: `tdoc_worker.py`

**`src/tdoc_crawler/clients/`:**
- Purpose: External API clients requiring authentication
- Contains: `portal.py` — `PortalClient` (EOL login, AJAX operations)
- Key files: `portal.py`

**`src/tdoc_crawler/constants/`:**
- Purpose: Regex patterns and URL templates
- Contains: `patterns.py` (TDOC_PATTERN, DATE_PATTERN, subdirectory lists), `urls.py` (MEETINGS_BASE_URL, PORTAL_BASE_URL, SPEC_URL_TEMPLATE, BROWSER_HEADERS)
- Key files: `patterns.py`, `urls.py`

**`src/tdoc_crawler/logging/`:**
- Purpose: Centralized logging configuration
- Contains: `__init__.py` — `get_logger()`, `get_console()`, `set_verbosity()`, `DEFAULT_LEVEL`
- Key files: `__init__.py`

**`packages/convert-lo/`:**
- Purpose: LibreOffice document conversion (internal workspace package)
- Contains: `convert_lo/converter.py` (Converter class), `locator.py` (soffice discovery), `formats.py` (format enum), `exceptions.py`
- Key files: `converter.py`, `locator.py`

**`packages/pool_executors/`:**
- Purpose: Lightweight executor pool extensions (internal workspace package)
- Contains: `pool_executors/factory.py` (create_executor), `serial.py`, `runner.py`, `types.py`
- Key files: `factory.py`

**`tests/`:**
- Purpose: pytest test suite
- Contains: Test files for each major component (`test_cli.py`, `test_database.py`, `test_crawler.py`, `test_specs_database.py`, `test_workspaces.py`, etc.), `conftest.py`, test data in `data/`, fixture configs in `config/`
- Key files: `conftest.py`, `test_database.py`, `test_crawler.py`, `test_workspaces.py`

**`docs/`:**
- Purpose: MkDocs project documentation
- Contains: `index.md`, `development.md`, `config.md`, `crawl.md`, `query.md`, `misc.md`, `whatthespec.md`, `convert-lo-usage.md`, `skills-reference.md`, `history/`
- Key files: `development.md`, `index.md`

**`.agents/skills/`:**
- Purpose: Agent skills for domain knowledge and code quality
- Contains: 65 skill directories including `3gpp-*` (domain), `python-ultimate`, `caveman-*`, `grepai-*`, `pydantic`, `uv`, `ty-skills`, etc.
- Key files: Each skill has `SKILL.md`

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents (generated, not committed by default)
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`, and potentially `STACK.md`, `INTEGRATIONS.md`, `CONVENTIONS.md`, `TESTING.md`, `CONCERNS.md`
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Depends on workflow

## Key File Locations

**Entry Points:**
- `src/tdoc_crawler/__main__.py`: `python -m tdoc_crawler` entry (delegates to `tdoc_app`)
- `src/tdoc_crawler/cli/tdoc_app.py`: `tdoc-crawler` console script
- `src/tdoc_crawler/cli/spec_app.py`: `spec-crawler` console script
- `src/tdoc_crawler/cli/mgmt_app.py`: `3gpp-crawler` console script
- `pyproject.toml` (lines 68-71): Console script definitions

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, workspace members, build system
- `src/tdoc_crawler/config/settings.py`: ThreeGPPConfig (pydantic-settings)
- `src/tdoc_crawler/config/cache_manager.py`: CacheManager singleton
- `src/tdoc_crawler/config/sources.py`: Config file discovery/loading
- `ruff.toml`: Ruff linter configuration
- `ty.toml`: Ty type checker configuration
- `tox.ini`: Tox test environments
- `.pre-commit-config.yaml`: Pre-commit hooks
- `codecov.yaml`: Coverage configuration
- `mkdocs.yml`: Documentation configuration

**Core Logic:**
- `src/tdoc_crawler/tdocs/operations/crawl.py`: TDoc crawl orchestrator (TDocCrawler)
- `src/tdoc_crawler/specs/sources/threegpp.py`: Primary spec metadata source
- `src/tdoc_crawler/extraction/convert.py`: OpenDataLoader Markdown conversion
- `src/tdoc_crawler/database/base.py`: Base database facade (DocDatabase)
- `src/tdoc_crawler/database/oxyde_models.py`: Oxyde ORM model definitions
- `src/tdoc_crawler/http_client/session.py`: Cached HTTP session factory
- `src/tdoc_crawler/cli/_workspace_commands.py`: Workspace CLI commands

**Testing:**
- `tests/conftest.py`: Shared fixtures (database, cache_dir, temp paths)
- `tests/test_database.py`: Database operation tests
- `tests/test_crawler.py`: Crawl operation tests
- `tests/test_workspaces.py`: Workspace management tests
- `tests/test_specs_database.py`: Spec database tests
- `tests/test_http_client.py`: HTTP client tests
- `tests/config/`: Test-specific configuration files
- `tests/data/`: Test data files

## Naming Conventions

**Files:**
- Lowercase with underscores: `cache_manager.py`, `http_client.py`, `doclist.py`
- CLI files prefixed with underscore for internal modules: `_shared.py`, `_workspace_commands.py`
- Domain models in `models.py` within each domain package
- Source implementations named after source: `doclist.py`, `portal.py`, `whatthespec.py`, `threegpp.py`
- Operations named after operation: `crawl.py`, `checkout.py`, `fetch.py`
- Test files: `test_<module>.py` (e.g., `test_database.py`, `test_crawler.py`)

**Directories:**
- Domain packages: `tdocs/`, `meetings/`, `specs/`, `workspaces/`
- Infrastructure: `config/`, `database/`, `http_client/`, `clients/`
- Sub-structure within domains: `sources/` (data sources), `operations/` (business logic)
- Package-level `__init__.py` with `__all__` exports

**Classes:**
- PascalCase: `CacheManager`, `ThreeGPPConfig`, `TDocDatabase`, `SpecSource`
- Exception classes: `*Error` suffix — `CacheManagerNotRegisteredError`, `DatabaseError`, `TDocNotFoundError`
- Config models: `*Config` suffix — `HttpConfig`, `CrawlConfig`, `PathConfig`

**Functions:**
- snake_case: `resolve_cache_manager()`, `create_cached_session()`, `normalize_tdoc_id()`
- Factory functions: `create_*` prefix — `create_cached_session()`, `create_workspace()`
- Resolution functions: `resolve_*` prefix — `resolve_cache_manager()`, `resolve_credentials()`, `resolve_spec_release()`

## Where to Add New Code

**New Domain (e.g., `change_requests/`):**
- Primary code: `src/tdoc_crawler/<domain>/` with `models.py`, `sources/`, `operations/`
- Models: `src/tdoc_crawler/models/` if shared across domains
- Database: `src/tdoc_crawler/database/<domain>.py` with Oxyde models in `oxyde_models.py`
- CLI: `src/tdoc_crawler/cli/<domain>_app.py` (if separate CLI) or new commands in existing app
- Tests: `tests/test_<domain>.py`

**New CLI Command (existing domain):**
- Implementation: `src/tdoc_crawler/cli/<existing_app>.py` — add `@app.command()` decorator
- Argument types: `src/tdoc_crawler/cli/args.py` — add new `Annotated` type
- Logic: Delegate to core library module — never implement in CLI
- Tests: `tests/test_cli.py`

**New Data Source:**
- Implementation: `src/tdoc_crawler/<domain>/sources/<source_name>.py`
- Must implement the domain's source protocol (`TDocSource` or `SpecSource`)
- Register in the domain's source resolution logic

**New Extraction Profile:**
- Add enum value to `src/tdoc_crawler/extraction/profiles.py:ExtractionProfile`
- Implement profile logic in `src/tdoc_crawler/extraction/convert.py`
- Add workspace CLI profile option if needed in `cli/_workspace_commands.py`

**New Utility Function:**
- Shared (cross-domain): `src/tdoc_crawler/utils/<module>.py`
- Domain-specific: `src/tdoc_crawler/<domain>/utils.py`
- Parsing: `src/tdoc_crawler/parsers/<name>.py`

**New Test File:**
- Location: `tests/test_<component>.py`
- Follow pattern: `conftest.py` fixtures → test file
- Integration tests (network): mark with `@pytest.mark.integration`

## Special Directories

**`.agents/skills/`:**
- Purpose: Agent skill definitions loaded by Claude Code and other tools
- Generated: No
- Committed: Yes
- 65 skill directories covering 3GPP domain knowledge, code quality, tool usage

**`.planning/`:**
- Purpose: GSD workflow planning artifacts (phases, codebase analysis)
- Generated: Yes (by GSD commands)
- Committed: Depends on workflow (typically yes)

**`.beads/`:**
- Purpose: BEADS task tracking system
- Generated: Yes
- Committed: Typically no

**`.grepai/`:**
- Purpose: GrepAI semantic code index configuration
- Generated: Yes
- Committed: Yes (configuration)

**`packages/`:**
- Purpose: UV workspace internal packages shared with the main project
- Generated: No
- Committed: Yes
- Contains: `convert-lo` (LibreOffice helpers), `pool-executors` (executor pools)

**`docs/history/`:**
- Purpose: Changelog and historical documentation entries
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-05-03*
