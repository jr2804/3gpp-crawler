# Testing Patterns

**Analysis Date:** 2026-05-22

## Test Framework

**Runner:**
- pytest (dev dependency, `pytest>=7.2.0`)
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- pythonpath: `["src"]`
- testpaths: `["tests"]`
- Custom markers: `integration` — marks slower tests requiring network

**Assertion Library:**
- Plain `assert` statements (pytest style)
- `pytest.raises()` for exception testing

**Async Support:**
- `pytest-asyncio>=1.2.0` (dev dependency)
- Mark async test classes with `@pytest.mark.asyncio`
- Async test methods: `async def test_...()`

**Run Commands:**
```bash
uv run pytest -v                        # Run all tests
uv run pytest tests/test_file.py -v     # Run single file
uv run pytest --cov=src --cov-report=term-missing  # Coverage
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing  # Subpackage coverage
```

## Test File Organization

**Location:**
- All tests in `tests/` directory (not co-located with source)
- Subdirectory mirrors for subpackages: `tests/convert_lo/`, `tests/pool_executor/`, `tests/config/`

**Naming:**
- Test files: `test_<module>.py` (e.g., `test_database.py`, `test_models.py`, `test_cache_manager.py`)
- Test classes: `Test<Feature>` (e.g., `TestTDocDatabase`, `TestWorkspaceModels`)
- Test methods: `test_<behavior_description>` (e.g., `test_case_insensitive_query`)

**Structure:**
```
tests/
├── conftest.py                    # Global fixtures
├── config/                        # Config subpackage tests
│   └── test_export.py
├── convert_lo/                    # convert-lo subpackage tests
│   ├── conftest.py                # Package-local fixtures
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   ├── test_integration.py
│   ├── test_formats.py
│   └── test_locator.py
├── data/                          # Test data files
├── pool_executor/                 # Pool executor subpackage tests
│   ├── test_executor_adapter.py
│   └── test_serial_executor.py
├── test_cache_manager.py
├── test_database.py
├── test_models.py
├── test_workspaces.py
└── ... (other test modules)
```

## Test Structure

**Suite Organization:**
```python
@pytest.mark.asyncio
class TestTDocDatabase:
    """Tests for TDocDatabase class."""

    async def test_database_initialization(self, test_db_path: Path) -> None:
        """Initialize database and create schema."""
        db = TDocDatabase(test_db_path)
        async with db:
            assert test_db_path.parent.exists()
        assert test_db_path.exists()

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
- Setup: Use pytest fixtures (injected via parameters), not `setUp()` methods
- Rare `setup_method()` only for singleton resets: `CacheManager._instance = None`
- Teardown: Handled by fixture cleanup and `tmp_path` auto-cleanup
- Assertions: Plain `assert` with descriptive failure messages via pytest rewriting

## Fixtures

**Global Fixtures** (`tests/conftest.py`):

| Fixture | Purpose | Scope |
|---------|---------|-------|
| `_reset_cache_manager` | Reset `CacheManager` singleton before each test (autouse) | function |
| `test_cache_dir` | Temporary cache directory + sets `TDC_CACHE_DIR` env var | function |
| `test_db_path` | Path to test database within `test_cache_dir` | function |
| `sample_tdocs` | Three sample `TDocMetadata` instances (RAN1, RAN2, SA4) | function |
| `sample_meetings` | Three sample meeting dictionaries (RAN1, RAN2, SA4) | function |
| `populated_db` | Pre-populated `TDocDatabase` instance | function |

**Package-Local Fixtures** (`tests/convert_lo/conftest.py`):

| Fixture | Purpose |
|---------|---------|
| `example_doc_path` | Path to legacy `.doc` example file |
| `example_docx_path` | Path to `.docx` example file |
| `output_dir` | Temporary output directory for conversions |

**Fixture Patterns:**
```python
@pytest.fixture
def test_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary cache directory for tests."""
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TDC_CACHE_DIR", str(cache_dir))
    return cache_dir
```

- Use `tmp_path` for file system isolation
- Use `monkeypatch.setenv()` for environment variable overrides
- Use named fixtures with `@pytest.fixture(name="...")` for clarity in sub-conftests
- Reset singletons in `setup_method()` or autouse fixtures

## Mocking

**Framework:** `unittest.mock` (stdlib)

**Patterns:**
```python
from unittest.mock import patch

# Patch external dependencies
with patch(
    "tdoc_crawler.cli.workspace.process.resolve_spec_release_from_db",
    return_value=("19.0.0", []),
):
    result = _effective_source_id(member)

# Patch to raise exceptions
with patch(
    "tdoc_crawler.cli.workspace.process.resolve_spec_release_from_db",
    side_effect=RuntimeError("DB connection failed"),
):
    result = _effective_source_id(member)
```

**What to Mock:**
- Database lookups for unit tests: `resolve_spec_release_from_db`
- External HTTP services
- File system dependencies where slow or non-deterministic

**What NOT to Mock:**
- Database operations in integration tests (use in-memory SQLite with `test_db_path`)
- Model construction and validation
- Pure logic functions (normalization, parsing)

## Fixtures and Factories

**Test Data:**
```python
# TDocMetadata construction (direct model instantiation)
TDocMetadata(
    tdoc_id="R1-2301234",
    tbid=373,
    url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
    meeting_id=12345,
    file_size=256000,
    title="Sample RAN1 TDoc",
    source="Test Source",
    contact="Test Contact",
    tdoc_type="Discussion",
    for_purpose="Discussion",
    agenda_item_nbr="7.1",
    agenda_item_text="Test agenda item",
    status="approved",
    is_revision_of="",
    date_created=datetime(2023, 1, 15, tzinfo=UTC),
    date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
    validated=False,
    validation_failed=False,
)
```

**Location:**
- Shared fixtures in `tests/conftest.py`
- Subpackage fixtures in `tests/<package>/conftest.py`
- Test data files in `tests/data/`
- Example documents in `tests/convert_lo/examples/`

## Coverage

**Requirements:** 90% target (configured in `codecov.yaml`)

**Configuration:**
- `pyproject.toml` `[tool.coverage.run]`: branch coverage enabled, source `["src"]`
- `pyproject.toml` `[tool.coverage.report]`: skip empty files
- `codecov.yaml`: range 70-100%, target 90%, threshold 0.5%

**View Coverage:**
```bash
uv run pytest --cov=src --cov-report=term-missing
```

**CI:**
- tox configured with coverage + XML report: `uv run python -m pytest --doctest-modules tests --cov --cov-config=pyproject.toml --cov-report=xml`
- ty type checking also runs in tox: `ty check`

## Test Types

**Unit Tests:**
- Scope: Individual functions, methods, model construction, normalization
- Examples: `test_models.py` (WorkingGroup, SubWorkingGroup, config models), `test_normalization.py`, `test_cache_manager.py`
- Approach: Direct function calls, model instantiation, enum validation

**Integration Tests:**
- Scope: Database CRUD operations, workspace lifecycle, HTTP client
- Mark with `@pytest.mark.integration` (requires network)
- Examples: `test_database.py` (async DB operations), `test_workspaces.py` (workspace CRUD with registry)
- Approach: In-memory/temporary SQLite via `test_db_path` fixture, async context managers

**E2E Tests:**
- Not formally structured
- `demo.bat` serves as a smoke test script for CLI commands
- Integration tests with `@pytest.mark.integration` cover network-dependent scenarios

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
class TestTDocDatabase:
    async def test_database_initialization(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as db:
            assert db.connection is not None
```

**Error Testing:**
```python
# Expected exceptions
with pytest.raises(ValueError, match="workspace_name must not be empty"):
    Workspace(workspace_name="")

with pytest.raises(DatabaseError):
    _ = db.connection  # outside context manager
```

**Regression Testing:**
```python
class TestSpecSourceDirNaming:
    """Regression: spec source dirs MUST include -REL suffix."""

    def test_spec_with_rel_suffix_unchanged(self) -> None:
        """Spec IDs that already have -REL must pass through unchanged."""
        assert _resolve_spec_source_id("26260-REL18.0.0") == "26260-REL18.0.0"
```

**Singleton Reset Pattern:**
```python
# In conftest.py (autouse)
@pytest.fixture(autouse=True)
def _reset_cache_manager() -> None:
    CacheManager._instance = None

# Or in setup_method
def setup_method(self) -> None:
    CacheManager._instance = None
```

**Private Helper Pattern in Tests:**
```python
class TestTDocDatabase:
    @staticmethod
    async def _insert_sample_meetings(database: TDocDatabase, meetings: list[dict]) -> None:
        """Helper to insert sample meetings for test setup."""
        ...
```

---

*Testing analysis: 2026-05-22*
