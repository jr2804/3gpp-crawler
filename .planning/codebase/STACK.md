# Technology Stack

**Analysis Date:** 2026-04-30

> CLI tool for crawling and querying structured 3GPP document data (TDocs, Specs, Meetings).
> Brownfield Python project using uv workspace monorepo.

---

## Languages & Runtimes

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Primary** | Python | `>=3.14,<4.0` | CPython, f-strings, type hints, `asyncio` |
| **SQL** | SQLite (via Oxyde ORM) | bundled | Schema auto-created at startup via `extract_current_schema()` |
| **Config** | TOML | stdlib | `import tomllib` (3.11+), fallback `tomli` |
| **Output** | Markdown, JSON, YAML, ISON, TOON | | Rich format serialization |

---

## Build System & Package Management

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Package manager** | `uv` | latest | Workspace monorepo management, lockfile, tool installs |
| **Build backend** | `hatchling` | via hatch | PEP 660 editable installs |
| **Versioning** | `uv-dynamic-versioning` | via git | PEP 440 versions from git tags, auto-bump |
| **Lockfile** | `uv.lock` | workspace-wide | Single lock for all workspace packages |
| **Entry points** | `[project.scripts]` | | 3 CLI entry points (see CLI section) |
| **Editable install** | `uv sync` | | Development workflow |

### Workspace Packages (monorepo)

| Package | Path | Version | Dependencies | Purpose |
|---------|------|---------|-------------|---------|
| `3gpp-crawler` | `src/tdoc_crawler/` | dynamic | 22+ | Main application |
| `convert-lo` | `packages/convert-lo/` | 0.1.0 | none | LibreOffice CLI conversion |
| `pool-executors` | `packages/pool_executors/` | 0.1.0 | none | Executor pool wrappers (serial, mp, thread, subinterpreter) |

Two workspace dependencies are sourced from git:
- `toon-format` — `git+https://github.com/toon-format/toon-python.git` (TOON output format)
- `doc2txt` — `git+https://github.com/Quantatirsk/doc2txt-pypi.git` (text extraction)

---

## Core Dependencies (pyproject.toml: `[project.dependencies]`)

### CLI & Terminal

| Library | Version | Purpose |
|---------|---------|---------|
| `typer` | `>=0.19.2` | CLI framework — decorator-based commands, auto-help, Rich integration |
| `rich` | `>=14.2.0` | Terminal formatting — tables (`rich.table`), progress bars (`rich.progress`), logging handler (`RichHandler`) |

### Database & ORM

| Library | Version | Purpose |
|---------|---------|---------|
| `oxyde` | `>=0.4.0` | Async SQLite ORM — `AsyncDatabase`, `Model`, `Field`, schema extraction/migration |
| `pydantic` | `>=2.12.2` | Data validation and model definitions (also used for Oxyde models) |
| `pydantic-settings` | `>=2.13.1` | `BaseSettings`-based config with env var loading, `AliasChoices` for env-to-field mapping |

### HTTP Client & Caching

| Library | Version | Purpose |
|---------|---------|---------|
| `niquests` | `>=3.18.4` | HTTP client — drop-in `requests` replacement with HTTP/2, brotli compression |
| `hishel` | `>=1.1.8` | HTTP response caching — `SyncSqliteStorage` backend, ETag/Cache-Control support |
| `brotli` | `>=1.2.0` | Brotli compression support for HTTP responses |

**Bridge code:** `_NiquetsCacheAdapter` in `http_client/session.py` bridges niquests-to-hishel type incompatibilities, since `niquests.PreparedRequest` does not inherit `requests.PreparedRequest`.

### Document Processing & Extraction

| Library | Version | Purpose |
|---------|---------|---------|
| `opendataloader-pdf[hybrid]` | `>=2.2.0` | Core document understanding — text/table/figure extraction via hybrid LLM pipeline |
| `convert-lo` | workspace | LibreOffice headless CLI conversion (DOCX-to-PDF, etc.) |
| `doc2txt` | git | Alternative text extraction from office documents |
| `liteparse` | `>=1.2.0` | Lightweight structural document parsing |

### Parsing & HTML

| Library | Version | Purpose |
|---------|---------|---------|
| `beautifulsoup4` | `>=4.14.2` | HTML parsing — portal pages, meeting listings |
| `lxml` | `>=6.0.2` | Fast XML/HTML tree operations |

### Excel Processing

| Library | Version | Purpose |
|---------|---------|---------|
| `python-calamine` | `>=0.5.3` | Fast Excel reading (Rust-backed) — TDoc document lists |
| `xlsxwriter` | `>=3.2.9` | Excel file generation |

### Data Serialization & Output

| Library | Version | Purpose |
|---------|---------|---------|
| `pyyaml` | `>=6.0.3` | YAML serialization for CLI output |
| `ison-py` | `>=1.0.2` | ISON format output (JSON superset with metadata) |
| `isonantic` | `>=1.0.1` | Pydantic-to-ISON bridge |
| `toon-format` | git | TOON format output |

### Utilities

| Library | Version | Purpose |
|---------|---------|---------|
| `packaging` | `>=25.0` | Version string parsing and normalization |
| `pandas` | `>=3.0.0` | Data manipulation and analysis |
| `python-dotenv` | `>=1.1.1` | `.env` file auto-loading (`load_dotenv()`) |
| `unzip-http` | `>=0.7` | Remote ZIP extraction over HTTP |
| `aiointerpreters` | `>=0.4.0` | Async subinterpreter management for parallel crawling |
| `pool-executors` | workspace | Thread/process/subinterpreter pool abstractions |

---

## Development Dependencies (`[dependency-groups.dev]`)

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=7.2.0` | Test framework |
| `pytest-asyncio` | `>=1.2.0` | Async test fixtures |
| `pytest-cov` | `>=4.0.0` | Coverage reporting |
| `pre-commit` | `>=2.20.0` | Pre-commit hook framework |
| `tox-uv` | `>=1.11.3` | Multi-env testing with uv |
| `deptry` | `>=0.23.0` | Dependency usage checking |
| `mkdocs` | `>=1.4.2` | Documentation generation |
| `mkdocs-material` | `>=8.5.10` | Material theme for mkdocs |
| `mkdocstrings[python]` | `>=0.26.1` | Python docstring extraction for mkdocs |
| `pydeps` | `>=3.0.2` | Dependency graph visualization |

---

## CLI Entry Points

Three separate Typer applications registered in `[project.scripts]`:

| CLI Command | Entry Point | Purpose |
|-------------|-------------|---------|
| `tdoc-crawler` | `tdoc_crawler.cli.tdoc_app:tdoc_app` | TDoc crawling, querying, checkout, stats |
| `spec-crawler` | `tdoc_crawler.cli.spec_app:spec_app` | Spec crawling, querying, checkout |
| `3gpp-crawler` | `tdoc_crawler.cli.mgmt_app:mgmt_app` | Config management, workspace management |

Each app has a `@callback()` that loads config, registers `CacheManager`, and sets verbosity.

---

## Internal Architecture (Source Layout)

```
src/tdoc_crawler/
├── cli/               # Typer command definitions (thin wrappers only)
│   ├── tdoc_app.py    # tdoc-crawler commands
│   ├── spec_app.py    # spec-crawler commands
│   ├── mgmt_app.py    # 3gpp-crawler (config+workspace) commands
│   ├── crawl.py       # Shared crawl command logic
│   ├── query.py       # Shared query command logic
│   ├── _shared.py     # Progress bars, clear options
│   ├── config.py      # CLI config loading helper
│   ├── args.py        # Typer Annotated type aliases
│   └── formatting.py  # Table/output formatting
├── config/            # Configuration system
│   ├── settings.py    # ThreeGPPConfig, PathConfig, HttpConfig, etc.
│   ├── cache_manager.py # Centralized path resolution (singleton)
│   ├── env_vars.py    # ConfigEnvVar StrEnum, env-to-config mapping
│   ├── sources.py     # Config file discovery, loading, merging
│   ├── export.py      # Config export/serialization
│   └── workspace_registry.py # Workspace state persistence
├── database/          # Database layer (Oxyde ORM)
│   ├── base.py        # DocDatabase — async context manager, schema management
│   ├── oxyde_models.py # All Oxyde Model definitions
│   ├── tdocs.py       # TDoc database operations
│   ├── meetings.py    # Meeting database operations
│   ├── specs.py       # Spec database operations
│   └── errors.py      # DatabaseError hierarchy
├── http_client/       # HTTP client with caching
│   ├── session.py     # create_cached_session(), download_to_file()
│   └── protocols.py   # HTTP-related protocol definitions
├── clients/           # External API clients
│   └── portal.py      # PortalClient — 3GPP authenticated portal access
├── parsers/           # Response parsers
│   ├── portal.py      # Portal HTML page parser
│   └── meetings.py    # Meeting HTML page parser
├── models/            # Shared data models (neutral layer)
│   ├── base.py        # OutputFormat, SortOrder, PortalCredentials
│   ├── workspaces.py  # Workspace, SourceKind, extraction models
│   ├── working_groups.py, subworking_groups.py # WG/SWG reference data
│   └── crawl_log.py   # Crawl log models
├── tdocs/             # TDoc domain (crawl, sources, operations)
├── meetings/          # Meeting domain (crawl, sources, operations)
├── specs/             # Spec domain (crawl, sources, operations)
├── extraction/        # Document extraction pipeline
├── workspaces/        # Workspace CRUD operations
├── workers/           # Subinterpreter worker functions
│   └── tdoc_worker.py # fetch_meeting_document_list_subinterpreter()
├── utils/             # Shared utilities
│   ├── async_helpers.py  # run_async() — safe sync-to-async bridge
│   ├── normalization.py  # ID, release, spec number normalization
│   ├── parse.py          # Spec version parsing
│   ├── security.py       # Path traversal checks, URL validation
│   ├── misc.py           # utc_now, etc.
│   └── date_parser.py    # Date parsing utilities
├── logging/           # RichHandler-based logging
│   └── __init__.py    # get_logger(), get_console(), set_verbosity()
└── constants/         # URL templates and patterns
    ├── urls.py        # PORTAL_BASE_URL, MEETINGS_BASE_URL, etc.
    └── patterns.py    # Regex patterns
```

---

## Key Patterns

### Async-to-Sync Bridge (`run_async`)
Found in `src/tdoc_crawler/utils/async_helpers.py`. Used by 4+ caller sites to run coroutines from synchronous contexts:
```python
from tdoc_crawler.utils.async_helpers import run_async
metadata = run_async(_resolve_metadata())  # safe whether or not loop is running
```
Detection logic: tries `asyncio.get_running_loop()`, falls back to `asyncio.run()` or background thread with its own loop.

### Configuration Precedence (highest to lowest)
1. CLI `--config` explicit file
2. Discovered config files (project-level `.toml`/`.yaml`/`.json`)
3. Environment variables (`TDC_*`, `HTTP_CACHE_*`)
4. Hard-coded defaults in `settings.py`

### CacheManager Singleton
`CacheManager(cache_dir).register()` at CLI startup to `resolve_cache_manager()` anywhere else.

---

## Platform Requirements

### Development

- Python 3.13+ (3.14+ preferred for subinterpreter support)
- Git (for version tagging via uv-dynamic-versioning)
- `uv` package manager (`pip install uv`)
- LibreOffice (optional, for local document conversion)

### Production / Runtime
- Python 3.14 runtime
- SQLite3 (bundled with Python)
- Network: `https://www.3gpp.org`, `https://portal.3gpp.org`, `https://pdf-convert.3gpp.org`, `https://whatthespec.3gpp.org`
- 2+ GB disk for cache (`~/.3gpp-crawler/`)
- No Dockerfile checked in (user-managed)

---

*Stack analysis: 2026-04-30*
