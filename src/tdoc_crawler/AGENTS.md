# tdoc_crawler

Core library for crawling and querying 3GPP TDoc data.

## Import Patterns

**Correct imports:**

```python
# TDoc operations (explicit submodule imports)
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.tdocs.models import TDocMetadata

# Meeting operations
from tdoc_crawler.meeting_crawler import MeetingCrawler

# Spec operations
from tdoc_crawler.database import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_spec
```

**Note:** Domain packages do not re-export operations to avoid circular imports.

## HTTP Caching (MANDATORY)

For 3gpp.org, whatthespec.net, portal traffic, all HTTP requests **MUST** use `create_cached_session()`:

```python
from tdoc_crawler.http_client import create_cached_session

with create_cached_session() as session:
    response = session.get(url)
```

Benefits: 50-90% faster incremental crawls, prevents rate-limiting.

## Anti-Duplication (DRY)

**CRITICAL:** Search before implementing:

1. Use grep/glob to check for existing implementations
1. Check relevant domain package (`tdocs/`, `meetings/`, `specs/`)
1. REFACTOR rather than duplicate

**Logic Placement:**

| Logic Type | Location |
|------------|----------|
| Domain logic | `src/tdoc_crawler/<domain>/` |
| Parsing logic | `src/tdoc_crawler/parsers/` |
| API clients | `src/tdoc_crawler/clients/` |
| Shared utilities | `src/tdoc_crawler/utils/` |

**Prohibited:** CLI duplication, test duplication, helper bloat.

## TDoc Data Sources

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl (`crawl-tdocs`) |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single lookups (`query`, `open`) |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes | ✗ | ✓ | Authenticated fallback |

## Database Schema

SQLite with Pydantic models via `pydantic-sqlite`:

| Table | Purpose |
|-------|---------|
| `tdocs`, `meetings`, `specs` | Core data |
| `working_groups`, `subworking_groups` | Reference data |
| `crawl_log`, `spec_downloads` | Audit/cache |

**Patterns:** Return Pydantic models, case-insensitive TDoc IDs via `.upper()`.

## Circular Import Prevention

**Rule:** Refactor to eliminate, never use `TYPE_CHECKING` as permanent solution.

**Strategy:**

1. Identify circular dependency
1. Extract shared types to `models/` layer
1. Both modules import from neutral `models/`

## Libraries

| Library | Purpose |
|---------|---------|
| `typer`, `rich` | CLI, console |
| `pydantic`, `pydantic-sqlite` | Models, database |
| `hishel`, `httpx` | HTTP caching |

## Testing

See `tests/AGENTS.md`. Test DB: `./tests/test-cache/tdoc_crawler.db`
