# Technology Stack

**Analysis Date:** 2026-04-30

## Languages

**Primary:**
- Python 3.14 (`requires-python = ">=3.14,<4.0"`) - Full codebase and CLI applications
- SQL (SQLite) - Native queries via Oxyde ORM for migrations and schema introspection

**Secondary:**
- TOML - Configuration files and build system
- Markdown - Documentation and extraction output

## Runtime

**Environment:**
- CPython 3.13+ (through 3.14)

**Package Manager:**
- `uv` (modern Python package manager and workspace manager)
- Lockfile: `uv.lock` (workspace-based monorepo lock)

## Frameworks

**Core CLI & Application:**
- `typer` (v0.19.2+) - CLI command framework with Rich integration
- `rich` (v14.2.0+) - Terminal formatting, tables, progress bars

**ORM & Database:**
- `oxyde` (v0.4.0+) - Async SQLite ORM (replaces previous pydantic-sqlite)
  - Async context manager pattern (`AsyncDatabase`, `async with`)
  - Auto-register models, schema extraction via `extract_current_schema()`
  - Used for: TDocs, Meetings, Specifications, Working Groups, Crawl Logs

**HTTP Client:**
- `niquests` (v3.18.4+) - Drop-in `requests` replacement with enhanced features (replaces `httpx`)
  - Supports HTTP/2, better compression, broader compatibility
  - Integrated with `hishel` for transparent caching

**Caching (HTTP):**
- `hishel` (v1.1.8+) - HTTP cache layer via `CacheAdapter`
  - `SyncSqliteStorage` backend (`http-cache.sqlite3`)
  - Bridges niquests ↔ hishel via custom adapter (`_NiquetsCacheAdapter`)
  - Caches responses per HTTP headers (ETags, Cache-Control)
  - Portal session login skips cache (explicit `http_cache_enabled=False`)

**Document Processing:**
- `opendataloader-pdf` (v2.2.0+, `hybrid` mode) - Primary text/table/figure extraction
  - Hybrid extraction: docling-fast LLM-based models
  - Output: Markdown + JSON with structured extraction
  - Supports PDF, Office formats (via LibreOffice)
  - Profiles: `PDF_ONLY`, `DEFAULT` (hybrid), `ADVANCED` (with VLM)

**PDF Conversion (Office → PDF):**
- `convert-lo` (workspace package) - LibreOffice automation via UNO bridge
  - Converts DOCX, PPTX, XLSX, etc. to PDF
  - Fallback remote API: `https://pdf-convert.3gpp.org` (optional)
  - Backend selection: LOCAL, REMOTE, AUTO (fallback)

**Text Extraction & Parsing:**
- `doc2txt` (git: `Quantatirsk/doc2txt-pypi.git`) - Alternative text extraction
- `liteparse` (v1.2.0+) - Lightweight structural parsing
- `beautifulsoup4` (v4.14.2+) - HTML parsing (portal pages, meetings)
- `lxml` (v6.0.2+) - Fast XML/HTML operations

**Data Formats & Serialization:**
- `pydantic` (v2.12.2+) - Data validation and model definitions
- `pydantic-settings` (v2.13.1+) - Environment-based configuration loading
- `ison-py` (v1.0.2) - ISON format output (JSON superset)
- `isonantic` (v1.0.1) - Pydantic ↔ ISON bridge
- `toon-format` (git: `toon-format/toon-python.git`) - TOON format output
- `pyyaml` (v6.0.3+) - YAML serialization

**Excel Processing:**
- `python-calamine` (v0.5.3+) - Fast Excel file reading (Rust-backed)
- `xlsxwriter` (v3.2.9+) - Excel file generation
- `openpyxl` (implicit, via calamine)

**Utilities:**
- `packaging` (v25.0+) - Version parsing and normalization
- `pandas` (v3.0.0+) - Data manipulation and analysis
- `python-dotenv` (v1.1.1+) - `.env` file loading
- `zipinspect` (v0.1.2) - Lightweight ZIP inspection
- `brotli` (v1.2.0) - Brotli compression support (for HTTP)
- `aiointerpreters` (v0.4.0+) - Async subprocess/interpreter management
- `pool-executors` (workspace package) - Thread/process pool utilities

## Key Dependencies

**Critical (extraction pipeline):**
- `opendataloader-pdf[hybrid]` v2.2.0+ — Core document understanding (tables, figures, text)
- `oxyde` v0.4.0+ — Persistent metadata storage (replaces volatile pydantic-based storage)
- `hishel` v1.1.8+ — HTTP response caching (60-80% bandwidth reduction on re-crawls)

**Infrastructure:**
- `niquests` v3.18.4+ — HTTP client with transparent compression and HTTP/2
- `convert-lo` (workspace) — Office format conversion (DOCX→PDF pipeline)
- `typer` v0.19.2+ — CLI command routing and context passing
- `pydantic` v2.12.2+ — Config validation, serialization schemas

**Telemetry & Development:**
- `rich` v14.2.0+ — Terminal output (tables, progress bars, error formatting)
- `pytest` v7.2.0+ (dev) — Test runner with async support
- `pytest-asyncio` v1.2.0+ (dev) — Async test fixtures
- `pytest-cov` v4.0.0+ (dev) — Coverage reporting

## Configuration

**Environment:**
- Loaded via `pydantic-settings` with `TDC_` prefix
- Key vars: `TDC_CACHE_DIR`, `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`, `TDC_HTTP_TIMEOUT`, `PDF_REMOTE_API_KEY`
- `.env` files auto-loaded by `python-dotenv` before CLI entry

**Build:**
- `pyproject.toml` — Single source of truth for deps, build config, metadata
- `hatch` (build backend via `hatchling`) — PEP 660 editable installs
- `uv-dynamic-versioning` — Git-based version management (PEP 440)

## Platform Requirements

**Development:**
- Python 3.13+ (stdlib, async/await stable)
- Git (for version tagging)
- LibreOffice (optional, for local PDF conversion)
- `uv` package manager

**Production:**
- Python 3.14 runtime
- SQLite3 (bundled with Python)
- Network access to `https://www.3gpp.org`, `https://portal.3gpp.org`
- 2+ GB disk for cache (tunable per `CacheManager`)

---

*Stack analysis: 2026-04-30*
