# Technology Stack

**Analysis Date:** 2026-03-25

## Languages

**Primary:**
- Python 3.14 - Core crawler library and CLI commands
- Python 3.13 - AI module (packages/3gpp-ai)

**Secondary:**
- Python 3.13 - Workspace packages (packages/convert-lo, packages/pool_executors)

## Runtime

**Environment:**
- Python 3.14+ (requires `>=3.14,<4.0`)
- UV package manager
- Lockfile: `uv.lock` (present)

- Virtual environment: `uv` (managed via `uv run`)

**Package Manager:**
- UV 0.5+ (modern, fast package management)
- Workspace support for multiple packages

- Version managed via `pyproject.toml` and dynamic versioning

- Dependencies added via `uv add <package>`

## Frameworks

**Core:**
- typer 0.19.2 - CLI framework with Rich integration
- rich 14.2.0 - Terminal formatting and progress bars
- pydantic 2.12.2 - Data validation and settings management
- pydantic-sqlite 0.4.0 - SQLite ORM wrapper

- requests 2.32.5 - HTTP client library
- hishel 1.1.8 - HTTP caching layer (RFC 9110 compliant)

- beautifulsoup4 4.14.2 - HTML/XML parsing
- lxml 6.0.2 - XML/HTML parser backend

- xlsxwriter 3.2.9 - Excel file generation
- python-calamine 0.5.3 - Fast Excel parsing
- pandas 3.0.0 - Data analysis and manipulation
- pyyaml 6.0.3 - YAML configuration parsing

- python-dotenv 1.1.1 - Environment variable management
- zipinspect 0.1.2 - ZIP file inspection
- pool-executors -0.1.0 - Executor pool utilities (workspace package)

- aiointerpreters 0.4.0 - Parallel execution with sub-interpreters

- brotli 1.2.0 - Brotli compression

- charset_normalizer 2-4 - Character encoding detection
- chardet 5.1.0 - Character encoding detection (fallback)

- pydantic-settings 2.13.1 - Settings management (AI package)

- litellm 1.81.15 - Multi-provider LLM gateway
- lightrag-hku 1.4.9.3 - RAG framework for knowledge graphs
- kreuzberg 4.0.0 - Document extraction (88+ formats)
- doc2txt 1.0.8 - DOC file conversion
- pg0-embedded 0.12.0 - Embedded PostgreSQL for vector storage

- docling - Document processing (via kreuzberg)

- sentence-transformers - Embedding support (via litellm)

- NetworkX - Graph storage (via LightRAG)

- NanoVectorDB - Vector storage (via LightRAG)

- JsonKVStorage - Key-value storage (via LightRAG)

- LanceDB (DEPRECATED - removed in favor of file-based storage

- `tdoc_ai.storage.lancedb` (removed)
- `tdoc_ai.operations.pipeline` (removed - replaced with new `tdoc_ai.operations.process_all()` approach

- convert-lo -0.1.0 - LibreOffice conversion (workspace package)
  - No dependencies (uses system LibreOffice)
  - Formats: ODT, DOC, DOCX, RTF, PDF, HTML, TXT, MD, EPUB, ODS, XLS, XLSX, CSV, ODP, PPT, PPTX, ODG, SVG

  - Conversion method: CLI mode (`soffice --headless --convert-to`)
  - No server required
  - Thread-unsafe ( conversions run sequentially
  - Default 5-minute timeout per file

  - External dependency: Requires LibreOffice installation

  - Located via: locator.py`

## Key Dependencies

**Critical:**
- requests 2.32.5 - HTTP client with caching support
- hishel 1.1.8 - Persistent HTTP caching (RFC 9110 compliant)
  - pydantic 2.12.2 - Data validation and serialization
- pydantic-sqlite 0.4.0 - SQLite database abstraction
- beautifulsoup4 4.14.2 - HTML/XML parsing
- lxml 6.0.2 - High-performance XML parser
- typer 0.19.2 - CLI framework
- rich 14.2.0 - Rich terminal output

- pyyaml 6.0.3 - YAML support
- python-dotenv 1.1.1 - .env file loading

- zipinspect 0.1.2 - ZIP file inspection
- aiointerpreters 0.4.0 - Parallel execution
- pool-executors 0.1.0 - Executor pool utilities (workspace)
- pandas 3.0.0 - Data analysis
- xlsxwriter 3.2.9 - Excel generation
- python-calamine 0.5.3 - Fast Excel parsing (calamine engine)
- brotli 1.2.0 - Brotli compression
- charset_normalizer 2-4 - Character encoding normalization
- chardet 5.1.0 - Character encoding detection

- doc2txt 1.0.8 - DOC to RTF conversion
- docling - Document processing (via kreuzberg)
- sentence-transformers - Embedding models (via litellm)
- NetworkX - Graph storage (via LightRAG)
- NanoVectorDB - Vector storage (via LightRAG)
- JsonKVStorage - Key-value storage (via LightRAG)
- pg0-embedded 0.12.0 - Embedded PostgreSQL (optional)
- litellm 1.81.15 - Multi-provider LLM gateway
- lightrag-hku 1.4.9.3 - RAG framework
- kreuzberg 4.0.0 - Document extraction (88+ formats)

- pg0-embedded 0.12.0 - Embedded PostgreSQL (optional)
- pydantic-settings 2.13.1 - Settings management

- pool-executors 0.1.0 - Executor utilities (workspace)

## Configuration

**Environment:**
- `.env` file with `TDC_*` variables
- Environment variables loaded via `python-dotenv`
- Configuration via `LightRAGConfig` from environment

- Example values in `src/tdoc_crawler/config/__init__.py`

- Config files in `pyproject.toml`, `mise.toml` (if exists)

- Build config in `hatch.build` via `hatchling`

- Version managed via `uv-dynamic-versioning` (Git-based)

- Test config in `pytest.ini_options`
- Coverage config in `pyproject.toml`
- Documentation in `mkdocs.yml` (if exists)

- MkDocs config in `mkdocs.yml`

- Tool config in `ruff.toml` (if exists)

- Linting config in `ruff.toml`

- VS Code config in `.vscode/settings.json` (if exists)

- Pre-commit config in `.pre-commit-config.yaml` (if exists)
- Editor config in `.editorconfig` (if exists)

- `.gitignore` for exclusion patterns
- `README.md` patterns
- `.env` patterns

- `tests/` patterns
- `__pycache__` patterns
- Cache directory
- Virtual environment files
- Build artifacts

- IDE/editor files

- Lock files (`uv.lock`, `.pyc-cryptographic hashes)

- `*.egg-info` files
- `*.manifest` files
- `dist/` directories
- Temporary test files
- Temporary directories created by OS or build tools

- Log files
- Sensitive files (credentials, keys)

- Database files (`*.db`, `*.sqlite`)
- Package-specific files

- `pyproject.toml` - Main package manifest
- `requirements.txt` - Python version requirements
- `uv.lock` - UV lock file
- `ruff.toml` - Ruff lintering configuration
- `pytest.ini_options` - Pytest configuration
- `mkdocs.yml` - MkDocs configuration
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.editorconfig` - Editor configuration
- `.gitignore` - Git ignore patterns

- `mise.toml` - Mise task runner (if exists)
- `.vscode/` - VS Code settings
- `pyc-python.tpc` - Python extension for VS Code
- `pyproject.toml` - Main package manifest
- `packages/*/pyproject.toml` - Workspace package manifests
- `uv-dynamic-versioning` - Dynamic versioning tool
- `README.md` - Project documentation
- `LICENSE` - License file (if exists)
- `CONTRIBUTING.md` - Contribution guidelines (if exists)
- `CHANGELOG.md` - Changelog (if exists)

- `.agents/` - Agent configuration and skills
- `docs/` - Documentation files
- `tests/` - Test suite

- `packages/3gpp-ai/tests/` - AI package tests
- `packages/convert-lo/tests/` - Convert-LO tests
- `packages/pool_executors/tests/` - Pool executors tests
- `.github/` - GitHub workflows (if exists)
- `src/tdoc_crawler/` - Main source code
- `src/tdoc_crawler/cli/` - CLI commands
- `src/tdoc_crawler/config/` - Configuration management
- `src/tdoc_crawler/database/` - Database layer
- `src/tdoc_crawler/models/` - Pydantic models
- `src/tdoc_crawler/http_client/` - HTTP client
- `src/tdoc_crawler/clients/` - API clients
- `src/tdoc_crawler/tdocs/` - TDoc operations
- `src/tdoc_crawler/specs/` - Specification operations
- `src/tdoc_crawler/meetings/` - Meeting operations
- `src/tdoc_crawler/parsers/` - Parsing utilities
- `src/tdoc_crawler/constants/` - Constants (URLs, patterns)
- `src/tdoc_crawler/workers/` - Worker processes
- `src/tdoc_crawler/utils/` - Utility functions
- `src/tdoc_crawler/credentials.py` - Credential management
- `src/tdoc_crawler/logging/` - Logging configuration
- `packages/3gpp-ai/threegpp_ai/` - AI package source
- `packages/convert-lo/convert_lo` - Convert-LO package source
- `packages/pool_executors/pool_executors` - Pool executors source
- `.planning/codebase/` - This document directory

- `data/` - Data files (if any)

- `logs/` - Log files (if any)
- `.tmp/` - Temporary files

- `*.bak` - Backup files
- `*.swp` - Swap files
- `*venv` - Virtual environment directories

- `node_modules` - Node.js modules
- `.tox` - Tox configuration
- `.mypy_cache` - MyPy cache
- `.pytest_cache` - Pytest cache
- `.ruff_cache` - Ruff cache
- `.coverage` - Coverage reports
- `*.pyc` - Python bytecode cache
- `*.egg-info` - Python package metadata
- `.venv` - Virtual environment
- `.idea` - IDE configuration
- `htmlcov` - HTML test coverage
- `*.manifest` - Android manifest
- `*.mo` - Motion files
- `*.ts` - TypeScript files
- `*.tsx` - TypeScript React files
- `*.js` - JavaScript files
- `*.css` - Style sheets
- `*.map` - JavaScript maps
- `*.sqlite` - SQLite databases
- `*.db` - SQLite database files
- `*.json` - JSON files
- `*.yaml` - YAML files
- `*.yml` - YAML files
- `*.toml` - TOML files
- `*.ini` - INI files
- `*.cfg` - CFG files
- `*.txt` - Text files
- `*.md` - Markdown files
- `*.rst` - reStructuredText files
- `*.pdf` - PDF files
- `*.zip` - ZIP archives
- `*.tar.gz` - Tarball archives
- `*.log` - Log files
- `*~` - Temporary files
- `._*` - macOS metadata
- `HP*` - HP printer files
- `Thumbs.db` - macOS thumbnail cache
- `Thumbs.db` - macOS thumbnail cache

- `.DS_Store` - macOS folder attributes
- `# JetBrains IDE` - JetBrains IDE files
- `# Rope project` - Rope project files
- `# rq` - Rope project files
- `# rope` - Rope project
- `# bbat` - Breadcrumbs build tool
- `# vagrant` - Vagrant files
- `# direnv` - Direnv files
- `# chef` - Chef files
- `# puppet` - AI Puppet files
- `# ansible` - Arduino/Ansible files
- `# puppet` - Puppet files
- `# ansible` - Ansible files
                prefix = "*_"
                enabled = true

[tool.mypy]
mypy_path = "src"
                mypy_config = "mypy.ini"
                disallow_untyped_defs = true
                warn_return_any = true
                warn_unused_ignores = true
                follow_imports_for_stdlib_or_third_party = true
                namespace_packages = true
                check_untyped_defs = true
                strict = true
                warn_redundant_exprs = true
                show_error_codes = true
                show_column_numbers = true
                extra_passes = [
                    "pydantic",
                ]

[tool.ruff]
line-length = 150
target-version = "py314"
select = [
    "ALL",
    "PLC0415",
    "ANN",
    "D",
    "ERA",
    "F",
    "I",
    "INP",
    "PERF",
    "PLR",
    "UP",
    "RUF",
    "SIM",
]
ignore = [
    # PLC0415 - import-outside-top-level (never)
    "D100", "S101", "BLE001",
    "RUF001",
    "RUF002",
    "RUF003",
    "RUF005",
    "RUF006",
    "RUF007",
    "RUF008",
    "RUF009",
    "RUF010",
    "D203",
    "D212",
    "D400",
    "D401",
    "CLI203",
    "PERF203",
    "PERF401",
    "INP001",
    "BLE001",
    "COM812",
    "PLW2901",
    "PLW2901",
    "ANN201",
    "ANN202",
    "ANN001",
    "ERA001",
    "PLW3201",
    "E402",
]
exclude = [
    ".git",
    "__pycache__"
    ".tox"
    ".pytest_cache"
    ".ruff_cache"
    ".mypy_cache"
    ".venv"
    ".idea"
    "node_modules"
    "dist"
    "data"
    "logs"
    "*.egg"
    "*.egg-info"
    "build"
    "eggs"
    "dist-info"
    "devel", "dev",
    "sdist"
    ".DS_Store"
    "Thumbs.db"
    "htmlcov"
    "tests/fixtures"
    "tests/output"
    "packages/*/tests"
    "packages/*/build"
    "packages/*/dist"
]
fixable = [
    # ANN401 - missing-type-self-argument
    # ANN401 - missing-return-type-special-method
    # ANN401 - missing-return-type-function
    # F401 - line-too-long
    # F841 - redefined-while-unused
    # COM812 - trailing-whitespace
    # PLW2901 - redefined-outer
    # PLW3201 - broad-exception-caught
]
dummy-variables-rgx = [
    # Example: https://example.com
]

dummy-variables-ruff.version = [
    # See: https://docs.astral.sh/ruff/0.10.0
]
pydocstyle = [
    # NumPy/SciPy style for docstrings
    "numpy",
]
# MKDocs documentation
theme = "material"
# Plugins for search, photos, "mkdocs-photoswipe"
# [markdown.extensions]
        "pymdownx.emoji"
        "pymdownx.highlight"
        "pymdownx.superfences"
        "pymdownx.tasklist"
        "pymdownx.tilde"
        "mkdocstrings"

]
# Repository info
repo_url = "https://forge.3gpp.org/rep/reimes/3gpp-crawler"
version = "0.1.0"
description = "Crawl 3GPP FTP server, cache all(!) 3GPP document data, return structured JSON/YAML for each document - all via CLI."
authors = [{ name = "Jan Reimes", email = "jan.reimes@head-acoustics.com" }]
readme = "README.md"
keywords = ['python']
requires-python = ">=3.14,<4.0"
classifiers = [
    "Intended Audience :: Developers",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

# Note: charset_normalizer and chardet are included as explicit dependencies to ensure compatibility with requests v2.32.5. This limitation might be lifted in future releases of requests, at which point these dependencies can be removed from this project.
dependencies = [
    "aiointerpreters>=0.4.0",
    "beautifulsoup4>=4.14.2",
    "brotli>=1.2.0",
    "hishel>=1.1.8",
    "pandas>=3.0.0",
    "pypyodantic>=2.12.2",
    "pydantic-sqlite>=0.4.0",
    "python-calamine>=0.5.3",
    "python-dotenv>=1.1.1",
    "pyyaml>=6.0.3",
    "requests>=2.2.5",
    "charset_normalizer>=2,<4",
    "chardet>=5.1.0,<6",
    "rich>=14.2.0",
    "typer>=0.19.2",
    "xlsxwriter>=3.2.9",
    "zipinspect>=0.1.2",
    "lxml>=6.0.2",
    "pool-executors",
]

[project.urls]
Repository = "https://forge.3gpp.org/rep/reimes/3gpp-crawler"


[dependency-groups]
dev = [
    "pytest>=7.2.0",
    "pre-commit>=2.20.0",
    "tox-uv>=1.11.3",
    "deptry>=0.23.0",
    "pytest-cov>=4.0.0",
    "mkdocs>=1.4.2",
    "mkdocs-material>=8.5.10",
    "mkdocstrings[python]>=0.26.1",
    "pytest-asyncio>=1.2.0",
    "pydeps>=3.0.2",
]

[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"
[project.scripts]
tdoc-crawler = "tdoc_crawler.cli.tdoc_app:app"
spec-crawler = "tdoc_crawler.cli.spec_app:spec_app"
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
# Register custom pytest marks
markers = [
    "integration: marks tests as integration tests (slower, requires network)",
]
# Suppress Pydantic deprecation warning from pydantic-sqlite library (external dependency)
filterwarnings = [
    "ignore:.*Accessing the 'model_fields' attribute on the instance is deprecated.*:DeprecationWarning",
]
[tool.coverage.report]
skip_empty = true
[tool.coverage.run]
branch = true
source = ["src"]
[tool.undersort]
# Method visibility ordering: public (no underscore), protected (single underscore), private (double underscore)
# Customize the order by specifying: "public", "protected", "private"
order = ["public", "protected", "private"]
# Method type ordering within each visibility level (optional)
# Options: "class" (classmethod), "static" (staticmethod), "source" (regular methods)
# Default order if not simple: ["instance", "class", "static"]
method_type_order = ["instance", "class", "static"]
# Exclude files/directories matching these patterns (optional)
# Patterns support glob syntax (e.g. "tests/*", "migrations/*.py", "**/generated/*")
# exclude = ["tests/*", "migrations/*.4.0]
exclude = ["tests/*", "migrations/*", "**/generated/*"]
[tool.hatch.build.targets.wheel]
packages = ["src/tdoc_crawler"]
[tool.hatch.version]
source = "uv-dynamic-versioning"
[tool.uv-dynamic-versioning]
vcs = "git"
style = "semver"
[tool.uv.workspace]
members = ["packages/*"]
[tool.uv.sources]
pool-executors = { workspace = true }
