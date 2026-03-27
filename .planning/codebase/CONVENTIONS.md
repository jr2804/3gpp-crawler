# Coding Conventions

**Analysis Date:** 2026-03-27

## Source of Truth

- **Root AGENTS.md**: `AGENTS.md` (project root)
- **Scoped AGENTS.md**: Check domain-specific AGENTS.md when working in subdirectories
- **Precedence**: Closest AGENTS.md wins — scoped files override root defaults

**Scoped AGENTS.md locations:**

- `src/tdoc_crawler/AGENTS.md` — core library conventions
- `src/tdoc_crawler/cli/AGENTS.md` — CLI-only code conventions
- `tests/AGENTS.md` — test organization guidelines
- `packages/3gpp-ai/AGENTS.md` — AI module SSOT patterns
- `packages/convert-lo/AGENTS.md` — LibreOffice conversion patterns

## Language Standards

- **Python Version**: 3.14 (strict: `requires-python = ">=3.14,<4.0"`)
- **Type Hints**: Mandatory for all function signatures
- **Modern Union Syntax**: Use `T | None` instead of `Optional[T]`
- **Comparisons**: Use `is` / `is not` for `None` comparisons
- **`from __future__ import annotations`**: Present at top of every Python file

## Code Style

### Ruff Configuration

Project uses ruff for both linting and formatting. Config in `ruff.toml`:

```toml
target-version = "py314"
line-length = 160
fix = true
unsafe-fixes = true
preview = true
explicit-preview-rules = true
```

**Run linting:**

```bash
ruff check src/ tests/
```

### Enabled Rule Sets

| Code | Description |
|------|-------------|
| `E`, `W` | pycodestyle errors/warnings |
| `F` | Pyflakes |
| `I` | isort (import sorting) |
| `D` | pydocstyle (Google convention) |
| `PT` | flake8-pytest-style |
| `PL` | Pylint (`max-locals = 20`) |
| `SIM` | flake8-simplify |
| `UP` | pyupgrade (modernize syntax) |
| `S` | flake8-bandit (security) |
| `ANN` | flake8-annotations |
| `B` | flake8-bugbear |
| `C4`, `C90` | comprehensions, complexity |
| `NPY` | NumPy-specific rules |

### Additional extend-select rules

| Code | Description |
|------|-------------|
| `RUF022` | unsorted `__dunder_all__` |
| `PLR6301` | no-self-use |
| `PLC0415` | import-outside-top-level |
| `E402` | module-import-not-at-top-of-file |

### Ignored Rules

| Code | Description | Why Ignored |
|------|-------------|-------------|
| `B024`, `B028`, `B904` | selective bugbear | project-specific relaxations |
| `C901` | complex-structure | no hard complexity limit |
| `D100`–`D107` | missing docstrings on various targets | selective docstring enforcement |
| `D200`, `D205`, `D212`, `D415` | docstring formatting | style preference |
| `E722` | bare except | allowed in specific contexts |
| `ANN002`, `ANN003` | missing `*args`/`**kwargs` annotation | not required |
| `ANN204`, `ANN401` | dynamically typed, `Any` type | allowed when needed |
| `PLR0912`, `PLR0913` | too-many-branches/args | practical limits |
| `PLR2004` | magic value in comparison | tolerated |
| `PT028` | test param with default | test convenience |

### Forbidden Linter Issues (NEVER introduce)

- `PLC0415` — import outside top-level
- `ANN001` — missing function parameter type annotation
- `ANN201` — missing return type annotation (public)
- `ANN202` — missing return type annotation (private)
- `E402` — module import not at top of file

### Test-Specific Ignores

```toml
[lint.per-file-ignores]
"tests/*.py" = ["S101", "S106", "PLR6301", "S603", "PLW1510"]
"tests/**/*.py" = ["S101", "S106", "PLR6301", "S603", "PLW1510"]
```

Relaxes: assert usage (`S101`), hardcoded passwords in tests (`S106`), subprocess calls (`S603`, `PLW1510`), no-self-use (`PLR6301`).

### Formatting Rules

```toml
[format]
docstring-code-format = true
docstring-code-line-length = 160
```

### Method Sorting (undersort)

```toml
[tool.undersort]
order = ["public", "protected", "private"]
method_type_order = ["instance", "class", "static"]
```

Enforced via pre-commit hook. Methods sorted within classes: public → protected (`_`) → private (`__`), then instance → classmethod → staticmethod.

## Naming Patterns

### Files

| Pattern | Example |
|---------|---------|
| Source modules | `http_client.py`, `meeting_crawler.py` |
| Test files | `test_crawler.py`, `test_http_client.py` |
| Config | `conftest.py` |
| Package init | `__init__.py` |

### Functions and Methods

| Type | Pattern | Example |
|------|---------|---------|
| Public | snake_case | `create_cached_session()`, `normalize_tdoc_id()` |
| Private | _snake_case | `_create_test_meeting()`, `_serialize_status()` |
| Validators (Pydantic) | `_normalize_`/`_validate_` prefix | `_normalize_tdoc_id`, `_validate_status` (classmethod) |
| Boolean properties | is_/has\_ prefix | `is_valid`, `has_valid_url` |

### Variables

| Type | Pattern | Example |
|------|---------|---------|
| Regular | snake_case | `test_db_path`, `cache_manager_name` |
| Private module | \_leading_underscore | `_TDOC_AI_AVAILABLE`, `_cache_managers` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_CACHE_DIR`, `EXCLUDED_DIRS`, `TDOC_PATTERN` |
| Private constants | \_UPPER_SNAKE_CASE | `_DEFAULT_TTL`, `_DEFAULT_TTL_ON_ACCESS` |

### Types and Classes

| Pattern | Example |
|---------|---------|
| Classes | PascalCase: `TDocCrawler`, `MeetingMetadata`, `CacheManager` |
| Enums | PascalCase class, UPPER values: `TDocStatus.APPROVED` |
| String Enums | `StrEnum` base: `class OutputFormat(StrEnum)` |
| Config classes | Suffix with `Config`: `TDocCrawlConfig`, `HttpCacheConfig` |
| Type aliases | Modern: `str \| None`, `list[str]`, `dict[str, object]` |
| Self-returning | Use `Self`: `def register(self) -> Self:` |

## Import Organization

### Order (enforced by isort via ruff `I` rules)

1. `from __future__ import annotations` (always first)
1. Standard library imports
1. Third-party imports
1. Local/application imports (`tdoc_crawler.*`, `pool_executors.*`, `tdoc_ai.*`)

### Key Import Patterns

```python
from __future__ import annotations  # Always first

import os                     # stdlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest                 # third-party
import requests
from pydantic import BaseModel, Field

from tdoc_crawler.config import CacheManager  # local
from tdoc_crawler.tdocs.models import TDocMetadata
```

### Explicit Submodule Imports (domain packages don't re-export)

```python
# ✅ CORRECT — explicit submodule path
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.specs.operations.checkout import checkout_spec

# ❌ WRONG — barrel imports through __init__.py
from tdoc_crawler.tdocs import fetch_missing_tdocs
```

### Path Resolution

- No path aliases configured
- `pythonpath = ["src"]` in `pyproject.toml` enables `from tdoc_crawler.*` without sys.path hacks

### Forbidden Import Patterns

- NO `typing.TYPE_CHECKING` guard blocks — refactor circular imports instead
- NO imports outside top-level — forbidden by `PLC0415`, `E402`
- NO circular imports — extract shared types to `models/` layer

## Type Annotation Standards

**Mandatory for all functions:**

```python
def create_cached_session(
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str = "default",
) -> requests.Session:
    ...
```

**Key patterns:**

- Modern union: `str | None` NOT `Optional[str]`
- Use `Self` for fluent APIs: `def register(self) -> Self:`
- Use `None` for void returns: `def configure() -> None:`
- Use `Iterable[str]` for collection parameters (flexible input)
- Use `StrEnum` for string enums
- Use `@dataclass` for simple value objects (`HttpCacheConfig`)
- Use `BaseModel` with `Field(description=...)` for complex models

## Error Handling

**Philosophy:** Fail fast, fail loud. Keep error handling simple.

```python
# ✅ CORRECT — consistent type, raise on invalid input
def get_info(number: str|int, message: str) -> InfoObject:
    if not isinstance(tdoc_id, (str, int)):
        raise TypeError("tdoc_id must be a string or integer")
    return process(tdoc_id)

# ❌ WRONG — inconsistent return types, encoding errors in returns
def get_info(number: str|int|None, message: str|None|Any) -> InfoObject|str|None:
    try:
        return process(number)
    except SomeSpecificError:
        return None        # Don't encode failure in return values
    except AnotherError:
        return "Error: ..."  # Don't return string errors
```

**Exception chaining:**

```python
try:
    result = some_operation()
except ValueError as e:
    raise ValueError("Failed to process data") from e
```

**Error handling in models:**

- Use `@field_validator` for input validation
- Use enum `_missing_()` for case-insensitive lookup with helpful error messages

**In tests:**

```python
with pytest.raises(ValueError, match="expected message"):
    ...

with pytest.raises(PortalAuthenticationError), PortalClient(...) as client:
    client.fetch_tdoc_metadata(tdoc_id)
```

## Logging

**Framework:** `logging` with `RichHandler` (from `src/tdoc_crawler/logging/`)

```python
from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)
_logger.info("Starting operation")
_logger.warning(f"URL validation failed for {tdoc_id}")
_logger.debug(f"Detailed diagnostic: {value}")
```

**Rules:**

- Use `get_logger(__name__)` — cached via `@functools.cache`
- Default level: `logging.WARNING`
- NEVER use `print()` — always use logging
- RichHandler auto-configured on first import
- Set verbosity via `set_verbosity(level)` accepting int, string, or logging constant

## Documentation

**Docstring convention:** Google style (enforced by `pydocstyle` with `convention = "google"`)

**Required for:** All public classes, all public functions/methods, all modules

**Format:**

```python
def fetch_missing_tdocs(
    database: TDocDatabase,
    tdocs: list[TDocMetadata],
    timeout: int = 30,
) -> FetchMissingResult:
    """Fetch missing TDocs from their respective source URLs.

    Downloads TDoc files that are not yet present in the checkout directory.

    Args:
        database: Active database connection for updating download status.
        tdocs: List of TDoc metadata entries to fetch.
        timeout: Request timeout in seconds per download.

    Returns:
        FetchMissingResult with counts of processed, skipped, and failed downloads.

    Raises:
        NetworkError: If all download attempts fail.
    """
```

**Comments:** Explain WHY, not WHAT. Domain context is valuable.

**`__all__` exports:**

- Explicit in leaf modules: `__all__ = ["TDocCrawlConfig", "TDocMetadata", ...]`
- Sorted by `undersort` pre-commit hook and `RUF022`

## Function Design

**Size guidelines:**

- Max 20 local variables: `max-locals = 20` (Pylint)
- No strict line limit (`C901` ignored)
- Max 13 parameters: `PLR0913` in ignore list (practical limit)

**Parameters:**

- Use Pydantic `BaseModel` for complex parameter groups (configs)
- Use `@dataclass` for simple value objects
- Use `Field(description=...)` for all Pydantic model fields

**Return values:**

- Always consistent type — never `SomeType | str | None`
- Return Pydantic models from database operations
- Use result dataclasses for operations: `TDocCrawlResult`, `FetchMissingResult`

## Module Design

**Exports:**

- Domain packages do NOT re-export from submodules
- Use explicit submodule paths
- `__all__` defined in leaf modules

**CLI/Library separation:**

- `cli/` imports from core — never the reverse
- Core is standalone library; `cli/` is optional consumer
- Typer commands in `cli/`, data/logic in core

## Path Management (CacheManager — CRITICAL)

**Single source of truth:** `src/tdoc_crawler/config/__init__.py`

```python
from tdoc_crawler.config import resolve_cache_manager, CacheManager

# Preferred: resolve already-registered instance
manager = resolve_cache_manager()

# Create and register (once at startup)
manager = CacheManager(cache_dir, name="default").register()

# Access paths
manager.root              # ~/.3gpp-crawler/
manager.db_file           # ~/.3gpp-crawler/3gpp_crawler.db
manager.http_cache_file   # ~/.3gpp-crawler/http-cache.sqlite3
manager.checkout_dir      # ~/.3gpp-crawler/checkout/
manager.ai_cache_dir      # ~/.3gpp-crawler/lightrag/
manager.ai_workspace_file # ~/.3gpp-crawler/lightrag/workspaces.json
manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
```

**Rules:**

- NEVER hardcode paths like `Path.home() / ".3gpp-crawler"`
- NEVER use `os.path.expanduser("~/.3gpp-crawler")`
- NEVER define duplicate path constants — check `config/__init__.py` first
- CacheManager must be registered at startup — no fallback/try-except boilerplate
- Environment overrides: `TDC_CACHE_DIR`, `TDC_AI_STORE_PATH`

## HTTP Requests (Mandatory Caching)

All HTTP requests to 3gpp.org, whatthespec.net, and portal MUST use cached sessions:

```python
from tdoc_crawler.http_client import create_cached_session

with create_cached_session() as session:
    response = session.get(url)
```

Module: `src/tdoc_crawler/http_client/` (package with `session.py`, `protocols.py`)

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:

| Hook | Version | Purpose |
|------|---------|---------|
| check-case-conflict | v5.0.0 | Prevent case-sensitivity issues |
| check-merge-conflict | v5.0.0 | Detect merge conflict markers |
| check-toml/yaml/json | v5.0.0 | Validate config files |
| pretty-format-json | v5.0.0 | Format JSON (--autofix, --no-sort-keys) |
| end-of-file-fixer | v5.0.0 | Ensure newline at EOF |
| trailing-whitespace | v5.0.0 | Remove trailing spaces |
| ruff-check | v0.12.7 | Lint Python files (--exit-non-zero-on-fix) |
| ruff-format | v0.12.7 | Format Python files |
| undersort | local | Sort `__all__` exports |

## Dependency Management

- **Adding dependencies**: Ask user first — minimize deps
- **Add command**: `uv add <package>`
- **Workspace packages**: `packages/3gpp-ai/`, `packages/convert-lo/`, `packages/pool_executors/`

## Domain Terminology

| Term | Meaning |
|------|---------|
| TDoc | 3GPP Temporary Document (e.g., `S4-250638`) |
| Spec | 3GPP Technical Specification (TS/TR, e.g., `TS 26.444`) |
| WG | Working Group (e.g., S4, RAN1, CT3) |
| TSG | Technical Specification Group (SA, RAN, CT) |
| Portal | 3GPP EOL authenticated portal |

## Antipatterns to Avoid

### Overly Careful Error Handling

```python
# ❌ WRONG — boilerplate safety
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    manager = CacheManager(default_cache_dir).register()

# ✅ CORRECT — let it fail (dev error)
manager = resolve_cache_manager()
```

### Code Duplication

Search before implementing. Refactor existing code rather than duplicating.

### Circular Imports

Extract shared types to `models/` directory. Never use `TYPE_CHECKING` as workaround.

### Inconsistent Return Types

Never encode failure in return values. Always return one consistent type.

______________________________________________________________________

*Convention analysis: 2026-03-27*
