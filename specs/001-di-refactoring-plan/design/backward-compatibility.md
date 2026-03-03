# Backward Compatibility Strategy

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

This document defines the strategy for maintaining backward compatibility during the dependency injection refactoring. The key principle is **zero breaking changes** - existing code must continue to work unchanged while new DI patterns are introduced.

## Core Principles

### 1. Zero Breaking Changes

All existing APIs, function signatures, and module imports remain unchanged. The DI system is an optional enhancement.

### 2. Opt-In, Not Required

DI adoption is completely voluntary. Existing code patterns work exactly as before.

### 3. Gradual Migration Path

Users can migrate incrementally, mixing DI and non-DI code during transition.

### 4. Feature Parity

All existing functionality must be accessible through both traditional and DI patterns.

## Compatibility Matrix

### Before/After Comparison

| Component | Before | After | Breaking? |
|-----------|--------|-------|-----------|
| CacheManager | `CacheManager(path).register()` | Same + Container | No |
| TDocDatabase | `TDocDatabase(db_file)` | Same + Factory | No |
| create_cached_session | `create_cached_session()` | Same + Provider | No |
| AiConfig.from_env | `AiConfig.from_env()` | Same + AppConfig | No |
| CLI commands | All commands work | Same + optional container | No |

### API Surface Preservation

```python
# All of these continue to work identically

# 1. CacheManager - unchanged
manager = CacheManager(cache_dir).register()
db_file = manager.db_file

# 2. Database - unchanged
with TDocDatabase(db_file) as db:
    results = db.query_tdocs(config)

# 3. HTTP session - unchanged
with create_cached_session() as session:
    response = session.get(url)

# 4. AI Config - unchanged
config = AiConfig.from_env(parallelism=8)

# 5. CLI - unchanged
tdoc-crawler query R1-2400001
```

## Implementation Strategy

### Phase 1: Additive DI (No Changes to Existing)

New DI components are added alongside existing code:

```python
# NEW: Add container (doesn't affect existing code)
container = ServiceContainer(cache_dir)

# OLD: Existing code unchanged
manager = CacheManager(cache_dir).register()
```

### Phase 2: Internal Adoption

New code uses DI internally while maintaining external API:

```python
# External API unchanged - receives traditional params
def query_tdocs(tdoc_id: str, cache_dir: Path | None = None):
    # Internally uses container
    container = ServiceContainer(cache_dir)
    db = container.get_tdoc_db()
    # ... query logic
```

### Phase 3: Support Both Patterns

Functions accept both traditional and DI-style arguments:

```python
def process_tdocs(
    tdoc_ids: list[str],
    # Traditional parameters
    cache_dir: Path | None = None,
    # OR DI container
    container: ServiceContainer | None = None,
):
    # Use whichever was provided
    if container is None:
        container = ServiceContainer(cache_dir)
    
    with container.get_tdoc_db() as db:
        # ... process
```

## Compatibility Wrappers

### CacheManager Registry Compatibility

```python
# Legacy: resolve_cache_manager continues to work
from tdoc_crawler.config import resolve_cache_manager

manager = resolve_cache_manager("default")  # Still works!

# New: Container uses same registry
container = ServiceContainer()
assert resolve_cache_manager(container._name) is container.cache_manager
```

### Database Context Manager Compatibility

```python
# Both patterns work identically

# Pattern 1: Direct instantiation (existing)
with TDocDatabase(db_file) as db:
    results = db.query_tdocs(config)

# Pattern 2: Via container (new)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

### HTTP Session Compatibility

```python
# Both patterns work identically

# Pattern 1: Direct factory (existing)
session = create_cached_session()
response = session.get(url)

# Pattern 2: Via provider (new)
provider = HttpClientProvider()
response = provider.get(url)

# Pattern 3: Via container (new)
response = container.get_session().get(url)
```

## Deprecation Strategy

When removing old patterns (far future), use deprecation warnings:

```python
import warnings

def resolve_cache_manager(name: str | None = None) -> CacheManager:
    """
    Resolve cache manager by name.
    
    .. deprecated::
        Use ServiceContainer instead for new code.
        This function will be removed in version 2.0.
    """
    warnings.warn(
        "resolve_cache_manager() is deprecated. "
        "Use ServiceContainer instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... existing implementation
```

## Testing Backward Compatibility

### Existing Tests Remain Valid

```python
# This test continues to work exactly as before
def test_existing_cache_manager_pattern():
    manager = CacheManager(tmp_path).register()
    assert manager.root == tmp_path
    assert manager.db_file == tmp_path / "tdoc_crawler.db"
```

### New Tests Verify Compatibility

```python
def test_container_matches_existing_behavior():
    """Verify container produces same results as direct instantiation."""
    # Setup via both methods
    container = ServiceContainer(cache_dir=tmp_path)
    manager = CacheManager(tmp_path).register()
    
    # Compare results
    assert container.cache_manager.root == manager.root
    assert container.cache_manager.db_file == manager.db_file
```

## Migration Assistance

### Side-by-Side Comparison

```python
# BEFORE: Direct instantiation (still works)
manager = CacheManager(Path.home() / ".tdoc-crawler").register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)
session = create_cached_session()

# AFTER: Via container (new optional pattern)
container = ServiceContainer()
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
session = container.get_session()

# Both produce identical results
```

### Automatic Migration Tool (Future)

A future migration tool could help convert existing code:

```python
# Input: Existing code
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)

# Output: Migrated code
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```

## Version Compatibility Table

| Version | DI Container | Registry | Old Patterns |
|---------|-------------|----------|--------------|
| 1.x | Added | Deprecated* | Fully Supported |
| 2.x | Standard | Removed | Deprecated* |
| 3.x | Standard | N/A | Migrated |

*Deprecation warnings issued but still functional.

## Related Documents

- [Migration Strategy](migration-path.md)
- [ServiceContainer Interface](service-container.md)
- [DatabaseFactory Protocol](database-factory.md)
