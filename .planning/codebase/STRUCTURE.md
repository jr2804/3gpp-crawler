# Codebase Structure

**Analysis Date:** 2026-03-26

## Directory Layout

```
3gpp-crawler/
├── src/tdoc_crawler/           # Core library
│   ├── cli/                   # CLI commands (Typer)
│   ├── clients/               # External API clients
│   ├── config/                # CacheManager, path configuration
│   ├── constants/             # Shared constants
│   ├── database/              # SQLite database layer
│   ├── http_client/           # HTTP session factory (hishel)
│   ├── logging/               # Logging configuration
│   ├── meetings/              # Meeting domain
│   │   ├── models.py          # MeetingMetadata, configs
│   │   ├── operations/        # Crawl operations
│   │   ├── sources/           # Portal/FTP sources
│   │   └── utils.py           # Meeting utilities
│   ├── models/                # Shared models
│   │   ├── base.py            # BaseConfigModel, enums
│   │   ├── crawl_limits.py    # CrawlLimit dataclass
│   │   ├── crawl_log.py       # CrawlLogEntry
│   │   ├── subworking_groups.py # SubWG records
│   │   └── working_groups.py   # WG enum/records
│   ├── parsers/               # HTML/Excel parsers
│   ├── specs/                 # Specification domain
│   │   ├── models.py          # Spec models
│   │   ├── operations/        # Checkout operations
│   │   └── sources/           # Spec metadata sources
│   ├── tdocs/                 # TDoc domain
│   │   ├── models.py          # TDocMetadata, configs
│   │   ├── operations/        # Crawl, fetch, checkout
│   │   ├── sources/           # Portal, WhatTheSpec, DocList
│   │   └── utils.py           # TDoc utilities
│   ├── utils/                 # Shared utilities
│   └── workers/               # Parallel execution workers
├── packages/
│   ├── 3gpp-ai/               # AI processing (LightRAG)
│   │   └── threegpp_ai/
│   │       ├── lightrag/       # LightRAG integration
│   │       └── operations/     # Processing operations
│   ├── convert-lo/             # LibreOffice conversion
│   │   └── convert_lo/
│   └── pool_executors/         # Executor utilities
│       └── pool_executors/
├── tests/                     # Test suite
├── pyproject.toml             # Project configuration
├── AGENTS.md                  # Agent guidelines (root)
└── .env.example               # Environment variable template
```

## Directory Purposes

**src/tdoc_crawler/cli/:**
- Purpose: CLI commands and argument definitions
- Contains: Typer commands, Rich console output, argument types
- Key files: `app.py` (main), `crawl.py`, `query.py`, `args.py`

**src/tdoc_crawler/database/:**
- Purpose: SQLite database abstraction
- Contains: Database classes with upsert/query operations
- Key files: `base.py` (DocDatabase), `tdocs.py`, `meetings.py`, `specs.py`

**src/tdoc_crawler/tdocs/:**
- Purpose: TDoc domain logic
- Contains: Sources, operations, models
- Key files: `models.py` (TDocMetadata), `operations/crawl.py`, `operations/fetch.py`

**src/tdoc_crawler/meetings/:**
- Purpose: Meeting domain logic
- Contains: Sources, operations, models
- Key files: `models.py` (MeetingMetadata), `operations/crawl.py` (MeetingCrawler)

**src/tdoc_crawler/specs/:**
- Purpose: Specification domain logic
- Contains: Sources, operations
- Key files: `sources/threegpp.py`, `operations/checkout.py`

**src/tdoc_crawler/config/:**
- Purpose: Configuration and path management
- Contains: CacheManager singleton
- Key files: `__init__.py` (CacheManager, resolve_cache_manager)

**src/tdoc_crawler/http_client/:**
- Purpose: HTTP session management
- Contains: Cached session factory
- Key files: `session.py` (create_cached_session, download_to_file)

**src/tdoc_crawler/parsers/:**
- Purpose: Data extraction from various formats
- Contains: HTML/Excel parsers for 3GPP data
- Key files: `meetings.py`, `portal.py`

**packages/3gpp-ai/threegpp_ai/:**
- Purpose: AI-powered document processing
- Contains: LightRAG integration, workspace management
- Key files: `lightrag/rag.py` (TDocRAG), `lightrag/processor.py` (TDocProcessor)

**packages/convert-lo/convert_lo/:**
- Purpose: LibreOffice document conversion
- Contains: Headless conversion via soffice CLI
- Key files: `converter.py` (Converter class)

**packages/pool_executors/pool_executors/:**
- Purpose: Execution utilities
- Contains: Serial/parallel executors
- Key files: `serial.py` (SerialPoolExecutor), `factory.py` (create_executor)

## Key File Locations

**Entry Points:**
- `src/tdoc_crawler/__main__.py`: Main CLI entry (`python -m tdoc_crawler`)
- `src/tdoc_crawler/cli/app.py`: Typer app definition
- `pyproject.toml`: Package scripts (`tdoc-crawler`, `spec-crawler`)

**Configuration:**
- `src/tdoc_crawler/config/__init__.py`: CacheManager, path resolution
- `src/tdoc_crawler/models/base.py`: BaseConfigModel, HttpCacheConfig
- `.env.example`: Environment variable templates

**Core Logic:**
- `src/tdoc_crawler/tdocs/operations/crawl.py`: TDoc crawling orchestration
- `src/tdoc_crawler/tdocs/operations/fetch.py`: Missing TDoc fetching
- `src/tdoc_crawler/tdocs/operations/checkout.py`: TDoc download/extract
- `src/tdoc_crawler/meetings/operations/crawl.py`: Meeting crawling
- `src/tdoc_crawler/specs/operations/checkout.py`: Spec download

**Database:**
- `src/tdoc_crawler/database/base.py`: DocDatabase base class
- `src/tdoc_crawler/database/tdocs.py`: TDocDatabase (queries, upserts)
- `src/tdoc_crawler/database/meetings.py`: MeetingDatabase (queries, upserts)
- `src/tdoc_crawler/database/specs.py`: SpecDatabase (queries, upserts)

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `tdoc_app.py`, `crawl_meetings.py`)
- Test files: `test_*.py` (e.g., `test_crawler.py`)
- AGENTS.md: `AGENTS.md` (scoped to directories)
- Config files: `*.toml`, `pyproject.toml`, `ruff.toml`

**Directories:**
- Domain packages: `{domain}/` (e.g., `tdocs/`, `meetings/`, `specs/`)
- Operations: `{domain}/operations/` (e.g., `tdocs/operations/`)
- Sources: `{domain}/sources/` (e.g., `tdocs/sources/`)
- CLI: `cli/` (e.g., `cli/app.py`)
- Config: `config/`
- Models: `models/`
- Database: `database/`
- Parsers: `parsers/`
- HTTP: `http_client/`
- Logging: `logging/`
- Utils: `utils/`

**Classes:**
- PascalCase: `TDocMetadata`, `MeetingCrawler`, `CacheManager`
- snake_case functions: `fetch_missing_tdocs`, `checkout_specs`
- UPPER_CASE enums: `FetchMethod`, `ProcessingResultStatus`
- Private prefix `_`: `_fetch_via_whatthespec` (internal methods)

- Type hints: `T | None` not `Optional[T]`

## Where to Add New code

**New Domain (e.g., Change Requests):**
- Structure:
  ```
  src/tdoc_crawler/change_requests/
  ├── __init__.py
  ├── models.py           # ChangeRequestMetadata, configs
  ├── sources/            # CR sources
  │   ├── __init__.py
  │   └── portal.py
  └── operations/        # CR operations
      ├── __init__.py
      └── crawl.py
  ```
- Database: Add `ChangeRequestDatabase` to `database/`
- CLI: Add commands to `cli/` or new `cr_app.py`

**New Source for Existing Domain:**
- Add to: `src/tdoc_crawler/{domain}/sources/`
- Implement: `TDocSource` or `SpecSource` protocol
- Register: Export from `sources/__init__.py`

**New CLI Command:**
- Add to: Existing `cli/crawl.py`, `cli/query.py`, or create new file
- Register: In `cli/app.py` via `app.command()`
- Arguments: Define in `cli/args.py`

**New Parser:**
- Add to: `src/tdoc_crawler/parsers/`
- Export: From `parsers/__init__.py`
- Use: In domain sources

**New AI Operation:**
- Add to: `packages/3gpp-ai/threegpp_ai/operations/`
- Register: Export from `operations/__init__.py`
- CLI: Add command to `threegpp_ai/cli.py`

**New Utility Function:**
- Add to: `src/tdoc_crawler/utils/`
- Create module for category (e.g., `utils/date_parser.py`, `utils/parse.py`)
- Keep general-purpose, domain-agnostic

## Special Directories
**~/.3gpp-crawler/ (Default cache location):**
- Purpose: User cache directory
- Contains: `3gpp_crawler.db`, `http-cache.sqlite3`, `checkout/`, `lightrag/`
- Generated: Yes (by commands)
- Configurable: Via `TDC_CACHE_DIR` env var

**tests/test-cache/:**
- Purpose: Test database and cache files
- Contains: Test SQLite database
- Generated: Yes (by tests)
- Committed: No (gitignored)

**.agents/skills/:**
- Purpose: Agent skills and domain knowledge
- Contains: `skills/` (3gpp-basics, 3gpp-tdocs, etc.)
- Generated: No
- Committed: Yes

**.planning/codebase/:**
- Purpose: Planning documents and analysis
- Contains: `codebase/` (architecture docs), phase plans
- Generated: Yes (by GSD commands)
- Committed: Optional

---

*Structure analysis: 2026-03-26*
