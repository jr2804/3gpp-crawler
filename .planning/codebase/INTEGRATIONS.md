# External Integrations

**Analysis Date:** 2026-04-27

## APIs & External Services

**3GPP public endpoints:**

- 3GPP meetings/spec pages (`www.3gpp.org`) - Meeting/spec metadata lookups
 	- SDK/Client: `niquests` sessions created by `create_cached_session()` in `src/tdoc_crawler/http_client/session.py`
 	- Auth: None
- 3GPP FTP spec archive (`https://www.3gpp.org/ftp/Specs/archive/...`) - Spec file downloads
 	- SDK/Client: URL templates in `src/tdoc_crawler/constants/urls.py`, downloads through `src/tdoc_crawler/specs/downloads.py`
 	- Auth: None

**3GPP portal endpoints:**

- Portal login and TDoc endpoints (`portal.3gpp.org`) - Authenticated fallback for TDoc metadata
 	- SDK/Client: `PortalClient` in `src/tdoc_crawler/clients/portal.py`
 	- Auth: `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD` (mapped in `src/tdoc_crawler/config/env_vars.py`)
- Meeting document list endpoint (`GenerateDocumentList.aspx`) - Unauthenticated Excel document list fetch
 	- SDK/Client: `src/tdoc_crawler/tdocs/sources/doclist.py`
 	- Auth: None

**Community metadata API:**

- WhatTheSpec (`whatthespec.net`) - Preferred unauthenticated TDoc/spec metadata source and fallback path
 	- SDK/Client: `src/tdoc_crawler/tdocs/sources/whatthespec.py`, `src/tdoc_crawler/specs/sources/whatthespec.py`
 	- Auth: None

**AI and conversion services:**

- LLM providers through LiteLLM - Summarization/figure description/completions
 	- SDK/Client: `litellm` via `packages/3gpp-ai/threegpp_ai/operations/llm_client.py`
 	- Auth: `TDC_AI_LLM_API_KEY` or provider-specific API key env vars
- Remote Office-to-PDF conversion service (`pdf-convert.3gpp.org`) - Fallback when local LibreOffice conversion fails
 	- SDK/Client: `packages/3gpp-ai/threegpp_ai/operations/conversion.py`
 	- Auth: `PDF_REMOTE_API_KEY` (Bearer token, optional)

## Data Storage

**Databases:**

- SQLite (primary metadata store)
 	- Connection: local file path via `PathConfig.db_file` in `src/tdoc_crawler/config/settings.py`
 	- Client: Oxyde `AsyncDatabase` in `src/tdoc_crawler/database/base.py` with `sqlite:///...` URL
- SQLite (HTTP cache store)
 	- Connection: local cache DB path via `PathConfig.http_cache_file`
 	- Client: `hishel.SyncSqliteStorage` in `src/tdoc_crawler/http_client/session.py`

**File Storage:**

- Local filesystem only (cache, checkout, AI workspace folders) managed by `PathConfig` and `CacheManager` in `src/tdoc_crawler/config/settings.py` and `src/tdoc_crawler/config/cache_manager.py`

**Caching:**

- HTTP response caching via `hishel` + SQLite in `src/tdoc_crawler/http_client/session.py`

## Authentication & Identity

**Auth Provider:**

- Custom credential-based portal auth for 3GPP EOL portal
 	- Implementation: username/password in `CredentialsConfig` (`src/tdoc_crawler/config/settings.py`) consumed by `PortalClient` (`src/tdoc_crawler/clients/portal.py`)

## Monitoring & Observability

**Error Tracking:**

- None detected (no external Sentry/New Relic/etc. integration)

**Logs:**

- Python logging with centralized helpers (`tdoc_crawler.logging.get_logger`) used across `src/tdoc_crawler/` and `packages/3gpp-ai/threegpp_ai/`

## CI/CD & Deployment

**Hosting:**

- Not detected (repository is CLI/package oriented)

**CI Pipeline:**

- No `.github/workflows/` directory detected
- Local/portable test orchestration via `tox.ini` (`tox` + `tox-uv`)

## Environment Configuration

**Required env vars:**

- Base crawler/runtime: `TDC_CACHE_DIR`, `HTTP_CACHE_TTL`, `TDC_TIMEOUT`, `TDC_MAX_RETRIES`
- Portal auth fallback: `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`
- AI pipeline: `TDC_AI_LLM_MODEL`, `TDC_AI_LLM_API_KEY`, `TDC_AI_LLM_API_BASE`, `TDC_AI_PARALLELISM`
- Optional remote conversion: `PDF_REMOTE_API_KEY`, `PDF_REMOTE_API_BASE`

**Secrets location:**

- Environment variables (primary)
- Optional local config files loaded by settings discovery (`src/tdoc_crawler/config/sources.py`); secrets should remain environment-backed

## Webhooks & Callbacks

**Incoming:**

- None

**Outgoing:**

- None

---

*Integration audit: 2026-04-27*
