# Testing Patterns

**Analysis Date:** 2026-05-03

## Test Framework

**Runner:**
- **pytest** ≥ 7.2.0
- Async support: `pytest-asyncio` ≥ 1.2.0
- Config: `pyproject.toml` section `[tool.pytest.ini_options]`

**Assertion Library:**
- Standard `assert` statements (no third-party assertion library)

**Run Commands:**
```bash
uv run pytest -v                                    # All tests (verbose)
uv run pytest tests/test_database.py -v             # Single test file
uv run pytest tests/test_database.py::TestTDocDatabase::test_upsert_tdoc -v  # Single test
uv run pytest --cov=src --cov-report=term-missing   # Coverage report
uv run pytest -m "not integration"                  # Skip integration tests
```

## Test File Organization

**Location:**
- All tests under `tests/` at project root (configured in `[tool.pytest.ini_options] testpaths = ["tests"]`)
- Mirror the source structure: `tests/test_database.py` tests `src/tdoc_crawler/database/`
- Subdirectories for package-specific tests: `tests/config/`, `tests/convert_lo/`, `tests/pool_executor/`
- `pythonpath = ["src"]` in pytest config so imports use `tdoc_crawler.*` directly

**Naming:**
- Test files: `test_*.py`
- Test classes: `class Test<ComponentName>` (e.g., `TestCacheManager`, `TestTDocMetadata`)
- Test methods: `def test_<behavior_description>()` (e.g., `test_case_insensitive_query`)
- `conftest.py` for shared fixtures at each level (`tests/conftest.py`, `tests/convert_lo/conftest.py`)

**Structure:**
```
tests/
├── conftest.py                   # Shared fixtures (cache_dir, db, sample data)
├── test_cache_manager.py         # Unit tests for CacheManager
├── test_database.py              # Database operations (async, @pytest.mark.asyncio)
├── test_models.py                # Pydantic model tests
├── test_normalization.py         # Normalization helpers
├── test_http_client.py           # HTTP client with unittest.mock
├── test_workspaces.py            # Workspace CRUD and models
├── config/
│   ├── test_sources.py           # Config source discovery
│   └── test_export.py            # Config export
├── convert_lo/
│   ├── conftest.py               # convert-lo specific fixtures
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   ├── test_formats.py
│   └── test_integration.py       # Integration tests
└── pool_executor/
    ├── test_serial_executor.py   # SerialPoolExecutor unit tests
    └── test_executor_adapter.py  # Runner adapter tests
```

## Test Structure

**Suite Organization (class-based):**
```python
class TestTDocDatabase:
    """Tests for TDocDatabase class."""

    async def test_upsert_tdoc(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Insert a TDoc record and validate persistence."""
        async with TDocDatabase(test_db_path) as db:
            await self._insert_sample_meetings(db, sample_meetings)
            created, changed = await db.upsert_tdoc(sample_tdocs[0])
            assert created is True
            assert changed is False
```

**Patterns:**
- **Setup:** `setup_method(self)` for per-test state reset (e.g., `CacheManager._instance = None`)
- **Fixtures:** Function-scoped `@pytest.fixture` for data and paths; fixtures use type annotations on parameters to declare dependencies
- **Assertions:** Plain `assert` with descriptive failure messages implicit in test method names
- **Teardown:** No explicit teardown — `tmp_path` fixture auto-cleans; async context managers (`async with db`) handle cleanup

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import MagicMock, patch

# Patching methods on objects
with patch.object(session, "get") as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_get.return_value = mock_response
    session.get("http://example.com")

# Fake response classes for HTTP mocking
class _FakeResponse:
    def __init__(self, url: str, payload: dict[str, Any]) -> None:
        self.url = url
        self._payload = payload
        self.status_code = 200
        self.request = MagicMock()
        self.request.url = url

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload
```

**What to Mock:**
- HTTP responses (network calls — never make real HTTP in unit tests)
- External service clients (portal, whatthespec API)
- File system operations (use `tmp_path` fixture instead)

**What NOT to Mock:**
- Core domain models (`TDocMetadata`, `Workspace`) — test real instances
- Database operations — tests use real SQLite in `tmp_path`
- CacheManager — use the actual singleton (reset via `_instance = None` in `setup_method`)
- Parser/validator logic — test actual transformations

## Fixtures and Factories

**Test Data (from `tests/conftest.py`):**
```python
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
            source="Test Source",
            # ... all required fields populated
        ),
        # ... more sample records
    ]

@pytest.fixture
def populated_db(
    test_db_path: Path,
    sample_meetings: list[dict[str, object]],
    sample_tdocs: list[TDocMetadata],
) -> TDocDatabase:
    """Create and populate a test database."""
    # Inserts sample data using async context manager
```

**Key fixtures (from `tests/conftest.py`):**

| Fixture | Scope | Returns | Purpose |
|---------|-------|---------|---------|
| `_reset_cache_manager` | function (autouse) | None | Reset CacheManager singleton before each test |
| `test_cache_dir` | function | `Path` | Temporary cache directory (tmp_path / "test-cache") |
| `test_db_path` | function | `Path` | Database path within test cache dir |
| `sample_tdocs` | function | `list[TDocMetadata]` | 3 representative TDoc records (RAN1, RAN2, SA4) |
| `sample_meetings` | function | `list[dict]` | 3 meeting dicts matching sample TDocs |
| `populated_db` | function | `TDocDatabase` | Pre-populated database with sample data |

**Location:**
- Shared fixtures: `tests/conftest.py`
- Package-specific fixtures: `tests/<package>/conftest.py` (e.g., `tests/convert_lo/conftest.py` for `example_docx_path`, `output_dir`)

## Coverage

**Requirements:** 70%+ target (stated in `docs/development.md`)

**Configuration (from `pyproject.toml`):**
```toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
skip_empty = true
```

**View Coverage:**
```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=tdoc_crawler --cov-report=html
```

## Test Types

**Unit Tests:**
- Most tests are unit tests — test individual functions, models, and classes in isolation
- Mock external dependencies (HTTP, subprocess)
- Use `tmp_path` for file I/O
- Example: `tests/test_models.py` tests Pydantic model creation and validation

**Integration Tests:**
- Marked with `@pytest.mark.integration` (registered in `pyproject.toml`)
- Require network access — skipped in CI by default
- Tests actual HTTP/portal interaction
- Run with `uv run pytest -v -m integration`

**Async Tests:**
- Use `@pytest.mark.asyncio` on test classes (or individual methods)
- Async fixtures use `asyncio.run()` internally in synchronous wrappers
- Database tests are async (pydantic-sqlite operations are async)

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
class TestTDocDatabase:
    async def test_database_initialization(self, test_db_path: Path) -> None:
        db = TDocDatabase(test_db_path)
        async with db:
            assert test_db_path.parent.exists()
```

**Error Testing:**
```python
def test_cache_manager_double_register_raises(self, tmp_path: Path) -> None:
    manager1 = CacheManager(tmp_path)
    manager1.register()
    manager2 = CacheManager(tmp_path / "other")
    with pytest.raises(RuntimeError, match="already registered"):
        manager2.register()
```

**Singleton Reset Pattern (in `setup_method` and shared fixture):**
```python
class TestCacheManager:
    def setup_method(self) -> None:
        """Reset CacheManager state before each test."""
        CacheManager._instance = None

# Also available as autouse fixture in conftest.py:
@pytest.fixture(autouse=True)
def _reset_cache_manager() -> None:
    CacheManager._instance = None
```

**Temporary Directory Pattern:**
```python
def test_cache_manager_creation(self, tmp_path: Path) -> None:
    manager = CacheManager(tmp_path)
    assert manager.root == tmp_path.resolve()
```

---

*Testing analysis: 2026-05-03*
