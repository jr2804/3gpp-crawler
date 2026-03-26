# Coding Conventions

**Analysis Date:** 2026-03-26

## Source of Truth

- **Root AGENTS.md**: `AGENTS.md` (project root)
- **Scoped AGENTS.md**: Check domain-specific AGENTS.md files when working in subdirectories
- **Precedence**: Closest AGENTS.md wins - scoped files override root defaults

## Language Standards

- **Python Version**: 3.14 (strict requirement: `requires-python = ">=3.14,<4.0"`)
- **Type Hints**: Mandatory for all function signatures
- **Modern Union Syntax**: Use `T | None` instead of `Optional[T]`
- **Comparisons**: Use `is` / `is not` for `None` comparisons

## Code Style

### Ruff Configuration

Project uses Ruff for both linting and formatting. Configuration in `ruff.toml`:

```toml
target-version = "py314"
line-length = 160
fix = true
unsafe-fixes = true
```

**Run linting:**
```bash
ruff check src/ tests/
```

### Enabled Rule Sets

| Code | Description |
|------|-------------|
| E, W | pycodestyle errors/warnings |
| F | Pyflakes |
| I | isort |
| D | pydocstyle (Google convention) |
| PT | flake8-pytest-style |
| PL | Pylint |
| SIM | flake8-simplify |
| UP | pyupgrade |
| S | flake8-bandit (security) |
| ANN | flake8-annotations |
| B | flake8-bugbear |
| NPY | NumPy-specific rules |

### Forbidden Linter Issues

**NEVER** introduce these in `src/` or `tests/`:
- `PLC0415` - Import outside top-level (indicates circular import)
- `E402` - Module level import not at top of file
- `ANN001` - Missing type annotation for function argument
- `ANN201` - Missing return type annotation for public function
- `ANN202` - Missing return type annotation for private function

### Test-Specific Ignores

Tests have relaxed rules (from `ruff.toml`):
```toml
[lint.per-file-ignores]
"tests/*.py" = ["S101", "S106", "PLR6301", "S603", "PLW1510"]
```

## Naming Patterns

### Files

| Pattern | Example |
|---------|---------|
| Modules | `http_client.py`, `crawler.py` |
| Tests | `test_crawler.py`, `test_models.py` |
| Config | `conftest.py` |

### Functions/Methods

| Type | Pattern | Example |
|------|---------|---------|
| Public | snake_case | `create_cached_session()` |
| Private | _snake_case | `_create_test_meeting()` |
| Boolean getters | is_/has_/can_ | `is_revision_of`, `validation_failed` |

### Variables

| Type | Pattern | Example |
|------|---------|---------|
| Regular | snake_case | `test_db_path`, `cache_manager_name` |
| Private | _leading_underscore | `_tdoc_ai_available` |
| Constants | UPPER_SNAKE_CASE | `EXCLUDED_DIRS`, `TDOC_PATTERN` |

### Types/Classes

| Pattern | Example |
|---------|---------|
| Classes | PascalCase: `TDocCrawler`, `MeetingMetadata` |
| Type hints | Modern syntax: `str | None`, `list[T]`, `dict[str, object]` |

## Import Patterns

### Order (handled by isort/Ruff)

1. Standard library imports
2. Third-party imports
3. Local application imports

### Correct Patterns

```python
# ✅ CORRECT - All imports at top
from pathlib import Path
from unittest.mock import MagicMock, patch

from tdoc_crawler.config import CacheManager, resolve_cache_manager
from tdoc_crawler.database import TDocDatabase

# ❌ WRONG - TYPE_CHECKING workaround (indicates bad structure)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tdoc_crawler.models import TDocMetadata
```

**Rule**: Avoid `typing.TYPE_CHECKING` entirely. If needed for circular imports, refactor the code structure instead.

### Import Paths

Use full import paths (no aliases configured):
```python
from tdoc_crawler.config import CacheManager
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.meetings import MeetingCrawler
```

## Error Handling

### Fail Fast, Fail Loud

Keep error handling simple. Let errors propagate rather than encoding them in return values:

```python
# ❌ WRONG - Encoding errors in return types, inconsistent returns
def get_info(number: str | None) -> InfoObject | str | None:
    if number is None:
        return None
    try:
        return process(number)
    except ValueError:
        return "Error: Invalid input"

# ✅ CORRECT - Consistent return type, let caller handle exceptions
def get_info(number: str) -> InfoObject:
    if not isinstance(number, str):
        raise TypeError("number must be a string")
    return process(number)  # Let ValueError propagate
```

### Exception Chaining

Use exception chaining to preserve context:

```python
try:
    result = some_operation()
except ValueError as e:
    raise ValueError("Failed to process data") from e
```

## Logging

Use `logging` module, never `print()`:

```python
import logging

logger = logging.getLogger(__name__)

def process_data(data: dict) -> None:
    logger.info("Processing data: %s", data.get("id"))
    logger.warning("Resource low: %d remaining", count)
    logger.error("Failed to process: %s", error)
```

## Path Management (CRITICAL)

### CacheManager Pattern

**Single Source of Truth**: All file paths MUST use `CacheManager` from `src/tdoc_crawler/config/__init__.py`.

```python
from tdoc_crawler.config import resolve_cache_manager

# ✅ CORRECT
manager = resolve_cache_manager()
path = manager.db_file

# ❌ WRONG - Never hardcode paths
path = Path.home() / ".3gpp-crawler" / "3gpp_crawler.db"
path = os.path.expanduser("~/.3gpp-crawler")
```

### Registration

```python
# At program start (CLI wrapper handles this)
from tdoc_crawler.config import CacheManager, register_cache_manager

cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
register_cache_manager(cache_manager, force=True)

# Later, in any module - NO fallback boilerplate!
manager = resolve_cache_manager()
```

### Available Paths

```python
manager.root              # ~/.3gpp-crawler/
manager.db_file           # ~/.3gpp-crawler/3gpp_crawler.db
manager.http_cache_file   # ~/.3gpp-crawler/http-cache.sqlite3
manager.checkout_dir      # ~/.3gpp-crawler/checkout/
manager.ai_cache_dir      # ~/.3gpp-crawler/lightrag/
manager.ai_workspace_file # ~/.3gpp-crawler/lightrag/workspaces.json
manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
```

## HTTP Requests

Use cached sessions for all HTTP requests:

```python
from tdoc_crawler.http_client import create_cached_session

session = create_cached_session()
response = session.get(url)
```

**Location**: `src/tdoc_crawler/http_client.py`

## Comments and Docstrings

### When to Comment

Explain **WHY**, not WHAT:

```python
# ✅ CORRECT - Explains reasoning
# Use subinterpreter to avoid memory leak in Excel parsing library
result = fetch_meeting_document_list_subinterpreter(url)

# ❌ WRONG - States the obvious
# Get the URL
url = config.url
```

### Docstrings

Google convention (configured in `ruff.toml`):

```python
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path.

    Args:
        test_cache_dir: Test cache directory

    Returns:
        Path to test database
    """
```

## Function Design

### Size Guidelines

- `max-locals = 20` (enforced by Ruff)
- No hard line limit, but complexity rules apply

### Parameters

Use Pydantic models for complex parameter groups:
```python
# ✅ Grouped parameters
class TDocCrawlConfig(BaseModel):
    working_groups: list[WorkingGroup]
    subgroups: list[SubWorkingGroup] | None = None
    meeting_ids: list[int] | None = None
    ...

# ❌ Many individual parameters
def crawl(wg, subgroups, meeting_ids, start_date, end_date, ...):
```

### Return Values

- Consistent return types
- Use Pydantic models for structured data
- Return tuples for multiple values: `tuple[int, int, int]`

## Module Design

### Exports

```python
# Explicit __all__ exports (sorted by undersort hook)
__all__ = ["CacheManager", "resolve_cache_manager", "register_cache_manager"]
```

### Barrel Files

Use `__init__.py` for clean imports:
```python
# src/tdoc_crawler/config/__init__.py
from .cache_manager import CacheManager, resolve_cache_manager, register_cache_manager

__all__ = ["CacheManager", "resolve_cache_manager", "register_cache_manager"]
```

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:

| Hook | Purpose |
|------|---------|
| check-case-conflict | Prevent case-sensitivity issues |
| check-merge-conflict | Detect merge conflict markers |
| check-toml/yaml/json | Validate config files |
| pretty-format-json | Format JSON files |
| end-of-file-fixer | Ensure newline at EOF |
| trailing-whitespace | Remove trailing spaces |
| ruff-check | Lint Python files |
| ruff-format | Format Python files |
| undersort | Sort `__all__` exports |

## Dependency Management

- **Adding dependencies**: Ask user first - minimize deps
- **Adding packages**: Use `uv add <package>`
- **Workspace packages**: `packages/3gpp-ai/`, `packages/convert-lo/`, `packages/pool_executors/`

## Pydantic Models

Follow patterns from `src/tdoc_crawler/models/`:

```python
from pydantic import BaseModel
from datetime import datetime

class TDocMetadata(BaseModel):
    tdoc_id: str
    title: str | None = None
    date_created: datetime | None = None
    validated: bool = False
```

## Antipatterns to Avoid

### Overly Careful Error Handling

```python
# ❌ WRONG - Too much safety boilerplate
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    try:
        manager = CacheManager(default_cache_dir).register()
    except Exception as e:
        raise RuntimeError("Failed...") from e

# ✅ CORRECT - Let it fail if not registered (dev error)
manager = resolve_cache_manager()
```

### Code Duplication

**Always search before implementing**. If similar code exists, refactor it.

### Circular Imports

Extract shared types to `models/` directory rather than using TYPE_CHECKING workarounds.

## Domain Terminology

| Term | Meaning |
|------|---------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## 3GPP Domain Questions

Load domain skills when working with 3GPP concepts:
- `3gpp-basics`, `3gpp-change-request`, `3gpp-meetings`
- `3gpp-portal-authentication`, `3gpp-releases`, `3gpp-specifications`
- `3gpp-tdocs`, `3gpp-working-groups`

---

*Convention analysis: 2026-03-26*
