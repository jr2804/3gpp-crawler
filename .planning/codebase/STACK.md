# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**

- Python 3.14 - Entire codebase (core crawler, CLI, AI module, all sub-packages)

## Runtime

**Environment:**

- Python >=3.14,\<4.0 (required by root `pyproject.toml`)
- Python >=3.13,\<4.0 (sub-packages: convert-lo, pool_executors)

**Package Manager:**

- `uv` - Workspace monorepo with `packages/*` as workspace members
- Lockfile: `uv.lock` (present)

**Build System:**

- `hatchling` as build backend (all packages)
- `uv-dynamic-versioning` for git-based semver (root package only)

## Frameworks

**Core CLI:**

- `typer`>=0.19.2 - CLI framework (entry points: `tdoc-crawler`, `spec-crawler`, `3gpp-ai`)
- `rich`>=14.2.0 - Terminal output, progress bars, tables, console formatting

**Data Validation & ORM:**

- `pydantic`>=2.12.2 - Data models, validation, serialization
- `pydantic-sqlite`>=0.4.0 - SQLite ORM via Pydantic models
- `pydantic-settings`>=2.13.1 - Environment-based settings (3gpp-ai only)

**HTTP:**

- `requests`>=2.32.5 - HTTP client
- `hishel`>=1.1.8 - HTTP response caching (RFC 9110 compliant, SQLite-backed)
- `brotli`>=1.2.0 - Brotli decompression
- `charset_normalizer`>=2,\<4 + `chardet`>=5.1.0,\<6 - Encoding detection (requests v2.32.5 compatibility)

**Data Parsing & Formats:**

- `beautifulsoup4`>=4.14.2 - HTML parsing
- `lxml`>=6.0.2 - Fast XML/HTML parser backend
- `pandas`>=3.0.0 - Excel file reading (meeting document lists)
- `python-calamine`>=0.5.3 - Low-level spreadsheet reading
- `xlsxwriter`>=3.2.9 - Excel file creation
- `pyyaml`>=6.0.3 - YAML output
- `zipinspect`>=0.1.2 - ZIP file inspection

**AI/RAG (packages/3gpp-ai):**

- `lightrag-hku[offline]`>=1.4.9.3 - Knowledge graph construction, RAG, chunking
- `litellm`>=1.81.15 - Unified multi-provider LLM API gateway
- `kreuzberg[all]`>=4.0.0 - Document extraction (88+ formats: PDF, Office, images, HTML, email, archives, academic)
- `doc2txt`>=1.0.8 (git dependency) - Document-to-text conversion
- `pg0-embedded`>=0.12.0 - Embedded PostgreSQL with pgvector (optional vector storage)

**Concurrency & Workers:**

- `aiointerpreters`>=0.4.0 - Sub-interpreter-based parallel execution
- `pool-executors` (workspace package) - Serial/parallel executor utilities (stdlib-based)

**Document Conversion (packages/convert-lo):**

- No Python dependencies - wraps LibreOffice headless CLI (`soffice --headless --convert-to`)
- Environment variable: `LIBREOFFICE_PATH` for custom installation path

## Key Dependencies

**Critical (core application cannot function without):**

- `requests` + `hishel` - All HTTP communication with 3GPP servers; hishel provides transparent caching
- `pydantic` + `pydantic-sqlite` - Data models and database layer
- `typer` + `rich` - CLI interface
- `beautifulsoup4` + `lxml` - HTML parsing for 3GPP pages

**Critical (AI features):**

- `lightrag-hku` - Knowledge graph and RAG engine
- `litellm` - Multi-provider LLM routing
- `kreuzberg` - Document extraction pipeline

**Infrastructure:**

- `python-dotenv`>=1.1.1 - `.env` file loading
- `packaging`>=25.0 - Version comparison

## Dev Dependencies

**Linting & Formatting:**

- `ruff` v0.12.7 - Linter + formatter (replaces flake8, isort, black)
  - Target: Python 3.14, line-length 160
  - Rule categories: E, F, C4, C90, D (google), I, PT, PL, SIM, UP, W, S, ANN, B, NPY
- `undersort` - Method visibility ordering (public → protected → private)
- `pre-commit`>=2.20.0 - Git hook management

**Testing:**

- `pytest`>=7.2.0 - Test runner
- `pytest-asyncio`>=1.2.0 - Async test support
- `pytest-cov`>=4.0.0 - Coverage reporting (branch coverage)
- `tox-uv`>=1.11.3 - Multi-environment test matrix
- `deptry`>=0.23.0 - Dependency health checking

**Documentation:**

- `mkdocs`>=1.4.2 - Static site generator
- `mkdocs-material`>=8.5.10 - Material theme
- `mkdocstrings[python]`>=0.26.1 - API docs from docstrings

**Analysis:**

- `pydeps`>=3.0.2 - Dependency graph visualization

## Configuration

**Environment Variables:**

- `.env` file loaded via `python-dotenv`
- Template: `.env.example` (132 lines, fully documented)
- Prefix convention: `TDC_*` for crawler, `TDC_AI_*` for AI, `HTTP_CACHE_*` for HTTP cache

**Build Configuration:**

- `pyproject.toml` - Root and per-package manifests
- `ruff.toml` - Linter/formatter config (target py314, line-length 160, google docstyle)
- `.pre-commit-config.yaml` - Git hooks: ruff-check, ruff-format, undersort, pre-commit-hooks v5.0.0
- `tox.ini` - Multi-Python test matrix (py39–py313)
- `mkdocs.yml` - Documentation site (Material theme, mkdocstrings Python handler)

## CLI Entry Points

| Command | Module | Purpose |
|---------|--------|---------|
| `tdoc-crawler` | `src/tdoc_crawler/cli/tdoc_app.py` | Main CLI: crawl, query, AI operations |
| `spec-crawler` | `src/tdoc_crawler/cli/spec_app.py` | Specification-focused CLI |
| `3gpp-ai` | `packages/3gpp-ai/threegpp_ai/cli.py` | AI workspace management |

## Platform Requirements

**Development:**

- Python 3.14+
- uv (package manager)
- mise (task runner for dev tools: ripgrep, tree-cli)
- LibreOffice (optional, for document conversion)
- Ollama (optional, for local LLM/embeddings)

**Production:**

- Python 3.14+ runtime
- No mandatory external server dependencies (SQLite file-based by default)
- Optional: LibreOffice for PDF conversion
- Optional: Ollama or cloud LLM provider for AI features
- Optional: pg0-embedded for PostgreSQL-backed vector storage

______________________________________________________________________

*Stack analysis: 2026-03-27*
