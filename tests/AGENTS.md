# Tests

Test conventions, fixtures, and coverage requirements.

## Quick Start

- **Framework:** pytest
- **Run:** `uv run pytest -v`
- **Coverage:** `uv run pytest --cov=src --cov-report=term-missing`
- **Paths:** use the `test_cache_dir` / `test_db_path` fixtures (tmp_path based). `test_cache_dir` also sets `TDC_CACHE_DIR`. Never write to a fixed path.

## Import Patterns

```python
from pool_executors import SerialPoolExecutor, create_executor
from tdoc_crawler.tdocs.operations import TDocCrawler
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.meetings.operations import MeetingCrawler
from tdoc_crawler.database import MeetingDatabase, SpecDatabase, TDocDatabase
```

## Anti-Duplication

Do not re-implement logic from `src/` or `packages/` into `tests/`. Import and verify actual implementation. If code is hard to test, refactor it to be more testable.

Use fixtures from `conftest.py` (`_reset_cache_manager` is autouse and resets the `CacheManager` singleton per test):

- `test_cache_dir` — Temporary cache directory
- `test_db_path` — Path to test database
- `sample_tdocs` — Sample TDocMetadata instances
- `sample_meetings` — Sample meeting metadata
- `populated_db` — Pre-populated TDocDatabase instance

## Pool Executor Tests

- `tests/pool_executor/test_executor_adapter.py` — `Runner` class tests
- `tests/pool_executor/test_serial_executor.py` — `SerialPoolExecutor`, `SerialFuture`, `create_executor`
- **Coverage target:** >90%

```bash
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

## Best Practices

- Test isolation: Each test independent
- Descriptive names: Clear method names describing behavior
- Minimal assertions: One specific behavior per test
- Mock external systems: Isolate tests from dependencies
