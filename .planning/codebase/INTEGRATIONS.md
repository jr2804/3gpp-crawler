# External Integrations

**Analysis Date:** 2026-05-22

## APIs & External Services

**3GPP Portal (ETSI Online):**
- Portal REST API — Meeting metadata, TDoc metadata, document downloads
  - Base URL: `https://portal.3gpp.org`
  - REST endpoint: `/webservices/Rest/Meetings.svc/GetMeetings` (`src/tdoc_crawler/constants/urls.py`)
  - DocList: `/ngppapp/GenerateDocumentList.aspx?meetingId={id}` — batch TDoc metadata
  - TDoc view: `/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={id}` — single TDoc metadata
  - TDoc download: `/ngppapp/DownloadTDoc.aspx?contributionUid={id}` — URL extraction
  - Login: `/login.aspx` + AJAX `/ETSIPages/LoginEOL.ashx` — EOL authentication
  - SDK/Client: `niquests` (via `PortalClient` in `src/tdoc_crawler/clients/portal.py`)
  - Auth: `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD` env vars
  - HTTP/3 issue: Portal advertises HTTP/3 via `Alt-Svc` but cannot handle it; all sessions must use `disable_http3=True`
  - Browser headers required (defined in `src/tdoc_crawler/constants/urls.py` as `BROWSER_HEADERS`)

**WhatTheSpec (Community API):**
- External metadata lookup for TDocs and Specs
  - Base URL: `https://whatthespec.net`
  - TDoc lookup: `/3gpp/tdoc.php?name={tdoc_id}&api=1`
  - Spec lookup: `/3gpp/spec.php?q={compact}&api=1`
  - SDK/Client: `niquests` (via `create_cached_session()`)
  - Auth: None (public API)
  - Implementation: `src/tdoc_crawler/tdocs/sources/whatthespec.py`, `src/tdoc_crawler/specs/sources/whatthespec.py`

**3GPP FTP Server:**
- Spec archive downloads
  - URL template: `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}`
  - Dynareport: `https://www.3gpp.org/dynareport/{compact}.htm` — spec version metadata
  - SDK/Client: `niquests` (via `create_cached_session()`)
  - Auth: None (public FTP/HTTPS)
  - Implementation: `src/tdoc_crawler/specs/sources/threegpp.py`

**Hugging Face Hub:**
- Model downloads for Docling ML pipeline
  - SDK/Client: Docling internal (uses `HF_TOKEN` if set)
  - Auth: `HF_TOKEN` env var (optional, avoids rate limits)
  - Used by: `src/tdoc_crawler/extraction/docling/` pipeline

## Data Storage

**Databases:**
- SQLite — Primary metadata store
  - Location: `{cache_dir}/3gpp_crawler.db` (default `~/.3gpp-crawler/`)
  - ORM: oxyde (`src/tdoc_crawler/database/base.py`)
  - Models: `src/tdoc_crawler/database/oxyde_models.py`
  - Tables: `WorkingGroupRecord`, `SubWorkingGroupRecord`, `CrawlLogEntry`, `TDocMetadata`, `MeetingMetadata`, `Specification`, `SpecificationVersion`, `SpecificationDownload`, `SpecificationSourceRecord`

- SQLite — HTTP response cache
  - Location: `{cache_dir}/http-cache.sqlite3`
  - Managed by: hishel `SyncSqliteStorage`
  - Config: TTL 7200s (2 hours) default, configurable via `HTTP_CACHE_TTL`

**File Storage:**
- Local filesystem only
  - Cache dir: `~/.3gpp-crawler/` (configurable via `TDC_CACHE_DIR`)
  - Checkout dir: `{cache_dir}/checkout/` — downloaded spec files
  - Workspaces dir: `{cache_dir}/workspaces/` — extraction workspaces
  - Path management: `CacheManager` singleton (`src/tdoc_crawler/config/cache_manager.py`)

**Caching:**
- hishel HTTP cache (SQLite-backed) — `src/tdoc_crawler/http_client/session.py`
- All HTTP requests MUST use `create_cached_session()` from `src/tdoc_crawler/http_client/`

## Authentication & Identity

**Auth Provider:**
- ETSI Online (EOL) — Custom form-based authentication
  - Implementation: `src/tdoc_crawler/clients/portal.py` → `PortalClient.authenticate()`
  - Login flow: Visit login page → POST AJAX endpoint with JSON credentials → Session cookies
  - Credentials: `src/tdoc_crawler/credentials.py` → `resolve_credentials()`
  - Interactive prompting: Supported via `TDC_EOL_PROMPT` or `--prompt-credentials` CLI flag
  - Non-cached session used for authentication to avoid hishel cache interfering with cookies

## Monitoring & Observability

**Error Tracking:**
- None (local CLI tool)

**Logs:**
- Python `logging` module with `rich.logging.RichHandler`
  - Factory: `src/tdoc_crawler/logging/__init__.py` → `get_logger()`
  - Console output with timestamps, tracebacks, markup support
  - Verbosity: Controlled via `TDC_VERBOSITY` or `--verbose`/`--quiet` CLI flags
  - Default level: `logging.WARNING`

## CI/CD & Deployment

**Hosting:**
- Local CLI tool (no server deployment)
- Repository: `https://forge.3gpp.org/rep/reimes/3gpp-crawler`

**CI Pipeline:**
- tox + tox-uv — Multi-Python test matrix
- Coverage target: 90% (configured in `codecov.yaml`)
- Pre-commit hooks: ruff check + format, undersort, standard checks (`.pre-commit-config.yaml`)

## Environment Configuration

**Required env vars:**
- `TDC_EOL_USERNAME` — EOL portal username (for authenticated access)
- `TDC_EOL_PASSWORD` — EOL portal password (for authenticated access)

**Optional env vars:**
- `TDC_CACHE_DIR` — Override default cache directory
- `TDC_TIMEOUT` — HTTP request timeout (default: 30s)
- `TDC_MAX_RETRIES` — Retry attempts (default: 3)
- `TDC_VERIFY_SSL` — SSL verification (default: true)
- `HTTP_CACHE_ENABLED` — Enable HTTP caching (default: true)
- `HTTP_CACHE_TTL` — Cache TTL in seconds (default: 7200)
- `TDC_WORKERS` — Parallel worker count (default: 4)
- `TDC_WORKING_GROUP` — Default WG filter (e.g., `SA4`)
- `TDC_START_DATE` / `TDC_END_DATE` — Date range filters
- `TDC_LIMIT_TDOCS` — Max TDocs per run (default: 1000)
- `TDC_PROFILE` — Extraction profile (pdf-only, markdown-only, default, advanced)
- `TDC_DEVICE` — Accelerator device (auto, cpu, cuda, mps)
- `HF_TOKEN` — Hugging Face API token (for Docling model downloads)
- `LIBREOFFICE_PATH` — Override LibreOffice executable path (for convert-lo)

**Secrets location:**
- `.env` file at project root (gitignored, documented in `.env.example`)
- Or environment variables
- Or TOML config files with `${ENV_VAR}` interpolation support

## Webhooks & Callbacks

**Incoming:**
- None (CLI tool, no server component)

**Outgoing:**
- None (fetch-only architecture)

## External Tool Dependencies

**LibreOffice:**
- Used by: `packages/convert-lo/` for headless document conversion
- Required for: DOC, DOCX, ODT, RTF, PPT, PPTX → PDF conversion
- Auto-detection: Searches standard install paths, overridable via `LIBREOFFICE_PATH`
- Thread safety: Sequential only (LibreOffice is not thread-safe)
- Timeout: 300 seconds per file default

---

*Integration audit: 2026-05-22*
