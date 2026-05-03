# External Integrations

**Analysis Date:** 2026-05-03

## APIs & External Services

### 3GPP Portal (Authenticated)

**Service:** 3GPP EOL Portal — Protected portal for TDoc metadata, meeting documents, and specification details.

- **Base URL:** `https://portal.3gpp.org` (defined in `src/tdoc_crawler/constants/urls.py`)
- **Client:** `PortalClient` in `src/tdoc_crawler/clients/portal.py`
- **Auth:** ETSI Online (EOL) username/password
  - Env vars: `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`
  - Login endpoint: `POST https://portal.3gpp.org/ETSIPages/LoginEOL.ashx` (AJAX JSON)
  - Session established via cookie-based auth after initial `GET /login.aspx`
- **Key Endpoints:**
  - TDoc metadata view: `GET /ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={tdoc_id}`
  - TDoc download URL extraction: `GET /ngppapp/DownloadTDoc.aspx?contributionUid={tdoc_id}`
  - Meeting document list (Excel): `GET /ngppapp/GenerateDocumentList.aspx?meetingId={id}`
  - Specification details: `GET https://www.3gpp.org/dynareport/{compact}.htm` → redirect to portal
- **Credential resolution order:** CLI parameters → Config file → Env vars → Interactive prompt (`src/tdoc_crawler/credentials.py`)
- **Error handling:** `PortalAuthenticationError`, `PortalCredentialsError` (`src/tdoc_crawler/clients/portal.py`)

### 3GPP FTP Archive (Unauthenticated)

**Service:** 3GPP specification FTP archive — ZIP file downloads for specifications.

- **URL template:** `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}` (defined in `src/tdoc_crawler/constants/urls.py`)
- **Client:** `SpecDownloads` + `HTTPZipReader` in `src/tdoc_crawler/specs/downloads.py`
- **Auth:** None (public HTTPS)
- **Usage:** Spec zip files downloaded, extracted to local checkout directory
- **Format:** Filename pattern `{compact}-{vercode}.zip` (e.g., `26260-j10.zip` → version 19.1.0)

### 3GPP Meeting Listings (Unauthenticated)

**Service:** 3GPP meeting directory pages — Meeting metadata discovery.

- **URL template:** `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm` (defined in `src/tdoc_crawler/constants/urls.py`)
- **Client:** `MeetingCrawler` in `src/tdoc_crawler/meetings/operations/crawl.py`
- **Parser:** `parse_meeting_page` in `src/tdoc_crawler/parsers/meetings.py`
- **Auth:** None (public)

### WhatTheSpec Community API (Unauthenticated)

**Service:** WhatTheSpec — Community-maintained 3GPP TDoc metadata API.

- **URL template:** `https://whatthespec.net/3gpp/tdoc.php?name={tdoc}&api=1` (defined in `src/tdoc_crawler/tdocs/sources/whatthespec.py`)
- **Client:** `WhatTheSpecSource` / `resolve_via_whatthespec()` in `src/tdoc_crawler/tdocs/sources/whatthespec.py`
- **Auth:** None
- **Usage:** Primary or fallback source for single TDoc metadata lookup; returns JSON array
- **Error handling:** `WhatTheSpecResolutionError`
- **Caveat:** Does not support bulk meeting queries; single-TDoc lookup only

### Remote PDF Converter (Optional)

**Service:** Remote PDF conversion API for office documents.

- **Default endpoint:** `https://pdf-convert.3gpp.org` (configurable, in `src/tdoc_crawler/extraction/conversion.py`)
- **Auth:** API key via `PDF_REMOTE_API_KEY` env var
- **Backend:** `REMOTE` option in `ConverterBackend` enum; fallback when LibreOffice is unavailable
- **Config class:** `ConverterConfig` in `src/tdoc_crawler/extraction/conversion.py`

### Hugging Face Hub (Optional)

**Service:** Hugging Face model and dataset hosting.

- **Auth:** API token via `HF_TOKEN` env var (documented in `.env.example`)
- **Usage:** For AI model downloads (models for document extraction/AI assistance in advanced profiles)
- **Status:** Optional; not required for core crawling/querying functionality

## Data Storage

**Databases:**
- **SQLite** — Primary metadata store
  - Connection: `sqlite:///{cache_dir}/3gpp_crawler.db` via oxyde `AsyncDatabase`
  - Client: oxyde ORM (`src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/database/oxyde_models.py`)
  - Tables: `tdocs`, `meetings`, `specs`, `spec_source_records`, `spec_versions`, `spec_downloads`, `working_groups`, `subworking_groups`, `crawl_log`
  - Pydantic models via oxyde `Model` base class
  - Async context manager lifecycle (`async with DocDatabase(...)`)
  - Auto-migration for incremental schema changes (`src/tdoc_crawler/database/base.py:_run_migrations`)
  - Reference data auto-populated at startup (working groups, subworking groups)

**HTTP Cache:**
- **SQLite** (separate database) — HTTP response cache
  - Location: `{cache_dir}/http-cache.sqlite3`
  - Client: `hishel.SyncSqliteStorage` (`src/tdoc_crawler/http_client/session.py`)
  - Default TTL: 7200 seconds (2 hours)
  - Refresh-on-access enabled by default

**File Storage:**
- Local filesystem under `~/.3gpp-crawler/` (configurable via `TDC_CACHE_DIR`)
- `checkout/` — Downloaded and extracted documents
- `workspaces/` — Workspace source files and processed artifacts

**Caching:**
- Primarily: hishel HTTP cache (transparent, header-based cache keys)
- Secondary: Local file system (documents checked out once, re-used)

## Authentication & Identity

**Auth Provider:**
- **ETSI Online (EOL)** — Single login for 3GPP portal access
  - Implementation: `PortalClient.authenticate()` in `src/tdoc_crawler/clients/portal.py`
  - Flow: 2-step: GET login page (establish cookies) → POST AJAX login with JSON payload
  - Credential store: `CredentialsConfig` via pydantic-settings (`src/tdoc_crawler/config/settings.py`)
  - Interactive fallback: Typer prompt for missing credentials (`src/tdoc_crawler/credentials.py`)
- **No OAuth, JWT, or SSO** — Cookie-based session only

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)
- Errors logged locally via Python `logging` with custom formatters (`src/tdoc_crawler/logging/`)
- Crawl operations tracked in `crawl_log` database table with status, timestamps, and error counts

**Logs:**
- Python standard `logging` module with `get_logger()` helper from `src/tdoc_crawler/logging/`
- Verbosity levels: CLI `--verbose` / `--quiet` flags
- Hybrid server logs: `{logs_dir}/hybrid-server.log` for the opendataloader-pdf server

## CI/CD & Deployment

**Hosting:**
- CLI tool — distributed as Python wheel, no server hosting required
- Repository: `https://forge.3gpp.org/rep/reimes/3gpp-crawler`

**CI Pipeline:**
- Not detected (no `.github/workflows/`, `.gitlab-ci.yml`, or similar in repo)
- `tox.ini` defines env list but no CI config references it

**Pre-commit:**
- `.pre-commit-config.yaml` present with ruff, undersort, and standard file checks

## Environment Configuration

**Required env vars for full functionality:**
| Variable | Required For | Default |
|----------|-------------|---------|
| `TDC_EOL_USERNAME` | Authenticated portal access | — |
| `TDC_EOL_PASSWORD` | Authenticated portal access | — |
| `TDC_CACHE_DIR` | Cache directory path | `~/.3gpp-crawler` |
| `TDC_TIMEOUT` | HTTP timeout | `30` |
| `TDC_WORKERS` | Parallel workers | `4` |
| `LIBREOFFICE_PATH` | Office→PDF conversion | Auto-detected |
| `HF_TOKEN` | AI model downloads (advanced profile) | — |
| `PDF_REMOTE_API_KEY` | Remote PDF converter | — |

**Secrets location:** `.env` file (gitignored, template in `.env.example`)

## Webhooks & Callbacks

**Incoming:** None — CLI tool, no HTTP server.

**Outgoing:**
- 3GPP Portal AJAX endpoints (synchronous HTTP requests)
- 3GPP FTP for spec downloads (synchronous)
- WhatTheSpec API (synchronous HTTP GET)
- opendataloader-pdf hybrid server (local HTTP on `127.0.0.1:5002`)

---

*Integration audit: 2026-05-03*
