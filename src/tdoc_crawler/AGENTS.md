# Assistant Rules for tdoc_crawler Package

Core library for crawling and querying 3GPP TDoc data.

---

## Import Patterns

**Correct imports:**

```python
# TDoc operations (use explicit submodule imports)
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.tdocs.models import TDocMetadata, TDocQueryConfig

# Meeting operations
from tdoc_crawler.meeting_crawler import MeetingCrawler
from tdoc_crawler.meetings.models import MeetingMetadata

# Spec operations
from tdoc_crawler.database import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_spec

# Database operations
from tdoc_crawler.database import TDocDatabase, MeetingDatabase
from tdoc_crawler.models import WorkingGroup, PortalCredentials
```

**Note:** Domain packages (`tdocs/`, `meetings/`) do not re-export operations to avoid circular imports. Use explicit submodule imports.

---

## HTTP Caching (MANDATORY)

For core crawler source traffic (3gpp.org, whatthespec.net, portal), all HTTP requests **MUST** use `create_cached_session()` from `tdoc_crawler.http_client`:

```python
from tdoc_crawler.http_client import create_cached_session

with create_cached_session() as session:
    # All HTTP calls use hishel caching
    response = session.get(url)
```

Benefits:
- 50-90% faster incremental crawls
- Prevents rate-limiting from 3GPP servers
- AI model-provider traffic is exempt

---

## Anti-Duplication (DRY)

**CRITICAL:** Code duplication drove major domain-oriented refactoring. Future assistants MUST NOT introduce duplicated logic.

**Search Before Implementing:**

1. Use grep/glob to check if similar implementation exists
2. Check relevant domain package (`tdocs/`, `meetings/`, `specs/`)
3. If logic exists but needs modification, REFACTOR rather than creating second version

**Logic Placement Rules:**

| Logic Type | Location |
|------------|----------|
| Domain logic | `src/tdoc_crawler/<domain>/` |
| Parsing logic | `src/tdoc_crawler/parsers/` |
| API clients | `src/tdoc_crawler/clients/` |
| Shared utilities | `src/tdoc_crawler/utils/` (only if truly generic) |

**Prohibited Patterns:**

- **CLI Duplication:** Do not copy domain logic into CLI. CLI handles I/O only
- **Test Duplication:** Do not copy library code into tests. Use proper mocking
- **Helper Bloat:** Do not create `utils.py` files that duplicate `src/tdoc_crawler/utils/`

---

## TDoc Data Sources

The package uses **three distinct mechanisms** for fetching TDoc metadata. Do NOT add new crawl mechanisms without understanding why these three exist.

| Source | Module | Auth | Batch | Single | Use Case |
|--------|--------|:----:|:-----:|:------:|----------|
| Excel DocList | `tdocs/sources/doclist.py` | No | ✓ | ✗ | Batch crawl all TDocs per meeting (`crawl-tdocs`) |
| WhatTheSpec API | `tdocs/sources/whatthespec.py` | No | ✗ | ✓ | Single/few TDoc lookups (`query`, `open`) |
| 3GPP Portal | `tdocs/sources/portal.py` | Yes (EOL) | ✗ | ✓ | Authenticated fallback when WhatTheSpec unavailable |

**Excel DocList (batch):** Primary for `crawl-tdocs` — downloads per-meeting Excel from 3GPP FTP. Cannot resolve single TDoc without meeting.

**WhatTheSpec API (single):** Community API at `whatthespec.net` — preferred for `query` and `open` commands. No auth required.

**3GPP Portal (fallback):** Official authenticated source via EOL portal. Use only as fallback or when explicitly requested.

---

## Database Schema

SQLite database with Pydantic models. Key tables managed via `pydantic-sqlite`:

| Table | Purpose |
|-------|---------|
| `tdocs` | TDoc metadata |
| `meetings` | Meeting records (working group, dates) |
| `working_groups` | Reference data (TBID → WG mapping) |
| `subworking_groups` | Reference data (SubTB → subgroup mapping) |
| `crawl_log` | Crawl history and audit |
| `specs` | Technical specification catalog |
| `spec_versions` | Spec version tracking |
| `spec_downloads` | Download cache |

**Key Patterns:**
- Return Pydantic models, not raw tuples
- Handle case-insensitive TDoc IDs via `.upper()` normalization
- Working group derived from meeting via JOIN (not stored column)

See `src/tdoc_crawler/models/` for current schema definition.

---

## Submodules

This package has submodule-specific AGENTS.md files:

| Location | Purpose |
|----------|---------|
| `src/tdoc_crawler/cli/AGENTS.md` | CLI patterns and constraints |

---

## Circular Import Prevention

**Rule:** If you encounter a circular import, refactor the code to eliminate it. Never use `TYPE_CHECKING` guards or lazy imports as a permanent solution.

**Strategy:**

1. Identify the circular dependency
2. Extract shared types to `models/` layer
3. Both modules import from the neutral models layer
4. Use lazy imports (inside functions) only for temporary fixes during refactoring

---

## Libraries

Primary dependencies for this package:

| Library | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `rich` | Console formatting |
| `pydantic` | Data models |
| `pydantic-sqlite` | Database layer |
| `hishel` | HTTP caching |
| `httpx` | HTTP client |

---

## Testing

See `tests/AGENTS.md` for detailed test patterns and fixtures.

- Use `pytest` with fixtures and parameterized tests
- Use mocking to isolate external systems
- Test locations: `./tests/test-cache/`, `./tests/test-cache/tdoc_crawler.db`
- Aim for 70%+ coverage