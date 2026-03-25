# Test Organization Guidelines

Test conventions, fixtures, mocking patterns, and coverage requirements for the 3GPP Crawler test suite.

## Quick Start

1. **General TDD patterns**: Use the `test-driven-development` skill for pytest, mocking, fixtures, and coverage
1. **Standard locations**: Cache `./tests/test-cache`, DB `./tests/test-cache/tdoc_crawler.db`
1. **Run tests**: `uv run pytest -v`

## Pool Executor Tests

The `pool_executor/` directory contains tests for the standalone `pool_executors` package.

### Test Files

- **test_executor_adapter.py**: Tests for `Runner` class (aiointerpreters-compatible API)
- **test_serial_executor.py**: Tests for `SerialPoolExecutor`, `SerialFuture`, `create_executor`

### Coverage Target

**>90% code coverage** required for this core component.

```bash
uv run pytest tests/pool_executor/ -v
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

## Import Guidelines

### Pool Executor Tests

```python
from pool_executors.pool_executors import SerialPoolExecutor, create_executor
```

### Domain-Specific Imports

Use domain-specific imports (legacy `crawlers/` package was removed):

```python
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.meetings import MeetingCrawler
from tdoc_crawler.specs import SpecDatabase
```

## Anti-Duplication in Tests

**CRITICAL:** Do not re-implement or copy logic from `src/` into `tests/`. Tests should import and verify actual implementation. If code is hard to test, refactor it to be more testable.

**Use fixtures** from `conftest.py` to avoid duplicating setup code:

- `test_db_path`: Path to test database
- `credentials`: Mock PortalCredentials
- `mock_session`: Mock HTTP session

## Best Practices

- Test isolation: Each test independent
- Descriptive names: Clear method names describing behavior
- Minimal assertions: One specific behavior per test
- Mock external systems: Isolate tests from dependencies
- Document edge cases: Test error conditions
