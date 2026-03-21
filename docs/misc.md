# Configuration & HTTP Caching

## HTTP Caching

To prevent rate-limiting and improve performance, `3gpp-crawler` caches all HTTP requests by default.

### Default Behavior

- **Cache Location**: `~/.3gpp-crawler/http-cache.sqlite3`
- **TTL**: 2 hours (7200 seconds).
- **Refresh**: TTL is extended whenever a cached item is accessed.

### Configuration

You can control caching via CLI or `.env`:

```bash
# Environment variables
HTTP_CACHE_TTL=7200
HTTP_CACHE_REFRESH_ON_ACCESS=true

# CLI Flags
--cache-ttl 3600
--no-cache-refresh
```

## ETSI Online (EOL) Credentials

Credentials provide access to the **official 3GPP portal**, acting as a reliable fallback for the primary community-maintained source.

### Why Credentials?

While `3gpp-crawler` primarily uses **WhatTheSpec** for its speed and lack of required authentication, EOL credentials provide a **3GPP-official fallback**:

- **Redundancy**: Ensures functionality if the primary community source is unavailable or encounters issues.
- **Official Verification**: Provides an alternative path to retrieve metadata directly from 3GPP endpoints.
- **Reliability**: Guarantees that the tool remains functional even if third-party indexing services are down.

### Resolution Order

The tool prefers unauthenticated community access first, falling back to 3GPP portal if credentials are provided:

1. CLI parameters (`--eol-username`, `--eol-password`).
1. Environment variables (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`).
1. Interactive prompt (if `TDC_EOL_PROMPT=true`).

## Directory Structure

By default, all data is stored in `~/.3gpp-crawler`:

- `tdoc_crawler.db`: Main metadata database.
- `http-cache.sqlite3`: HTTP request cache.
- `tdocs/`: Downloaded and extracted TDoc files.
- `checkout/`: Files specifically exported for user review.

You can override the root directory using the `--cache-dir` flag on most commands.
