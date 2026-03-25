# Testing

Test structure, patterns, and practices for the 3GPP Crawler project.

## Test Framework

- **Framework**: pytest
- **Python Path**: `src/` (configured in `pyproject.toml`)
- **Test Location**: `tests/`

## Running Tests

| Task | Command | ~Time |
|------|---------|-------|
| All tests | `uv run pytest -v` | ~2m |
| Single file | `uv run pytest tests/test_file.py -v` | ~5s |
| With coverage | `uv run pytest --cov=src --cov-report=term-missing` | ~2m |
| Specific marker | `uv run pytest -m "not integration"` | varies |

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures, pytest configuration
├── test_crawler.py          # Core crawler tests
├── test_cli.py              # CLI command tests
├── test_database.py         # Database layer tests
├── test_models.py           # Pydantic model tests
├── test_http_client.py      # HTTP client tests
├── test_portal_*.py         # Portal authentication tests
├── test_specs_*.py          # Specification tests
├── ai/                      # AI module tests
│   ├── conftest.py          # AI-specific fixtures
│   ├── test_ai_*.py         # AI component tests
├── convert_lo/              # LibreOffice converter tests
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   └── test_formats.py
└── pool_executor/           # Executor package tests
    ├── test_executor_adapter.py
    └── test_serial_executor.py
```

## Pytest Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "integration: marks tests as integration tests (slower, requires network)",
]
filterwarnings = [
    "ignore:.*Accessing the 'model_fields' attribute.*:DeprecationWarning",
]
```

## Fixtures

### Core Fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory and register CacheManager."""
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)
    return cache_dir

@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path."""
    return test_cache_dir / "tdoc_crawler.db"

@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    """Create sample TDoc metadata for testing."""
    return [
        TDocMetadata(
            tdoc_id="R1-2301234",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
            meeting_id=12345,
            file_size=256000,
            title="Sample RAN1 TDoc",
            # ... other fields
        ),
    ]

@pytest.fixture
def populated_db(test_db_path, sample_meetings, sample_tdocs) -> TDocDatabase:
    """Create and populate a test database."""
    with TDocDatabase(test_db_path) as db:
        insert_sample_meetings(db, sample_meetings)
        for tdoc in sample_tdocs:
            db.upsert_tdoc(tdoc)
    return TDocDatabase(test_db_path)
```

### AI Module Fixtures (`tests/ai/conftest.py`)

AI tests have their own conftest.py with AI-specific fixtures.

## Test Patterns

### Test Class Organization

```python
class TestTDocCrawler:
    """Tests for TDocCrawler class."""
    
    def test_crawler_initialization(self, test_db_path: Path) -> None:
        """Ensure crawler stores the provided database instance."""
        with TDocDatabase(test_db_path) as database:
            crawler = TDocCrawler(database)
            assert crawler.database is database
    
    def test_tdoc_pattern(self) -> None:
        """Verify TDoc filename regex matches expected inputs."""
        assert TDOC_PATTERN.search("R1-2301234.zip")
        assert not TDOC_PATTERN.search("README.txt")
```

### Mocking External Dependencies

```python
from unittest.mock import MagicMock, patch

@patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
def test_crawl_connection_failure(
    self,
    mock_fetch: MagicMock,
    test_db_path: Path,
) -> None:
    """Handle document list fetch failures gracefully."""
    mock_fetch.side_effect = OSError("Connection refused")
    # ... test code
```

### Database Tests

```python
def test_database_operations(test_db_path: Path) -> None:
    """Test database CRUD operations."""
    with TDocDatabase(test_db_path) as database:
        # Use context manager for automatic cleanup
        meeting = _create_test_meeting()
        database.upsert_meeting(meeting)
```

## Coverage

### Configuration

```toml
[tool.coverage.report]
skip_empty = true

[tool.coverage.run]
branch = true
source = ["src"]
```

### Coverage Targets

- **Pool Executor**: >90% coverage required
- **Core Modules**: High coverage expected
- **AI Module**: Integration tests may have lower coverage

## Test Naming Conventions

- **File names**: `test_<module>.py` (e.g., `test_crawler.py`)
- **Class names**: `Test<Component>` (e.g., `TestTDocCrawler`)
- **Method names**: `test_<behavior>` (e.g., `test_crawl_connection_failure`)

## Test Isolation

Each test must be independent:

```python
# ✅ CORRECT - Uses fixtures for isolation
def test_with_fixture(self, test_cache_dir: Path) -> None:
    # test_cache_dir is fresh for each test
    ...

# ❌ WRONG - Relies on test order or shared state
_shared_state = {}

def test_writes_state(self) -> None:
    _shared_state["key"] = "value"
```

## Integration Tests

Mark slow/network-dependent tests:

```python
import pytest

@pytest.mark.integration
def test_live_api_call(self) -> None:
    """Test against real 3GPP FTP server."""
    ...
```

Run without integration tests:
```bash
uv run pytest -m "not integration"
```

## AI Test Collection Ignore

The core test suite ignores `tests/ai/`:

```python
# tests/conftest.py
def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    """Ignore legacy tests/ai suite in the core tdoc_crawler package."""
    path_text = str(collection_path).replace("\\", "/").lower()
    return "/tests/ai/" in path_text or path_text.endswith("/tests/ai")
```

## Best Practices

1. **One behavior per test**: Each test validates one specific behavior
2. **Descriptive names**: Test names describe the expected behavior
3. **Minimal assertions**: Assert only what's relevant to the test
4. **Mock external systems**: Isolate tests from network, file system, etc.
5. **Document edge cases**: Test error conditions and boundary cases

## Anti-Duplication

**CRITICAL**: Do not re-implement logic from `src/` in `tests/`. Tests should import and verify actual implementation.

```python
# ✅ CORRECT - Import from source
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.config import resolve_cache_manager

# ❌ WRONG - Re-implementing source logic in tests
class FakeTDocCrawler:
    def crawl(self):
        # This duplicates production code!
```

## Pool Executor Tests

Located in `tests/pool_executor/`:

```bash
# Run pool executor tests
uv run pytest tests/pool_executor/ -v

# With coverage (>90% required)
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

## Debugging Failed Tests

```bash
# Verbose output with full diffs
uv run pytest tests/test_crawler.py -v --tb=long

# Stop on first failure
uv run pytest tests/ -x

# Run specific test
uv run pytest tests/test_crawler.py::TestTDocCrawler::test_crawler_initialization -v
```
