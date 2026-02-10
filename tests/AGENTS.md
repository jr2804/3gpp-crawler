# Test Organization Guidelines for Coding Assistants

This document provides guidance for organizing and extending tests in the TDoc-Crawler project.

## Pool Executor Tests (`tests/pool_executor/`)

The `pool_executor/` directory contains all tests related to the `pool_executors` package, which provides executor pool extensions including serial execution support.

### Why a Separate Directory?

1. **Package Isolation**: The `pool_executors` package is designed as a standalone package that could be extracted from this repository in the future. Keeping its tests in a dedicated directory mirrors this separation.

1. **Clear Ownership**: Tests for executor functionality are clearly grouped together, making it easier to find and maintain them.

1. **Import Clarity**: When working on pool executor tests, imports use the package path `pool_executors.pool_executors` rather than `tdoc_crawler` imports, reinforcing the package's independence.

### Test Files

- **test_executor_adapter.py**: Tests for the `Runner` class that provides aiointerpreters-compatible API using pool_executors
- **test_serial_executor.py**: Comprehensive tests for `SerialPoolExecutor`, `SerialFuture`, and the `create_executor` factory

### Running Pool Executor Tests

```bash
# Run all pool executor tests
uv run pytest tests/pool_executor/ -v

# Run specific test file
uv run pytest tests/pool_executor/test_serial_executor.py -v

# Run with coverage
uv run pytest tests/pool_executor/ --cov=pool_executors --cov-report=term-missing
```

### Coverage Target

Pool executor tests should maintain **>90% code coverage** to ensure reliability of this core component.

## Adding New Tests

### For Pool Executor Features

When adding new features to the `pool_executors` package:

1. Add tests to `tests/pool_executor/test_serial_executor.py` for SerialPoolExecutor changes
1. Add tests to `tests/pool_executor/test_executor_adapter.py` for Runner adapter changes
1. Ensure all new tests follow the existing patterns:
   - Use pytest
   - Include docstrings
   - Test both success and failure cases
   - Aim for comprehensive coverage

### For Other Features

Follow the existing pattern in the appropriate test file in `tests/`. If adding a substantial new feature, consider creating a new test file in the appropriate location.

## Test Fixtures

Shared fixtures are defined in `conftest.py`. Key fixtures include:

- `test_db_path`: Path to test database
- `credentials`: Mock PortalCredentials for testing
- `mock_session`: Mock HTTP session

## Import Guidelines

### Pool Executor Tests

Use package-level imports:

```python
from pool_executors.pool_executors import SerialPoolExecutor, create_executor
```

### Domain-Specific Imports

**Since the refactoring (Steps 1-14), use domain-specific imports:**

```python
# TDoc functionality
from tdoc_crawler.tdocs import TDocCrawler, HybridTDocCrawler
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.tdocs.sources.doclist import fetch_meeting_document_list

# Meeting functionality
from tdoc_crawler.meetings import MeetingCrawler

# Spec functionality
from tdoc_crawler.specs import SpecDatabase

# Constants (patterns, URLs)
from tdoc_crawler.constants.patterns import EXCLUDED_DIRS, TDOC_PATTERN
from tdoc_crawler.constants.urls import TDOC_DOWNLOAD_URL

# Portal client
from tdoc_crawler.clients.portal import PortalClient, create_portal_client

# Parsers
from tdoc_crawler.parsers.portal import parse_tdoc_portal_page
```

**NEVER use:** `from tdoc_crawler.crawlers import ...` (this package was removed)

## Anti-Duplication in Tests

### Use Fixtures

Avoid duplicating setup code or data loading in tests. Use `conftest.py` and pytest fixtures.

### No Library Logic in Tests

Do not re-implement or copy logic from `src/` into `tests/` for the sake of mocking or testing. Tests should verify the actual implementation by importing it. If the code is hard to test, refactor the code to be more testable rather than duplicating logic.

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on state from other tests
1. **Descriptive Names**: Use clear test method names that describe what is being tested
1. **Minimal Assertions**: Each test should verify one specific behavior
1. **Use Fixtures**: Leverage shared fixtures to reduce duplication
1. **Mock External Systems**: Use mocking to isolate tests from external dependencies
1. **Document Edge Cases**: Add tests for edge cases and error conditions

## Continuous Integration

Pool executor tests are run as part of the full test suite:

```bash
# Full test suite
uv run pytest tests/ -v

# Quick smoke test
uv run pytest tests/pool_executor/test_serial_executor.py::TestSerialFuture::test_serial_future_immediate_execution -v
```
