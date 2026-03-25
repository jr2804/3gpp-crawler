# Codebase Structure

**Analysis Date:** 2026-03-25

## Directory Layout

```
3gpp-crawler/
├── .agents/                    # AI agent skills and configuration
├── .beads/                     # Task tracking (beads CLI)
├── .config/                   # Configuration (mise, open projects)
├── .grepai/                  # Semantic code search index
├── .kreuzberg/               # Document extraction cache
├── .opencode/                 # OpenCode configuration
├── .planning/                # Planning documents (GSD workflow)
│   └── codebase/              # Generated codebase documents
├── .pytest_cache/              # Test cache
├── .ruff_cache/               # Linter cache
├── .venv/                    # Virtual environment
├── .vscode/                 # VS Code settings
├── docs/                     # Documentation (Mksite)
├── packages/                 # Workspace packages
│   ├── 3gpp-ai/            # AI processing package
│   ├── convert-lo/            # LibreOffice conversion
│   └── pool_executors/         # Executor utilities
├── scripts/                 # Utility scripts
├── src/                     # Main source code
│   ├── tdoc_crawler/          # Core library
│   │   ├── cli/                # CLI commands
│   │   ├── clients/              # API clients
│   │   ├── config/              # Configuration management
│   │   ├── constants/            # Shared constants
│   │   ├── database/            # Database layer
│   │   ├── http_client/         # HTTP caching
│   │   ├── logging/             # Logging utilities
│   │   ├── meetings/            # Meeting domain
│   │   ├── models/              # Pydantic models
│   │   ├── parsers/             # Parsing logic
│   │   ├── specs/               # Specification domain
│   │   ├── tdocs/               # TDoc domain
│   │   ├── utils/               # Shared utilities
│   │   └── workers/              # Background workers
├── tests/                       # Test suite
├── .env.example               # Environment variable template
├── pyproject.toml             # Project configuration
├── uv.lock                  # Dependency lock file
├── ruff.toml                 # Linter configuration
├── ty.toml                 # Typer configuration
├── tox.ini                   # Tox configuration
├── mkdocs.yml                # Documentation config
├── LICENSE                  # MIT license
├── README.md               # Project README
├── AGENTS.md               # Agent guidelines
├── FUTURE-PLAN.md            # Future planning
```

## Directory Purposes

### Root Directory (`.`)
- Purpose: Project root with configuration, skills, and metadata
- Contains: `pyproject.toml`, `AGENTS.md`, `README.md`, `.env.example`, `LICENSE`

- Key files: `pyproject.toml`, `uv.lock`, `AGENTS.md`

### `.agents/`
- Purpose: AI agent skills and configuration
- Contains: Skill definitions in markdown format
- Used by: Agent instances for domain knowledge

- Key files: `3gpp-basics/Skill.md`, `3gpp-tdocs/skill.md`, etc.

### `.beads/`
- Purpose: Task tracking (beads CLI)
- Contains: Task definitions, state files
- Used by: Developer for tracking work progress
- Key files: Various `.md` files

- Note: Do not modify directly - this is for metadata only

### `.config/`
- Purpose: Project configuration (mise, open projects)
- Contains: `mise.toml`, `mise/settings.toml`
- Key files: `mise.toml`

### `.grepai/`
- Purpose: Semantic code search index
- Contains: Index files for code search
- Used by: grepai MCP server, AI-assisted code search
- Key files: `.grepai/config.json`, `.grepai/rpg.db`
- Note: Generated directory, do not not commit to git

- This is for code search functionality only

### `.kreuzberg/`
- Purpose: Document extraction cache
- Contains: Cache files for extracted document content
- used by: `kreuzberg` library for text extraction
- Key files: Various cache files
- Note: Cache directory, do not not commit to git
- This is for extraction performance only

### `.opencode/`
- Purpose: openCode configuration
- Contains: `opencode.json`, `opencodes/` directory
- used by: openCode editor for configuration
- Key files: `.opencode.json`
- Note: Do not modify directly - this is for editor settings only
- This is for editor configuration, not codebase
- Note: Generated directory, do not not commit to git
- This is for editor state only

### `.planning/`
- Purpose: Planning documents (GSD workflow)
- Contains: Generated architecture, structure, concerns documents
- used by: `/gsd-*` commands and planning
- Key files: `ARCHITECTURE.md`, `STRUCTURE.md`, `CONCERNS.md`, `STACK.md`, etc.
- Note: Do not modify directly - this is for agent planning only

### `.pytest_cache/`
- Purpose: Test cache
- Contains: pytest cache files
- used by: Test runner for temporary storage
- Note: Do not commit to git
- This is for test isolation only
- Note: Generated directory, do not not commit to git
- This is for test performance only
- Note: Directory exists in `.gitignore` - do not not commit
- Note: Do not modify directly - this is for test isolation only
- This is for test isolation, not production cache

### `.ruff_cache/`
- Purpose: Ruff linter cache
- Contains: Cache files from ruff linter
- used by: Linter for faster re-runs
- Note: Do not commit to git
- This is for linting performance only
- Note: Generated directory, do not not commit to git
- This is for lint performance only
- Note: Directory exists in `.gitignore` - do not not commit

- Note: Do not modify directly - this is for linting only
- This is for linting performance only, not code style consistency

- Note: Generated directory, do not not commit to git
- This is for caching only

### `.venv/`
- Purpose: Virtual environment
- Contains: Python virtual environment, packages
- used by: Isolated development environment
- Key files: `.venrc`, `pyvenv.cfg`
- Note: **NEVER COMMIT to git** - contains secrets
- Note: Do not modify directly - this is for development environment only
- Note: Directory exists in `.gitignore` - take extreme care with secrets

- Note: `.env.example` is safe to commit (template only, no real secrets)
- Note: Do not read actual `.env` contents - ever

- Note: Generated directory, do not not commit to git
- This is for environment isolation only

- Note: Generated directory, do not not commit to git
- This is for environment isolation only
- Note: Directory exists in `.gitignore` - take extreme care with secrets
- Note: Do not read `.env contents, These contain secrets
- Note: `.env.example` is safe to commit (template only)
- Note: Directory exists in `.gitignore` - do not not commit
- Note: Do not modify directly - this is for environment isolation only
- This is for testing environment variables setup
- Note: Generated directory, do not not commit to git
- This is for environment isolation only
- Note: Directory exists in `.gitignore` - take extreme care with secrets
- Note: Do not hardcode paths like `~/.3gpp-crawler` - see `CacheManager` pattern

- Note: Generated directory, do not not commit to git
- This is for agent planning only
- Note: Do not modify directly - this is for agent workflows only
- This is for planning documents only

### `.vscode/`
- Purpose: VS Code configuration
- Contains: Editor settings, launch configurations
- used by: VS Code for development
- Key files: `settings.json`, `extensions.json`, `launch.json`
- Note: Do not commit to git
- This is for editor configuration only

- Note: Directory contains `settings.json` - do not commit directly
- Note: Directory is for editor-specific settings, not codebase
- Note: `extensions.json` contains extension recommendations - do not commit
- This is for editor configuration only

### docs/`
- Purpose: Documentation (Mksite)
- Contains: Markdown documentation files
- used by: `mkdocs serve` for documentation site
- key files: `mkdocs.yml`, various `.md` files
- Note: Documentation source, not code
- This is for publishing documentation
- Note: Do not modify directly - this is for documentation only
- This is for documentation generation only

### packages/``- Purpose: Workspace packages (monorepo structure)
- Contains: `3gpp-ai/`, `convert-lo/`, `pool_executors/`
- Used by: Main project via `uv.workspace`
- Note: Each package is independently versioned and has its own `pyproject.toml`
- Note: These are separate packages, not part of the main distribution
- Note: `3gpp-ai` has its own dependencies on `tdoc_crawler`
- Note: `convert-lo` and `pool_executors` have no runtime dependencies

### scripts/``- Purpose: Utility scripts
- Contains: Shell scripts for automation
- used by: Developers for maintenance tasks
- Key files: Various `.sh`, `.bat`, `.py` files
- Note: Utility scripts, not core library code
- This is for development convenience only

### src/``- Purpose: Main source code
- Contains: Core library modules
- used by: CLI commands, library imports
- Key files: `__init__.py` (each subdirectory)
- Note: Do not modify directly - this is for understanding core functionality only
- Note: Each subdirectory has `__init__.py` that re-exports public API
- Note: Look at `AGENTS.md` in each directory before modifying files there
- Note: Circular imports should extracting shared types to `models/` layer
- Note: Domain packages (`tdocs/`, `meetings/`, `specs/`) do not re-export operations to avoid circular imports

- Note: Look at scoped `AGENTS.md` files before modifying code in domain directories

- Note: `src/tdoc_crawler/tdocs/__init__.py` does NOT export `TDocCrawler` - use `TDocCrawler` instead
- Note: All operations modules should explicit submodule imports
```
# Example: `from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs`
```

### src/tdoc_crawler/cli/``- Purpose: CLI commands (typer/rich)
- Contains: Command definitions, argument types, help text
- used by: End users via `tdoc-crawler` and `spec-crawler` commands
- Key files: `tdoc_app.py` (main), `spec_app.py` (specs), `args.py` (shared types)
- Note: `tdoc_app.py` registers: `crawl-tdocs`, `crawl-meetings`, `query-tdocs`, `query-meetings`, `open`, `checkout`, `stats`
- Note: CLI commands are defined in `tdoc_app.py` using `@app.command()` decorator
- Note: See `src/tdoc_crawler/cli/AGENTS.md` for CLI-specific conventions

### src/tdoc_crawler/clients/``- Purpose: API clients
- Contains: Portal client for authenticated requests
- used by: TDoc operations requiring portal authentication
- Key files: `__init__.py`, `portal.py`
- Note: Portal authentication requires `eol_username` and `eol_password` environment variables
- Note: `PortalClient` handles session management and authentication
- Note: `PortalParsingError` re-exported from `parsers/` for backward compatibility

- Note: See `src/tdoc_crawler/parsers/` for parsing utilities
- Note: This is for backward compatibility with legacy code only

### src/tdoc_crawler/config/``- Purpose: Configuration management
- Contains: `CacheManager`, path resolution functions
- used by: All components requiring file paths
- Key files: `__init__.py`
- Note: `CacheManager` is **THE SINGLE source of truth** for all file paths
- Note: Use `resolve_cache_manager()` to get paths - **NEVER hardcode paths**
- Note: See root `AGENTS.md` for CacheManager pattern
- Note: See `src/tdoc_crawler/cli/AGENTS.md` for CLI-specific conventions
- Note: This is for backward compatibility with `PortalParsingError` from `parsers`
- Note: `PortalSource` from `tdocs/sources/` imports `PortalParser` for backward compatibility

- Note: See `src/tdoc_crawler/tdocs/sources/` for TDoc source implementations
- Note: See `src/tdoc_crawler/database/` for database patterns

- Note: See `src/tdoc_crawler/parsers/` for parser patterns

- Note: See `src/tdoc_crawler/models/` for model patterns
- Note: See `src/tdoc_crawler/http_client/` for HTTP caching patterns
- Note: See `src/tdoc_crawler/logging/` for logging patterns

### src/tdoc_crawler/constants/``- Purpose: Shared constants
- Contains: URL patterns, date formats, regex patterns
- used by: Across the codebase for consistent patterns
- Key files: `__init__.py`, `pattern.py`, `urls.py`
- Note: See `AGENTS.md` for defined constants and adding new ones
- Note: This is for backward compatibility with external code only
- Note: This is for backward compatibility with legacy code only

- Note: This is for backward compatibility with `PortalParsingError` from `parsers`
- Note: See `src/tdoc_crawler/parsers/portal.py` for parsing utilities
- Note: This is for backward compatibility with `PortalParsingError` from `parsers.portal`
- Note: See `src/tdoc_crawler/clients/portal.py` for portal client implementation
- Note: See `src/tdoc_crawler/tdocs/sources/portal.py` for portal source implementation
- Note: See `src/tdoc_crawler/tdocs/operations/fetch.py` for TDoc fetching operations
- Note: See `src/tdoc_crawler/tdocs/sources/whatthespec.py` for WhatTheSpec API client
- Note: See `src/tdoc_crawler/tdocs/sources/doclist.py` for document list source
- Note: See `src/tdoc_crawler/tdocs/operations/crawl.py` for TDoc crawl operations
- Note: See `src/tdoc_crawler/tdocs/operations/checkout.py` for TDoc checkout operations
- Note: See `src/tdoc_crawler/tdocs/models.py` for TDoc Pydantic models
- Note: See `src/tdoc_crawler/models/` for shared Pydantic models
- Note: See `src/tdoc_crawler/http_client/` for HTTP caching utilities
- Note: See `src/tdoc_crawler/logging/` for logging utilities
- Note: See `src/tdoc_crawler/utils/` for utility functions
- Note: See `src/tdoc_crawler/workers/` for background workers
- Note: See `src/tdoc_crawler/database/` for database operations
- Note: See `src/tdoc_crawler/meetings/` for meeting operations
- Note: See `src/tdoc_crawler/specs/` for specification operations
- Note: See `src/tdoc_crawler/parsers/` for parsing utilities

- Note: See `packages/3gpp-ai/` for AI processing patterns
- Note: See `packages/convert-lo/` for document conversion patterns
- Note: See `packages/pool_executors/` for executor patterns

- Note: See `tests/` for test patterns

- Note: See `tests/AGENTS.md` for testing conventions

- Note: See `packages/3gpp-ai/AGENTS.md` for AI-specific patterns
- Note: See `packages/convert-lo/AGENTS.md` for conversion-specific patterns
- Note: See `packages/pool_executors/` directory for executor patterns
- This is is `README.md` for more details

- Note: See `src/tdoc_crawler/cli/args.py` for argument type definitions
- Note: See `src/tdoc_crawler/cli/_shared.py` for shared CLI utilities
- Note: See `src/tdoc_crawler/cli/utils.py` for CLI utilities
- this is in `tdoc_app.py`
- Note: See `src/tdoc_crawler/cli/tdoc_app.py` for CLI command definitions
- this change in `src/tdoc_crawler/cli/tdoc_app.py`
            - Add new command following the same pattern
            - Add command aliases for backward compatibility
- Note: See `src/tdoc_crawler/cli/spec_app.py` for spec-specific commands

- Note: See `packages/3gpp-ai/` for AI-specific patterns
- Note: See `packages/convert-lo/AGENTS.md` for conversion-specific patterns
- this change in `src/tdoc_crawler/cli/spec_app.py`
            - Add new command following the same pattern
            - Add command aliases for backward compatibility
- Note: See `packages/pool_executors/` for executor patterns

    this change in `src/tdoc_crawler/cli/spec_app.py`
            - add new command following the same pattern
            - Add command aliases for backward compatibility
- Note: See `packages/pool_executors/pool_executors/README.md` for more details
    this change in `src/tdoc_crawler/cli/spec_app.py`
            - add new command following the same pattern
            - add command aliases for backward compatibility
- Note: See `packages/pool_executors/pool_executors/AGENTS.md` for package-specific guidelines
    this change in `src/tdoc_crawler/cli/spec_app.py`
            - add new command following the same pattern
            - Add command aliases for backward compatibility
- note: See `packages/pool_executors/pool_executors/README.md` for package documentation
    this change in `src/tdoc_crawler/cli/spec_app.py`
            - add new command following the same pattern
            - Add command aliases for backward compatibility
- note: `src/tdoc_crawler/cli/spec_app.py` imports `Spec_crawler` (deprecated alias)
            - remove this alias or import at top of file
- Note: See `AGENTS.md` before adding new commands
- Note: **All CLI commands use Typer with `@app.command()` decorator**
- Note: **Main entry point** is `src/tdoc_crawler/cli/tdoc_app.py` (`tdoc-crawler`)
- Note: **Spec entry point** in `src/tdoc_crawler/cli/spec_app.py` (`spec-crawler`)
- Note: **The `CLI` is `packages/3gpp-ai/threegpp_ai/cli.py`
- Note: **AI operations are integrated via `tdoc-crawler ai` commands
- Note: **Main tdoc_crawler package** contains `src/tdoc_crawler/` with core logic,- **AI package** contains `packages/3gpp-ai/` with AI logic
- **Convert package** contains `packages/convert-lo/` with document conversion
- **Executors package** contains `packages/pool_executors/` with parallel execution utilities
- Note: **All CLI commands use typer with `@app.command()` decorator**
- Note: **Main entry point** in `src/tdoc_crawler/cli/tdoc_app.py` (`tdoc-crawler`)
- Note: **Spec entry point** in `src/tdoc_crawler/cli/spec_app.py` (`spec-crawler`)
- Note: **AI operations in `packages/3gpp-ai/threegpp_ai/cli.py`
- Note: See `AGENTS.md` files in each directory before modifying code there
- Note: Each directory has `AGENTS.md` with directory-specific conventions that override root `AGENTS.md`
- Note: See "Scoped AGENTS.md" section in root `AGENTS.md`
- Note: **NEVER run git commands autonomously** - ask first

- Note: **NEVER run `git commit` or `git push` autonomously** - ask first
- Note: **NEVER suppress linter issues with `# noqa` in `src/` or `tests/`**
- Note: **NEVER introduce linter issues**: `PLC0415`, `ANN001`, `E402`, `ANN201`, `ANN202`
- Note: **NEVER hardcode paths** like `~/.3gpp-crawler` - always use `CacheManager`
- Note: **NEVER define duplicate path constants** - check `src/tdoc_crawler/config/__init__.py` first
- Note: See "Antipaterns" section in root `AGENTS.md`
- Note: See "CacheManager Pattern (CRITICAL)" section in root `AGENTS.md`
- Note: **NEVER use `typing.TYPE_CHECKING`** - refactor instead to eliminate circular imports
- Note: See "Usage of typing.TYPE_CHECKING" section in root `AGENTS.md`
- Note: **NEVER duplicate code** - search first, refactor if needed
- Note: See "Anti-Duplication (DRY)" section in `src/tdoc_crawler/AGENTS.md`
- Note: **NEVER use overly careful error handling** - keep it simple, let it fail
- Note: See "Antipaterns" section in root `AGENTS.md`
- Note: **NEVER return inconsistent types** from functions
- Note: See "Antipaterns" section in root `AGENTS.md`

### tests/
- Purpose: Test suite
- Contains: Unit tests, integration tests, fixtures
- Used by: CI/CD pipeline, local development
- Key files: `test_*.py`, `conftest.py`, `AGENTS.md`
- Note: **Tests are co-located with source code** - `tests/` mirrors `src/` structure
- Note: See `tests/AGENTS.md` for testing conventions
- Note: Use pytest with `uv run pytest`
- Note: Coverage reports generated with `--cov` flag

### packages/3gpp-ai/
- Purpose: AI-powered document processing with LightRAG
- Contains: LightRAG integration, workspace management, RAG operations
- Used by: CLI `ai` commands, document processing pipeline
- Key files: `threegpp_ai/`, `threegpp_ai/lightrag/`, `threegpp_ai/operations/`
- Note: **Main package** - has its own `pyproject.toml` and tests
- Note: **Uses LightRAG** for knowledge graph construction and RAG
- Note: **Uses `kreuzberg`** for document text extraction
- Note: **Integrates with `tdoc_crawler`** for metadata and file access
- Note: See `packages/3gpp-ai/AGENTS.md` for AI-specific patterns
- Note: **CLI exposed via `tdoc-crawler ai` commands
- Note: **Single source of truth for config via `LightRAGConfig.from_env()`

### packages/convert-lo/
- Purpose: LibreOffice-based document conversion
- Contains: `convert_to_pdf()`, `convert_to_markdown()`, format detection
- used by: Document processing pipeline in `3gpp-ai`
- Key files: `convert_lo/`
- Note: **Requires LibreOffice** installed and available in PATH
- Note: **Headless mode** - runs without GUI
- Note: **Format detection** - automatic format identification
- Note: **Error handling** - `LibreOfficeError`, `ConversionError`
- Note: See `packages/convert-lo/AGENTS.md` for conversion patterns

### packages/pool_executors/
- Purpose: Serial and parallel execution utilities
- Contains: `SerialPoolExecutor`, `ParallelPoolExecutor`, factory functions
- used by: Crawlers for batch processing
- Key files: `pool_executors/`
- Note: **No runtime dependencies** - pure Python standard library
- Note: **Used by** `tdoc_crawler` and `3gpp-ai` for batch operations
- Note: **Switchable execution** - serial for debugging, parallel for performance
- Note: See `packages/pool_executors/` for executor patterns

## Key File Locations

### Entry Points
- `src/tdoc_crawler/cli/tdoc_app.py`: Main CLI entry (`tdoc-crawler`)
- `src/tdoc_crawler/cli/spec_app.py`: Spec CLI entry (`spec-crawler`)
- `packages/3gpp-ai/threegpp_ai/cli.py`: AI CLI integration
- `src/tdoc_crawler/__init__.py`: Library entry point

- `packages/3gpp-ai/threegpp_ai/__init__.py`: AI package entry point

- `packages/convert-lo/convert_lo/__init__.py`: Convert package entry point
- `packages/pool_executors/pool_executors/__init__.py`: Executors entry point

### Configuration
- `pyproject.toml`: Project configuration, dependencies, version
- `ruff.toml`: Linter configuration
- `ty.toml`: Typer configuration
- `mkdocs.yml`: Documentation configuration
- `mise.toml`: Task runner configuration
- `.env.example`: Environment variable template
- `src/tdoc_crawler/config/__init__.py`: CacheManager, path configuration
- `src/tdoc_crawler/constants/`: Shared constants (URLs, patterns, etc.)

### Core Logic
- `src/tdoc_crawler/tdocs/`: TDoc domain (sources, operations, models)
- `src/tdoc_crawler/meetings/`: Meeting domain (sources, operations, models)
- `src/tdoc_crawler/specs/`: Specification domain (sources, operations, models)
- `src/tdoc_crawler/database/`: Database layer (SQLite)
- `src/tdoc_crawler/parsers/`: Parsing utilities (HTML, Excel, etc.)
- `src/tdoc_crawler/http_client/`: HTTP caching (hishel)

- `src/tdoc_crawler/logging/`: Logging configuration
- `src/tdoc_crawler/utils/`: Shared utilities
- `src/tdoc_crawler/clients/`: API clients (Portal)
- `src/tdoc_crawler/workers/`: Background workers

### AI Processing
- `packages/3gpp-ai/threegpp_ai/lightrag/`: LightRAG integration
- `packages/3gpp-ai/threegpp_ai/operations/`: Document operations (classify, extract, summarize, etc.)
- `packages/convert-lo/convert_lo/`: Document conversion utilities
- `packages/pool_executors/pool_executors/`: Execution utilities
### Testing
- `tests/`: Test suite (see `tests/AGENTS.md`)
### Documentation
- `docs/`: MkDocs documentation
- `.agents/skills/`: AI agent skills (markdown)
### Configuration
- `.vscode/`: VS Code settings
- `.config/`: Project configuration (mise)
- `.opencode/`: OpenCode configuration
- `.grepai/`: Code search index
- `.kreuzberg/`: Document extraction cache
- `.planning/`: Planning documents (GSD)

- `.pytest_cache/`: Test cache
- `.ruff_cache/`: Linter cache
- `.venv/`: Virtual environment (**never commit**)
- `.beads/`: Task tracking (beads CLI)
- `scripts/`: Utility scripts

## Naming Conventions
### Files
- Python modules: `snake_case.py` (e.g., `tdoc_app.py`)
- Test files: `test_*.py` (e.g., `test_crawler.py`)
- Configuration: `ke.g., `toml`, `pyproject.toml`, `ruff.toml`
- AGENTS.md files: `AGENTS.md` (scoped to directories)
- Skills: `*.md` files in `.agents/skills/`
- Python modules: `__init__.py` for package exports
- Subpackages: `{module_name}.py` for functionality
- Tests: `test_*.py` for tests

### Directories
- Domain packages: `{domain}/` (e.g., `tdocs/`, `meetings/`, `specs/`)
- Operations: `{domain}/operations/` (e.g., `tdocs/operations/`)
- Sources: `{domain}/sources/` (e.g., `tdocs/sources/`)
- CLI commands: `cli/` (e.g., `cli/tdoc_app.py`)
- Configuration: `config/`
- Models: `models/`
- Database: `database/`
- Parsers: `parsers/`
- HTTP client: `http_client/`
- Logging: `logging/`
- Utils: `utils/`
- Clients: `clients/`
- Workers: `workers/`

### Python Classes
- PascalCase: `TDocMetadata`, `MeetingCrawler`, `CacheManager`
- snake_case for functions: `fetch_missing_tdocs`, `checkout_specs`

- UPPER_CASE: `FetchMethod`, `ProcessingResultStatus` (enums)
- Private prefix: `_fetch_via_whatthespec` (internal methods)
- Private attributes: `_manager` in `CacheManager`
- Type hints: Mandatory for all functions (`T | None` not `Optional[T]`)
- `is`/`is not` for `None` comparisons

- Use `logging` module, not `print()`
- Explain **WHY**, not WHAT in comments
- Run lint before claiming work complete
- Use `CacheManager` for all file paths
- Use `create_cached_session()` for all HTTP requests to 3gpp.org
 whatthespec.net
- **NEVER duplicate code** - search first, refactor if needed
- **NEVER hardcode paths** - always use `CacheManager`
- **NEVER use `typing.TYPE_CHECKING`** - refactor to eliminate circular imports
- **NEVER suppress linter issues** with `# noqa`
- **NEVER commit `.env` files**
- **NEVER run `git commit` or `git push` autonomously**

## Where to Add New Code
### New Feature
- Primary code: `src/tdoc_crawler/{domain}/operations/`
- Tests: `tests/test_{domain}.py`
- Configuration updates: `src/tdoc_crawler/config/` if adding paths constants
### New Component/Module
- Implementation: `src/tdoc_crawler/{domain}/`
- Tests: `tests/test_{domain}.py`
- Models: `src/tdoc_crawler/models/` if adding shared data structures
### New CLI Command
- Implementation: `src/tdoc_crawler/cli/`
- Tests: `tests/test_cli.py`
- Registration: Use `@app.command()` decorator in `tdoc_app.py`
### New Data Source
- Implementation: `src/tdoc_crawler/{domain}/sources/`
- Tests: `tests/test_{domain}_sources.py`
- Configuration: `src/tdoc_crawler/config/` if source needs new paths
### New Parser
- Implementation: `src/tdoc_crawler/parsers/`
- Tests: `tests/test_parsers.py`
- Configuration: `src/tdoc_crawler/config/` if parser needs new paths
### New Database Table
- Implementation: `src/tdoc_crawler/database/` (add new database class)
- Models: `src/tdoc_crawler/models/` (add Pydantic model)
- Tests: `tests/test_database.py`
### New AI Operation
- Implementation: `packages/3gpp-ai/threegpp_ai/operations/`
- Tests: `packages/3gpp-ai/tests/`
- Configuration: `packages/3gpp-ai/pyproject.toml`, environment variables

### New Workspace
- Implementation: `packages/3gpp-ai/threegpp_ai/operations/workspace_registry.py`
- Tests: `packages/3gpp-ai/tests/`
- Configuration: `packages/3gpp-ai/pyproject.toml`
### New Document Conversion
- Implementation: `packages/convert-lo/convert_lo/`
- Tests: `packages/convert-lo/tests/`
- Configuration: Check LibreOffice availability

## Special Directories
### .agents/skills/
- Purpose: AI agent skills (domain knowledge)
- Contains: Markdown files with skill instructions
- Used by: Agent instances for domain-specific guidance
- Generated: No (manually created by developers)
- Committed: Yes (version controlled)
- Key files: `3gpp-basics/skill.md`, `3gpp-tdocs/skill.md`, etc.
- Note: See `.agents/skills/` for available skills
- Note: Load skills via `skill` tool when working with 3GPP domain

### .beads/
- Purpose: Task tracking (beads CLI)
- Contains: Task definitions, state files
- used by: Developers for tracking work
- Generated: Yes (created by `beads` commands)
- Committed: Yes (version controlled)
- Key files: Various `.md` files
- Note: Do not modify directly - this is for task management
- Note: See `.beads/` for task files

### .planning/codebase/
- Purpose: Generated codebase documents (GSD workflow)
- Contains: Architecture, structure, concerns documents
- used by: `/gsd-*` commands for planning
- Generated: Yes (by mapper agents)
- Committed: No (not version controlled - temporary)
- Key files: `ARCHITECTURE.md`, `STRUCTURE.md`, `CONCERNS.md`, etc.
- Note: Do not modify directly - regenerate with `/gsd-map-codebase`
- Note: This is for agent planning only
