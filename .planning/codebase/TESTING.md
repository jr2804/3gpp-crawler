# Testing Patterns

**Analysis Date:** 2026-03-27

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
uv run pytest -v                                        # Run all tests (~2m)
uv run pytest tests/test_file.py -v                     # Run single file (~5s)
uv run pytest --cov=src --cov-report=term-missing       # Coverage report (~2m)
uv run pytest -m integration                            # Integration tests only
uv run pytest -m "not integration"                      # Skip integration tests
uv run pytest tests/pool_executor/ -v                   # Pool executor tests
uv run pytest tests/convert_lo/ -v                      # Convert-LO tests
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

**Key config details:**

- `testpaths = ["tests"]` — all tests live in `tests/`
- `pythonpath = ["src"]` — enables `from tdoc_crawler.*` without sys.path manipulation
- `@pytest.mark.integration` — marks slow/network-dependent tests

## Test File Organization

**Location:** Co-located in `tests/` at project root, subdirectories mirror source structure

**Naming:** `test_<module_name>.py`

**Directory layout:**

```
tests/
├── __init__.py
├── AGENTS.md                      # Test-specific guidelines
├── conftest.py                    # Root-level shared fixtures
├── data/                          # Test data files (downloaded/generated)
├── ai/                            # AI module tests (conditional collection)
│   ├── conftest.py                # AI-specific fixtures + skip logic
│   ├── test_ai_embeddings.py      # Embedding tests (some placeholders)
│   ├── test_ai_classification.py
│   ├── test_ai_workspaces.py
│   ├── test_ai_extraction_artifacts.py
│   ├── test_chunking.py
│   ├── test_cli_aggregator.py
│   ├── test_metadata.py
│   ├── test_operations_metrics.py
│   ├── test_figure_descriptor.py
│   ├── test_lightrag_config.py
│   ├── test_extraction_elements.py
│   └── test_integration.py
├── convert_lo/                    # LibreOffice conversion tests
│   ├── __init__.py
│   ├── conftest.py                # Document fixtures (doc, docx, output_dir)
│   ├── test_converter.py
│   ├── test_hybrid_converter.py
│   ├── test_formats.py
│   ├── test_locator.py
│   ├── examples/                  # Test document fixtures
│   └── test_integration.py
├── pool_executor/                 # Pool executor tests (>90% coverage required)
│   ├── test_executor_adapter.py
│   └── test_serial_executor.py
├── test_crawler.py                # Core crawler tests
├── test_cli.py                    # CLI command tests (919 lines — largest test file)
├── test_new_cli_flags.py          # New CLI flag tests
├── test_database.py               # Database layer tests
├── test_models.py                 # Pydantic model tests
├── test_http_client.py            # HTTP client/caching tests
├── test_portal_auth.py            # Portal authentication tests
├── test_portal_client.py          # Portal client tests
├── test_specs_normalization.py    # Spec number normalization tests
├── test_specs_downloads.py        # Spec download tests
├── test_specs_database.py         # Spec database tests
├── test_specs_sources.py          # Spec source tests
├── test_specs_cli.py              # Spec CLI tests
├── test_meeting_document_list.py  # Meeting document list tests
├── test_whatthespec.py            # WhatTheSpec API tests
├── test_checkout.py               # TDoc checkout tests
└── test_targeted_fetch.py         # Targeted fetch tests
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
    def test_crawl_connection_failure(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Handle document list fetch failures gracefully."""
        mock_fetch.side_effect = OSError("Connection refused")
        ...
        assert result.errors
```

**Test naming convention:**

- `test_<method>_<behavior>`: `test_crawl_connection_failure`, `test_case_insensitive_query`
- Descriptive docstrings explaining expected behavior
- One specific behavior per test

**Patterns:**

- **Setup:** Fixtures from `conftest.py` (never shared mutable state between tests)
- **Teardown:** Context managers (`with TDocDatabase(...) as db:`) and `tmp_path` auto-cleanup
- **Assertions:** Direct assertions + Pydantic model validation

## Fixtures and Factories

### Root Fixtures (`tests/conftest.py`)

| Fixture | Type | Purpose |
|---------|------|---------|
| `test_cache_dir(tmp_path)` | Path | Creates `tmp_path/test-cache/`, registers `CacheManager` with `force=True` |
| `test_db_path(test_cache_dir)` | Path | Returns `resolve_cache_manager().db_file` |
| `sample_tdocs` | list[TDocMetadata] | 3 pre-built TDoc entries (R1, R2, S4) with realistic data |
| `sample_meetings` | list[dict] | 3 meeting dicts (RAN1#98, RAN2#98, SA4#134) |
| `populated_db` | TDocDatabase | Pre-populated database with meetings + TDocs |

**CacheManager registration pattern (critical):**

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory for tests."""
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)
    return cache_dir
```

**Module-level fallback registration:**

```python
# At end of tests/conftest.py — ensures AiConfig.from_env() works
# for tests that don't explicitly use test_cache_dir fixture
_cache_manager = CacheManager(ensure_paths=False, name="default")
_cache_manager.register(force=True)
```

**Helper function for DB population:**

```python
def insert_sample_meetings(
    database: MeetingDatabase,
    meetings: list[dict[str, object]],
) -> None:
    """Insert sample meetings using the proper database API."""
    for meeting_dict in meetings:
        meeting_metadata = MeetingMetadata(...)
        database.upsert_meeting(meeting_metadata)
```

**Module-level helper for test data creation:**

```python
def _create_test_meeting() -> MeetingMetadata:
    """Create a reusable test meeting."""
    return MeetingMetadata(
        meeting_id=12345,
        tbid=373,
        subtb=379,
        short_name="RAN1#98",
        ...
    )
```

### AI Module Fixtures (`tests/ai/conftest.py`)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `_require_tdoc_ai` (autouse) | function | Skip all AI tests when 3gpp-ai not installed |
| `test_data_dir` | session | Path to `tests/ai/data/`, auto-downloads test ZIPs from 3GPP FTP |
| `mock_storage` | function | MagicMock with stubbed `get_status`, `query_graph` |
| `runner` | function | Typer `CliRunner` instance for AI CLI tests |
| `reset_ai_service_container` (autouse) | function | No-op (backward compat after singleton removal) |

**Conditional test collection:**

```python
# tests/ai/conftest.py
_TDOC_AI_AVAILABLE = True
try:
    from threegpp_ai.config import AiConfig
except ModuleNotFoundError:
    _TDOC_AI_AVAILABLE = False

@pytest.fixture(autouse=True)
def _require_tdoc_ai() -> None:
    if not _TDOC_AI_AVAILABLE:
        pytest.skip("3gpp-ai not installed")

def pytest_ignore_collect(collection_path, config):
    return not _TDOC_AI_AVAILABLE
```

**Root-level AI collection suppression:**

```python
# tests/conftest.py — prevents double-collection
def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    path_text = str(collection_path).replace("\\", "/").lower()
    return "/tests/ai/" in path_text or path_text.endswith("/tests/ai")
```

**Kreuzberg mock (optional dependency):**

```python
kreuzberg_mock = MagicMock()
sys.modules["kreuzberg"] = kreuzberg_mock
```

### Convert-LO Fixtures (`tests/convert_lo/conftest.py`)

| Fixture | Purpose |
|---------|---------|
| `example_doc_path` | Legacy `.doc` from `tests/convert_lo/examples/` |
| `example_docx_path` | Default `.docx` (medium size) |
| `example_small_docx_path` | Small `.docx` for quick tests |
| `example_medium_docx_path` | Modern `.docx` for load tests |
| `output_dir(tmp_path)` | Temporary output directory |

Named fixtures use `@pytest.fixture(name="example_doc_path")` for explicit naming.

### Portal Auth Fixtures (`tests/test_portal_auth.py`)

| Fixture | Purpose |
|---------|---------|
| `credentials` | Loads from env vars (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`); skips if missing |
| `check_internet` (autouse) | Skips all tests in file if no internet |

## Mocking

**Framework:** `unittest.mock` (MagicMock, patch)

### Patterns

**Patch decorator (most common):**

```python
@patch("tdoc_crawler.tdocs.operations.crawl.fetch_meeting_document_list_subinterpreter")
def test_crawl_collects_tdocs(
    self,
    mock_fetch: MagicMock,
    test_db_path: Path,
) -> None:
    mock_fetch.return_value = json.dumps([tdoc.model_dump_json()])
    ...
    mock_crawler.crawl.assert_called_once()
```

**Side effects for errors:**

```python
mock_fetch.side_effect = OSError("Connection refused")
```

**Patch object (inline):**

```python
with patch.object(session, "get") as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    session.get("http://example.com")
```

**Environment variable mocking:**

```python
with patch.dict(os.environ, {"HTTP_CACHE_TTL": "3600", "HTTP_CACHE_REFRESH_ON_ACCESS": "false"}):
    config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=1800)
```

**CLI command mocking:**

```python
@patch("tdoc_crawler.cli.crawl.TDocCrawler")
@patch("tdoc_crawler.cli.crawl.TDocDatabase")
def test_crawl_basic(self, mock_db_class: MagicMock, mock_crawler_class: MagicMock, ...) -> None:
    mock_db = MagicMock(spec=TDocDatabase)
    mock_db_class.return_value.__enter__.return_value = mock_db
```

**What to Mock:**

- External HTTP requests (portal, WhatTheSpec, 3GPP FTP)
- File system operations when testing business logic
- Database in CLI tests (mock the DB class, not the real DB)
- External services (LLM APIs, embedding models, kreuzberg)
- Subinterpreter calls (`fetch_meeting_document_list_subinterpreter`)

**What NOT to Mock:**

- Internal business logic — test directly
- Pydantic model validation — use real models
- Database queries in database tests — use real SQLite via `test_db_path`
- TDoc/Meeting normalization functions — test directly

## Coverage

**Configuration (from `pyproject.toml`):**

```toml
[tool.coverage.report]
skip_empty = true

[tool.coverage.run]
branch = true
source = ["src"]
```

**Requirements:**

- **pool_executors**: >90% code coverage required (from `tests/AGENTS.md`)
- **Core modules**: High coverage expected
- **AI module**: Integration tests may have lower coverage; some test files contain placeholders

**Run coverage:**

```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

## Test Types

### Unit Tests

- Fast, isolated tests with mocked dependencies
- Test individual functions, methods, models
- Examples: `test_crawler.py`, `test_models.py`, `test_http_client.py`
- Test normalization: `test_specs_normalization.py` (318 lines, exhaustive parameterized variants)

### Integration Tests

- Marked with `@pytest.mark.integration`
- Slower, may require network access
- Skip gracefully on failure: `pytest.skip(f"Network request failed: {e}")`
- Examples: `tests/convert_lo/test_integration.py`, HTTP caching tests in `test_http_client.py`

```python
@pytest.mark.integration
def test_caching_works_with_real_request(self, test_cache_dir: Path) -> None:
    try:
        response1 = session.get("https://httpbin.org/get", timeout=10)
        ...
    except requests.RequestException as e:
        pytest.skip(f"Network request failed: {e}")
```

### CLI Tests

- Use Typer's `CliRunner`: `runner = CliRunner()`
- Full command execution with string arguments
- Verify exit code and stdout
- Largest test file: `tests/test_cli.py` (919 lines)

```python
runner = CliRunner()

result = runner.invoke(app, ["crawl-tdocs", "--cache-dir", str(test_cache_dir)])
assert result.exit_code == 0
assert "Processed" in result.stdout
assert "10" in result.stdout
```

### Portal/Auth Tests

- Conditional on credentials and internet
- Auto-skip when env vars missing: `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`
- Tests real 3GPP portal structure — can break when portal changes
- File: `tests/test_portal_auth.py`

### Skipped Tests

```python
@pytest.mark.skip(reason="Requires sentence-transformers")
def test_vector_dimensions_match_model(self) -> None:
    ...

@pytest.mark.skip(reason="Legacy pipeline removed")
def test_pipeline_removed(self) -> None:
    ...
```

### Placeholder Tests

Some AI test files contain placeholder assertions (e.g., `test_ai_embeddings.py`):

```python
def test_chunk_extraction_from_markdown(self) -> None:
    assert True  # Placeholder - actual implementation would test chunking logic
```

## Test Marks

| Mark | Usage |
|------|-------|
| `@pytest.mark.integration` | Slow/network-dependent tests |
| `@pytest.mark.skip(reason="...")` | Skip with documented reason |
| `@pytest.mark.parametrize(...)` | Data-driven tests |

**Parametrize example:**

```python
@pytest.mark.parametrize("format_value", list(LibreOfficeFormat))
def test_libreoffice_format_values(self, format_value: LibreOfficeFormat) -> None:
    assert isinstance(format_value.value, str)
```

## Anti-Duplication in Tests

**CRITICAL rule (from `tests/AGENTS.md`):** Do not re-implement logic from `src/` into `tests/`.

```python
# ✅ CORRECT — import and verify actual implementation
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.config import resolve_cache_manager

# ❌ WRONG — duplicating production logic in tests
class FakeTDocCrawler:
    def crawl(self):
        # This duplicates production code!
```

**Use fixtures from `conftest.py`** instead of duplicating setup code:

- `test_db_path` — don't create DB paths inline
- `sample_tdocs` — don't create TDoc metadata inline
- `insert_sample_meetings()` — don't write raw SQL inserts

## Best Practices (from `tests/AGENTS.md`)

1. **Test isolation:** Each test independent — use fixtures, never shared mutable state
1. **Descriptive names:** Test names describe expected behavior: `test_case_insensitive_query`
1. **Minimal assertions:** One specific behavior per test
1. **Mock external systems:** Isolate from network, file system, external services
1. **Document edge cases:** Test error conditions and boundary values

## Debugging Failed Tests

```bash
# Verbose output with full diffs
uv run pytest tests/test_crawler.py -v --tb=long

# Stop on first failure
uv run pytest tests/ -x

# Run specific test method
uv run pytest tests/test_crawler.py::TestTDocCrawler::test_crawler_initialization -v

# Show print statements (overrides stdout capture)
uv run pytest tests/test_crawler.py -v -s
```

## Common Patterns

### Database Testing

```python
def test_upsert_tdoc(self, test_db_path, sample_tdocs, sample_meetings) -> None:
    with TDocDatabase(test_db_path) as db:
        insert_sample_meetings(db, sample_meetings)
        created, changed = db.upsert_tdoc(sample_tdocs[0])
        assert created is True
        assert changed is False

        results = db.query_tdocs(TDocQueryConfig())
        assert len(results) == 1
```

### Error Testing

```python
def test_crawl_connection_failure(self, mock_fetch, test_db_path) -> None:
    mock_fetch.side_effect = OSError("Connection refused")
    result = crawler.crawl(config)
    assert result.processed == 0
    assert result.errors

def test_parse_meeting_row_invalid_raises(self) -> None:
    with pytest.raises(ValueError, match="Unknown working group"):
        WorkingGroup.from_literal("X")
```

### Environment Variable Testing

```python
def test_cli_params_override_everything(self) -> None:
    with patch.dict(os.environ, {"HTTP_CACHE_TTL": "3600"}):
        config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=1800)
        assert config.ttl == 1800  # CLI wins over env var
```

### Conditional Skip Pattern

```python
@pytest.fixture
def credentials() -> PortalCredentials:
    creds = _get_credentials()
    if not creds:
        pytest.skip("Missing TDC_EOL_USERNAME or TDC_EOL_PASSWORD")
    return creds
```

______________________________________________________________________

*Testing analysis: 2026-03-27*
