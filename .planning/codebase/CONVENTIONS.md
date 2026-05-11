# CONVENTIONS

Code style, naming, error handling, imports, CLI patterns, logging, docstrings, and
modelling conventions for the 3gpp-crawler project.

## Python Version

Python 3.13+ only (requires-python = ">=3.13,<4.0").
Code can use all 3.13 features (T | None is native and preferred).

## Code Style

### Type Hints

- **Use T | None, never Optional[T].** The project uses Python 3.13 and
  `from __future__ import annotations` in all files, so `str | None` is universal.
- **Use list[X], dict[K, V], tuple[X, ...]** from builtins -- never
  typing.List, typing.Dict, etc.
- **Use Self** for return type annotations of __aenter__ and factory methods
  (from typing import Self).
- **Use TYPE_CHECKING guards** for expensive type-only imports
  (e.g., from collections.abc import Iterable, from pathlib import Path).
  NOTE: TYPE_CHECKING is acceptable here (unlike the older tdoc-crawler project).
- **Avoid Any where possible.** Narrow types. Use cast() from typing
  when the type checker cannot infer.
- **Function return types are always annotated.**
  No bare `def foo()` without `-> ReturnType`.
- **Parameters use Annotated[type, ...]** for Typer CLI options/arguments.

### f-strings

- **Prefer f-strings** over % formatting or .format().
  Logging exception: `_logger.exception("Failed: %s", var)`
  (lazy evaluation in stdlib logging).
- No str() calls where an f-string would do.

### pathlib

- **Use pathlib.Path, never os.path.**
  No os.path.join(), os.path.exists(), etc.
  Directories: path.mkdir(parents=True, exist_ok=True).
- Paths resolved with .resolve() and expanded with .expanduser().
- ~ expansion: Path("~/.3gpp-crawler").expanduser(), not os.path.expanduser.

### Naming

- **Snake case everywhere:** snake_case for variables, functions, methods, modules.
- **PascalCase for classes**: Pydantic models, database classes, custom exceptions.
- **UPPER_CASE for module-level constants.**
- **Private methods/functions** prefixed with _
  (e.g., _normalize_tdoc_id, _ensure_tables_exist).

#### Path Variable Suffixes (CRITICAL)

Variables holding file paths MUST use _file suffix;
variables holding directory paths MUST use _dir suffix. Examples:

- db_file: Path -- path to a database file
- cache_dir: Path -- path to a cache directory
- checkout_dir: Path -- path to a checkout directory
- config_file: Path | None -- path to a config file
- http_cache_file: Path -- path to HTTP cache file
- output_dir: Path -- path to an output directory

Applies to all variables: function parameters, locals, dataclass/pydantic fields.

#### Test Naming

Tests follow test_<scenario> pattern for functions.
Test classes use Test<ClassName> or Test<Feature>:

```python
class TestTDocDatabase:
    async def test_upsert_tdoc(self) - None: ...
    async def test_case_insensitive_query(self) - None: ...
```

### Code Size Limits (Soft)

| Scope | Limit |
|-------|-------|
| Module | < 250 lines |
| Function | < 75 lines |
| Class | < 200 lines |

## Error Handling

### Exception Hierarchy

- **DatabaseError(RuntimeError)** -- Base exception for database failures.
  Uses code: str and optional detail: str.
  Factory classmethods like DatabaseError.connection_not_open().
- **CacheManagerNotRegisteredError(RuntimeError)** -- Singleton not yet registered.
- **NormalizationError(ValueError)** -- Input normalization failures.

### Patterns

- **Raise specific exceptions.** Never raise Exception("...").
  Each domain has its own exception class.
- **No bare except:**.
- **raise ... from exc** for exception chaining in context managers.
- **Let it fail:** Do not defensively wrap resolve_cache_manager().
  If not registered, that is a dev error.
- **pytest.raises(SomeError, match="...")** for asserting specific errors.

### Return Type Discipline

- **Avoid inconsistent return types.** A function returns X | None,
  not sometimes X, sometimes str, sometimes None.
  See docs/development.md for the documented antipattern.
- **Raise, don't return error strings.**
  Return None for "not found"; raise for invalid input.

## Imports

### Order

1. from __future__ import annotations (always first, mandatory)
2. Standard library
3. Third-party (pydantic, typer, pytest, etc.)
4. First-party: tdoc_crawler.*
5. Local (relative imports only in tests: from .conftest import ...)

### Style

- **Absolute imports** within tdoc_crawler. No relative imports in src/.
- **Never import *** -- project uses explicit __all__ in every module.
- **Prefer importing classes/functions over modules:**
  from tdoc_crawler.config import CacheManager.
- **No TYPE_CHECKING for circular import workarounds.**
  Extract shared types to models/ instead.
- **TYPE_CHECKING acceptable** for expensive type-only imports
  (Iterable, Path, Version) in non-hot paths.

## Pydantic Models vs Dataclasses

### Pydantic Models (pydantic.BaseModel)

Use for:
- Data crossing system boundaries (database, JSON, YAML, CLI)
- Data needing validation (field validators, type coercion)
- Configuration classes (BaseSettings via pydantic-settings)

Pattern:
```python
class TDocMetadata(BaseModel):
    tdoc_id: str = Field(..., description="...")
    meeting_id: int = Field(..., description="...")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        return normalize_tdoc_id(value)

    @field_serializer("agenda_item_nbr")
    def _serialize_agenda_item_nbr(cls, value: AgendaItemNumber) -> str: ...
```

Key practices:
- Field(..., description="...") on every field
- Validators: _validate_<field> or _normalize_<field>
- Serializers: _serialize_<field>
- model_config = {"str_strip_whitespace": True} on config models
- model_dump(mode="json") for serialization

### Dataclasses

Use @dataclass for:
- Simple DTOs without validation
- Internal data transfer objects
- Example: PortalCredentials(username: str, password: str)

## CLI Conventions

### Architecture

- **cli/ is thin** -- Only Typer command definitions and Rich formatting.
  All logic belongs in core library modules.
- **Never duplicate core library logic in CLI.**
  See src/tdoc_crawler/cli/AGENTS.md.

### Typer Annotated Pattern

All CLI parameters use Annotated[type, typer.Option(...)] in cli/args.py:

```python
# In args.py:
WorkingGroupOption = Annotated[
    list[str] | None,
    typer.Option("--working-group", "-w", help="...", envvar="TDC_WORKING_GROUP"),
]

# In command definition:
def crawl_tdocs(
    working_group: WorkingGroupOption = None,
    limit_tdocs: LimitTDocsOption = None,
) -> None: ...
```

### Rich Output

- console from tdoc_crawler.cli._shared or tdoc_crawler.logging.get_console()
- Rich Tables with TableColumnSpec for structured data
- Rich Markup: [red]Error[/red], [green]OK[/green]
- Progress bars via create_progress_bar() from tdoc_crawler.cli._shared

### Command Registration

Commands registered with app.command("name", rich_help_panel=...).
Aliases use hidden=True:
```python
tdoc_app.command("crawl", rich_help_panel=HELP_PANEL_CRAWLING)(crawl_tdocs)
tdoc_app.command("ct", rich_help_panel=HELP_PANEL_CRAWLING, hidden=True)(crawl_tdocs)
```

## Logging

- **Use get_logger(__name__)** from tdoc_crawler.logging.
- **Logger variable always named _logger.**
- **%-style formatting** for lazy evaluation:
  _logger.info("Found %d items", count).
- **_logger.exception(...)** for exception logging (includes traceback).
- **No logging.basicConfig()** -- root logger configured via configure_logger().
- Verbosity via set_verbosity(level).

## Docstrings

- **Google-style** (enforced by ruff: [lint.pydocstyle] convention = "google").
- **Required** for all public functions, classes, and methods (ruff D group).
- **Optional** for private/dunder methods (D100-D107 selectively ignored).
- Module-level docstrings are optional (D100 ignored).

## Ruff Configuration

See ruff.toml:

- target-version = "py313"
- line-length = 160
- preview = true
- Selected rule sets: E, F, C4, C90, D, I, PT, PL, SIM, UP, W, S, ANN, B, NPY
- Tests ignore: S101 (assert), S106, PLR6301, S603, PLW1510

## HTTP Caching

- **All HTTP requests MUST use create_cached_session()** from tdoc_crawler.http_client.
- Cache: SQLite via hishel.
- Session uses niquests (not requests).
- Pool configuration via PoolConfig.
- SSL verification via resolve_ssl_verify().