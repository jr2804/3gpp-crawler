# Coding Conventions

**Analysis Date:** 2026-05-22

## Naming Patterns

**Files:**
- Snake_case: `cache_manager.py`, `oxyde_models.py`, `version_types.py`
- Module directories are lowercase: `http_client/`, `version_types.py`
- CLI argument type aliases use `PascalCase` with `Option`/`Argument` suffix: `TDocIdsArgument`, `WorkersOption` in `src/tdoc_crawler/cli/args.py`
- Test files use `test_` prefix: `test_database.py`, `test_models.py`
- Fixtures in subdirectory conftest: `tests/convert_lo/conftest.py`

**Functions:**
- snake_case: `resolve_cache_manager()`, `normalize_working_group_alias()`
- Private helpers use `_` prefix: `_build_column_sql()`, `_utcnow()`
- Async functions use `async def` without naming prefix: `async def upsert_tdoc()`
- Factory functions start with `create_` or `get_`: `create_cached_session()`, `get_logger()`
- Test methods are descriptive sentences: `test_case_insensitive_query()`, `test_spec_without_suffix_resolves()`

**Variables:**
- snake_case: `cache_dir`, `db_file`, `tdoc_id`
- Module-level constants are UPPER_SNAKE_CASE: `DEFAULT_DATABASE_FILENAME`, `PORTAL_BASE_URL`
- `Final` annotated constants: `TDOC_PATTERN_STR: Final[str]`
- Private module-level variables use `_` prefix: `_PYTHON_TO_SQLITE_TYPE`, `_logger`

**Types:**
- PascalCase for classes and enums: `CacheManager`, `TDocMetadata`, `ExtractionProfile`
- StrEnum subclasses for fixed-value options: `FiguresMode`, `TablesMode`, `DeviceType`, `OutputFormat`
- Generic type aliases use PascalCase: `PoolConfig`
- Version subclasses for custom field types: `AgendaItem`, `SpecVersion` in `src/tdoc_crawler/utils/version_types.py`

## Code Style

**Formatting:**
- Tool: ruff (formatter + linter)
- Config: `ruff.toml`
- Line length: 160
- Target: Python 3.13
- Docstring code blocks formatted at 160 line length
- `unsafe-fixes = true` enabled

**Linting:**
- Tool: ruff with preview rules
- Config: `ruff.toml` `[lint]` section
- Key rule sets: `E`, `F`, `D`, `I`, `PL`, `SIM`, `UP`, `S`, `ANN`, `B`, `PT`
- Docstring convention: Google style (`convention = "google"`)
- Enforced: `PLC0415` (no import-outside-top-level), `PLR6301` (no-self-use)
- Ignored in tests: `S101`, `S106`, `PLR6301`, `S603`, `PLW1510`
- Type checker: ty (`ty.toml`), Python 3.14 target

**Pre-commit hooks:**
- Config: `.pre-commit-config.yaml`
- Runs: ruff check + format, trailing whitespace, end-of-file fixer, JSON/TOML/YAML validation, undersort (method ordering)
- Method visibility ordering: public → protected → private (`[tool.undersort]` in `pyproject.toml`)

## Import Organization

**Order (enforced by ruff isort):**
1. `from __future__ import annotations` — always first when present
2. Standard library (`pathlib`, `datetime`, `json`, `re`, `enum`, `dataclasses`, `typing`)
3. Third-party (`oxyde`, `pydantic`, `pytest`, `typer`, `rich`, `packaging`)
4. Local application (`tdoc_crawler.*`)

**Path Aliases:**
- No custom path aliases configured
- Source on `pythonpath`: `src/` (configured in `pyproject.toml` `[tool.pytest.ini_options]`)

**Pattern:**
```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer
from oxyde import Field, Model

from tdoc_crawler.config import CacheManager
from tdoc_crawler.logging import get_logger
```

## Error Handling

**Patterns:**
- Custom exception hierarchy: `DatabaseError(RuntimeError)` in `src/tdoc_crawler/database/errors.py`, `ConversionError(Exception)` in `src/tdoc_crawler/extraction/errors.py`, `CacheManagerNotRegisteredError(RuntimeError)` in `src/tdoc_crawler/config/cache_manager.py`
- Errors carry structured data: `DatabaseError(code, detail=...)` pattern
- Class methods for common errors: `DatabaseError.connection_not_open()`
- Exception chaining with `raise ... from exc`:
  ```python
  raise DatabaseError("database-initialization-failed", detail=str(exc)) from exc
  ```
- No silent error swallowing (except `RuntimeError` on disconnect in `__aexit__` for pool already closed)
- Logger integration: `_logger.exception()` for full stack traces in failure paths

**Context Manager Pattern:**
- Database connections use `async with` context managers
- `CacheManager` uses singleton registration pattern
- HTTP sessions use `with create_cached_session() as session:` pattern

## Logging

**Framework:** Rich via `src/tdoc_crawler/logging/__init__.py`

**Patterns:**
- Logger creation: `logger = get_logger(__name__)` — cached, module-level
- Console singleton: `get_console()` — shared Rich Console at 120 width
- Verbosity control: `set_verbosity(level)` — accepts int, string, or logging constant
- Default level: `logging.WARNING`
- Rich handler with: `show_time=True`, `show_path=False`, `rich_tracebacks=True`
- No-color mode when stdout is not a TTY

## Comments

**When to Comment:**
- Module docstrings required (Google convention, enforced by ruff D rules)
- Function/method docstrings for public APIs with Args/Returns/Raises sections
- `# noqa: ...` comments for specific suppressions (e.g., `S105` for password-like env var names)
- Section dividers in long classes: `# ------------------------------------------------------------------` with comment blocks

**Docstrings:**
- Convention: Google style (enforced by `ruff.toml` `[lint.pydocstyle]`)
- Classes: one-line summary + detailed description + Example sections
- Functions: Args/Returns/Raises when non-trivial
- Examples use `>>>` doctest syntax in docstrings
- D100-D107 ignored (module/class/function docstrings not enforced)

## Function Design

**Size:** Functions generally under 50 lines. Complex operations decomposed into private helpers.

**Parameters:**
- Type-annotated parameters required (enforced by `ANN` ruff rules, `ANN002`/`ANN003` ignored for `*args`/`**kwargs`)
- Optional parameters use `| None` syntax: `limit: int | None = None`
- Default values preferred over `None` where sensible

**Return Values:**
- Explicit return types on all functions (enforced by ty type checker)
- Database operations return tuples: `(created: bool, changed: bool)`
- Query functions return typed lists: `list[TDocMetadata]`
- Context managers return `Self`

## Module Design

**Exports:**
- Explicit `__all__` in every module — lists public names alphabetically
- Re-exports through `__init__.py` with `from ... import ...` pattern
- `__all__` must be sorted (enforced by `RUF022`)

**Barrel Files:**
- Used in `__init__.py` files to re-export public API
- Example: `src/tdoc_crawler/config/__init__.py` re-exports from submodules
- Domain packages avoid re-exporting operations to prevent circular imports

## Architecture Conventions

**Model Choice:**
- SQLite persistence → Oxyde `Model` in `src/tdoc_crawler/database/oxyde_models.py`
- In-memory transfer → `dataclass` in domain module
- Validation/serialization → Pydantic `BaseModel` in domain module

**CLI is Thin:**
- CLI `src/tdoc_crawler/cli/` contains only Typer/Rich wrappers
- All business logic in core `src/tdoc_crawler/` library
- CLI options defined as `Annotated` types in `src/tdoc_crawler/cli/args.py`
- Multi-value CLI options MUST use `StrEnum` — never bare `str` with manual validation

**Single Source of Truth:**
- All paths via `CacheManager` from `tdoc_crawler.config` — never hardcode `~/.3gpp-crawler`
- All HTTP requests via `create_cached_session()` from `tdoc_crawler.http_client`
- All URLs as `Final` constants in `src/tdoc_crawler/constants/urls.py`
- All regex patterns as `Final` constants in `src/tdoc_crawler/constants/patterns.py`
- All env vars via `ConfigEnvVar` StrEnum in `src/tdoc_crawler/config/env_vars.py`
- CLI option env var bindings reference `ConfigEnvVar.TDC_*.name` — never hardcoded strings
- One Oxyde model per database table — no duplicate Pydantic models for the same entity

**Import Direction:**
- CLI (`cli/`) → Core (`tdoc_crawler/`)
- Core submodules → Common layer (`models/`)
- Never: Core importing from CLI

**Async:**
- Database operations are `async` using Oxyde's `AsyncDatabase`
- Test helpers use `asyncio.run()` for sync wrappers: `insert_sample_meetings()` wraps `insert_sample_meetings_async()`

---

*Convention analysis: 2026-05-22*
