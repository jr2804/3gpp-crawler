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

When creating a **raw** `requests.Session()` or `niquests.Session()` (not via `create_cached_session`), **ALWAYS** pass `disable_http3=True`:

```python
# CORRECT — disables HTTP/3 to avoid MustDowngradeError from 3GPP servers
session = requests.Session(disable_http3=True)
# or
with requests.Session(disable_http3=True) as session:
    ...

# WRONG — will crash with MustDowngradeError on 3GPP portal
session = requests.Session()  # NEVER this
```

**Why:** `portal.3gpp.org` and `www.3gpp.org` advertise HTTP/3 via Alt-Svc header but cannot actually handle it. niquests tries to upgrade, fails with `MustDowngradeError`, and wastes up to 10 seconds retrying per request.

**Scope:** Applies to ALL naked `Session()` calls outside `create_cached_session()`:

| Location | File | Fixed? |
|----------|------|--------|
| `meetings/sources/portal.py` | `niquests.Session(...)` | ✅ |
| `http_client/session.py` | `requests.Session(...)` (via `create_cached_session`) | ✅ |
| `tdocs/operations/checkout.py` | `requests.Session(...)` (3 locations) | ✅ |

**Enforcement:** If you ever create a raw `niquests.Session()` or `requests.Session()` (aliased from niquests), add `disable_http3=True` without exception. The `create_cached_session()` factory already handles this correctly.

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

## Testing

See `tests/AGENTS.md`.
