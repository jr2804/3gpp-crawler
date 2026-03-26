# Testing Patterns

**Analysis Date:** 2026-03-26

## Test Framework

**Runner:**
- pytest 7.2.0+
- Config: `pyproject.toml` → `[tool.pytest.ini_options]`
- Async support: `pytest-asyncio>=1.2.0`
- Coverage: `pytest-cov>=4.0.0`

**Assertion Library:**
- Built-in pytest assertions
- Pydantic model validation

**Run Commands:**
```bash
uv run pytest -v                           # Run all tests (~2m)
uv run pytest tests/test_file.py -v        # Run single file (~5s)
uv run pytest --cov=src --cov-report=term-missing  # Coverage (~2m)
uv run pytest -m integration               # Integration tests only
uv run pytest -m "not integration"         # Skip integration tests
```

## Test File Organization

**Location:**
- Co-located in `tests/` directory at project root
- Subdirectories mirror source structure

**Naming:**
- Pattern: `test_<module_name>.py`
- Examples: `test_crawler.py`, `test_http_client.py`, `test_cli.py`

**Structure:**
```
tests/
├── conftest.py              # Shared fixtures (test_db_path, sample_tdocs, etc.)
├── AGENTS.md               # Test-specific guidelines
├── data/                   # Test data files (downloaded/generated)
├── ai/                     # AI module tests
│   ├── conftest.py         # AI-specific fixtures
│   ├── test_ai_embeddings.py
│   ├── test_ai_pipeline.py
│   ├── test_ai_storage.py
│   └── ...
├── convert_lo/             # LibreOffice conversion tests
│   ├── conftest.py
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   ├── test_formats.py
│   ├── test_locator.py
│   └── test_integration.py
├── pool_executor/          # Pool executor tests (>90% coverage required)
│   ├── test_executor_adapter.py
│   └── test_serial_executor.py
├── test_crawler.py         # Core crawler tests
├── test_cli.py             # CLI command tests
├── test_database.py        # Database layer tests
├── test_models.py          # Pydantic model tests
├── test_http_client.py     # HTTP client tests
├── test_portal_*.py        # Portal authentication tests
├── test_specs_*.py         # Specification tests
└── test_*.py               # Other tests
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

## Test Structure

**Suite Organization:**
```python
class TestTDocCrawler:
    """Tests for TDocCrawler class."""

    def test_crawler_initialization(self, test_db_path: Path) -> None:
        """Ensure crawler stores the provided database instance."""
        with TDocDatabase(test_db_path) as database:
            crawler = TDocCrawler(database)
            assert crawler.database is database

    @patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
    def test_crawl_connection_failure(self, mock_fetch: MagicMock, test_db_path: Path) -> None:
        """Handle document list fetch failures gracefully."""
        mock_fetch.side_effect = OSError("Connection refused")
        ...
        assert result.errors  # Verify error was recorded
```

**Patterns:**
- **Setup:** Use fixtures from `conftest.py`
- **Teardown:** Context managers (`with TDocDatabase(...) as db:`)
- **Assertion:** Direct assertions + Pydantic validation

## Fixtures and Factories

### Core Fixtures (`tests/conftest.py`)

| Fixture | Purpose | Scope |
|---------|---------|-------|
| `test_cache_dir` | Temporary cache directory | function |
| `test_db_path` | Path to test database | function |
| `sample_tdocs` | Sample TDoc metadata list | function |
| `sample_meetings` | Sample meeting data list | function |
| `populated_db` | Pre-populated TDocDatabase | function |

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory for tests."""
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)
    return cache_dir

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
            ...
        ),
    ]
```

### AI Module Fixtures (`tests/ai/conftest.py`)

| Fixture | Purpose | Scope |
|---------|---------|-------|
| `test_data_dir` | AI test data directory | session |
| `mock_storage` | Mock storage object | function |
| `runner` | Typer CLI runner | function |
| `ai_storage` | Temporary AI storage | function |
| `test_workspace` | Test workspace name | function |

### Convert-LO Fixtures (`tests/convert_lo/conftest.py`)

| Fixture | Purpose |
|---------|---------|
| `example_doc_path` | Path to example .doc file |
| `example_docx_path` | Path to example .docx file |
| `example_small_docx_path` | Path to small .docx for quick tests |
| `example_medium_docx_path` | Path to medium .docx for load tests |
| `output_dir` | Temporary output directory |

## Mocking

**Framework:** `unittest.mock` (MagicMock, patch)

**Patterns:**
```python
from unittest.mock import MagicMock, patch

# Patch decorator
@patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
def test_crawl_collects_tdocs(self, mock_fetch: MagicMock, test_db_path: Path) -> None:
    tdoc = TDocMetadata(...)
    mock_fetch.return_value = json.dumps([tdoc.model_dump_json()])
    ...
    mock_crawler.crawl.assert_called_once()

# Side effect for errors
@patch("tdoc_crawler.http_client.create_cached_session")
def test_connection_failure(self, mock_session: MagicMock) -> None:
    mock_session.side_effect = OSError("Connection refused")
    ...

# Patch object
def test_with_patch_object(self) -> None:
    with patch.object(SomeClass, 'method', return_value=42):
        ...
```

**What to Mock:**
- External HTTP requests
- File system operations (when testing business logic)
- Database operations (when testing isolated logic)
- External services (LLM APIs, embedding models)

**What NOT to Mock:**
- Internal business logic (test it directly)
- Pydantic model validation (test with real models)
- Database queries (use test database)

## Coverage

**Configuration:**
```toml
[tool.coverage.report]
skip_empty = true

[tool.coverage.run]
branch = true
source = ["src"]
```

**Requirements:**
- **pool_executors**: >90% coverage required
- **Core modules**: High coverage expected
- **AI module**: Integration tests may have lower coverage

**View Coverage:**
```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

## Test Types

### Unit Tests
- Fast, isolated tests
- Mock external dependencies
- Test individual functions/methods
- Examples: `test_crawler.py`, `test_models.py`

### Integration Tests
- Marked with `@pytest.mark.integration`
- Slower, may require network
- Test component interactions
- Example: `tests/convert_lo/test_integration.py`

```python
@pytest.mark.integration
def test_fetch_meeting_document_list_network_error(self) -> None:
    """Test against real 3GPP FTP server."""
    ...
```

### CLI/E2E Tests
- Use Typer's `CliRunner`
- Full command execution
- Examples: `test_cli.py`, `test_new_cli_flags.py`

```python
from typer.testing import CliRunner

def test_crawl_basic(self, mock_db_class: MagicMock, test_cache_dir: Path) -> None:
    result = runner.invoke(app, ["crawl-tdocs", "--cache-dir", str(test_cache_dir)])
    assert result.exit_code == 0
    assert "Processed" in result.stdout
```

### Skipped Tests
```python
@pytest.mark.skip(reason="Requires sentence-transformers")
def test_vector_dimensions_match_model(self) -> None:
    ...

@pytest.mark.skip(reason="Legacy pipeline removed; tests retained as historical reference.")
def test_pipeline_removed(self) -> None:
    ...
```

## Test Marks

| Mark | Usage |
|------|-------|
| `@pytest.mark.integration` | Slow/network-dependent tests |
| `@pytest.mark.skip(reason="...")` | Skip test with reason |
| `@pytest.mark.parametrize(...)` | Data-driven tests |

**Parametrize Example:**
```python
@pytest.mark.parametrize("format_value", list(LibreOfficeFormat))
def test_libreoffice_format_values(self, format_value: LibreOfficeFormat) -> None:
    assert isinstance(format_value.value, str)
```

## Test Discovery Control

**AI Test Collection:**
```python
# tests/conftest.py
def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    """Ignore AI tests when 3gpp-ai package is unavailable."""
    path_text = str(collection_path).replace("\\", "/").lower()
    return "/tests/ai/" in path_text or path_text.endswith("/tests/ai")
```

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:

| Hook | Version | Purpose |
|------|---------|---------|
| check-case-conflict | v5.0.0 | Prevent case-sensitivity issues |
| check-merge-conflict | v5.0.0 | Detect merge conflict markers |
| check-toml/yaml/json | v5.0.0 | Validate config files |
| pretty-format-json | v5.0.0 | Format JSON (--autofix) |
| end-of-file-fixer | v5.0.0 | Ensure newline at EOF |
| trailing-whitespace | v5.0.0 | Remove trailing spaces |
| ruff-check | v0.12.7 | Lint Python files |
| ruff-format | v0.12.7 | Format Python files |
| undersort | local | Sort `__all__` exports |

## CI/CD Pipeline

**No GitHub Actions:** `.github/workflows/` directory does not exist

**tox.ini:** Multi-version testing configuration
```ini
[tox]
skipsdist = true
envlist = py39, py310, py311, py312, py313

[gh-actions]
python =
    3.9: py39
    3.10: py310
    3.11: py311
    3.12: py312
    3.13: py313

[testenv]
passenv = PYTHON_VERSION
allowlist_externals = uv
commands =
    uv sync --python {envpython}
    uv run python -m pytest --doctest-modules tests --cov --cov-config=pyproject.toml --cov-report=xml
    ty check
```

## Best Practices (from tests/AGENTS.md)

1. **Test isolation:** Each test independent - use fixtures, never shared state
2. **Descriptive names:** Test names describe expected behavior
3. **Minimal assertions:** One specific behavior per test
4. **Mock external systems:** Isolate from network, file system, external services
5. **Document edge cases:** Test error conditions and boundary cases

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

**Test Files:**
- `test_executor_adapter.py`: Tests for `Runner` class
- `test_serial_executor.py`: Tests for `SerialPoolExecutor`, `SerialFuture`, `create_executor`

## Debugging Failed Tests

```bash
# Verbose output with full diffs
uv run pytest tests/test_crawler.py -v --tb=long

# Stop on first failure
uv run pytest tests/ -x

# Run specific test
uv run pytest tests/test_crawler.py::TestTDocCrawler::test_crawler_initialization -v

# Show print statements
uv run pytest tests/test_crawler.py -v -s
```

## Common Patterns

### Database Testing
```python
def test_database_operations(test_db_path: Path) -> None:
    """Test database CRUD operations."""
    with TDocDatabase(test_db_path) as database:
        meeting = _create_test_meeting()
        result = database.upsert_meeting(meeting)
        assert result == 1  # Inserted
```

### Error Testing
```python
def test_crawl_connection_failure(self, mock_fetch: MagicMock, test_db_path: Path) -> None:
    """Handle document list fetch failures gracefully."""
    mock_fetch.side_effect = OSError("Connection refused")
    ...
    assert result.errors  # Verify error was recorded
```

### CLI Testing
```python
from typer.testing import CliRunner

runner = CliRunner()

def test_command(self) -> None:
    result = runner.invoke(app, ["command", "--flag", "value"])
    assert result.exit_code == 0
    assert "Expected output" in result.stdout
```

---

*Testing analysis: 2026-03-26*
