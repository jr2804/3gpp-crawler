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
| `utils.py` | Helper functions - check classification rules above |
| `printing.py` | Table and output formatting for CLI |


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
