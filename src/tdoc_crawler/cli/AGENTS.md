# CLI Submodule

CLI-only code conventions for the `tdoc_crawler` CLI.

## Design Principle

`cli/` contains **only CLI-related functionality**. The core `tdoc_crawler` package is a standalone library.

**STRICT RULE: NEVER duplicate core library logic in CLI.** If functionality belongs in the core, move it there and have CLI import it.

## Classification

### CLI Code (belongs in `cli/`)

- Typer command definitions (`@app.command()`)
- Typer argument/option types (`Annotated[...]`)
- Rich console output and formatting
- CLI-specific input parsing

### Library Code (belongs in core)

- Data models and schemas
- Database operations
- HTTP fetching and caching
- Data normalization/transformation

**Rule of thumb:** If useful to a Python developer using `tdoc_crawler` as a library, it belongs in the core.

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `app.py` | Typer command definitions |
| `args.py` | Typer Annotated types |
| `console.py` | Rich Console singleton |
| `utils.py` | CLI helpers (check classification rules) |
| `printing.py` | Table and output formatting |

## Import Direction

- CLI (`cli/`) → Core (`tdoc_crawler/`)
- Core submodules → Common layer (`models/`)
- **Never:** Core importing from CLI
