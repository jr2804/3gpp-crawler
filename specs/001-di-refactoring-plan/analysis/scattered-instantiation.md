# Scattered Instantiation Findings

## Overview

This document analyzes how core dependencies are instantiated throughout the tdoc-crawler codebase. The analysis reveals **widespread scattered instantiation** with no centralized dependency management.

## Key Findings

### 1. CacheManager Instantiation

**Pattern:** Direct instantiation at point-of-use across multiple layers.

**Locations:**

```python
# CLI layer (src/tdoc_crawler/cli/app.py:75)
manager = CacheManager(cache_dir).register()

# HTTP client (src/tdoc_crawler/http_client.py:111)
manager = resolve_cache_manager(cache_manager_name)

# AI config (src/tdoc_crawler/ai/config.py:152)
self.ai_cache_dir = resolve_cache_manager(self.cache_manager_name).ai_embed_dir(self.embedding_model)

# WhatTheSpec source (src/tdoc_crawler/tdocs/sources/whatthespec.py:79)
manager = resolve_cache_manager(cache_manager_name)
with MeetingDatabase(manager.db_file) as db:
    meeting_id = db.resolve_meeting_id(meeting_name) or 0
```

**Problems:**

- No single source of truth for cache configuration
- Each module decides when/how to create CacheManager
- Testing requires mocking multiple instantiation points
- Global registry (`_cache_managers`) acts as hidden singleton

### 2. Database Instantiation

**Pattern:** Direct instantiation with file paths, no abstraction.

**Locations:**

```python
# CLI (src/tdoc_crawler/cli/app.py:80)
with TDocDatabase(manager.db_file) as database:
    results = database.query_tdocs(config)

# WhatTheSpec (src/tdoc_crawler/tdocs/sources/whatthespec.py:80)
with MeetingDatabase(manager.db_file) as db:
    meeting_id = db.resolve_meeting_id(meeting_name)

# Workspace operations (src/tdoc_crawler/ai/operations/workspaces.py:462)
with SpecDatabase(db_path) as db:
    checkout_paths = checkout_specs(...)

# Tests (tests/conftest.py:175)
with TDocDatabase(test_db_path) as db:
    _ = db.upsert_tdoc(tdoc)
```

**Problems:**

- Every caller must know database file location
- No connection pooling or lifecycle management
- Context manager pattern repeated everywhere
- Hard to substitute mock databases in tests

### 3. HTTP Session Instantiation

**Pattern:** Factory function called at point-of-use.

**Locations:**

```python
# CLI (src/tdoc_crawler/cli/app.py:79)
with create_cached_session() as session:
    # ... use session

# WhatTheSpec (src/tdoc_crawler/tdocs/sources/whatthespec.py:52)
temp_session = create_cached_session(cache_manager_name=cache_manager_name, http_cache=http_cache)

# Download helper (src/tdoc_crawler/http_client.py:55)
temp_session = create_cached_session(http_cache=http_cache, cache_manager_name=cache_manager_name)
```

**Problems:**

- Session lifecycle managed manually in each caller
- Caching configuration passed redundantly
- No session reuse across operations
- Tests must mock `create_cached_session` in multiple locations

### 4. Configuration Loading

**Pattern:** Environment variable parsing duplicated across modules.

**Locations:**

```python
# AI config (src/tdoc_crawler/ai/config.py:103-144)
@classmethod
def from_env(cls, **overrides: str | int | Path | None) -> AiConfig:
    data: dict[str, str | int | Path | None] = {}
    
    if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
        data["embedding_model"] = embedding_model
    # ... 20+ lines of environment parsing

# HTTP cache config (src/tdoc_crawler/models/crawl_limits.py:98-107)
@classmethod
def resolve_http_cache_config(cls) -> HttpCacheConfig:
    ttl = os.getenv("HTTP_CACHE_TTL")
    refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS")
    # ... manual parsing
```

**Problems:**

- Each config class implements its own environment parsing
- No unified configuration loading strategy
- Type conversion logic duplicated
- Default values scattered across multiple locations

## Impact Analysis

### Testability Impact: **HIGH**

To test a single CLI command, mocks must be set up at multiple levels:

```python
# Typical test setup requires:
@patch("tdoc_crawler.cli.app.CacheManager")
@patch("tdoc_crawler.cli.app.TDocDatabase")
@patch("tdoc_crawler.cli.app.create_cached_session")
@patch("tdoc_crawler.http_client.resolve_cache_manager")
def test_something(...):
    pass
```

### Maintainability Impact: **MEDIUM-HIGH**

- Changing CacheManager constructor requires updates in 5+ locations
- Database connection strategy changes require touching 10+ files
- HTTP session configuration changes ripple through entire codebase

### Code Duplication: **MEDIUM**

- Environment variable parsing: ~40 lines duplicated
- Context manager boilerplate: ~20 repetitions
- Error handling for failed instantiations: inconsistent

## Quantitative Summary

| Dependency Type | Instantiation Count | Unique Locations | Modules Affected |
|----------------|-------------------|-----------------|-----------------|
| CacheManager | 8+ | 6 | cli, http_client, ai/config, tdocs/sources |
| Database | 12+ | 8 | cli, tdocs, specs, meetings, ai/operations |
| HTTP Session | 6+ | 5 | cli, http_client, tdocs/sources, specs/sources |
| Config from Env | 3 | 3 | ai/config, models/crawl_limits, cli/args |

## Recommendations

1. **Introduce Container Pattern**: Centralize dependency creation in a DI container
2. **Factory Abstraction**: Replace direct instantiation with factory interfaces
3. **Configuration Unification**: Single configuration loading mechanism
4. **Lifecycle Management**: Explicit dependency lifecycle (singleton vs. transient)

## Related Documents

- [Tight Coupling Findings](tight-coupling.md)
- [DI Opportunities Summary](di-opportunities.md)
- [Analysis Summary](summary.md)
