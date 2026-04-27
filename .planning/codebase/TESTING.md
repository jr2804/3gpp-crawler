# Testing Patterns

**Analysis Date:** 2026-04-27

## Test Framework

**Runner:**

- `pytest` (declared in `pyproject.toml` as `pytest>=7.2.0`)
- Config: `pyproject.toml` (`[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["src"]`, custom `integration` marker)

**Assertion Library:**

- Native `pytest` assertions (`assert ...`) and `pytest.raises(...)`

**Run Commands:**

```bash
uv run pytest -v                                   # Run default test suite
uv run pytest tests/test_http_client.py -v         # Run a single file
uv run pytest --cov=src --cov-report=term-missing  # Coverage report
```

## Test File Organization

**Location:**

- Separate `tests/` tree with domain-focused subdirectories (`tests/config/`, `tests/convert_lo/`, `tests/pool_executor/`, `tests/ai/`)

**Naming:**

- `test_*.py` files (`tests/test_crawler.py`, `tests/test_cli.py`)
- class suites use `Test*` (`TestTDocCrawler`, `TestCreateCachedSession`)

**Structure:**

```
tests/
├── conftest.py
├── test_*.py
├── config/test_*.py
├── convert_lo/test_*.py
├── pool_executor/test_*.py
└── ai/test_*.py
```

## Test Structure

**Suite Organization:**

```python
class TestTDocCrawler:
    @pytest.mark.asyncio
    async def test_crawler_initialization(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            crawler = TDocCrawler(database)
            assert crawler.database is database
```

**Patterns:**

- Setup pattern: shared fixtures in `tests/conftest.py` (`test_cache_dir`, `test_db_path`, `sample_tdocs`, `sample_meetings`)
- Teardown pattern: resource cleanup is mainly context-managed (`async with ...`, `session.close()`) rather than explicit fixture teardown blocks
- Assertion pattern: direct state checks (`assert result.inserted == 1`, `assert cache_db.exists()`)

## Mocking

**Framework:**

- `unittest.mock.patch` and `MagicMock`
- `pytest` `monkeypatch` fixture for environment and attribute overrides

**Patterns:**

```python
@patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
@pytest.mark.asyncio
async def test_crawl_connection_failure(mock_fetch: MagicMock, test_db_path: Path) -> None:
    mock_fetch.side_effect = OSError("Connection refused")
```

```python
def test_existing_env_vars_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TDC_CACHE_DIR", "...")
```

**What to Mock:**

- external boundaries: network fetchers, portal auth, subprocesses, CLI dependencies (`tests/test_crawler.py`, `tests/test_cli.py`, `tests/convert_lo/test_hybrid_converter.py`)

**What NOT to Mock:**

- domain model behavior and normalization/parsing logic where deterministic local assertions are feasible (`tests/test_normalization.py`, parser tests in `tests/test_crawler.py`)

## Fixtures and Factories

**Test Data:**

```python
@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    return [TDocMetadata(...), ...]
```

**Location:**

- shared fixtures in `tests/conftest.py`
- static fixture assets under `tests/data/`

## Coverage

**Requirements:**

- Project target: 90% (`codecov.yaml`)
- Branch coverage enabled (`pyproject.toml` -> `[tool.coverage.run] branch = true`)
- Additional strict expectation for pool executor tests documented in `tests/AGENTS.md` (>90%)

**View Coverage:**

```bash
uv run pytest --cov=src --cov-report=term-missing
```

## Test Types

**Unit Tests:**

- dominant mode; isolated behavior checks with in-memory/temp-path resources and mocks (`tests/test_http_client.py`, `tests/test_cache_manager.py`)

**Integration Tests:**

- explicitly marked with `@pytest.mark.integration` for networked behavior (`tests/test_http_client.py`)
- selected via marker expression from pytest config

**E2E Tests:**

- Not detected as a dedicated browser/system E2E suite.

## Common Patterns

**Async Testing:**

```python
@pytest.mark.asyncio
async def test_crawl_collects_tdocs(test_db_path: Path) -> None:
    async with TDocDatabase(test_db_path) as database:
        ...
```

**Error Testing:**

```python
with pytest.raises(ValueError, match="unsupported-url-scheme"):
    download_to_file("file://example", target_file)
```

Additional repository-specific pattern:

- core `tdoc_crawler` test run excludes `tests/ai/` using `pytest_ignore_collect(...)` in `tests/conftest.py`; AI tests are executed separately when needed.

---

*Testing analysis: 2026-04-27*
