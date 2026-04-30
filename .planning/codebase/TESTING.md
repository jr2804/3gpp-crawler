# TESTING

Test framework, fixtures, mocking patterns, naming conventions, coverage requirements,
and execution commands for the 3gpp-crawler project.

## Test Framework

- **pytest 7.2+** -- single test framework for all testing.
- **pytest-asyncio** for async test support (@pytest.mark.asyncio).
- **pytest-cov** for coverage reporting.
- **Run with** `uv run pytest -v`.
- Configuration in pyproject.toml:
  - testpaths = ["tests"]
  - pythonpath = ["src"]
  - markers: integration (slower, requires network)

## Test Directory Structure

```
tests/
+-- conftest.py                    # Root fixtures
+-- test_cache_manager.py
+-- test_cli.py                    # CLI command tests (Typer CliRunner)
+-- test_database.py               # Database CRUD tests
+-- test_http_client.py            # HTTP session tests
+-- test_models.py                 # Model validation tests
+-- test_normalization.py          # Normalization function tests
+-- test_specs_database.py
+-- (18 more test_*.py files)
+-- convert_lo/
|   +-- conftest.py                # Subpackage fixtures
|   +-- test_converter.py
|   +-- test_integration.py
+-- config/
|   +-- test_export.py
|   +-- test_sources.py
+-- pool_executor/
    +-- test_executor_adapter.py
    +-- test_serial_executor.py
```

## Key Fixtures (tests/conftest.py)

All defined in tests/conftest.py. Import by name in test function signatures.

### test_cache_dir

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
```
- Creates tmp_path / "test-cache" directory.
- Sets TDC_CACHE_DIR env var for CLI tests.
- Isolates filesystem access.

### test_db_path

```python
@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
```
- Returns PathConfig(cache_dir=test_cache_dir).db_file within test cache.

### sample_tdocs

```python
@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
```
- Returns 3 TDocMetadata instances (R1-2301234, R2-2301567, S4-2301890).
- Used for database CRUD, query, and stats tests.

### sample_meetings

```python
@pytest.fixture
def sample_meetings() -> list[dict[str, object]]:
```
- Returns 3 meeting dicts (RAN1#98, RAN2#98, SA4#134).
- Keys: meeting_id, tbid, subtb, short_name, start_date, end_date, location, files_url.

### populated_db

```python
@pytest.fixture
def populated_db(...) -> TDocDatabase:
```
- Creates and populates a test database with sample meetings and TDocs.
- Returns TDocDatabase instance (not opened; caller uses async with).

### _reset_cache_manager (autouse)

```python
@pytest.fixture(autouse=True)
def _reset_cache_manager() -> None:
```
- Resets CacheManager._instance = None before each test.
- Prevents "CacheManager already registered" errors.

## Mocking Patterns

### unittest.mock (primary)

- from unittest.mock import MagicMock, AsyncMock, patch
- MagicMock for synchronous mocks, AsyncMock for async methods.
- @patch("module.path.ClassName") decorator for replacing implementations.
- Patch paths use import paths (where looked up), not definition paths.

### CLI Tests (Typer CliRunner)

```python
runner = CliRunner()

@patch("tdoc_crawler.cli.crawl.TDocCrawler")
@patch("tdoc_crawler.cli.crawl.TDocDatabase")
def test_crawl_basic(self, mock_db_class, mock_crawler_class, test_cache_dir):
    mock_db = MagicMock(spec=TDocDatabase)
    mock_db_class.return_value.__enter__.return_value = mock_db
    mock_crawler = MagicMock()
    mock_crawler_class.return_value = mock_crawler
    mock_crawler.crawl = AsyncMock(...)

    result = runner.invoke(tdoc_app, ["crawl", "--limit-tdocs", "10"])
    assert result.exit_code == 0
```

Key patterns:
- mock_db_class.return_value.__enter__.return_value = mock_db (sync ctx mgr)
- mock_db_class.return_value.__aenter__.return_value = mock_db (async ctx mgr)
- assert exit_code == 0 for success, == 1 for expected failures.

### Database Tests

Use real SQLite files (not mocks) for CRUD validation:

```python
@pytest.mark.asyncio
async def test_upsert_tdoc(self, test_db_path, sample_tdocs, sample_meetings):
    async with TDocDatabase(test_db_path) as db:
        created, changed = await db.upsert_tdoc(sample_tdocs[0])
        assert created is True
```

### HTTP Client Tests

Use unittest.mock.patch to mock network requests:
```python
with patch.object(session, "get") as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
```

### respx

Respx is NOT used. All HTTP mocking uses unittest.mock.patch.

## Test Naming Conventions

- **Files:** test_<module_name>.py (e.g., test_database.py, test_http_client.py).
- **Classes:** Test<ClassName> or Test<Feature> for grouping.
  - class TestTDocDatabase:
  - class TestCrawlCommand:
  - class TestNormalizeTdocId:
- **Methods:** test_<scenario> -- describes behavior being tested.
  - test_case_insensitive_query
  - test_upsert_tdoc
  - test_open_missing_tdoc
- **Free functions** (outside classes): def test_upsert_specification_roundtrip():

## Coverage Requirements

- **Target:** 70%+ overall coverage (docs/development.md).
- **Run:** `uv run pytest --cov=src --cov-report=term-missing`
- Coverage config in pyproject.toml:
  - branch = true
  - source = ["src"]
  - skip_empty = true
- No minimum enforcement in CI; coverage is a development guideline.

## Integration Tests

- Marked with @pytest.mark.integration.
- Slower tests requiring network access.
- Included in full run; or run only with `pytest -m integration`.

## Unit vs Integration Test Patterns

### Unit Tests
- Test a single function/class in isolation.
- Mock external dependencies (database, network, filesystem).
- Use test_cache_dir and tmp_path for filesystem isolation.
- Fast -- no network calls.

### Integration Tests
- Marked with @pytest.mark.integration.
- Test real HTTP requests (test_http_client.py).
- Real database CRUD with SQLite files.
- Test CLI commands end-to-end with mocked internals.

### Anti-Duplication

Do not re-implement src/ logic in tests/. Import production code directly:
```python
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.tdocs.models import TDocMetadata
```

If code is hard to test, refactor it in src/ rather than writing complex harnesses.

## Test Database Isolation

- Each test that needs a database uses test_cache_dir or tmp_path.
- populated_db fixture returns populated but unopened database.
- No shared state between tests.
- _reset_cache_manager autouse ensures clean singleton per test.

## Running Tests

| Action | Command |
|--------|---------|
| All tests | uv run pytest -v |
| Single file | uv run pytest tests/test_database.py -v |
| Coverage | uv run pytest --cov=src --cov-report=term-missing |
| Integration only | uv run pytest -m integration |
| Lint | ruff check src/ tests/ |