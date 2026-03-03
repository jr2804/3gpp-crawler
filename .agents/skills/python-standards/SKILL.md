---
name: python-standards
description: Python coding standards, type hints, code quality, and best practices for this project. Use when writing, reviewing, or refactoring Python code.
---

# Python Standards

## Overview

This skill defines the Python coding standards, type hints, code quality requirements, and best practices for the tdoc-crawler project. These standards ensure consistency, maintainability, and type safety across the codebase.

## Type Hints (Mandatory)

Type hints are required everywhere for all function parameters and return values.

```python
from typing import Any

# Function with type hints
def process_tdoc(tdoc_id: str, meeting_id: int) -> dict[str, Any]:
    """Process a TDoc and return metadata."""
    return {"id": tdoc_id, "meeting": meeting_id}

# Always use pipe syntax for optional types
def fetch_tdoc(tdoc_id: str | None) -> dict[str, Any] | None:
    """Fetch TDoc metadata, returns None if not found."""
    if tdoc_id is None:
        return None
    return {"id": tdoc_id}

# NEVER use Optional[T]
# WRONG: from typing import Optional; def fetch(tdoc_id: Optional[str])
```

### Type Hints Rules

- Use `T | None` instead of `Optional[T]`
- Use `Any` from `typing` instead of `object` as a type hint
- Type hints are mandatory for function parameters AND return values
- Include type hints in docstrings for function parameters and return values

## String Formatting

Use f-strings for all string formatting:

```python
# CORRECT
name = "S4-123456"
meeting = "SA4#99e"
print(f"Processing {name} from {meeting}")

# WRONG - do not use .format() or %
print("Processing {} from {}".format(name, meeting))
print("Processing %s from %s" % (name, meeting))
```

## Data Structures and Built-ins

### Use Comprehensions

```python
# List comprehension
ids = [t.id for t in tdocs if t.active]

# Dictionary comprehension
tdoc_map = {t.id: t for t in tdocs}
```

### Use enumerate() for Index and Value

```python
# CORRECT - when you need both index and value
for i, tdoc in enumerate(tdocs):
    print(f"{i}: {tdoc.id}")

# WRONG - do not manually track index
for i in range(len(tdocs)):
    print(f"{i}: {tdocs[i].id}")
```

### Use pathlib.Path for File Paths

```python
from pathlib import Path

# CORRECT
cache_dir = Path.home() / ".tdoc-crawler" / "cache"
cache_dir.mkdir(parents=True, exist_ok=True)

# WRONG - do not use os.path
import os.path
cache_dir = os.path.join(os.path.expanduser("~"), ".tdoc-crawler", "cache")
```

### Null Comparisons

Use `is` and `is not` for comparing to `None`, not `==` or `!=`:

```python
# CORRECT
if tdoc_id is None:
    return None
if result is not None:
    process(result)

# WRONG
if tdoc_id == None:
    return None
if result != None:
    process(result)
```

### Resource Management

Use `with` statements when working with files:

```python
# CORRECT
from pathlib import Path

with open("data.json") as f:
    data = json.load(f)

# WRONG
f = open("data.json")
data = json.load(f)
f.close()
```

## Code Size Limits

Keep modules and symbols small to preserve maintainability:

- **Modules (single `.py` file)**: < 250 lines (exception: CLI command registration files can be larger)
- **Functions**: < 75 lines
- **Classes**: < 200 lines

**Refactor when limits are exceeded:**
- Split large functions into smaller helper functions
- Extract common logic to separate utilities
- Split large classes into composition of smaller classes

## Logging

Use the `logging` module instead of `print()`:

```python
import logging

logger = logging.getLogger(__name__)

# CORRECT
logger.debug("Processing TDoc: %s", tdoc_id)
logger.info("Successfully fetched metadata for %s", tdoc_id)
logger.warning("Retry attempt %d for %s", retry_count, tdoc_id)
logger.error("Failed to process %s: %s", tdoc_id, exc_info=True)

# WRONG
print(f"Processing TDoc: {tdoc_id}")
```

## Library Preferences

Use these libraries for specific tasks:

| Task | Preferred Library | Notes |
|-------|------------------|-------|
| CLI | typer | Type hints for CLI |
| Terminal formatting | rich | Beautiful terminal output |
| Data models | pydantic | Validation and serialization |
| Database | pydantic-sqlite | Type-safe SQLite |
| Testing | pytest | Testing framework |
| Formatting/linting | ruff, isort, ty | Code quality tools |
| Excel reading | pandas + python-calamine | Fast Excel reading |
| Excel writing | xlsxwriter | Excel output |
| Type checking | ty (Mypy wrapper) | Static type checking |

## Comment Policy

Comments should explain intent or subtle constraints, not restate what's obvious from names.

```python
# GOOD - explains WHY
# TDoc IDs are case-insensitive, so normalize to uppercase
tdoc_id = tdoc_id.upper()

# GOOD - documents a subtle constraint
# The portal API rate-limits to 10 requests/second
time.sleep(0.1)

# BAD - restates what the code does
# Get the ID from the tdoc object
id = tdoc.id

# BAD - numbered steps are hard to maintain
# Step 1: Fetch the metadata
# Step 2: Parse the response
metadata = fetch_metadata()
parsed = parse_response(metadata)
```

### Comment Guidelines

- **Be concise and clear**: Comments should be suitable for inclusion in final production code
- **Explain intent, not mechanics**: Describe WHY something is done, not WHAT it does
- **Document subtle constraints**: Use comments when code avoids bugs or has non-obvious requirements
- **DO NOT repeat obvious names**: Variable/function names should already describe what they are
- **DO NOT include "what you did"**: Comments like "Added this function" belong in commit messages
- **DO NOT use decorative headings**: Avoid "===== MIGRATION TOOLS =====" or fancy formatting
- **DO NOT number steps**: "// Step 3: Fetch data" is hard to maintain. Use "// Now fetch the data" instead
- **DO NOT use emojis or Unicode**: No ①, •, –, —, or similar characters in comments
- **DO NOT use special unicode**: Keep comments plain ASCII for portability and clarity
- DO NOT use emojis or special Unicode characters in comments

## Linting Rules

After significant changes, run the project's formatters/linters:

```bash
# Run linter
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Sort imports
isort src/ tests/

# Type check
ty src/
```

### Prohibited Linter Issues

NEVER suppress linter issues with `# noqa` in `src/` or `tests/`. Instead, fix the underlying issue.

You MUST NOT introduce these linter rules:
- **PLC0415** - Import at top of file (refactor circular imports instead)
- **ANN001** - Missing type annotation for function argument
- **E402** - Module-level import not at top of file
- **ANN201** - Missing return type annotation for public function
- **ANN202** - Missing return type annotation for private function

### Circular Import Prevention

If you encounter a circular import, refactor the code to eliminate it. Never use `TYPE_CHECKING` guards as a permanent solution.

```python
# WRONG - Using TYPE_CHECKING as permanent solution
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tdoc_crawler.database import TDocDatabase

# RIGHT - Refactor to extract shared types or use lazy import (temporary only)
def _resolve_meeting_id(db_file: Path) -> int:
    from tdoc_crawler.database import TDocDatabase  # Lazy import for temporary fix
    with TDocDatabase(db_file) as db:
        return db.resolve_meeting_id(name)
```

## Virtual Environment

Always ensure the Python virtual environment is activated before running shell commands:

```bash
# Use uv run for Python commands
uv run pytest -v
uv run python -m mypy src/

# Scripts can also use uv run
uv run scripts/update_cache.py
```

## Docstrings

Write clear, concise docstrings using Google style:

```python
def fetch_tdoc_metadata(tdoc_id: str, source: str) -> dict[str, Any] | None:
    """Fetch TDoc metadata from the specified source.

    Args:
        tdoc_id: The TDoc identifier (e.g., "S4-123456")
        source: The metadata source ("whatthespec", "portal", or "doclist")

    Returns:
        Dictionary with metadata fields (title, author, meeting_id, etc.),
        or None if the TDoc is not found.

    Raises:
        ValueError: If source is not recognized
        ConnectionError: If the API endpoint is unreachable

    Examples:
        >>> fetch_tdoc_metadata("S4-123456", "whatthespec")
        {"id": "S4-123456", "title": "Example document", ...}
    """
```

## Testing

- Use `pytest` for testing
- Use fixtures and parameterized tests to reduce duplication
- Use mocking to isolate tests from external systems
- Test cache directory: `./tests/test-cache`
- Aim for 70%+ overall coverage

## See Also

- **@python-linter** - For fixing specific Python linter issues (B008, S108, PLC0415, etc.)
- **@test-driven-development** - TDD methodology with pytest and fixtures
- **@code-deduplication** - Prevent code duplication with capability index

## Resources

This skill does not include additional resources. All Python standards are documented in this SKILL.md file.
