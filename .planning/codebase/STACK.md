# Technology Stack

**Analysis Date:** 2026-05-03

## Languages

**Primary:**
- Python 3.14 — All source code, CLI, database, crawling, parsing

**Secondary:**
- Not applicable — Pure Python project

## Runtime

**Environment:**
- Python >=3.14,<4.0 (defined in `pyproject.toml`)
- Windows primary development platform (Linux-compatible)

**Package Manager:**
- uv — Modern Python package manager with workspace support
- Lockfile: `uv.lock` (present)
- Workspace: `packages/*` members (convert-lo, pool-executors)

## Frameworks

**Core:**
- typer >=0.19.2 — CLI framework with rich integration
- rich >=14.2.0 — Terminal formatting and progress display
- pydantic >=2.12.2 — Data validation and serialization models
- pydantic-settings >=2.13.1 — Configuration management from env vars / config files

**Testing:**
- pytest >=7.2.0 — Test runner
- pytest-cov >=4.0.0 — Coverage reporting
- pytest-asyncio >=1.2.0 — Async test support
- tox >=4 (via tox-uv) — Multi-environment testing

**Build/Dev:**
- hatchling + uv-dynamic-versioning — Build backend with git-based PEP 440 versioning
- ruff >=0.12.7 — Linting and formatting (preview mode, extensive rule set)
- ty — Astral's type checker (config: `ty.toml`)
- pre-commit — Git hooks (ruff, undersort, standard hooks)
- deptry >=0.23.0 — Dependency analysis
- mkdocs + mkdocs-material — Documentation site generation
- mkdocstrings[python] — API documentation from docstrings

## Key Dependencies

**Critical:**
- niquests >=3.18.4 — HTTP client (requests-compatible, replaces `requests`)
- hishel >=1.1.8 — HTTP caching layer (SQLite-backed, wraps niquests)
- oxyde >=0.4.0 — Async ORM for SQLite (replaces pydantic-sqlite)
- opendataloader-pdf[hybrid] >=2.2.0 — PDF extraction with hybrid server mode
- liteparse >=1.2.0 — Lightweight document parsing
- convert-lo (workspace) — LibreOffice headless document conversion
- pool-executors (workspace) — Parallel execution with subinterpreter support
- aiointerpreters >=0.4.0 — Subinterpreter-based parallelism for Python 3.14

**Infrastructure:**
- beautifulsoup4 >=4.14.2 — HTML parsing (3GPP portal pages)
- lxml >=6.0.2 — XML/HTML parsing backend
- pandas >=3.0.0 — DataFrame operations (Excel document lists)
- python-calamine >=0.5.3 — Fast Excel file reading
- xlsxwriter >=3.2.9 — Excel file writing
- packaging >=25.0 — Version parsing and comparison
- python-dotenv >=1.1.1 — .env file loading
- pyyaml >=6.0.3 — YAML config file support
- brotli >=1.2.0 — Brotli decompression for HTTP responses
- zipinspect >=0.1.2 — ZIP archive inspection
- doc2txt >=1.0.8 — Document text extraction (git source)
- ison-py >=1.0.2 — ISON format support
- isonantic >=1.0.1 — ISON antipattern detection
- toon-format (git) — Toon data format support

## Configuration

**Environment:**
- pydantic-settings `ThreeGPPConfig` (`src/tdoc_crawler/config/settings.py`)
- Multi-source config: TOML/YAML/JSON files + env vars + CLI args
- Config discovery: global (`~/.config/3gpp-crawler/`) + project-level (`3gpp-crawler.toml`)
- Env var prefix: `TDC_*`, `TDC_EOL_*`, `TDC_CRAWL_*`, `HTTP_CACHE_*`
- All env var names defined in `src/tdoc_crawler/config/env_vars.py` as `ConfigEnvVar` enum

**Build:**
- `pyproject.toml` — Project metadata, dependencies, build config
- `ruff.toml` — Linting and formatting rules
- `ty.toml` — Type checker configuration
- `tox.ini` — Multi-Python version testing
- `.pre-commit-config.yaml` — Git hook definitions
- `mkdocs.yml` — Documentation site config
- `codecov.yaml` — Coverage thresholds (90% target)

## Platform Requirements

**Development:**
- Python 3.14+ (required for subinterpreter parallelism)
- LibreOffice (for document-to-PDF conversion via `convert-lo`)
- uv package manager
- Git (for versioning, VCS-based dynamic version)

**Production:**
- Python 3.14+ runtime
- LibreOffice (optional, for office document conversion)
- opendataloader-pdf-hybrid server (optional, for advanced PDF extraction)
- Local filesystem for cache/database (default: `~/.3gpp-crawler/`)

## Entry Points

Three CLI commands registered in `pyproject.toml`:

| Command | Entry Point | Purpose |
|---------|-------------|---------|
| `tdoc-crawler` | `tdoc_crawler.cli.tdoc_app:tdoc_app` | TDoc crawling and querying |
| `spec-crawler` | `tdoc_crawler.cli.spec_app:spec_app` | Spec crawling and querying |
| `3gpp-crawler` | `tdoc_crawler.cli.mgmt_app:mgmt_app` | Management/config commands |

## Monorepo Workspace Packages

| Package | Path | Purpose |
|---------|------|---------|
| convert-lo | `packages/convert-lo/` | LibreOffice headless conversion wrapper |
| pool-executors | `packages/pool_executors/` | Lightweight executor pool with serial fallback |
| 3gpp-ai | `packages/3gpp-ai/threegpp_ai/` | AI-assisted processing (LightRAG, embeddings) — no pyproject.toml (subpackage) |

---

*Stack analysis: 2026-05-03*
