# External Integrations

**Analysis Date:** 2026-04-30

## APIs & External Services

**3GPP Portal (portal.3gpp.org):**
- Authentication: EOL (Escape Online) credentials required
- Purpose: TDoc metadata extraction, unauthenticated document URL extraction
- Client: `PortalClient` in `src/tdoc_crawler/clients/portal.py`
- URLs:
  - Login: `https://portal.3gpp.org/login.aspx`
  - TDoc view: `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx`
  - TDoc download: `https://portal.3gpp.org/ngppapp/DownloadTDoc.aspx`
- Auth Pattern: HTTP POST with username/password, session cookie retention
- Session Management:
  - Cached session reused across requests
  - Cache disabled for login requests (explicit `http_cache_enabled=False`)
  - Browser user-agent required to avoid 403 Forbidden

**3GPP Public Website (3gpp.org):**
- Purpose: Meeting pages, spec FTP archive access, TDoc search
- URLs:
  - Meetings: `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm`
  - Spec archive: `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}`
- Auth: None (public, requires User-Agent header)
- Data formats: HTML (parsed via BeautifulSoup), Excel (document lists), PDF/Office documents

**Document List Service (3GPP Portal):**
- Purpose: Meeting TDoc metadata (title, status, contact, URL)
- Format: Excel (.xlsx) files
- Download via: HTTP GET to portal
- Parsing: `calamine` (Rust-backed Excel reader) → `TDocMetadata` models

**PDF Remote Conversion API (pdf-convert.3gpp.org):**
- Purpose: Fallback Office → PDF conversion (when local LibreOffice unavailable)
- Base URL: `https://pdf-convert.3gpp.org` (env: `PDF_REMOTE_API_BASE`)
- Auth: API key (env: `PDF_REMOTE_API_KEY`)
- Trigger: Automatic fallback when `ConverterBackend.AUTO` selected
- Formats supported: DOCX, PPTX, XLSX, DOC, PPT, XLS

## Data Storage

**Databases:**
- SQLite 3 (file-based: `~/.3gpp-crawler/3gpp_crawler.db`)
  - ORM: Oxyde (async)
  - Tables: TDocMetadata, MeetingMetadata, Specification, SpecificationVersion, SpecificationDownload, SpecificationSourceRecord, CrawlLogEntry, WorkingGroupRecord, SubWorkingGroupRecord
  - Schema auto-migrated via `extract_current_schema()` at startup

**HTTP Cache Database:**
- SQLite 3 (file-based: `~/.3gpp-crawler/http-cache.sqlite3`)
  - Backend: Hishel `SyncSqliteStorage`
  - Stores: Full HTTP responses (headers + body) keyed by request URL
  - Expiration: Honors Cache-Control, ETags, Last-Modified
  - Fallback: Returns stale cache on 5xx errors (conditional)

**File Storage (Checkout Directory):**
- Local filesystem: `~/.3gpp-crawler/checkout/`
  - TDoc files: `checkout/{meeting}_{tdoc_id}/`
  - Spec files: `checkout/Specs/{series}/{normalized}/`
  - Wiki extraction: `wiki/{workspace_id}/members/{member_id}/`

**Workspace Registry:**
- File-based JSON: `~/.3gpp-crawler/workspaces.json`
- Stores: Workspace metadata, extraction profiles, member specs
- Mutation: In-memory model serialized back to disk

## Authentication & Identity

**Auth Provider:**
- Custom (3GPP EOL credentials)
  - Pattern: HTTP Basic-like (username + password sent as POST form)
  - Storage: `PortalCredentials` model (username, password fields)
  - Initialization: `set_credentials(username, password)` called at CLI startup
  - Retrieval: `resolve_credentials()` from global registry
  - Validation: Attempted on first portal request; `PortalAuthenticationError` on failure

**Session Management:**
- Stateful session: `requests.Session` object with hishel `CacheAdapter`
- Cookie jar: Automatic per `requests` library
- Retry logic: `urllib3.Retry` with exponential backoff (5xx errors, timeouts)
- SSL verification: Configurable (default: system CA bundle)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/Rollbar integration)
- Errors logged via `logging` module (`get_logger(__name__)`)
- Crawl failures recorded in `CrawlLogEntry` table with exception text

**Logs:**
- File-based: `~/.3gpp-crawler/logs/` (optional, configured via settings)
- Console: Rich-formatted output (colors, tables, progress bars)
- Levels: DEBUG, INFO, WARNING, ERROR (controlled via `--verbosity` CLI flag)
- Structured logging via Pydantic validation errors and context-passing

## CI/CD & Deployment

**Hosting:**
- On-premises or Docker deployment (user-managed)
- CLI entry points:
  - `tdoc-crawler` — TDoc crawling and querying
  - `spec-crawler` — Specification crawling and querying
  - `3gpp-crawler` — Workspace management and configuration

**CI Pipeline:**
- GitHub Actions (optional, not checked in)
- Pre-commit hooks available (ruff, pytest, deptry)
- Tox integration for multi-Python testing

**Docker Support:**
- Not pre-configured; user builds own image from `Dockerfile`
- Key dependencies: Python 3.14, libssl-dev, libxml2-dev (for lxml)

## Environment Configuration

**Required env vars:**
- `TDC_EOL_USERNAME` — 3GPP portal username
- `TDC_EOL_PASSWORD` — 3GPP portal password

**Optional env vars:**
- `TDC_CACHE_DIR` — Cache directory (default: `~/.3gpp-crawler`)
- `TDC_HTTP_TIMEOUT` — Request timeout in seconds (default: 30)
- `TDC_HTTP_RETRIES` — Max retries on 5xx (default: 3)
- `TDC_OUTPUT` — Default output format: `table`, `json`, `ison`, `toon`, `yaml`
- `PDF_REMOTE_API_KEY` — Remote PDF converter API key
- `PDF_REMOTE_API_BASE` — Remote PDF converter base URL (default: `https://pdf-convert.3gpp.org`)
- `TDC_LOG_LEVEL` — Logging level (default: `INFO`)

**Secrets location:**
- `.env` file (auto-loaded by `python-dotenv`)
- Environment variables (direct export)
- `~/.3gpp-crawler/config.toml` (optional, includes credentials section)

## Webhooks & Callbacks

**Incoming:**
- None (CLI-only, no HTTP server)

**Outgoing:**
- None (no push notifications, webhooks, or async job submission)

## Data Sources & Crawling

**TDoc Sources:**
1. **Portal-based (authenticated):**
   - `PortalClient.fetch_tdoc_metadata()` — Crawl TDoc URLs from portal search
   - Returns: Full metadata (title, contact, status, file size, dates)
   - Frequency: Once per meeting per crawl session

2. **Document List (Excel):**
   - `fetch_meeting_tdocs_from_doclist()` — Excel document list parsing
   - Source: `{portal_base}/ngppapp/DownloadTDocFile.aspx?filename={meeting_doclist}.xlsx`
   - Returns: Flattened TDoc metadata from Excel rows
   - Faster than portal crawl, requires parsing

**Specification Sources:**
1. **Direct 3GPP FTP Download:**
   - Base URL: `https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/`
   - Pattern: Follows 3GPP FTP directory structure (TS/TR numbering)
   - Formats: PDF, Word, ZIP archives

2. **Meeting Document Sources (optional):**
   - Specs referenced in TDoc metadata
   - Cross-indexed via working group + release

**Meeting Sources:**
1. **3GPP Meetings Portal:**
   - URL: `https://www.3gpp.org/dynareport?code=Meetings-{code}.htm`
   - Format: HTML table (parsed via BeautifulSoup)
   - Fields: Meeting ID, date range, location, files URL
   - Frequency: Annually scanned (stable data)

## Performance Characteristics

**HTTP Caching:**
- Layer: Hishel `SyncSqliteStorage`
- Backend: SQLite3 with in-memory index
- Cache ratio: ~60-80% hit rate on re-crawls (depends on ETags)
- TTL: Per Cache-Control header (3GPP files: often indefinite/immutable)
- Warmup: First crawl populates cache; subsequent runs use cached responses

**Async Architecture:**
- Crawling: Async/await for concurrent network I/O (`asyncio`)
- Database: Async context manager (`AsyncDatabase.__aenter__/__aexit__`)
- Executor pools: `aiointerpreters` + `pool-executors` for CPU-bound work (PDF parsing)
- Concurrency: Up to 10 concurrent requests (configurable via `PoolConfig`)

**Document Processing Pipeline:**
- PDF extraction: OpenDataLoader (fast, hybrid LLM-based)
- Format conversion: LibreOffice UNO (5–15s per file) or remote API (2–5s)
- Caching: Converted PDFs cached in checkout directory (no re-conversion)
- Performance: ~2–5 documents/second (dependent on file size and LLM load)

## Failure Modes & Resilience

**Portal Authentication Failures:**
- Symptom: 401/403 on metadata fetch
- Recovery: Automatic retry with fresh session (up to 3 attempts)
- Fallback: Use document list (Excel) as alternative source

**Network Timeouts:**
- Default: 30 seconds per request
- Retry: Exponential backoff (1s, 2s, 4s)
- Fallback: Cached response (if available and not stale)
- User notice: Progress bar shows "⚠ timeout, retrying..."

**PDF Conversion Failures:**
- Local LibreOffice crashes: Fallback to remote API
- Remote API 500s: Manual intervention required (or skip document)
- Logging: Full exception stack in `~/.3gpp-crawler/logs/`

**Database Corruption:**
- Strategy: WAL mode (write-ahead logging) enabled by default
- Recovery: Manual backup + schema re-creation via `--clear-db` flag
- Prevention: No concurrent writers (single CLI process)

---

*Integration audit: 2026-04-30*
