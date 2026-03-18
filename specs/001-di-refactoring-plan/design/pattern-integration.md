# Existing Pattern Integration

**Date**: 2026-03-02\
**Feature**: Dependency Injection Refactoring Planning\
**Branch**: `001-di-refactoring-plan`\
**Status**: Draft

## Overview

This document defines how the new DI system integrates with existing patterns in the codebase, including the CacheManager registry, test fixtures, and configuration loading mechanisms.

## Integration with Existing Patterns

### 1. CacheManager Registry

The container wraps the existing registry:

```python
# Existing code - unchanged
from tdoc_crawler.config import register_cache_manager, resolve_cache_manager

manager = CacheManager(cache_dir).register()
resolved = resolve_cache_manager("default")

# Container uses registry under the hood
container = ServiceContainer(cache_dir)
# Internally calls: register_cache_manager(container._cache_manager)
assert resolve_cache_manager(container._name) is container.cache_manager
```

**Key points:**

- Registry remains the source of truth
- Container registers its own manager on first access
- Cleanup unregisters to maintain consistency

### 2. Test Fixtures Integration

The DI system integrates with existing pytest fixtures:

```python
# tests/conftest.py - existing fixtures remain
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "test-cache"
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)
    return cache_dir

# New fixture for container
@pytest.fixture
def test_container(test_cache_dir) -> ServiceContainer:
    """Create test container from existing test_cache_dir."""
    container = ServiceContainer(cache_dir=test_cache_dir)
    yield container
    container.close()
```

### 3. Configuration Pattern Integration

```python
# Existing: Individual config loading
ai_config = AiConfig.from_env()
http_config = HttpCacheConfig.resolve_http_cache_config()

# New: Unified config
app_config = AppConfig.from_env()

# Both work together
assert app_config.ai.embedding_model == ai_config.embedding_model
assert app_config.http.ttl == http_config.ttl
```

### 4. Factory Function Pattern

The `create_cached_session()` function remains available:

```python
# Existing: Direct factory usage
session = create_cached_session(cache_manager_name="default")

# New: Via provider
provider = HttpClientProvider(cache_manager_name="default")
session = provider.session

# New: Via container
container = ServiceContainer()
session = container.get_session()

# All produce equivalent sessions
```

### 5. Context Manager Pattern

Database context managers work unchanged:

```python
# Existing
with TDocDatabase(db_file) as db:
    results = db.query_tdocs(config)

# New - same interface
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

## Pattern Mapping

| Existing Pattern | DI Equivalent | Integration |
|-----------------|---------------|-------------|
| `CacheManager(path).register()` | `container.cache_manager` | Container manages registry |
| `resolve_cache_manager(name)` | `container.get_cache_manager()` | Same registry |
| `TDocDatabase(db_file)` | `container.get_tdoc_db()` | Factory creates instance |
| `create_cached_session()` | `container.get_session()` | Provider wraps factory |
| `AiConfig.from_env()` | `container.get_config()` | AppConfig unifies |
| `CacheManager` registry | Container internal | Maintains compatibility |

## Migration Examples

### Example 1: Direct to Container

```python
# Before
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)

# After (optional)
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

### Example 2: Multiple Services

```python
# Before: Multiple instantiations
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as tdoc_db:
    with MeetingDatabase(manager.db_file) as meeting_db:
        tdocs = tdoc_db.query_tdocs(config)
        meetings = meeting_db.query_meetings(config)

# After: Single container
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as tdoc_db:
    with container.get_meeting_db() as meeting_db:
        tdocs = tdoc_db.query_tdocs(config)
        meetings = meeting_db.query_meetings(config)
```

### Example 3: HTTP + Database

```python
# Before
session = create_cached_session()
with TDocDatabase(db_file) as db:
    # Use session for HTTP, db for data
    response = session.get(url)
    results = db.query_tdocs(config)

# After
container = ServiceContainer(cache_dir)
session = container.get_session()
with container.get_tdoc_db() as db:
    response = session.get(url)
    results = db.query_tdocs(config)
```

## Compatibility Layer

### Wrapper Functions (Future)

Optional wrappers for convenience:

```python
def get_default_container() -> ServiceContainer:
    """Get default container, creating if needed."""
    global _default_container
    if _default_container is None:
        _default_container = ServiceContainer()
    return _default_container


def get_tdoc_database() -> TDocDatabase:
    """Get TDoc database using default container."""
    return get_default_container().get_tdoc_db()


# These are purely optional helpers
# Direct usage still preferred for explicit dependencies
```

## Design Principles Applied

1. **Don't break existing**: All patterns continue working
1. **Opt-in DI**: Container is additive, not required
1. **Consistent interface**: Same method names where possible
1. **Clean separation**: New code can use DI, old code unchanged

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
- [Migration Strategy](migration-path.md)
