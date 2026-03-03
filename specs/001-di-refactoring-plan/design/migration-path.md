# Migration Strategy

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

This document defines the migration strategy for moving from the current scattered instantiation pattern to the new DI-based architecture. The strategy prioritizes minimal risk, gradual adoption, and complete backward compatibility.

## Migration Phases

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Establish DI infrastructure without changing existing code

**Tasks**:
1. Create `ServiceContainer` class
2. Implement `DatabaseFactory` protocol
3. Implement `HttpClientProvider` class
4. Create `AppConfig` class
5. Add tests for new components

**Changes**: None to existing code
**Risk**: Zero - all new code

### Phase 2: Internal Adoption (Weeks 3-4)

**Goal**: New code uses DI, existing code unchanged

**Tasks**:
1. Update internal functions to accept container
2. Add container-based fixtures to tests
3. Create test doubles (in-memory DB, mock HTTP)

**Changes**:
- New functions can accept container
- Tests can use fixtures
- Existing functions unchanged

**Example**:
```python
# New internal function accepts container
def _process_tdocs(config, container=None):
    if container is None:
        container = ServiceContainer()
    return container.get_tdoc_db().query_tdocs(config)

# Existing command unchanged
@app.command("query-tdocs")
def query_tdocs(config):
    return _process_tdocs(config)  # Works!
```

### Phase 3: Gradual Migration (Weeks 5-8)

**Goal**: Migrate existing modules to use DI

**Tasks**:
1. Migrate one module at a time
2. Update tests to use DI fixtures
3. Verify no regression in functionality

**Migration Order**:
1. `ai/config.py` - Config loading
2. `tdocs/sources/*` - Source classes
3. `specs/sources/*` - Spec sources
4. `http_client.py` - HTTP utilities
5. CLI commands (last, highest risk)

### Phase 4: Full Adoption (Weeks 9-10)

**Goal**: Default to DI, deprecate old patterns

**Tasks**:
1. Set DI as default for new code
2. Add deprecation warnings to old patterns
3. Update documentation
4. Finalize migration guide

## Migration Checklist

### For Each Module

- [ ] Identify all instantiation points
- [ ] Create factory/protocol for dependencies
- [ ] Update constructor to accept protocol types
- [ ] Add tests with test doubles
- [ ] Verify backward compatibility
- [ ] Update module documentation

### Module Migration Example

```python
# Before: Module with direct instantiation
# src/tdoc_crawler/tdocs/source.py
class WhatTheSpecSource:
    def __init__(self, config: TDocSourceConfig):
        self.session = create_cached_session()
        self.config = config
    
    def fetch(self, tdoc_id: str):
        response = self.session.get(f"/tdoc/{tdoc_id}")
        return response.json()

# After: Module accepts protocol
# src/tdoc_crawler/tdocs/source.py
class WhatTheSpecSource:
    def __init__(
        self,
        config: TDocSourceConfig,
        http_client: HttpClientProtocol | None = None,
    ):
        self._http_client = http_client
        self.config = config
    
    @property
    def http_client(self) -> HttpClientProtocol:
        if self._http_client is None:
            self._http_client = HttpClientProvider()
        return self._http_client
    
    def fetch(self, tdoc_id: str):
        response = self.http_client.get(f"/tdoc/{tdoc_id}")
        return response.json()
```

## Rollback Plan

If migration causes issues:

1. **Immediate Rollback**: Revert to previous commit
2. **Feature Flag**: Use flag to disable DI
3. **Gradual Rollback**: Revert one module at a time

```python
# Feature flag for emergency rollback
USE_DI_CONTAINER = os.getenv("TDC_USE_DI", "false").lower() == "true"

def get_database():
    if USE_DI_CONTAINER:
        return container.get_tdoc_db()
    else:
        # Original behavior
        manager = CacheManager(cache_dir).register()
        return TDocDatabase(manager.db_file)
```

## Testing During Migration

### Before/After Comparison

```python
def test_migration_equivalence():
    """Verify new code produces same results as old."""
    # Old pattern
    manager = CacheManager(tmp_path).register()
    with TDocDatabase(manager.db_file) as old_db:
        old_results = old_db.query_tdocs(config)
    
    # New pattern  
    container = ServiceContainer(cache_dir=tmp_path)
    with container.get_tdoc_db() as new_db:
        new_results = new_db.query_tdocs(config)
    
    # Compare
    assert old_results == new_results
```

### Integration Test Suite

```python
# Run full test suite after each module migration
def test_full_migration():
    """Verify complete workflow with new DI."""
    container = ServiceContainer()
    
    # Database operations
    with container.get_tdoc_db() as db:
        db.upsert_tdoc(tdoc)
        results = db.query_tdocs(config)
    
    # HTTP operations
    client = container.get_http_client()
    response = client.get(url)
    
    # Config
    cfg = container.get_config()
    
    # All work together
    assert results is not None
    assert response.status_code == 200
    assert cfg is not None
```

## Documentation Updates

### Update Strategy

1. **API Docs**: Document new container-based APIs
2. **Migration Guide**: Step-by-step migration instructions
3. **Examples**: Show both old and new patterns
4. **FAQ**: Address common migration questions

### Example Documentation

```markdown
## Choosing a Pattern

### Traditional Pattern
Use when:
- Quick scripts
- One-off commands
- Migrating from older versions

```python
manager = CacheManager(cache_dir).register()
with TDocDatabase(manager.db_file) as db:
    results = db.query_tdocs(config)
```

### Container Pattern
Use when:
- Building larger applications
- Writing tests
- Need for multiple coordinated services

```python
container = ServiceContainer(cache_dir)
with container.get_tdoc_db() as db:
    results = db.query_tdocs(config)
```
```

## Timeline Summary

| Phase | Duration | Risk | Backward Compatible |
|-------|----------|------|---------------------|
| Foundation | 2 weeks | None | Yes |
| Internal | 2 weeks | Low | Yes |
| Migration | 4 weeks | Medium | Yes |
| Adoption | 2 weeks | Medium | Yes (deprecated) |

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Backward Compatibility Strategy](backward-compatibility.md)
- [Testability Approach](testability.md)
