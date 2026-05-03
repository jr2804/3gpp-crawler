# Testing Patterns

**Analysis Date:** 2026-05-03

## Test Framework

**Runner:**
- pytest with pytest-asyncio
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`
- Python path: `["src"]` (enables `from tdoc_crawler.config import ...`)

**Assertion Library:**
- Plain `assert` statements (no `unittest.TestCase`)
- `pytest.raises()` for exception testing

**Run Commands:**
```bash
uv run pytest -v                                  # Run all tests
uv run pytest tests/test_file.py -v               # Run single file
uv run pytest tests/test_file.py::TestClass -v    # Run single class
uv run pytest --cov=src --cov-report=term-missing  # Coverage
```

**Custom Markers:**
- `@pytest.mark.asyncio` — Required for async test methods/classes
- `@pytest.mark.integration` — Marks integration tests (slower, requires network)

## Test File Organization

**Location:**
- Co-located in `tests/` directory at project root
- Sub-packages have their own test subdirectories:
  - `tests/convert_lo/` — Tests for the `convert-lo` workspace package
  - `tests/pool_executor/` — Tests for the `pool-executors` workspace package
  - `tests/config/` — Tests for configuration modules

**Naming:**
- Test files: `test_{module_name}.py` (e.g., `test_models.py`, `test_database.py`)
- Test classes: `Test{ComponentName}` (e.g., `TestTDocMetadata`, `TestCacheManager`)
- Test methods: `test_{behavior_description}` (e.g., `test_case_normalization`, `test_crawl_basic`)

**Structure:**
```
tests/
├── __init__.py
├── conftest.py                          # Root fixtures (autouse reset, DB, sample data)
├── test_cache_manager.py
├── test_cli.py
├── test_crawler.py
├── test_database.py
├── test_formatting.py
├── test_models.py
├── test_normalization.py
├── config/
│   ├── test_sources.py
│   └── test_export.py
├── convert_lo/
│   ├── __init__.py
│   ├── conftest.py                      # Package-specific fixtures
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   └── test_integration.py
└── pool_executor/
    ├── test_executor_adapter.py
    └── test_serial_executor.py
```

## Test Structure

**Suite Organization:**
```python
class TestTDocMetadata:
    """Tests for TDocMetadata model."""

    def test_creation(self) -> None:
        """Test creating TDocMetadata instance."""
        metadata = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=0,
            title="Test TDoc",
            ...
        )
        assert metadata.tdoc_id == "R1-2301234"

    def test_case_normalization(self) -> None:
        """Test TDoc ID case normalization to uppercase."""
        ...
```

**Patterns:**
- **Setup:** Use pytest fixtures (defined in `conftest.py` or test file)
- **Teardown:** Not needed — `tmp_path` auto-cleans, `_reset_cache_manager` autouse fixture resets singletons
- **Assertion:** Plain `assert` with descriptive error messages; `pytest.raises()` for expected exceptions

**Async Tests:**
```python
@pytest.mark.asyncio
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
```

## Fixtures

**Root `conftest.py` (`tests/conftest.py`):**

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `_reset_cache_manager` | `autouse` | Resets `CacheManager._instance = None` before each test |
| `test_cache_dir` | function | Creates `tmp_path / "test-cache"` directory |
| `test_db_path` | function | Returns `PathConfig(cache_dir=test_cache_dir).db_file` |
| `sample_tdocs` | function | Returns 3 `TDocMetadata` instances (R1, R2, S4) |
| `sample_meetings` | function | Returns 3 meeting dicts (RAN1#98, RAN2#98, SA4#134) |
| `populated_db` | function | Creates and populates `TDocDatabase` with sample data |

**Package `conftest.py` (`tests/convert_lo/conftest.py`):**

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `example_doc_path` | function | Path to legacy `.doc` example file |
| `example_docx_path` | function | Path to `.docx` example file |
| `output_dir` | function | Temporary output directory for conversions |

**Custom fixture naming:**
```python
@pytest.fixture(name="example_doc_path")
def fixture_example_doc_path() -> Path:
    """Return the legacy .doc example fixture path."""
    return Path(__file__).parent / "examples" / "example_legacy.doc"
```

**Important:** The `_reset_cache_manager` autouse fixture is critical. The CLI callback registers a CacheManager singleton on every invocation. Without resetting, the second test that invokes the CLI will fail with "CacheManager already registered".

## Mocking

**Framework:** `unittest.mock` (stdlib)

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

class TestCrawlCommand:
    @patch("tdoc_crawler.cli.crawl.TDocCrawler")
    @patch("tdoc_crawler.cli.crawl.TDocDatabase")
    def test_crawl_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=10, inserted=10, updated=0, errors=[]
            )
        )
        ...
```

**What to Mock:**
- Database classes (`TDocDatabase`, `MeetingDatabase`, `SpecDatabase`)
- Crawler classes (`TDocCrawler`, `MeetingCrawler`)
- External HTTP calls (via session mocks)
- File system operations (use `tmp_path` fixture instead when possible)

**What NOT to Mock:**
- Pydantic model validation — test it directly with real instances
- Normalization functions — test with actual inputs
- Configuration parsing — test with real config objects

**CLI Testing Pattern:**
```python
from typer.testing import CliRunner
from tdoc_crawler.cli import tdoc_app

runner = CliRunner()

result = runner.invoke(
    tdoc_app,
    ["--cache-dir", str(test_cache_dir), "crawl", "--limit-tdocs", "10"],
)
assert result.exit_code == 0
assert "Processed" in result.stdout
```

## Fixtures and Factories

**Test Data:**
```python
# Sample TDocMetadata creation in conftest.py
TDocMetadata(
    tdoc_id="R1-2301234",
    url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
    meeting_id=12345,
    file_size=256000,
    title="Sample RAN1 TDoc",
    source="Test Source",
    contact="Test Contact",
    tdoc_type="Discussion",
    for_purpose="Discussion",
    agenda_item_nbr=Version("7.1"),
    agenda_item_text="Test agenda item",
    status="approved",
    is_revision_of=None,
    date_created=datetime(2023, 1, 15, tzinfo=UTC),
    date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
    validated=False,
    validation_failed=False,
)
```

**Location:**
- Shared fixtures in `tests/conftest.py`
- Package-specific fixtures in `tests/{package}/conftest.py`
- Test-specific inline data in individual test files

## Coverage

**Requirements:** Branch coverage enabled; no enforced target percentage.

**Configuration:**
```toml
[tool.coverage.report]
skip_empty = true

[tool.coverage.run]
branch = true
source = ["src"]
```

**View Coverage:**
```bash
uv run pytest --cov=src --cov-report=term-missing
```

**Codecov:** `codecov.yaml` present at project root.

## Test Types

**Unit Tests:**
- Pure function testing (normalization, parsing, model validation)
- No external dependencies, fast execution
- Examples: `test_models.py`, `test_normalization.py`, `test_formatting.py`, `test_cache_manager.py`

**Integration Tests:**
- Database operations with real SQLite (in `tmp_path`)
- CLI command execution via `CliRunner`
- Examples: `test_database.py`, `test_cli.py`, `test_crawler.py`

**E2E Tests:**
- Not present in current test suite
- `demo.bat` serves as manual smoke test for full workflow

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_database_operation(self, test_db_path: Path) -> None:
    async with TDocDatabase(test_db_path) as db:
        result = await db.upsert_tdoc(metadata)
        assert result == (True, False)
```

**Error Testing:**
```python
def test_invalid_raises(self) -> None:
    with pytest.raises(ValueError, match="Unknown working group"):
        normalize_working_group_alias("XYZ")
```

**CLI Testing with Mocked Database:**
```python
@patch("tdoc_crawler.cli.crawl.TDocDatabase")
def test_query_no_results(self, mock_db_class: MagicMock, test_cache_dir: Path) -> None:
    mock_db = MagicMock(spec=TDocDatabase)
    mock_db_class.return_value.__aenter__.return_value = mock_db
    mock_db.query_tdocs = AsyncMock(return_value=[])

    result = runner.invoke(tdoc_app, ["--cache-dir", str(test_cache_dir), "query"])
    assert result.exit_code == 0
    assert "No TDocs found" in result.stdout
```

**Environment Variable Testing:**
```python
def test_env_var_workers(self, mock_db_class, mock_crawler_class, monkeypatch) -> None:
    monkeypatch.setenv("TDC_WORKERS", "8")
    result = runner.invoke(tdoc_app, ["crawl"])
    assert result.exit_code == 0
    # Verify parameter propagation
    call_args = mock_crawler.crawl.call_args[0]
    config = call_args[0]
    assert config.workers == 8
```

**Database Population Helper:**
```python
# In conftest.py — shared async helper for populating test databases
async def insert_sample_meetings_async(database: MeetingDatabase, meetings: list[dict[str, object]]) -> None:
    for meeting_dict in meetings:
        meeting_metadata = MeetingMetadata(...)
        _ = await database.upsert_meeting(meeting_metadata)

def insert_sample_meetings(database, meetings) -> None:
    asyncio.run(insert_sample_meetings_async(database, meetings))
```

**Test Collection Filtering:**
```python
# In conftest.py — skip legacy AI test directories
def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    path_text = str(collection_path).replace("\\", "/").lower()
    return "/tests/ai/" in path_text or path_text.endswith("/tests/ai")
```

## Best Practices

- **Test isolation:** Each test independent; `autouse` fixture resets singletons
- **Descriptive names:** Class `Test{Component}`, method `test_{behavior}`
- **Minimal assertions:** One specific behavior per test method
- **Mock external systems:** Isolate tests from network and filesystem via `@patch` and `tmp_path`
- **Anti-duplication:** Do not re-implement logic from `src/` in `tests/`. Import and verify actual implementation
- **Coverage target:** >90% for workspace packages (`pool_executors`, `convert-lo`)

---

*Testing analysis: 2026-05-03*
