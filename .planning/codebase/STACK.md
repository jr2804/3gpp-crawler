# Technology Stack

**Analysis Date:** 2026-05-22

## Languages

**Primary:**
- Python 3.13 — Main application language (`requires-python >=3.13,<3.14`)
  - Used for all source code in `src/tdoc_crawler/`, `packages/`, and `tests/`

**Secondary:**
- TOML — Configuration files (`pyproject.toml`, `ruff.toml`, `ty.toml`, `3gpp-crawler.toml` user configs)
- YAML — CI/tox config (`tox.ini`, `.pre-commit-config.yaml`, `mkdocs.yml`, `codecov.yaml`)
- Markdown — Documentation (`docs/`, `README.md`, AGENTS.md files)

## Runtime

**Environment:**
- Python 3.13 (strict: `>=3.13,<3.14`)
- Note: `tox.ini` lists `py39` through `py313` but `pyproject.toml` constrains to 3.13 only
- Type checker (`ty.toml`) targets Python 3.14 for forward-compatibility

**Package Manager:**
- uv (with workspace support)
- Lockfile: `uv.lock` present (gitignored per `.gitignore`)
- Workspace: `[tool.uv.workspace]` with `members = ["packages/*"]`

## Frameworks

**Core:**
- typer >=0.19.2 — CLI framework (Typer/Rich wrappers)
- rich >=14.2.0 — Terminal output formatting, progress bars, logging handlers
- pydantic >=2.12.2 — Data validation and models
- pydantic-settings >=2.13.1 — Configuration management from env vars and files

**ORM / Database:**
- oxyde >=0.4.0 — SQLite ORM (replaces previous pydantic-sqlite)
  - All DB models in `src/tdoc_crawler/database/oxyde_models.py`

**HTTP:**
- niquests >=3.18.4 — HTTP client (requests-compatible, HTTP/3 capable, fork/upgrade of requests)
- hishel >=1.1.8 — HTTP response caching (SQLite-backed)
- Custom `_NiquetsCacheAdapter` bridges niquests ↔ hishel (`src/tdoc_crawler/http_client/session.py`)

**Document Processing:**
- docling >=2.93.0 — ML-based structured document extraction (PDF, DOCX → Markdown + JSON)
- pymupdf >=1.27.2.3 — PDF manipulation (PyMuPDF)
- pymupdf4llm >=1.27.2.3 — Fast layout-aware Markdown extraction (no ML)
- convert-lo — Internal workspace package for LibreOffice headless conversion
- beautifulsoup4 >=4.14.2 — HTML parsing
- lxml >=6.0.2 — XML/HTML processing
- python-calamine >=0.5.3 — Excel file reading (`.xlsx`, `.xls`)
- xlsxwriter >=3.2.9 — Excel file writing
- opencv-python-headless >=4.13.0.92 — Image processing for extraction pipeline

**Testing:**
- pytest >=7.2.0 — Test runner
- pytest-cov >=4.0.0 — Coverage reporting
- pytest-asyncio >=1.2.0 — Async test support

**Build/Dev:**
- hatchling — Build backend
- uv-dynamic-versioning — Git-based versioning
- ruff v0.12.7 — Linter and formatter (via pre-commit)
- ty (Astral) — Type checker (`ty.toml`)
- pre-commit v5.0.0 — Git hook management
- tox + tox-uv — Multi-environment testing
- deptry >=0.23.0 — Dependency audit
- undersort — Method ordering enforcement

**Documentation:**
- mkdocs + mkdocs-material — Documentation site
- mkdocstrings[python] — API documentation from docstrings

## Key Dependencies

**Critical:**
- oxyde >=0.4.0 — All database persistence; every model inherits `oxyde.Model`
- niquests >=3.18.4 — All HTTP requests; must use `disable_http3=True` (see `src/tdoc_crawler/AGENTS.md`)
- hishel >=1.1.8 — HTTP caching layer; SQLite-backed cache at `{cache_dir}/http-cache.sqlite3`
- pydantic-settings >=2.13.1 — Central config via `ThreeGPPConfig` (`src/tdoc_crawler/config/settings.py`)

**Infrastructure:**
- packaging >=24.0 — Version parsing for spec/TDoc version numbers
- pandas >=3.0.0 — Data manipulation (Excel DocList parsing)
- pyyaml >=6.0.3 — YAML config file support
- python-dotenv >=1.1.1 — `.env` file loading for credentials
- brotli >=1.2.0 — HTTP response decompression
- unzip-http >=0.7 — Streaming ZIP extraction over HTTP
- liteparse >=1.2.0 — Lightweight document parsing
- ison-py >=1.0.2 — ISON configuration format support
- isonantic >=1.0.1 — ISON-related utilities
- toon-format — Token-efficient output format (git dependency)

**Document Conversion:**
- convert-lo — Workspace package; wraps `soffice --headless --convert-to` for DOC/DOCX/ODT → PDF
- pool-executors — Workspace package; executor pool extensions including serial execution support

## Configuration

**Environment:**
- Config via pydantic-settings with env vars (prefix `TDC_*`)
- Config file discovery: TOML/YAML/JSON, mise-style hierarchy
  - Global: `~/.config/3gpp-crawler/config.toml`
  - Project: `3gpp-crawler.toml`, `.3gpp-crawler.toml`, `.config/` variants
- `.env` file support via python-dotenv (loaded at CLI entry point)
- Central `CacheManager` singleton for all file paths (`src/tdoc_crawler/config/cache_manager.py`)
- Config precedence: CLI args > Config file > Env vars > Defaults

**Build:**
- `pyproject.toml` — Project metadata, dependencies, tool config
- `ruff.toml` — Linter/formatter rules (target py313, line-length 160)
- `ty.toml` — Type checker rules (targets Python 3.14)
- `tox.ini` — Multi-Python test matrix
- `.pre-commit-config.yaml` — Pre-commit hooks (ruff, undersort, standard checks)
- `mkdocs.yml` — Documentation site generation
- `codecov.yaml` — Coverage reporting config (target 90%)

**Entry Points (CLI):**
- `tdoc-crawler` → `tdoc_crawler.cli.tdoc_app:tdoc_app`
- `spec-crawler` → `tdoc_crawler.cli.spec_app:spec_app`
- `3gpp-crawler` → `tdoc_crawler.cli.mgmt_app:mgmt_app`

## Platform Requirements

**Development:**
- Python 3.13
- uv package manager
- LibreOffice (for document conversion via `convert-lo`)
- Optional: CUDA GPU (for accelerated Docling ML extraction)
- Optional: Hugging Face token (`HF_TOKEN`) for model downloads without rate limits

**Production:**
- Python 3.13 runtime
- SQLite (bundled with Python, used for metadata DB and HTTP cache)
- LibreOffice (for DOC/DOCX/ODT → PDF conversion)
- ETSI Online (EOL) credentials for authenticated portal access

---

*Stack analysis: 2026-05-22*
