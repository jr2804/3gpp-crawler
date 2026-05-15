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

## CRITICAL: Spec Source Directory Naming

Spec source directories under `wiki/<workspace>/sources/` **MUST** include the `-REL<version>` suffix:

```
# CORRECT
wiki/atias/sources/26260-REL18.0.0/
wiki/atias/sources/26131-REL19.0.0/

# WRONG — NEVER do this
wiki/atias/sources/26260/
wiki/atias/sources/26131/
```

When processing a spec workspace member:
1. If the member ID already has `-REL` (e.g. `26260-REL18.0.0`), use it as-is.
2. If the member ID is bare (e.g. `26131`), resolve the release from the database and construct the full ID.
3. If the release cannot be resolved, fall back to the bare ID.

This applies to **all** code paths that create or reference spec source directories:
- `_effective_source_id()` / `_resolve_spec_source_id()`
- `_process_member()` — `wiki_source_dir` construction
- `_should_skip_member()` — existing output detection

A regression test exists in `TestSpecSourceDirNaming` (test_workspaces.py).

## Idempotent Processing

`workspace process` MUST be idempotent — running it twice without `--force` produces the same result as running it once. Existing output files are never overwritten.

Two-layer protection:

1. **`_should_skip_member()`** (fast path): Checks if output artifacts exist before entering `convert_for_wiki()`. Controlled by `--skip-existing` (default: True).

2. **`convert_for_wiki()`** (hard guarantee): Each profile branch checks for existing output and returns early when `force=False`:
   - `PDF_ONLY`: `ensure_pdf()` skips if PDF exists
   - `MARKDOWN_ONLY`: skips if `.md` exists
   - `DEFAULT`/`ADVANCED`: skips if both `.md` and `.json` exist

The `--force` flag is the ONLY way to overwrite existing output. It defaults to `False`.

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

## CRITICAL: Multi-Value CLI Options Must Use StrEnum

CLI options accepting two or more fixed string values **MUST** be backed by `StrEnum` classes — never bare `str` with manual validation.

```python
# CORRECT — StrEnum defined alongside ExtractionProfile in profiles.py
class FiguresMode(StrEnum):
    EMBED = "embed"
    REFERENCE = "reference"

# CLI option uses the enum type directly
FiguresModeOption = Annotated[
    FiguresMode,
    typer.Option("--figures", ...),
]

# WRONG — bare str with manual if/else validation
FiguresModeOption = Annotated[str, typer.Option("--figures", ...)]
# ... then later:
if figures not in ("embed", "reference"):  # ← NEVER do this
```

**Why:** Typer validates enum values automatically. No manual string checks, no typos, no forgotten cases. The enum is the single source of truth for valid values.

**Where to define:** Extraction-related enums go in `extraction/profiles.py` alongside `ExtractionProfile`. Domain-agnostic enums go in `models/base.py`.

**Current enums:** `ExtractionProfile`, `FiguresMode`, `TablesMode`, `DeviceType`, `SourceKind`, `TDocStatus`, `OutputFormat`, `SortOrder`.
