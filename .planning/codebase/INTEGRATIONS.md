# External Integrations

**Analysis Date:** 2026-05-03

## APIs & External Services

### 3GPP Portal (Primary)
- **Service:** 3GPP EOL (ETSI Online) authenticated portal
- **Base URL:** `https://portal.3gpp.org` (defined in `src/tdoc_crawler/constants/urls.py`)
- **Endpoints:**
  - `/ngppapp/CreateTdoc.Aspx` — TDoc metadata view (authenticated)
  - `/ngppapp/DownloadTDoc.aspx` — TDoc file download URL extraction
  - `/ngppapp/GenerateDocumentList.aspx` — Meeting document list Excel export
  - `/ETSIPages/LoginEOL.ashx` — AJAX login endpoint (JSON POST)
  - `/login.aspx` — Login page (session establishment)
- **Client:** `PortalClient` in `src/tdoc_crawler/clients/portal.py`
- **Auth:** EOL username/password via `TDC_EOL_USERNAME` / `TDC_EOL_PASSWORD`
- **Resolution order:** CLI args > config file > env vars > interactive prompt (`src/tdoc_crawler/credentials.py`)

### WhatTheSpec.net (Fallback)
- **Service:** Community 3GPP metadata API
- **Base URL:** `https://whatthespec.net/3gpp/`
- **Endpoints:**
  - `tdoc.php?name={tdoc}&api=1` — TDoc metadata lookup
  - `spec.php?q={compact}&api=1` — Spec metadata lookup
- **Client:** `src/tdoc_crawler/tdocs/sources/whatthespec.py`, `src/tdoc_crawler/specs/sources/whatthespec.py`
- **Auth:** None required (public API)
- **Role:** Fallback for TDoc/spec resolution; primary is 3GPP portal

### 3GPP dynareport (Spec Metadata)
- **Service:** 3GPP specification version listing
- **Base URL:** `https://www.3gpp.org/dynareport/{compact}.htm`
- **Client:** `src/tdoc_crawler/specs/sources/threegpp.py`
- **Auth:** None required
- **Role:** Primary source for spec metadata and version information

### 3GPP FTP (Spec Downloads)
- **Service:** 3GPP specification archive FTP server
- **Base URL:** `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}`
- **Template:** Defined in `src/tdoc_crawler/constants/urls.py` as `SPEC_URL_TEMPLATE`
- **Auth:** None (public FTP over HTTPS)
- **Role:** Download specification documents

### 3GPP Meetings Page
- **Service:** 3GPP meetings listing
- **Base URL:** `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm`
- **Template:** Defined in `src/tdoc_crawler/constants/urls.py` as `MEETINGS_BASE_URL`
- **Auth:** None required

### PDF Remote Converter (Optional Fallback)
- **Service:** Remote PDF conversion API
- **Base URL:** `https://pdf-convert.3gpp.org` (configurable via `PDF_REMOTE_API_BASE`)
- **Client:** `src/tdoc_crawler/extraction/conversion.py`
- **Auth:** API key via `PDF_REMOTE_API_KEY` env var
- **Role:** Fallback when LibreOffice is not available locally

### Hugging Face Hub (Optional)
- **Service:** Model hosting for AI/embedding features
- **Auth:** `HF_TOKEN` env var (optional, avoids rate limits)
- **Role:** Download AI models for opendataloader-pdf hybrid mode

## Data Storage

**Databases:**
- SQLite (via Oxyde ORM)
  - Connection: `CacheManager.db_file` → `~/.3gpp-crawler/3gpp_crawler.db`
  - ORM Client: `oxyde.AsyncDatabase` (`src/tdoc_crawler/database/base.py`)
  - Models: `src/tdoc_crawler/database/oxyde_models.py`
  - Tables: `tdocs`, `meetings`, `specs`, `spec_versions`, `spec_downloads`, `spec_source_records`, `working_groups`, `subworking_groups`, `crawl_log`
- SQLite (HTTP Cache)
  - Connection: `CacheManager.http_cache_file` → `~/.3gpp-crawler/http-cache.sqlite3`
  - Managed by: `hishel.SyncSqliteStorage`
  - Purpose: HTTP response caching with TTL and refresh-on-access

**File Storage:**
- Local filesystem via `CacheManager`
  - Cache root: `~/.3gpp-crawler/` (configurable via `TDC_CACHE_DIR`)
  - Checkout dir: `~/.3gpp-crawler/checkout/` (downloaded/converted documents)
  - Workspaces dir: `~/.3gpp-crawler/workspaces/` (AI workspace data)

**Caching:**
- HTTP response cache — hishel SQLite-backed (configurable TTL, default 7200s / 2 hours)
- File-based cache for downloaded documents (checkout directory)

## Authentication & Identity

**Auth Provider:**
- ETSI Online (EOL) — 3GPP portal authentication
  - Implementation: `PortalClient.authenticate()` in `src/tdoc_crawler/clients/portal.py`
  - Credentials model: `PortalCredentials` in `src/tdoc_crawler/models/base.py`
  - Resolution: `resolve_credentials()` in `src/tdoc_crawler/credentials.py`
  - Flow: Session-based (cookies), AJAX login API with JSON payload
  - Resolution order: CLI > config file > env vars > interactive prompt

## Monitoring & Observability

**Error Tracking:**
- None (external)

**Logs:**
- Rich-based console logging (`src/tdoc_crawler/logging/__init__.py`)
- `get_logger(__name__)` pattern throughout codebase
- `set_verbosity()` for runtime log level control
- Verbosity controlled via `TDC_VERBOSITY` or CLI `--verbose` flag

## CI/CD & Deployment

**Hosting:**
- Local CLI tool (no deployment target)
- Repository: `https://forge.etsi.org/rep/reimes/3gpp-crawler`

**CI Pipeline:**
- tox for multi-Python version testing (py39–py313)
- Codecov integration (`codecov.yaml`, 90% coverage target)
- pre-commit hooks (ruff check/format, undersort, standard checks)

## Environment Configuration

**Required env vars:**
- `TDC_EOL_USERNAME` — EOL portal username (for authenticated features)
- `TDC_EOL_PASSWORD` — EOL portal password (for authenticated features)

**Optional env vars:**
- `TDC_CACHE_DIR` — Cache directory override
- `TDC_DB_FILENAME` — SQLite database filename
- `TDC_TIMEOUT` — HTTP request timeout (default: 30)
- `TDC_MAX_RETRIES` — Retry count (default: 3)
- `TDC_VERIFY_SSL` — SSL verification toggle (default: true)
- `TDC_WORKERS` — Parallel worker count (default: 4)
- `HTTP_CACHE_ENABLED` — HTTP cache toggle (default: true)
- `HTTP_CACHE_TTL` — Cache TTL in seconds (default: 7200)
- `PDF_REMOTE_API_KEY` — Remote PDF converter API key
- `PDF_REMOTE_API_BASE` — Remote converter base URL
- `HF_TOKEN` — Hugging Face API token
- `LIBREOFFICE_PATH` — LibreOffice executable path override

**Secrets location:**
- `.env` file (gitignored, documented in `.env.example`)
- Config files support `${ENV_VAR}` interpolation (`src/tdoc_crawler/config/sources.py`)
- Interactive prompt fallback for EOL credentials

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## HTTP Infrastructure

**Session Factory:**
- `create_cached_session()` in `src/tdoc_crawler/http_client/session.py`
- Uses niquests (HTTP/2-capable, requests-compatible API)
- Hishel CacheAdapter bridges niquests↔hishel for HTTP caching
- `_NiquetsCacheAdapter` custom subclass handles type incompatibility
- Browser headers injected from `src/tdoc_crawler/constants/urls.py` to avoid 403 responses
- Decompression: gzip, deflate, brotli handled explicitly (`_decompress_body()`)
- Download helper: `download_to_file()` with streaming and empty-download detection
- Pool config: `PoolConfig` dataclass for connection pool tuning

---

*Integration audit: 2026-05-03*
