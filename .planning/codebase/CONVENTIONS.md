# Coding Conventions

**Analysis Date:** 2026-05-03

## Naming Patterns

**Files:**
- Snake_case for Python modules: `cache_manager.py`, `crawl.py`, `date_parser.py`
- Test files prefixed with `test_`: `test_models.py`, `test_database.py`
- Sub-packages as directories with `__init__.py`

**Functions:**
- snake_case for all functions: `normalize_tdoc_id()`, `resolve_cache_manager()`
- Private helpers prefixed with single underscore: `_parse_date()`, `_build_scope_description()`
- Field validators use `_validate_` prefix: `_validate_status()`, `_validate_agenda_item_nbr()`
- Field serializers use `_serialize_` prefix: `_serialize_status()`

**Variables:**
- Path variables use suffix convention: `cache_dir`, `db_file`, `checkout_dir`, `http_cache_file` (never `dir_cache`, `file_db`)
- Module-level private defaults use `_UPPER_SNAKE` prefix: `_DEFAULT_CACHE_DIR_STR`, `_DEFAULT_DATABASE_FILENAME`
- Regex patterns use `UPPER_SNAKE`: `TDOC_PATTERN`, `DATE_PATTERN`, `_DOTTED_BODY_PATTERN`
- Constants use `UPPER_SNAKE`: `DEFAULT_LEVEL`, `BROWSER_HEADERS`, `TDOC_SUBDIRS`

**Types:**
- Pipe syntax for unions: `str | None`, `Path | str | None` — **never** `Optional[T]` or `Union[T, None]`
- Type aliases at module level: `StructuredData = dict | list | str | int | float | bool | None`
- Pydantic models use PascalCase: `TDocMetadata`, `MeetingCrawlConfig`, `ThreeGPPConfig`
- Enums use PascalCase members: `WorkingGroup.RAN`, `TDocStatus.AGREED`
- `Final` for constants: `DEFAULT_LEVEL: Final[int] = logging.WARNING`

**CLI Option Types:**
- Typer options defined as module-level `Annotated` aliases in `src/tdoc_crawler/cli/args.py`
- Naming convention: `{Name}Option`, `{Name}Argument` (PascalCase): `WorkingGroupOption`, `TDocIdsArgument`, `ForceOption`

## Code Style

**Formatting:**
- Ruff formatter (replaces Black)
- Line length: 160 characters
- Target: Python 3.14
- Docstring code blocks: also 160 chars line length

**Linting:**
- Ruff with preview rules enabled
- Key rule categories: E, F, C4, C90, D, I, PT, PL, SIM, UP, W, S, ANN, B, NPY
- Extended: RUF022 (sorted `__all__`), PLR6301 (no-self-use), PLC0415, E402
- Docstring convention: Google style (`[lint.pydocstyle] convention = "google"`)

**Key Ignored Rules (intentional):**
- D100–D107 (module/class/function docstrings not required)
- PLR0913 (many parameters allowed for config models)
- ANN401 (dynamically typed expressions allowed)
- C901 (complex structure — mccabe)

**Forbidden Patterns (non-negotiable):**
- PLC0415 (`import-outside-top-level`) — **NEVER** introduce inline imports
- No `# noqa` comments to suppress legitimate linting issues
- No `TYPE_CHECKING` guards
- No `.format()` or `%` string formatting — **f-strings only**
- No hardcoded paths like `~/.3gpp-crawler` — use `CacheManager`
- No hardcoded string values — use existing enums/structures from `constants/`, `models/`, or `ConfigEnvVar`

## Import Organization

**Order (enforced by Ruff isort):**
1. Standard library: `from __future__ import annotations`, then `pathlib`, `re`, `asyncio`, etc.
2. Third-party: `pydantic`, `typer`, `rich`, `pytest`, etc.
3. Local application: `from tdoc_crawler.config import ...`, `from tdoc_crawler.models import ...`

**Pattern:**
```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer
from pydantic import BaseModel, Field

from tdoc_crawler.config import CacheManager
from tdoc_crawler.logging import get_logger
```

**Path Aliases:**
- No path aliases configured (no `tsconfig`-style paths)
- All imports use full package path: `from tdoc_crawler.cli.args import ...`
- Workspace packages imported by name: `from pool_executors.pool_executors import ...`

**`__all__` exports:**
- Every module defines `__all__` as a list of public names
- Ruff RUF022 enforces sorted `__all__`

## Error Handling

**Patterns:**
- Custom exceptions inherit from domain-appropriate base: `CacheManagerNotRegisteredError(RuntimeError)`, `NormalizationError(ValueError)`, `ConfigLoadError(Exception)`
- Raise with `from` for exception chaining: `raise ValueError(f"...") from exc` (see `src/tdoc_crawler/utils/normalization.py`)
- Database errors wrapped in `DatabaseError`
- Never silently swallow errors — let CacheManagerNotRegisteredError propagate if not registered
- Pydantic validators return normalized values or raise `ValueError`

**Anti-patterns:**
```python
# ❌ WRONG — defensive fallback for CacheManager
try:
    manager = resolve_cache_manager()
except CacheManagerNotRegisteredError:
    manager = CacheManager(default_cache_dir).register()

# ✅ CORRECT — let it fail, registration is a dev concern
manager = resolve_cache_manager()
```

## Logging

**Framework:** Standard `logging` with Rich handler via `src/tdoc_crawler/logging/__init__.py`

**Logger acquisition:**
```python
from tdoc_crawler.logging import get_logger
_logger = get_logger(__name__)
```

**Patterns:**
- Module-level logger: `_logger = get_logger(__name__)` at top of module
- Use `_logger.debug()`, `_logger.info()`, `_logger.warning()` etc.
- Rich markup supported in log messages
- Verbosity set via `set_verbosity(level)` at CLI entry points
- Default level: `WARNING` (constant `DEFAULT_LEVEL`)

## Comments

**When to Comment:**
- Google-style docstrings for all public classes and functions
- Module-level docstring in every `.py` file
- Docstrings include `Args:`, `Returns:`, `Raises:` sections
- Include `Examples:` section for utility functions

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Pydantic `Field(description=...)` serves as inline documentation for model fields

## Function Design

**Size:** Functions range from single-line helpers to ~50 line methods. Complex operations broken into helper functions.

**Parameters:** Use Pydantic config models (e.g., `TDocCrawlConfig`, `TDocQueryConfig`) for functions with many parameters rather than long parameter lists.

**Return Values:**
- Pydantic models for structured data: `TDocMetadata`, `MeetingMetadata`
- Result dataclasses/tuples for operation outcomes: `TDocCrawlResult(processed, inserted, updated, errors)`
- `bool` for success/failure where appropriate
- `None` for void operations

## Module Design

**Exports:**
- Every module defines `__all__` with all public names
- Package `__init__.py` re-exports from submodules for convenient imports
- Example: `from tdoc_crawler.config import CacheManager, resolve_cache_manager`

**Barrel Files:**
- Used selectively in `__init__.py` files for major subpackages
- Domain packages (`tdocs/`, `meetings/`, `specs/`) do **not** re-export operations to avoid circular imports

**CLI thin layer:**
- `src/tdoc_crawler/cli/` contains only Typer/Rich wrappers
- All domain logic belongs in `src/tdoc_crawler/<domain>/`
- CLI commands call core library functions; never implement business logic in CLI

## Async Patterns

- Database operations are async: `async with TDocDatabase(db_file) as db:`
- CLI bridges sync→async with `asyncio.run()`: `result = asyncio.run(run_tdoc_crawl())`
- Async context managers for database connections
- `@pytest.mark.asyncio` for async test methods

## Configuration Patterns

**Config precedence (highest to lowest):**
1. CLI explicit `--config` parameter
2. Discovered config files (later overrides earlier)
3. Environment variables (`TDC_*`, `TDC_EOL_*`, `TDC_CRAWL_*`, `HTTP_CACHE_*`)
4. Hard-coded defaults

**Environment variables:**
- Defined as `ConfigEnvVar` enum in `src/tdoc_crawler/config/env_vars.py`
- CLI options reference env vars via `ConfigEnvVar.TDC_WORKING_GROUP.name`
- pydantic-settings `AliasChoices` maps env vars to config fields

**Singleton pattern:**
- `CacheManager` uses class-level `_instance` singleton
- Registered once at CLI startup via `CacheManager(cache_dir).register()`
- Resolved everywhere via `resolve_cache_manager()`
- Reset in tests via `_reset_cache_manager` autouse fixture

## Pre-commit Hooks

**Config:** `.pre-commit-config.yaml`
- `ruff-check` with `--exit-non-zero-on-fix`
- `ruff-format`
- `undersort` (method visibility ordering: public → protected → private)
- Standard hooks: check-toml, check-yaml, check-json, end-of-file-fixer, trailing-whitespace

---

*Convention analysis: 2026-05-03*
