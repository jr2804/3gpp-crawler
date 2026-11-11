# Configuration & HTTP Caching

## HTTP Caching

To prevent rate-limiting and improve performance, `3gpp-crawler` caches all
HTTP requests by default.

### Default Behavior

- **Cache location**: `~/.3gpp-crawler/http-cache-v2.sqlite3`
- **TTL**: 2 hours (7200 seconds).
- **Refresh**: TTL is extended whenever a cached item is accessed.

### Configuration

Via `.env` or config file (see [Configuration](config.md)):

```bash
HTTP_CACHE_TTL=7200
```

## ETSI Online (EOL) Credentials

Credentials provide access to the **authenticated 3GPP portal** endpoints.
They are optional: single/missing TDocs are fetched from the official
(unauthenticated) portal by default, with [WhatTheSpec](whatthespec.md) used
only as a third-party fallback when credentials are unavailable.

### Why credentials?

- **Official data**: metadata directly from 3GPP endpoints — no third-party
  service that can change or disappear.
- **Full metadata**: `--full-metadata` fetching requires authentication.
- **Reliability**: keeps working even if WhatTheSpec is down or its API
  changes.

### Resolution order

1. CLI parameters (`--eol-username`, `--eol-password`).
1. Environment variables (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`).
1. Interactive prompt (if `TDC_EOL_PROMPT=true`).

## Directory Structure

By default, all data is stored in `~/.3gpp-crawler`:

| Path | Purpose |
|------|---------|
| `3gpp_crawler.db` | Main metadata database. |
| `http-cache-v2.sqlite3` | HTTP request cache (hishel 2 schema; older `http-cache.sqlite3` files are not reused). |
| `tdocs/` | Downloaded and extracted TDoc files. |
| `checkout/` | Files exported for offline review. |

Override the root directory with the `--cache-dir` flag on most commands
or via `TDC_CACHE_DIR`.
