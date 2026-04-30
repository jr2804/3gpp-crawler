# External Integrations

**Analysis Date:** 2026-04-30

> Documented external services, storage layers, auth mechanisms, and integration points
> for the 3GPP Crawler CLI application.

---

## External Services

### 3GPP Portal (portal.3gpp.org)
*Authenticated HTTP access to TDoc metadata.*

| Detail | Value |
|--------|-------|
| Base URL | `https://portal.3gpp.org` |
| Login URL | `https://portal.3gpp.org/login.aspx` |
| TDoc View | `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx` |
| TDoc Download | `https://portal.3gpp.org/ngppapp/DownloadTDoc.aspx` |
| Client class | `PortalClient` in `src/tdoc_crawler/clients/portal.py` |
| Auth | HTTP POST with `TDC_EOL_USERNAME`/`TDC_EOL_PASSWORD`, session cookies retained |
| Cache | Login requests explicitly skip cache (`http_cache_enabled=False`) |
| User-Agent | Browser-like headers to avoid 403 Forbidden |

**Key methods:**
- `PortalClient.fetch_tdoc_metadata()` — Crawl TDoc URLs from portal search pages
- `PortalClient.download_tdoc()` — Stream TDoc file download
- Error: `PortalAuthenticationError` on 401/403

### 3GPP Public Website (www.3gpp.org)
*Public HTML/excel sources for meetings and spec archives.*

| Detail | Value |
|--------|-------|
| Meetings URL | `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm` |
| Spec Archive | `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}` |
| Auth | None (public, browser User-Agent required) |
| Parsing | `BeautifulSoup` (HTML), `python-calamine` (Excel .xlsx) |

**TDoc Document List (Excel):**
- URL pattern: `{portal_base}/ngppapp/DownloadTDocFile.aspx?filename={meeting_doclist}.xlsx`
- Module: `tdocs/sources/doclist.py` — `fetch_meeting_document_list()`
- Parsing: `calamine` (Rust-backed Excel reader) → `TDocMetadata` models
- Can be called from subinterpreters via `workers/tdoc_worker.py`

### WhatTheSpec (whatthespec.3gpp.org)
*Community-maintained API for TDoc and spec lookups.*

| Detail | Value |
|--------|-------|
| Module | `src/tdoc_crawler/tdocs/sources/whatthespec.py` |
| Module (specs) | `src/tdoc_crawler/specs/sources/whatthespec.py` |
| Auth | None (public API) |
| Purpose | Primary source for single TDoc/spec lookups (faster than portal) |
| Fallback | 3GPP Portal when WhatTheSpec unavailable |

**Call pattern:**
```python
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
metadata = resolve_via_whatthespec(tdoc_id, session)
```

### PDF Remote Conversion API (pdf-convert.3gpp.org)
*Remote Office-to-PDF conversion fallback.*

| Detail | Value |
|--------|-------|
| Base URL | `https://pdf-convert.3gpp.org` (env: `PDF_REMOTE_API_BASE`) |
| Auth | API key (env: `PDF_REMOTE_API_KEY`) |
| Trigger | Automatic fallback when `ConverterBackend.AUTO` selected |
| Formats | DOCX, PPTX, XLSX, DOC, PPT, XLS |
| Local equivalent | `convert-lo` workspace package (LibreOffice CLI) |

---

## Storage Layer

### SQLite Database (Oxyde ORM)

| Property | Value |
|----------|-------|
| File | `{cache_dir}/3gpp_crawler.db` (default: `~/.3gpp-crawler/3gpp_crawler.db`) |
| ORM | `oxyde>=0.4.0` → `AsyncDatabase`, `Model` subclasses |
| Mode | WAL (write-ahead logging) for concurrent read performance |
| Connection | Async context manager: `async with DocDatabase(db_file) as db:` |
| Schema | Auto-created at startup via `extract_current_schema(dialect="sqlite")` |
| Migration | Schema diff on startup (not formal migrations — table create-if-not-exists) |
| URL format | `sqlite:///{db_file.as_posix()}` |

**Oxyde ORM Models** (in `src/tdoc_crawler/database/oxyde_models.py`):

| Model | Table | Key Fields | Purpose |
|-------|-------|------------|---------|
| `WorkingGroupRecord` | `working_groups` | `tbid` (PK), `code`, `name` | WG reference data |
| `SubWorkingGroupRecord` | `subworking_groups` | `subtb` (PK), `tbid`, `code`, `name` | SWG reference data |
| `CrawlLogEntry` | `crawl_log` | `log_id` (PK), `crawl_type`, `status`, timestamps | Crawl operation tracking |
| `MeetingMetadata` | `meetings` | `meeting_id` (PK), `tbid`, `subtb`, dates, location | Meeting records |
| `TDocMetadata` | `tdocs` | `tdoc_id` (PK), `meeting_id`, `title`, `source`, etc. | TDoc records |
| `Specification` | `specs` | `spec_number` (PK), `spec_type`, `title`, `status` | Spec identity |
| `SpecificationSourceRecord` | `spec_source_records` | `record_id` (PK), `spec_number`, `source_name`, `versions` | Source-specific snapshots |
| `SpecificationVersion` | `spec_versions` | `record_id` (PK), `spec_number`, `version`, `file_name` | Per-version metadata |
| `SpecificationDownload` | `spec_downloads` | `record_id` (PK), download info, checkout path | Download outcomes |

**Database facade:** `DocDatabase` in `src/tdoc_crawler/database/base.py`:
- Context manager lifecycle: `__aenter__` → connect, ensure tables, ensure reference data → `__aexit__` → disconnect
- `clear_tdocs()`, `clear_specs()` — truncate tables
- `log_crawl_start()` / `log_crawl_end()` — operational audit trail

**Subclass databases** (each adds domain-specific query methods):
- `MeetingDatabase` — meeting queries, statistics
- `TDocDatabase` — TDoc queries
- `SpecDatabase` — spec queries

### HTTP Cache Database

| Property | Value |
|----------|-------|
| File | `{cache_dir}/http-cache.sqlite3` (default: `~/.3gpp-crawler/http-cache.sqlite3`) |
| Backend | Hishel `SyncSqliteStorage` |
| Storage | Full HTTP responses (headers + body), keyed by request URL |
| Default TTL | 7200 seconds (2 hours), configurable via `HTTP_CACHE_TTL` or `HttpConfig.cache_ttl` |
| ETags/Cache-Control | Honored by hishel automatically |
| Fallback | Stale cache returned on 5xx errors (conditional) |

**Bridge adapter:** `_NiquetsCacheAdapter` in `http_client/session.py` — wraps hishel `CacheAdapter` to accept `niquests.PreparedRequest` objects.

**Session factory:**
```python
from tdoc_crawler.http_client import create_cached_session

# With caching (default)
session = create_cached_session()

# Without caching (portal login)
session = create_cached_session(http_cache_enabled=False)

# With explicit config
session = create_cached_session(http_config=config.http, pool_config=PoolConfig(max_connections=10))
```

### File Storage (Checkout)

| Path | Pattern | Purpose |
|------|---------|---------|
| `{checkout_dir}/{meeting}_{tdoc_id}/` | `checkout/SP-240000/SP-240000.docx` | Extracted TDoc files |
| `{checkout_dir}/Specs/{series}/{normalized}/` | `checkout/Specs/26_series/26444/` | Spec files |
| `{wiki_dir}/{workspace_id}/members/{member_id}/` | `wiki/default/members/SA-260638/` | Wiki extraction artifacts |

Checkout dir default: `~/.3gpp-crawler/checkout/`

### Workspace Registry

| Property | Value |
|----------|-------|
| File | `{cache_dir}/workspaces.json` (default: `~/.3gpp-crawler/workspaces.json`) |
| Format | JSON with version field |
| Storage | `WorkspaceRegistry` dataclass, serialized to/from JSON |
| Location | `src/tdoc_crawler/config/workspace_registry.py` |

Structure:
```json
{
  "version": 1,
  "workspaces": {
    "default": {
      "created_at": "...", "description": "",
      "members": [{"source_item_id": "...", "source_kind": "tdoc", ...}]
    }
  },
  "active": "default"
}
```

---

## Authentication & Identity

### Credentials Flow

| Step | Mechanism | Location |
|------|-----------|----------|
| 1. CLI input | `--eol-username`/`--eol-password` flags | `cli/args.py` |
| 2. Env vars | `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD` | `credentials.py` → `os.environ` |
| 3. Config file | `credentials.username` / `credentials.password` in TOML | `config/settings.py` → `CredentialsConfig` |
| 4. Interactive | `typer.prompt()` fallback | `credentials.py:resolve_credentials()` |
| 5. Global store | `set_credentials()` → writes to env | `credentials.py:set_credentials()` |

**Resolution order:** CLI > Config file > Env vars > Interactive prompt.

**Credential model:** `PortalCredentials` dataclass (`username: str`, `password: str`) in `models/base.py`.

**Session authentication:**
- `PortalClient` calls `create_cached_session(http_cache_enabled=False)` for login
- HTTP POST to `LOGIN_URL` with form data
- Response cookies stored in session for subsequent requests
- Validation: attempted on first portal request, `PortalAuthenticationError` on failure

### Secrets Storage
- `.env` file (auto-loaded by `python-dotenv` at module import time)
- Environment variables (direct export)
- `~/.3gpp-crawler/config.toml` (optional, credentials section)
- No encrypted credential store (plaintext in env/config)

---

## Configuration System

### ThreeGPPConfig (pydantic-settings)
`src/tdoc_crawler/config/settings.py`

```python
config = ThreeGPPConfig.from_settings()           # auto-discover
config = ThreeGPPConfig.from_settings(config_file=...)  # explicit
```

**Nested config models:**

| Sub-model | Env Prefix | Key Fields |
|-----------|-----------|------------|
| `PathConfig` | `TDC_` | `cache_dir`, `db_filename`, `checkout_dirname` |
| `HttpConfig` | (none, +HTTP_CACHE_*) | `cache_ttl`, `cache_enabled`, `verify_ssl`, `max_retries`, `timeout` |
| `CredentialsConfig` | `TDC_EOL_` | `username`, `password`, `prompt` |
| `CrawlConfig` | `TDC_CRAWL_` | `working_group`, `sub_group`, `date_start`, `date_end`, `limit`, `workers` |

**Config file discovery** (lowest to highest precedence):
1. Global: `~/.config/3gpp-crawler/config.toml`
2. Global `conf.d/`: `~/.config/3gpp-crawler/conf.d/*.toml`
3. Project-level (CWD-relative):
   - `.config/.3gpp-crawler/conf.d/*.toml`
   - `.config/.3gpp-crawler/config.toml`
   - `.config/3gpp-crawler.toml`
   - `.3gpp-crawler/config.toml`
   - `.3gpp-crawler.toml`
   - `3gpp-crawler.toml` (highest precedence)

**Format support:** TOML, YAML, JSON. Environment variable interpolation in values (`${VAR}`).

**ConfigEnvVar StrEnum** (`config/env_vars.py`): Maps env var names → TOML config paths for use in `pydantic.AliasChoices` and `typer.Option(envvar=...)`.

### CacheManager (Runtime Paths)
`src/tdoc_crawler/config/cache_manager.py`

Singleton pattern — registered once at CLI startup, resolved everywhere:

```python
# Startup (CLI callback)
CacheManager(config.path.cache_dir).register()

# Anywhere else
manager = resolve_cache_manager()
manager.root              # ~/.3gpp-crawler
manager.db_file           # ~/.3gpp-crawler/3gpp_crawler.db
manager.http_cache_file   # ~/.3gpp-crawler/http-cache.sqlite3
manager.checkout_dir      # ~/.3gpp-crawler/checkout
manager.workspace_registry_file  # ~/.3gpp-crawler/workspaces.json
manager.llm_wiki_dir      # ~/.3gpp-crawler/wiki
```

**Rule:** Never hardcode `~/.3gpp-crawler`. Always use `resolve_cache_manager()`.

---

## HTTP Client Patterns

### Module: `src/tdoc_crawler/http_client/`
- `session.py` — Core implementation
- `__init__.py` — Re-exports: `create_cached_session`, `download_to_file`, `PoolConfig`, `resolve_ssl_verify`

### `create_cached_session()` (the MANDATORY pattern)
```python
from tdoc_crawler.http_client import create_cached_session

# Standard usage — caching enabled, retries, browser headers
session = create_cached_session()

# With explicit config
session = create_cached_session(
    http_cache_file=custom_path,
    http_cache_enabled=True,
    pool_config=PoolConfig(max_connections=10, max_per_host=5),
    http_config=config.http,  # ThreeGPPConfig.http
)
```

**Internals:**
1. Creates `niquests.Session` with browser-like headers
2. Configures SSL verification (from `HttpConfig.verify_ssl` or explicit arg)
3. If caching enabled: creates `SyncSqliteStorage` → wraps in `_NiquetsCacheAdapter` with retry config
4. If caching disabled: configures plain `HTTPAdapter` with retries
5. Mounts adapter on `http://` and `https://`

### `download_to_file()` — Stream download helper
```python
from tdoc_crawler.http_client import download_to_file

session = download_to_file(
    url="https://...",
    target_file=Path("output.docx"),
    session=existing_session,  # optional, creates one if None
)
```
Streams in 8KB chunks, creates parent directories, returns session (or None if closing).

### PoolConfig
```python
@dataclass
class PoolConfig:
    max_connections: int = 10
    max_per_host: int = 5
    connection_timeout: float = 30.0
    enable_retry: bool = True
    retry_attempts: int = 3
```

### Retry Strategy
```
urllib3.Retry(
    total=retry_attempts,     # default 3
    backoff_factor=1,          # 1s, 2s, 4s
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
)
```

---

## Logging & Observability

| Aspect | Implementation |
|--------|---------------|
| **Framework** | Python `logging` + `RichHandler` |
| **Factory** | `get_logger(__name__)` in `src/tdoc_crawler/logging/__init__.py` |
| **Console** | `get_console()` — `Console(no_color=not sys.stdout.isatty(), width=120)` |
| **Verbosity** | `set_verbosity(level)` — sets root logger level, accepts str or int |
| **Default level** | `WARNING` |
| **Error tracking** | None (no Sentry/Rollbar) |
| **File logging** | Optional — not configured by default |
| **Rich features** | Colored output, tracebacks, markup, progress bars |

---

## Concurrency & Parallelism

| Technique | Library | Use Case |
|-----------|---------|----------|
| **Async I/O** | `asyncio` + `aiohttp`-style | Database operations, multiple HTTP requests |
| **Subinterpreters** | `aiointerpreters>=0.4.0` | Parallel TDoc crawling (isolated per meeting) |
| **Executor pools** | `pool-executors` (workspace) | Serial/thread/multiprocess/subinterpreter abstraction |
| **Sync-to-async bridge** | `run_async()` in `utils/async_helpers.py` | Calling coroutines from sync code (4+ call sites) |

**Worker module:** `src/tdoc_crawler/workers/tdoc_worker.py`
- `fetch_meeting_document_list_subinterpreter()` designed for `aiointerpreters`
- Serializes results as JSON for IPC between interpreters

---

## CI/CD & Deployment

| Aspect | Details |
|--------|---------|
| **CI** | Not checked into repo (no `.github/workflows/`) |
| **Pre-commit** | Ruff, pytest, deptry — config in `.pre-commit-config.yaml` |
| **Docker** | No Dockerfile checked in (user-managed deployment) |
| **Install** | `uv tool install` or `pip install 3gpp-crawler` |
| **Python req** | 3.14+ runtime |

### Data Flow Summary

```
3GPP FTP/HTTP ──→ niquests+hishel ──→ parsers (BeautifulSoup/calamine) ──→ Oxyde Models ──→ SQLite
                                                                                        │
WhatTheSpec API ──→ niquests ──→ TDocMetadata Pydantic model ──────────────────────────┤
                                                                                        │
Portal (auth) ──→ PortalClient ──→ Portal HTML parser ────────────────────────────────┤
                                                                                        │
                                                                                        ▼
                                                                              CLI Output (table/json/yaml/ison/toon)
                                                                                        │
                                                                                        ▼
                                                                              File checkout (DOCX/ZIP extraction)
```

---

*Integration audit: 2026-04-30*
