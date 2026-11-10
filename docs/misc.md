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

Credentials provide access to the **official 3GPP portal**, acting as a
reliable fallback for the primary community-maintained source
([WhatTheSpec](whatthespec.md)).

### Why credentials?

While `3gpp-crawler` primarily uses **WhatTheSpec** for its speed and lack
of required authentication, EOL credentials provide a 3GPP-official
fallback:

- **Redundancy**: functionality if the community source is unavailable.
- **Official verification**: metadata directly from 3GPP endpoints.
- **Reliability**: the tool remains functional if third-party services are down.

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
