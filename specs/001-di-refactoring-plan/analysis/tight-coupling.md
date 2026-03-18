# Tight Coupling Findings

## Overview

This document identifies areas of **tight coupling** in the tdoc-crawler codebase where components depend on concrete implementations rather than abstractions, making the system rigid and difficult to test or extend.

## Coupling Categories

### 1. Concrete Class Dependencies

#### Problem: Direct instantiation of concrete classes

**Example 1: TDocCrawler**

```python
# src/tdoc_crawler/tdocs/operations/crawl.py:37-40
class TDocCrawler:
    def __init__(self, database: TDocDatabase) -> None:
        if not isinstance(database, TDocDatabase):
            raise TypeError(f"Expected TDocDatabase, got {type(database)}")
        self.database = database
```

**Issues:**

- Type check prevents using subclasses or mocks without inheritance
- No interface/protocol defined for database operations
- Caller must construct `TDocDatabase` instance before creating crawler

**Example 2: WhatTheSpecSource**

```python
# src/tdoc_crawler/tdocs/sources/whatthespec.py:112-124
class WhatTheSpecSource(TDocSource):
    def __init__(
        self,
        config: TDocSourceConfig,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session
```

**Issues:**

- Depends on concrete `requests.Session` instead of protocol
- Cannot easily swap HTTP client implementation
- Session lifecycle unclear (who creates/closes?)

### 2. Module-Level Coupling

#### Problem: Hard-coded imports create rigid dependencies

**Example: Database Module**

```python
# src/tdoc_crawler/database/tdocs.py:8
from tdoc_crawler.database.meetings import MeetingDatabase

class TDocDatabase(MeetingDatabase):
    """Unified database operations for TDocs and Meetings."""
```

**Inheritance Chain:**

```
TDocDatabase → MeetingDatabase → DocDatabase
```

**Issues:**

- Deep inheritance hierarchy (3 levels)
- Child classes inherit all parent methods, even if irrelevant
- Changes to base class affect all descendants
- Cannot use TDoc operations without meeting database

**Example: AI Workspace Operations**

```python
# src/tdoc_crawler/ai/operations/workspaces.py:14-16
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
```

**Issues:**

- Workspace module knows about database internals
- Direct dependency on checkout operations
- Cannot test workspace logic without full database setup

### 3. Configuration Coupling

#### Problem: Configuration and business logic intertwined

**Example: AiConfig**

```python
# src/tdoc_crawler/ai/config.py:146-154
@model_validator(mode="after")
def _resolve_paths(self) -> AiConfig:
    if self.ai_cache_dir is None:
        self.ai_cache_dir = resolve_cache_manager(self.cache_manager_name).ai_embed_dir(self.embedding_model)
    return self
```

**Issues:**

- Model validation depends on global state (cache manager registry)
- Cannot create AiConfig without CacheManager being registered
- Side effects in validator make testing difficult

**Example: HTTP Client**

```python
# src/tdoc_crawler/http_client.py:108-112
http_cache = http_cache or HttpCacheConfig.resolve_http_cache_config()
if http_cache.cache_file is None:
    manager = resolve_cache_manager(cache_manager_name)
    http_cache.cache_file = str(manager.http_cache_file)
```

**Issues:**

- Function reaches into global state to resolve dependencies
- Caller cannot predict what configuration will be used
- Hidden coupling to CacheManager registry

### 4. Global State Dependencies

#### Problem: Reliance on module-level singletons

**Example: Cache Manager Registry**

```python
# src/tdoc_crawler/config.py:18
_cache_managers: dict[str, CacheManager] = {}

def resolve_cache_manager(name: str | None = None) -> CacheManager:
    name = name or DEFAULT_MANAGER
    manager = _cache_managers.get(name)
    if manager is None:
        raise ValueError(f"No cache manager registered under name '{name}'.")
    return manager
```

**Issues:**

- Global mutable state shared across all modules
- Order of initialization matters (must register before resolving)
- Tests must clean up registry between runs
- Hidden dependency not visible in function signatures

**Example: Workspace Registry**

```python
# src/tdoc_crawler/ai/operations/workspace_registry.py:102
def load(cls) -> WorkspaceRegistry:
    """Load registry from file."""
    if not cls._registry_file.exists():
        return cls()
    # ... load from file
```

**Issues:**

- Singleton pattern with file I/O
- Cannot create multiple isolated instances
- Tests must manage file system state

## Coupling Metrics

### Inheritance Depth

| Class | Depth | Parent Classes |
|-------|-------|---------------|
| TDocDatabase | 3 | MeetingDatabase → DocDatabase |
| MeetingDatabase | 2 | DocDatabase |
| SpecDatabase | 2 | DocDatabase |

### Direct Dependencies per Module

| Module | Direct Imports | Concrete Dependencies |
|--------|---------------|---------------------|
| cli/app.py | 15+ | CacheManager, TDocDatabase, MeetingDatabase |
| tdocs/operations/crawl.py | 8 | TDocDatabase, MeetingDatabase |
| ai/operations/workspaces.py | 6 | SpecDatabase, WorkspaceRegistry |
| http_client.py | 5 | CacheManager, HttpCacheConfig |

### Global State Access Points

| Global | Access Count | Modules Using |
|--------|-------------|---------------|
| `_cache_managers` | 8+ | config, http_client, ai/config, tdocs/sources |
| `WorkspaceRegistry._registry_file` | 4+ | ai/operations/workspaces, ai/cli |
| `DEFAULT_MANAGER` | 6+ | config, cli, http_client |

## Impact on Testability

### Mock Complexity

Testing a single operation requires mocking multiple layers:

```python
# To test TDocCrawler.crawl():
@patch("tdoc_crawler.tdocs.operations.crawl.TDocDatabase")
@patch("tdoc_crawler.tdocs.operations.crawl.MeetingDatabase")
@patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
@patch("tdoc_crawler.config._cache_managers")
def test_crawl(...):
    pass
```

### Test Setup Requirements

```python
# tests/conftest.py:241-244
# Register default cache manager at module level for all tests
_cache_manager = CacheManager(ensure_paths=False, name="default")
_cache_manager.register(force=True)
```

**Problem:** Global state must be initialized before any tests run.

## Recommendations

1. **Introduce Protocols**: Define interfaces for database, HTTP client, cache
1. **Constructor Injection**: Pass dependencies explicitly, don't reach for globals
1. **Composition over Inheritance**: Replace deep inheritance with component composition
1. **Factory Pattern**: Abstract object creation behind interfaces
1. **Explicit Configuration**: Make all dependencies visible in function signatures

## Related Documents

- [Scattered Instantiation Findings](scattered-instantiation.md)
- [Existing DI-like Patterns](existing-patterns.md)
- [DI Opportunities Summary](di-opportunities.md)
