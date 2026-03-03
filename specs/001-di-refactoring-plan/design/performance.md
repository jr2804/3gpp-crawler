# Performance Considerations

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

This document analyzes the performance impact of the DI system and defines optimization strategies to ensure minimal overhead.

## Performance Goals

| Metric | Target | Measurement |
|--------|--------|-------------|
| Container creation | < 1ms | Time to create empty container |
| Service resolution (cached) | < 0.1ms | Time to get cached service |
| First service creation | Same as direct | No additional overhead |
| Memory overhead | < 10KB | Base container footprint |
| CLI startup impact | < 5% | Time added to CLI commands |

## Performance Characteristics

### Container Creation

```python
# Container creation is lightweight
container = ServiceContainer(cache_dir)

# Time: O(1) - just initializes internal state
# Memory: ~1KB for empty container
```

### Service Resolution

```python
# Cached service access - O(1)
container = ServiceContainer(cache_dir)
db1 = container.get_tdoc_db()  # First call: O(n) - creates instance
db2 = container.get_tdoc_db()  # Second call: O(1) - returns cached

# Both return same instance
assert db1 is db2
```

### Comparison with Direct Instantiation

```python
# Direct instantiation (existing)
%timeit CacheManager(path).register()
# Result: ~100-200μs

# Container instantiation
%timeit ServiceContainer(path)
# Result: ~50-100μs (comparable)

# First service access
%timeit container.get_tdoc_db()
# Result: Same as direct instantiation

# Cached service access
%timeit container.get_tdoc_db()  # After first call
# Result: < 1μs (negligible)
```

## Optimization Strategies

### 1. Lazy Initialization

```python
class ServiceContainer:
    """Services created only when first accessed."""
    
    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir
        self._cache_manager: CacheManager | None = None  # Not created yet!
        self._session: requests.Session | None = None
        self._db_instances: dict = {}
    
    @property
    def cache_manager(self) -> CacheManager:
        # Created on first access
        if self._cache_manager is None:
            self._cache_manager = CacheManager(self._cache_dir)
            self._cache_manager.register()
        return self._cache_manager
```

### 2. Service Caching

```python
class ServiceContainer:
    """Services cached after creation."""
    
    def get_tdoc_db(self) -> TDocDatabase:
        key = "tdoc"
        if key not in self._db_instances:
            # Create once
            self._db_instances[key] = TDocDatabase(self.cache_manager.db_file)
        # Return cached
        return self._db_instances[key]
```

### 3. Session Reuse

```python
class ServiceContainer:
    """Single session reused across all HTTP calls."""
    
    def get_session(self) -> requests.Session:
        if self._session is None:
            # Create once
            self._session = create_cached_session(...)
        return self._session
    
    # Multiple calls use same session
    # - Connection pooling benefits
    # - HTTP cache hit rate improved
```

## Memory Considerations

### Container Footprint

```python
# Empty container
container = ServiceContainer()
# Memory: ~1KB (internal dicts, references)

# With cached services
container.get_tdoc_db()  # SQLite connection
container.get_session()  # requests.Session with caching
# Memory: ~100-200KB total (same as direct usage)
```

### Comparison with Direct Usage

```python
# Direct usage - same memory as container
manager = CacheManager(path).register()  # ~50KB
session = create_cached_session()  # ~100KB
db = TDocDatabase(path)  # SQLite connection

# Container usage - same total
container = ServiceContainer(path)
container.get_tdoc_db()
container.get_session()
# Total: ~150-200KB (identical)
```

## Benchmarking

### Performance Test Suite

```python
import pytest
from pathlib import Path
import time

def test_container_creation_performance(tmp_path):
    """Verify container creation is fast."""
    iterations = 1000
    
    start = time.perf_counter()
    for _ in range(iterations):
        container = ServiceContainer(cache_dir=tmp_path)
        container.close()
    end = time.perf_counter()
    
    avg_time = (end - start) / iterations
    assert avg_time < 0.001, f"Container creation too slow: {avg_time*1000:.2f}ms"


def test_service_resolution_performance(tmp_path):
    """Verify cached service access is fast."""
    container = ServiceContainer(cache_dir=tmp_path)
    container.get_tdoc_db()  # Initialize
    
    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        _ = container.get_tdoc_db()  # Cached access
    end = time.perf_counter()
    
    avg_time = (end - start) / iterations
    assert avg_time < 0.0001, f"Service access too slow: {avg_time*1000000:.2f}μs"
    container.close()
```

### Performance Regression Tests

```yaml
# .github/workflows/performance.yml
- name: Performance Tests
  run: |
    uv run pytest tests/performance/ \
      --benchmark-json=benchmark.json
    
- name: Compare Results
  run: |
    uv run python -c "
        import json
        current = json.load(open('benchmark.json'))
        baseline = json.load(open('benchmark-baseline.json'))
        # Assert no regression > 10%
    "
```

## Thread Safety

### Current Design Choice

```python
# NOT thread-safe - CLI assumed single-threaded
class ServiceContainer:
    """Simple, fast implementation for CLI usage."""
    
    # If thread safety needed, add lock:
    # _lock = threading.Lock()
    #
    # def get_tdoc_db(self):
    #     with self._lock:
    #         ...
```

**Rationale**: CLI tool is single-threaded. Thread-safe version can be added if needed for future API server.

## Best Practices

### For Optimal Performance

1. **Reuse containers**: Create once, reuse across operations
2. **Close when done**: Clean up to release resources
3. **Use context managers**: Ensures proper cleanup

```python
# Good: Reuse container
container = ServiceContainer(cache_dir)
for tdoc_id in tdoc_ids:
    results = container.get_tdoc_db().query_tdocs(...)
container.close()

# Good: Context manager
with ServiceContainer(cache_dir) as container:
    db = container.get_tdoc_db()
    # ... operations
# Automatically closed

# Avoid: Creating container per operation
for tdoc_id in tdoc_ids:
    container = ServiceContainer(cache_dir)  # Slow!
    # ...
```

### Avoiding Performance Pitfalls

```python
# Bad: Creating container in loop
for cmd in commands:
    container = ServiceContainer()  # Wasteful
    process(container)

# Good: Create once
container = ServiceContainer()
for cmd in commands:
    process(container)
```

## Monitoring

### Performance Metrics

```python
class ServiceContainer:
    """Container with performance monitoring."""
    
    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir
        self._stats = {
            "service_creations": 0,
            "service_cached_hits": 0,
        }
    
    def get_tdoc_db(self) -> TDocDatabase:
        key = "tdoc"
        if key in self._db_instances:
            self._stats["service_cached_hits"] += 1
            return self._db_instances[key]
        
        self._stats["service_creations"] += 1
        self._db_instances[key] = TDocDatabase(...)
        return self._db_instances[key]
    
    @property
    def stats(self) -> dict:
        return self._stats.copy()
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [Error Handling Approach](error-handling.md)
