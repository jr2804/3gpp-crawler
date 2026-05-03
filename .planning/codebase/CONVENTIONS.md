# Coding Conventions

**Analysis Date:** 2026-05-03

## Naming Patterns

**Files:**
- `snake_case` for all module files: `cache_manager.py`, `env_vars.py`, `test_database.py`
- Session constants in `constants/` subdirectory: `urls.py`, `patterns.py`
- CLI layer: `tdoc_app.py`, `spec_app.py`, `mgmt_app.py` for Typer entry points

**Functions:**
- `snake_case` for functions and methods: `resolve_cache_manager()`, `normalize_tdoc_id()`, `create_workspace()`
- Private helpers prefixed with `_`: `_parse_spec_number()`, `_decompress_body()`, `_strip_prefixes()`
- Factory functions use descriptive names: `create_cached_session()`, `get_logger()`, `get_metrics_tracker()`

**Variables:**
- `snake_case` for local variables and instance attributes: `cache_dir`, `sample_tdocs`, `test_db_path`
- Module-level constants use `UPPER_CASE` with `Final` type: `DEFAULT_DATABASE_FILENAME`, `MEETINGS_BASE_URL`
- Logger instances: `_logger` (private) or `logger` (public) — set at module level via `get_logger(__name__)`

**Types/Classes:**
- `PascalCase` for classes and models: `CacheManager`, `TDocMetadata`, `ThreeGPPConfig`
- `PascalCase` for custom exceptions: `CacheManagerNotRegisteredError`, `NormalizationError`, `DatabaseError`
- Enum members: individual members `UPPER_CASE` (e.g., `WorkingGroup.RAN`), not used in code directly
- Typed argument aliases use `PascalCase`: `TdocIdArgument`, `WorkingGroupOption`, `OutputFormatOption`

## Code Style

**Formatting:**
- Tool: `ruff format` (with `ruff.toml` config)
- Line length: **160 characters** (`line-length = 160`)
- Docstring code line length: 160
- Target Python version: `py314`
- `undersort` pre-commit hook enforces method ordering: public → protected → private
- `from __future__ import annotations` in **every** module (enforced by `pyupgrade`/`UP` rules)

**Linting:**
- Tool: `ruff check` — ruleset in `ruff.toml`:
  - `E`, `W` — pycodestyle
  - `F` — Pyflakes
  - `I` — isort (import ordering)
  - `D` — pydocstyle (Google convention)
  - `ANN` — flake8-annotations (type annotations required)
  - `PL` — Pylint (complexity, antipatterns)
  - `SIM` — flake8-simplify
  - `S` — flake8-bandit (security)
  - `C4`, `C90` — comprehensions, complexity
  - `PT` — flake8-pytest-style
- Critical enforced rules: `PLC0415` (no import-outside-top-level), `E402` (module-import-not-at-top-of-file)
- Per-file ignores: `tests/` relaxes `S101`, `S106`, `S603` (bandit warns about test assets); `tdoc_app.py` allows `E402` for `load_dotenv()` ordering

## Import Organization

**Standard order (enforced by ruff `I`/isort):**
1. `from __future__ import annotations` — always first
2. Standard library imports
3. Third-party imports (`typer`, `pydantic`, `rich`, `niquests`, etc.)
4. `tdoc_crawler.*` local imports

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field
import typer

from tdoc_crawler.config import CacheManager
from tdoc_crawler.logging import get_logger
```

**Path Aliases:**
- No import path aliases (no `@src` or `~` prefixes). All imports are relative to the `src/` root via the `tdoc_crawler` package.
- `pyproject.toml` sets `pythonpath = ["src"]` for pytest.

**`__all__` Exports:**
- Every package `__init__.py` declares an `__all__` list with **sorted** public API (enforced by `RUF022` unsorted-dunder-all rule):
  ```python
  __all__ = [
      "CacheManager",
      "CacheManagerNotRegisteredError",
      "resolve_cache_manager",
  ]
  ```

## Error Handling

**Strategy:** Raise explicitly typed exceptions. Never return `None` as an error signal. Let errors propagate unless there is a specific recovery strategy.

**Custom Exception Hierarchy:**
- `DatabaseError(RuntimeError)` in `database/errors.py` — database constraint/execution failures
- `CacheManagerNotRegisteredError(RuntimeError)` in `config/cache_manager.py` — missing CacheManager registration
- `NormalizationError(ValueError)` in `utils/normalization.py` — spec number parsing failures
- `SpecNotFoundError` in `specs/sources/threegpp.py` — spec resolution failures

**Patterns:**
```python
# ✅ CORRECT — raise dedicated exception with diagnostic info
if CacheManager._instance is None:
    raise CacheManagerNotRegisteredError("CacheManager not registered.")
```

**Anti-patterns (explicitly forbidden per `docs/development.md`):**
- Do **NOT** catch `CacheManagerNotRegisteredError` to create a fallback — let it fail
- Do **NOT** return `None` to encode errors — use exceptions
- Do **NOT** use inconsistent return types (`InfoObject | str | None`)
- Do **NOT** use `typing.TYPE_CHECKING` as a circular import workaround — refactor to `models/` layer instead

## Logging

**Framework:** Standard `logging` module with `RichHandler` (from `rich.logging`)

**Implementation:** `src/tdoc_crawler/logging/__init__.py`
- Root logger configured once via `@functools.cache` (`configure_logger()`)
- Factory function `get_logger(name: str) -> logging.Logger` — cached per name
- Default level: `logging.WARNING`
- Level set via `set_verbosity(level)` at CLI startup

**Patterns:**
```python
# Module-level logger (highest scope safe)
from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)
```

**Usage conventions:**
- Use `_logger.debug()` for diagnostics, `_logger.info()` for key events, `_logger.warning()` for recoverable issues, `_logger.error()` for failures
- Never use `print()` — always use logger or `console` from `rich.console`
- CLI output uses `rich.console.Console` (via `get_console()` singleton) for user-facing messages

## Comments

**Docstrings:**
- **Google-style** docstrings (configured in `ruff.toml`: `convention = "google"`)
- Required for public functions/classes (enforced by pydocstyle `D` rules with relaxed granularity — module-level `D100` ignored)
- Docstring code formatting enabled: `docstring-code-format = true`

**When to Comment:**
- Module-level docstrings describe purpose and usage
- Class docstrings with `Example:` sections where helpful
- Function docstrings with `Args:` and `Returns:` for public API
- Inline comments only for non-obvious logic (sparingly — let code self-document)

## Function Design

**Size:** No hard limit, but `PLR0912` (too-many-branches) and `PLR0913` (too-many-arguments) are ignored. `max-locals = 20` (pylint).

**Parameters:**
- Use `*` for keyword-only arguments where appropriate: `def delete_workspace(workspace, *, delete_artifacts=False)`
- Type annotations on all parameters (enforced by `ANN` rules, except `ANN002`, `ANN003` ignored for `*args`/`**kwargs`)
- Return type annotations required (enforced by `ANN` rules, except `ANN204` for dynamic types)

**Return Values:**
- Consistent return types (no `Union[str, None]` as error encoding)
- Use `None` only for optional values where the semantics are "not applicable," not "error occurred"

## Module Design

**Exports:**
- Explicit `__all__` in every `__init__.py`
- Re-export from `__init__.py` for top-level convenience: `from tdoc_crawler.config import CacheManager`
- Do **NOT** re-export from domain packages to avoid circular imports (`tdocs/operations/` imports are explicit submodule imports)

**Package Structure:**
- `cli/` — thin Typer/Rich wrappers only; all logic in core library
- `models/` — shared types, enums, dataclasses (the neutral layer for cross-domain types)
- `database/` — SQLite/pydantic-sqlite persistence
- Domain packages (`tdocs/`, `specs/`, `meetings/`) — operations and domain-specific models

## Type Annotation Patterns

- Use `X | None` (not `Optional[X]`)
- Use `list[X]`, `dict[K, V]` (not `typing.List`, `typing.Dict`)
- `Annotated[X, typer.Argument(...)]` for CLI argument types in `cli/args.py`
- `ClassVar` for class-level mutable state: `_instance: ClassVar[CacheManager | None] = None`
- `Final[str]` for module-level immutable constants
- `StrEnum` with `auto()` for string enumeration types

## Pydantic Model Conventions

- Use `pydantic.BaseModel` for data models that enter the database
- Use `@dataclass` for simple data holders not stored in DB (e.g., `PortalCredentials`)
- `field_validator` with `mode="before"` for input normalization
- `AliasChoices` for env var + config key dual resolution
- `model_config = SettingsConfigDict(env_prefix="...", ...)` for pydantic-settings models

## Forbidden Patterns

| Pattern | Why Forbidden | Reference |
|---------|---------------|-----------|
| Hardcoded paths (`~/.3gpp-crawler`) | Must use `CacheManager` | `AGENTS.md`, `docs/development.md` |
| `typing.TYPE_CHECKING` for circular imports | Refactor to `models/` layer instead | `docs/development.md` |
| Inline imports (`import` inside functions) | Violates `PLC0415` rule | `ruff.toml` |
| Defensive CacheManager fallbacks | Let it fail if not registered | `docs/development.md` |
| Returning `None` for errors | Use exceptions with consistent return types | `docs/development.md` |
| CLI containing business logic | `cli/` is thin — all logic in core | `AGENTS.md` |
| HTTP requests without `create_cached_session()` | Must use cached session | `AGENTS.md` |
| Hardcoded env var strings in CLI options | Use `ConfigEnvVar` enum | `cli/args.py` |

---

*Convention analysis: 2026-05-03*
