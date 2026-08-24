# tdoc_crawler — Core Library

Domain-oriented architecture for crawling and querying 3GPP TDoc, Spec, and Meeting data.

## Import Patterns

```python
# TDoc operations (explicit submodule imports)
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.tdocs.models import TDocMetadata

# Meeting operations
from tdoc_crawler.meetings.operations import MeetingCrawler

# Spec operations
from tdoc_crawler.database import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_spec
```

**Note:** Domain packages do not re-export operations to avoid circular imports.

## HTTP Caching (MANDATORY)

All HTTP requests **MUST** use `create_cached_session()`:

```python
from tdoc_crawler.http_client import create_cached_session

with create_cached_session() as session:
    response = session.get(url)
```

## HTTP/3 MustDowngradeError (CRITICAL)

`www.3gpp.org` and `portal.3gpp.org` advertise HTTP/3 via `Alt-Svc` header but cannot handle it. This triggers `MustDowngradeError` from `urllib3-future` (bundled with niquests), wasting ~10 seconds per request in retries.

**Two fixes required:**

### 1. `niquests.Session(disable_http3=True)` — for raw sessions

Applies to ALL naked `Session()` calls outside `create_cached_session()`:

```python
# CORRECT
session = requests.Session(disable_http3=True)
with requests.Session(disable_http3=True) as session:
    ...

# WRONG — will crash with MustDowngradeError
session = requests.Session()
```

| Location | Fixed? |
|----------|--------|
| `meetings/sources/portal.py` | ✅ |
| `tdocs/operations/checkout.py` (3 locations) | ✅ |

### 2. `_NiquetsCacheAdapter.init_poolmanager()` — for hishel cached sessions

`create_cached_session()` mounts a `_NiquetsCacheAdapter` (hishel `CacheAdapter` subclass). On cache misses, hishel delegates to `requests.adapters.HTTPAdapter.send()` → `urllib3` transport. Since niquests installs `urllib3-future` (which supports HTTP/3), the `disable_http3=True` on the `Session` has **no effect** — the hishel adapter creates its own connection pool.

The fix: `_NiquetsCacheAdapter.init_poolmanager()` injects `disabled_svn={HttpVersion.h3}` into the pool manager kwargs, disabling HTTP/3 at the `urllib3-future` connection level.

**Enforcement:** If you ever create a raw `niquests.Session()` or `requests.Session()` (aliased from niquests), add `disable_http3=True` without exception. If you create a custom adapter mounted on a cached session, ensure `init_poolmanager` disables HTTP/3.

## Multiprocessing Spawn Deadlock Under MCP (CRITICAL)

The stdio MCP server (`mcp_server.py`) runs with stdin/stdout in overlapped
(async I/O) mode on Windows. `ProcessPoolExecutor` spawn children inherit
those handles and deadlock on synchronous I/O — symptoms: crawl hangs forever,
no errors. `TDocCrawlConfig.executor` lets callers pick in-process parallelism
(`"threading"`, or `"subinterpreter"` on Python 3.14+); the MCP wrapper picks
it automatically. Never use multiprocessing executors from MCP tool code.

## Anti-Duplication (DRY)

Search before implementing. Check relevant domain package (`tdocs/`, `meetings/`, `specs/`). Refactor rather than duplicate.

**Logic Placement:**

| Logic Type | Location |
|------------|----------|
| Domain logic | `<domain>/` |
| Parsing logic | `parsers/` |
| API clients | `clients/` |
| Shared utilities | `utils/` |

## TDoc Data Sources

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single lookups |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes | ✗ | ✓ | Authenticated fallback |

## Database

SQLite via `pydantic-sqlite`. Return Pydantic models. TDoc IDs use `.upper()` for case-insensitive comparison.

## Circular Import Prevention

Refactor to eliminate circular dependencies. Extract shared types to `models/` layer — both modules import from neutral `models/`.

Known hard cycle: `tdocs/operations/checkout.py` ← `extraction/fetch_tdoc.py` (extraction imports checkout's `checkout_tdoc`). Therefore `checkout.py` must never import from `extraction` at module level — that is why `_TDOC_DOCUMENT_SUFFIXES` is defined locally instead of reusing `OFFICE_FORMATS`. The former `cli/mcp_app.py` cycle was resolved structurally: the `tdoc checkout` command lives in `cli/checkout.py` (not `tdoc_app`) so `mcp_server` never imports `tdoc_app`. Inline imports are forbidden (csort hoists them) — resolve cycles by moving code, not by deferring imports.

## TDoc Checkout Layout

`tdoc open` (`prepare_tdoc_file`) and `tdoc checkout` (`checkout_tdocs` in `cli/checkout.py`) MUST share one business-logic path: both compute the on-disk location via `get_checkout_path()` (mirrors the 3GPP server URL: `checkout_dir/<tsg>/<wg>/<meeting>/Docs/<tdoc_id>`). Never introduce a parallel layout.

The "main file" inside an extracted zip is picked by `_select_main_file()` using positive suffix classification (`_TDOC_DOCUMENT_SUFFIXES`): TDoc-ID-prefixed document > largest document > largest non-clutter file. OS/archive clutter is filtered by gitignore-style patterns from `utils/clutter.py`: defaults ship as packaged data (`utils/clutter-ignore`), copied to `<cache-dir>/clutter-ignore` for user editing (`!` negation re-includes; deleting the file restores defaults). The filter runs at BOTH the extraction boundary (`safe_extract_zip`) — because sidecars inherit the original's suffix, so suffix-based consumers like `--pdf` conversion cannot distinguish them — and in `_select_main_file` (covers pre-existing checkout dirs with legacy clutter on disk).

## Testing

See `tests/AGENTS.md`.
