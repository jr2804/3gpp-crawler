# Testability Approach

**Date**: 2026-03-02\
**Feature**: Dependency Injection Refactoring Planning\
**Branch**: `001-di-refactoring-plan`\
**Status**: Draft

## Overview

This document defines the testability improvements achieved through the dependency injection refactoring. The goal is to reduce test complexity, eliminate global state dependencies, and enable true unit testing without integration overhead.

## Current Testability Challenges

From the analysis, current challenges include:

| Challenge | Current State | Target |
|-----------|--------------|--------|
| Mocks per test | 4.2 average | 1-2 |
| Setup/logic ratio | 3.1 | 1.0 |
| Global state tests | 18% | 0% |
| Test execution time | 120ms avg | \<50ms |

## Design for Testability

### Protocol-Based Dependency Injection

```python
# Instead of concrete types, use protocols
class TDocCrawler:
    def __init__(
        self,
        database: TDocDatabaseProtocol,  # Protocol, not concrete class
        http_client: HttpClientProtocol | None = None,
    ) -> None:
        self.database = database
        self._http_client = http_client
```

This enables simple mock injection:

```python
def test_crawler_queries_database():
    """Test crawler queries database correctly."""
    # Arrange: Create mock
    mock_db = Mock(spec=TDocDatabaseProtocol)
    mock_db.query_tdocs.return_value = [
        TDocMetadata(id="R1-2400001", title="Test")
    ]
    
    # Act: Use mock in crawler
    crawler = TDocCrawler(database=mock_db)
    results = crawler.find_tdocs("*test*")
    
    # Assert: Verify interaction
    mock_db.query_tdocs.assert_called_once()
    assert len(results) == 1
```

## Test Fixtures

### Container-Based Fixtures

```python
# tests/fixtures.py
import pytest
from pathlib import Path

@pytest.fixture
def test_container(tmp_path: Path) -> ServiceContainer:
    """
    Create test container with temporary cache.
    
    Automatically cleans up after test.
    """
    container = ServiceContainer(cache_dir=tmp_path)
    yield container
    container.close()


@pytest.fixture
def in_memory_factory() -> InMemoryDatabaseFactory:
    """
    Create in-memory database factory for testing.
    
    Fast, isolated tests without file I/O.
    """
    factory = InMemoryDatabaseFactory()
    yield factory
    factory.close()


@pytest.fixture
def mock_http_client() -> MockHttpClient:
    """
    Create mock HTTP client.
    
    Records all requests and returns configurable responses.
    """
    return MockHttpClient()
```

### Fixture Usage Examples

```python
def test_with_container(test_container):
    """Use container for integration testing."""
    db = test_container.get_tdoc_db()
    assert db is not None


def test_with_in_memory_db(in_memory_factory):
    """Use in-memory DB for unit testing."""
    db = in_memory_factory.tdoc_db()
    db.upsert_tdoc(TDocMetadata(id="R1-2400001", title="Test"))
    
    results = db.query_tdocs(TDocQueryConfig())
    assert len(results) == 1


def test_with_mock_http(mock_http_client):
    """Use mock HTTP for network-independent tests."""
    mock_http_client.mock_response(
        "GET",
        "https://api.example.com/data",
        response_text='{"key": "value"}',
    )
    
    client = WhatTheSpecSource(config, http_client=mock_http_client)
    result = client.fetch_data()
    
    assert result == {"key": "value"}
```

## Test Doubles

### In-Memory Database

```python
class InMemoryTDocDatabase:
    """
    In-memory TDoc database for testing.
    
    Provides same interface as TDocDatabase but uses
    dictionaries instead of SQLite.
    """
    
    def __init__(self) -> None:
        self._tdocs: dict[str, TDocMetadata] = {}
        self._is_open = True
    
    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        """Query TDocs with filtering."""
        results = list(self._tdocs.values())
        
        if config.tdoc_ids:
            results = [t for t in results if t.id in config.tdoc_ids]
        
        return results
    
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update TDoc."""
        is_new = metadata.id not in self._tdocs
        self._tdocs[metadata.id] = metadata
        return (is_new, not is_new)
    
    def __enter__(self) -> "InMemoryTDocDatabase":
        return self
    
    def __exit__(self, *args) -> None:
        self._is_open = False
    
    def close(self) -> None:
        """Close database (no-op for in-memory)."""
        self._is_open = False
```

### Mock HTTP Client

See [HttpClientProvider](http-provider.md) for complete MockHttpClient implementation.

### Fake Cache Manager

```python
class FakeCacheManager:
    """Fake cache manager for testing."""
    
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("/fake/cache")
        self.db_file = self.root / "tdoc_crawler.db"
        self.checkout_dir = self.root / "checkout"
        self.name = "test"
    
    def register(self, force: bool = False) -> "FakeCacheManager":
        """Register fake manager (no-op)."""
        return self
    
    def unregister(self) -> None:
        """Unregister fake manager (no-op)."""
        pass
```

## Testing Patterns

### Unit Testing with Mocks

```python
def test_crawler_processes_tdocs():
    """Unit test crawler logic with mocks."""
    # Arrange
    mock_db = Mock(spec=TDocDatabaseProtocol)
    mock_db.query_tdocs.return_value = [
        TDocMetadata(id="R1-2400001", title="Test TDoc", ...)
    ]
    mock_http = MockHttpClient()
    mock_http.mock_response("GET", "https://api.example.com/1", ...)
    
    crawler = TDocCrawler(database=mock_db, http_client=mock_http)
    
    # Act
    results = crawler.crawl(TDocCrawlConfig(target_ids=["R1-2400001"]))
    
    # Assert
    assert len(results) == 1
    mock_db.query_tdocs.assert_called_once()
```

### Integration Testing with Containers

```python
def test_crawl_integration(test_container):
    """Integration test with real database."""
    # Setup
    config = TDocCrawlConfig(working_groups=[WorkingGroup.RAN1])
    
    # Execute
    crawler = TDocCrawler(database=test_container.get_tdoc_db())
    results = crawler.crawl(config)
    
    # Verify
    assert isinstance(results, list)
```

### Property-Based Testing

```python
from hypothesis import given, strategies as st

@given(st.lists(st.text(min_size=1)))
def test_query_config_accepts_any_tdoc_ids(tdoc_ids):
    """Property test: any string list should be valid input."""
    config = TDocQueryConfig(tdoc_ids=tdoc_ids)
    assert config.tdoc_ids == tdoc_ids
```

## Global State Isolation

### Reset Between Tests

```python
@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    # Clear cache managers
    from tdoc_crawler.config import _cache_managers
    _cache_managers.clear()
    
    # Reset any other global state
    yield
    
    # Cleanup after test
    _cache_managers.clear()
```

### Using Container Instead of Globals

```python
# Before: Tests depend on global state
def test_something():
    manager = CacheManager(tmp_path).register()  # Modifies global!
    # Test logic

# After: Tests use isolated container
def test_something(test_container):
    db = test_container.get_tdoc_db()  # No global state
    # Test logic
```

## Test Coverage Targets

| Component | Current | Target | Approach |
|-----------|---------|--------|----------|
| ServiceContainer | N/A | 90%+ | Unit tests for all methods |
| DatabaseFactory | N/A | 90%+ | Unit + integration tests |
| HttpClientProvider | N/A | 85%+ | Mock-based unit tests |
| AppConfig | 71% | 85%+ | More edge case tests |
| CLI commands | 23% | 60%+ | Container-based tests |

## CI/CD Integration

### Test Execution

```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    
    - name: Run tests
      run: |
        uv run pytest tests/ \
          --cov=src/tdoc_crawler \
          --cov-report=xml \
          --tb=short
    
    - name: Check coverage
      run: |
        uv run coverage check --fail-under=70
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [DatabaseFactory Protocol](database-factory.md)
- [HttpClientProvider Abstraction](http-provider.md)
- [Testability Challenges Analysis](../analysis/testability-challenges.md)
