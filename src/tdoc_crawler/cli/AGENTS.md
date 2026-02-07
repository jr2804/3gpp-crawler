# CLI Submodule Guidelines

This document provides guidelines for development in the `tdoc_crawler.cli` submodule.

## Design Principle

The `cli/` submodule should contain **only CLI-related functionality**. The core `tdoc_crawler` package should be usable as a standalone library without depending on the CLI. Think of `cli/` as an optional extras package (installable as `tdoc_crawler[cli]`).

## Classification Rules

When deciding whether code belongs in `cli/` or the core library, ask:

### Is this clearly CLI code?

- Typer command definitions (`@app.command()`)
- Typer argument/option types (`Annotated[...]` with `typer.Option/Argument`)
- Rich console output and formatting
- CLI-specific parsing of user input strings
- System calls for opening files (`os.startfile`, `xdg-open`)

### Is this clearly library code?

- Data models and schemas
- Database operations
- HTTP fetching and caching
- Data normalization and transformation
- File I/O operations

### When in doubt...

Assume `cli/` could be separated as an optional package. If a function would be useful to a Python developer using `tdoc_crawler` as a library, it belongs in the core package.

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `app.py` | Typer command definitions and CLI entry points |
| `args.py` | Typer Annotated types for arguments and options |
| `console.py` | Rich Console singleton for CLI output |
| `helpers.py` | Helper functions - check classification rules above |
| `fetching.py` | TDoc fetching - check classification rules below |
| `printing.py` | Table and output formatting for CLI |

## Function Classification

### `helpers.py`

**CLI Functions (stay in cli/):**

- `parse_working_groups()` - CLI argument parsing
- `parse_subgroups()` - CLI argument parsing
- `collect_spec_numbers()` - CLI stdin/file input handling
- `build_limits()` - CLI config builder wrapper
- `launch_file()` - System calls for opening files
- `resolve_http_cache_config()` - CLI/env var configuration parsing
- `infer_working_groups_from_ids()` - CLI string inference

**Library Functions (moved to core):**

- `normalize_portal_meeting_name()` → `tdoc_crawler.specs.normalization`
- `resolve_meeting_id()` → `tdoc_crawler.database`
- `download_to_path()` → `tdoc_crawler.http_client`
- `prepare_tdoc_file()` → `tdoc_crawler.checkout`
- `database_path()` → `tdoc_crawler.database`

### `fetching.py`

**CLI Functions (stay in cli/):**

- `fetch_missing_tdocs()` - Uses CLI console output
- `_fetch_via_whatthespec()` - Uses CLI console output
- `maybe_fetch_missing_tdocs()` - CLI console and flag handling

**Library Functions:**

- `fetch_tdoc()` - Import from `tdoc_crawler.fetching` (not duplicated in CLI)

## Lessons Learned

### Circular Import Resolution

During the CLI refactoring, a circular import was discovered between `database/` and `specs/` modules:

```
database/__init__.py → database/connection.py → specs/query.py → specs/__init__.py → specs/catalog.py → database
```

**Solution:** Created a neutral `models/specs.py` layer for shared types (`SpecQueryFilters`, `SpecQueryResult`). Both `database/` and `specs/` import from `models/` without circularity.

**Key Insight:** Circular imports always indicate a structural problem. Never use TYPE_CHECKING or local imports to work around them - refactor the module organization instead.

### Import Pattern

The correct import direction is:

- CLI (`cli/`) → Core (`tdoc_crawler/`)
- Core submodules (`database/`, `specs/`, etc.) → Common layer (`models/`)

**Never:** Core modules importing from CLI modules.

### Before and After

**Before refactoring:**

- `cli/helpers.py` contained 5 library functions
- `cli/fetching.py` duplicated `fetch_tdoc()` from core
- Core modules could not be used independently

**After refactoring:**

- CLI contains only CLI-specific code
- All library functions in appropriate core modules
- Core package is a standalone library (installable without CLI extras)
