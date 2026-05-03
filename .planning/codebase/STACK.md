# Technology Stack

**Analysis Date:** 2026-05-03

## Languages

**Primary:**
- Python ≥3.14,<4.0 — All source code: `src/tdoc_crawler/`, `packages/convert-lo/`, `packages/pool_executors/`

**Secondary:**
- Node.js / Bun — Dev tools (GrepAI MCP, add-mcp, add-skills scripts via mise)

## Runtime

**Environment:**
- Python 3.14 (explicit in `pyproject.toml` requires-python, `ty.toml` python-version, `ruff.toml` target-version)

**Package Manager:**
- uv — Environment management, dependency resolution, script running
- Lockfile: `uv.lock` present
- Build backend: hatchling with `uv-dynamic-versioning` for PEP 440 Git-derived versions

**Task Runner:**
- mise — Defined in `.config/mise/config.toml`; tasks for lint, test, format, type-check, etc.

## Frameworks

**Core:**
- Typer ≥0.19.2 — CLI framework (`src/tdoc_crawler/cli/tdoc_app.py`, `mgmt_app.py`, `spec_app.py`)
- Rich ≥14.2.0 — Terminal output formatting, progress bars, tables
- Pydantic ≥2.12.2 — Data models, validation, serialization (`src/tdoc_crawler/tdocs/models.py`, `src/tdoc_crawler/database/oxyde_models.py`)
- pydantic-settings ≥2.13.1 — Configuration management from env vars and TOML files (`src/tdoc_crawler/config/settings.py`)

**Testing:**
- pytest ≥7.2.0 — Test runner with `pytest-cov`, `pytest-asyncio`
- tox-uv ≥1.11.3 — Multi-environment test runner (`tox.ini`)

**Build/Dev:**
- ruff — Formatting and linting (`ruff.toml`, `.pre-commit-config.yaml`)
- ty — Static type checking (`ty.toml`)
- undersort — Method ordering within classes
- pre-commit ≥2.20.0 — Git hook management
- mkdocs + mkdocs-material + mkdocstrings — Documentation (`mkdocs.yml`)

## Key Dependencies

**Critical:**
- niquests ≥3.18.4 — HTTP client (requests-compatible, with Brotli support) — `src/tdoc_crawler/http_client/session.py`
- hishel ≥1.1.8 — HTTP response caching with SQLite storage backend — `src/tdoc_crawler/http_client/session.py`
- oxyde ≥0.4.0 — Async ORM for SQLite database — `src/tdoc_crawler/database/base.py`
- opendataloader-pdf[hybrid] ≥2.2.0 — PDF extraction pipeline with local hybrid server — `src/tdoc_crawler/extraction/hybrid_server.py`, `src/tdoc_crawler/extraction/convert.py`
- liteparse ≥1.2.0 — Document parsing and conversion
- doc2txt ≥1.0.8 — Document-to-text extraction
- convert-lo — LibreOffice headless document conversion (workspace package: `packages/convert-lo/`)
- Python stdlib: `gzip`, `zlib`, `brotli` ≥1.2.0 — Response body decompression

**Infrastructure:**
- python-dotenv ≥1.1.1 — `.env` file loading (loaded in CLI startup, `src/tdoc_crawler/cli/tdoc_app.py`)
- beautifulsoup4 ≥4.14.2 + lxml ≥6.0.2 — HTML parsing for portal pages and meetings
- pandas ≥3.0.0 + python-calamine ≥0.5.3 — Excel document list parsing
- aiointerpreters ≥0.4.0 — Parallel crawling via sub-interpreters
- pool-executors — Serial and parallel executor pool extensions (workspace package: `packages/pool_executors/`)
- packaging ≥25.0 — Semantic version parsing and comparison
- zipinspect ≥0.1.2 — Remote ZIP inspection for spec downloads (`src/tdoc_crawler/specs/downloads.py`)
- xlsxwriter ≥3.2.9 — Excel export capability
- pyyaml ≥6.0.3 — YAML parsing for config and data
- ison-py ≥1.0.2 + isonantic ≥1.0.1 — JSON utilities
- toon-format — Token-efficient format serialization
- brotli ≥1.2.0 — Brotli decompression for HTTP responses

## Configuration

**Environment:**
- `.env` file loaded via `python-dotenv` at CLI startup (`src/tdoc_crawler/cli/tdoc_app.py`, `src/tdoc_crawler/cli/mgmt_app.py`)
- Environment variables documented in `.env.example` with TDC_ prefix
- pydantic-settings provides type-safe config with TOML file fallback
- Config file discovery: `~/.config/3gpp-crawler/config.toml`, `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.3gpp-crawler/config.toml`
- Config precedence: CLI args → Config file → Env vars → Defaults

**Key Environment Variables:**
- `TDC_CACHE_DIR` — Root cache directory (default: `~/.3gpp-crawler`)
- `TDC_DB_FILENAME` — SQLite database filename (default: `3gpp_crawler.db`)
- `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD` — ETSI Online credentials for 3GPP portal
- `TDC_TIMEOUT` — HTTP request timeout (default: 30s)
- `TDC_MAX_RETRIES` — HTTP retry attempts (default: 3)
- `HTTP_CACHE_ENABLED` / `HTTP_CACHE_TTL` / `HTTP_CACHE_REFRESH_ON_ACCESS` — HTTP caching behavior
- `TDC_WORKERS` — Parallel worker count (default: 4)
- `HF_TOKEN` — Hugging Face API token (optional, for AI model access)
- `PDF_REMOTE_API_KEY` — Remote PDF converter API key (optional)
- `LIBREOFFICE_PATH` — Override LibreOffice executable path

**Build:**
- `pyproject.toml` — Build config (hatchling), workspace members (packages/*), tool configs (pytest, coverage, uv-dynamic-versioning)
- `ruff.toml` — Linting rules (Python 3.14 target, 160-char line length, Google docstring convention)
- `ty.toml` — Type checker config
- `tox.ini` — Multi-version test runner (py39–py313)

## Platform Requirements

**Development:**
- Python ≥3.14
- uv + mise
- LibreOffice (for office→PDF conversion; auto-detected or via `LIBREOFFICE_PATH`)
- Node.js / Bun (for development tooling, GrepAI)
- Git with pre-commit hooks configured

**Production / Distribution:**
- CLI tool packaged as Python wheel (`pyproject.toml` → `hatchling.build`)
- Three entry points: `tdoc-crawler`, `spec-crawler`, `3gpp-crawler`
- Published via internal Forge (forge.3gpp.org)
- Local SQLite database at `~/.3gpp-crawler/3gpp_crawler.db`
- LibreOffice required for office document conversion
- Network access to 3GPP portal and FTP servers for crawling

---

*Stack analysis: 2026-05-03*
