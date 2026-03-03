---
name: test-driven-development
description: TDD methodology with pytest, mocking, and coverage analysis
---

# Test-Driven Development (TDD) Skill

## Test Framework

- Use `pytest` as the primary testing framework
- Prefer small, focused unit tests first
- Add integration-style tests when necessary

## Test Organization

### File Structure

```bash
tests/
├── conftest.py          # Shared fixtures
├── test_module.py       # Unit tests for src/module.py
├── test_another.py      # Unit tests for src/another.py
└── integration/         # Integration tests (if needed)
    └── test_workflow.py
```

### Fixture Guidelines

- Define reusable fixtures in `conftest.py`
- Use descriptive fixture names that explain their purpose
- Parameterize fixtures for test variations
- Use fixture scope appropriately: `function` (default), `class`, `module`, `session`

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Path to a temporary test database."""
    return tmp_path / "test.db"

@pytest.fixture
def mock_data():
    """Mock data for testing."""
    return {"key": "value"}
```

## Mocking External Dependencies

### HTTP Requests

When testing code that makes HTTP requests:

**Rule**: Patch at the import location where the Session is constructed or used.

```python
# Import the module that uses requests
import mymodule

def test_api_call(monkeypatch):
    """Test API call with mocked HTTP session."""
    # Patch at the module level where Session is used
    def mock_get(url, **kwargs):
        class MockResponse:
            def __init__(self, status_code, text):
                self.status_code = status_code
                self.text = text

        return MockResponse(200, "<html><body>Test</body></html>")

    monkeypatch.setattr("requests.Session.get", mock_get)
    result = mymodule.fetch_data("http://example.com")
    assert result == "expected"
```

### Authentication Tests

Tests must not require real credentials:

- Use environment variables only for local manual runs, not for CI
- Prefer mocking authentication requests for deterministic test behavior
- Use dummy/mock credentials in tests

```python
# Use environment variables for local manual testing only
import os
import pytest

@pytest.fixture
def test_credentials():
    """Mock credentials for testing."""
    # Load from environment if available (local manual run)
    if "TEST_USERNAME" in os.environ:
        return Credentials(
            username=os.environ["TEST_USERNAME"],
            password=os.environ["TEST_PASSWORD"]
        )
    # Otherwise use dummy credentials for CI
    return Credentials(username="test_user", password="test_pass")
```

## Database Testing

### Standard Test Locations

Use consistent paths for test resources:

- Cache directory: `./tests/test-cache`
- Database file: `./tests/test-cache/test.db`

### Foreign Key Constraints

When working with databases that have foreign keys:

**Critical Rule**: Always insert parent records before child records.

```python
# WRONG: Inserting TDoc without meeting
db.upsert_tdoc(TDoc(id="S4-12345", meeting_id=1))  # ❌ Fails if meeting_id=1 doesn't exist

# RIGHT: Insert meeting first, then TDoc
db.upsert_meeting(Meeting(id=1, name="S4-123"))
db.upsert_tdoc(TDoc(id="S4-12345", meeting_id=1))  # ✓ Success
```

### In-Memory Databases

For fast tests, use in-memory databases:

```python
@pytest.fixture
def test_db():
    """Create an in-memory SQLite database."""
    from myapp.database import create_database
    db = create_database(":memory:")
    yield db
    db.close()
```

## Test Coverage

### Coverage Goals

- Aim for **70%+** overall coverage
- Critical components should have **90%+** coverage
- Run coverage reports: `pytest --cov=mymodule --cov-report=term-missing`

### What to Cover

- Happy paths (success cases)
- Error conditions (exceptions, invalid inputs)
- Edge cases (empty inputs, boundary values)
- Integration points (database, HTTP, file system)

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_module.py -v

# Run specific test
pytest tests/test_module.py::test_specific_function -v

# Run with coverage
pytest --cov=mypackage --cov-report=html

# Run only failed tests from last run
pytest --lf

# Run until first failure (stop early)
pytest -x
```

### Filtering Tests

```bash
# Run tests matching keyword
pytest -k "auth"

# Run tests NOT matching keyword
pytest -k "not slow"

# Run tests in a directory
pytest tests/integration/
```

## Best Practices

### Test Structure (AAA Pattern)

Organize tests using **Arrange-Act-Assert**:

```python
def test_user_authentication():
    # Arrange: Set up test data and mocks
    user = User(username="test", password="hashed")
    mock_auth = MagicMock(return_value=True)

    # Act: Execute the code being tested
    result = authenticate(user, mock_auth)

    # Assert: Verify the result
    assert result.success is True
    assert result.user_id == user.id
    mock_auth.assert_called_once()
```

### Test Isolation

- Each test should be independent
- Tests should not rely on state from other tests
- Use fixtures to set up and tear down dependencies
- Clean up resources after tests

### Descriptive Names

```python
# GOOD: Clear and descriptive
def test_user_authentication_with_valid_credentials_returns_success()
def test_database_connection_failure_raises_exception()

# AVOID: Vague or unclear
def test_auth1()
def test_db()
```

### Minimal Assertions

Each test should verify one specific behavior:

```python
# AVOID: Testing too much in one test
def test_user_operations():
    user = create_user("test")
    assert user.name == "test"
    assert user.id is not None
    assert user.active is True  # Too many assertions!

# GOOD: Focused tests
def test_user_creation_returns_valid_id():
    user = create_user("test")
    assert user.id is not None

def test_user_is_active_by_default():
    user = create_user("test")
    assert user.active is True
```

### Parameterized Tests

Use `@pytest.mark.parametrize` for test variations:

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_to_uppercase(input, expected):
    assert to_uppercase(input) == expected
```

## Anti-Patterns

### What to Avoid

1. **Testing Implementation Details**: Test behavior, not how it's achieved
2. **Fragile Tests**: Tests that break when implementation changes but behavior doesn't
3. **Over-Mocking**: Only mock external dependencies, not internal logic
4. **Test Duplication**: Don't repeat the same test with different assertions
5. **Sleep in Tests**: Use mocking instead of `time.sleep()` for timing
6. **Global State**: Tests shouldn't rely on or modify global state

## Debugging Tests

### Print Statements

Use `-s` flag to see print output:

```bash
pytest -s tests/test_module.py
```

### Dropping into PDB

Use `--pdb` to drop into debugger on failure:

```bash
pytest --pdb tests/test_module.py
```

Or insert breakpoints in code:

```python
def test_something():
    breakpoint()  # Python 3.7+
    assert True
```

### Show Local Variables

Use `-l` or `--showlocals` to see local variables on failure:

```bash
pytest -l tests/test_module.py
```

## Continuous Integration

### CI Configuration

Run tests in CI with these flags:

```bash
pytest -v --cov=mypackage --cov-report=xml --junitxml=test-results.xml
```

### Fast Feedback

- Use `pytest -x` to stop on first failure (fast feedback)
- Use `pytest --lf` to re-run only failed tests
- Parallelize test execution with `pytest-xdist`: `pytest -n auto`
