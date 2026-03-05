# CLI Submodule Guidelines

## Design Principle

The `cli/` submodule contains **only CLI-related functionality**. The core `tdoc_crawler` package is a standalone library. Think of `cli/` as an optional extras package.

**STRICT RULE: NEVER duplicate core library logic in CLI.** If functionality belongs in the core, move it there and have CLI import it.

## Classification Rules

### CLI Code (belongs in `cli/`)

- Typer command definitions (`@app.command()`)
- Typer argument/option types (`Annotated[...]`)
- Rich console output and formatting
- CLI-specific input parsing
- System calls for opening files

### Library Code (belongs in core)

- Data models and schemas
- Database operations
- HTTP fetching and caching
- Data normalization/transformation
- File I/O operations

**Rule of thumb:** If useful to a Python developer using `tdoc_crawler` as a library, it belongs in the core.

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `app.py` | Typer command definitions |
| `args.py` | Typer Annotated types |
| `console.py` | Rich Console singleton |
| `utils.py` | CLI helpers (check classification rules) |
| `printing.py` | Table and output formatting |

## Lessons Learned

### Circular Import Resolution

Circular import between `database/` and `specs/` was resolved by creating neutral `models/specs.py` layer for shared types. Both modules import from `models/` without circularity.

**Key Insight:** Circular imports indicate structural problems. Never use `TYPE_CHECKING` or local imports as workarounds—refactor module organization instead.

### Domain-Oriented Refactoring

Legacy `crawlers/` package was eliminated:

**Before:**
```python
from tdoc_crawler.crawlers import TDocCrawler, MeetingCrawler
```

**After:**
```python
from tdoc_crawler.tdocs import TDocCrawler
from tdoc_crawler.meetings import MeetingCrawler
```

**Result:** `crawlers/` folder no longer exists. All functionality lives in domain packages.

### Import Pattern

- CLI (`cli/`) → Core (`tdoc_crawler/`)
- Core submodules → Common layer (`models/`)
- **Never:** Core importing from CLI
