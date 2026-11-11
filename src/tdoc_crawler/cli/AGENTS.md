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
| `mgmt_app.py` | `3gpp-crawler` entry point; mounts `tdoc`, `spec`, `config`, `tag`, `database`, `mcp` |
| `tdoc_app.py` | `tdoc-crawler` entry point: crawl, query, open, stats, checkout |
| `spec_app.py` | `spec-crawler` entry point: crawl, query, checkout, open |
| `config_app.py` | `config init`, `show`, `validate`, `docs` |
| `tag_app.py` | `tag add`, `remove`, `list` |
| `database_app.py` | `database` (alias `db`): `clear-tdocs`, `clear-specs`, `clear-meetings`, `clear-all`, `export-tags`, `import-tags`; owns all destructive DB operations |
| `mcp_app.py` | `mcp` command (Model Context Protocol server) |
| `checkout.py` | `tdoc checkout` command; standalone so `mcp_server` can import it without cycling through `tdoc_app` |
| `specs.py` | `spec checkout` and `spec open` commands |
| `crawl/`, `query/` | Command implementations for the crawl and query subcommands |
| `args.py` | Typer `Annotated` option and argument types |
| `_shared.py` | Shared Typer helpers (`GlobSafeTyper`, `parse_scope` for `--working-group`/`--sub-group`) |
| `utils.py`, `formatting.py`, `printing.py` | CLI helpers, output formatting, Rich tables |
| `constants.py`, `config.py` | CLI constants; `load_cli_config` |

`--working-group` is RAN/SA/CT only; sub-working group codes (`SA4`, `S4`, `R1`)
belong in `--sub-group`, and `parse_scope()` enforces that split. Exceptions:
`query/specs.py` filters on the stored sub-WG string via
`parse_spec_working_group()` (so `spec query -w SA4` works).

## Import Direction

- CLI (`cli/`) → Core (`tdoc_crawler/`)
- Core submodules → Common layer (`models/`)
- **Never:** Core importing from CLI

## CRITICAL: Multi-Value CLI Options Must Use StrEnum

CLI options accepting two or more fixed string values **MUST** be backed by `StrEnum` classes — never bare `str` with manual validation.

```python
# CORRECT — the enum is the single source of truth
class Mode(StrEnum):
    FAST = "fast"
    FULL = "full"

ModeOption = Annotated[
    Mode,
    typer.Option("--mode", ...),
]

# WRONG — bare str with manual if/else validation
ModeOption = Annotated[str, typer.Option("--mode", ...)]
if mode not in ("fast", "full"):  # ← NEVER do this
```

**Why:** Typer validates enum values automatically. No manual string checks, no typos, no forgotten cases.

**Where to define:** Domain-agnostic enums go in `models/base.py`; the logging level enum `LogLevel` lives in `logging/__init__.py` next to `set_verbosity()`. Domain enums stay in their domain module (e.g. `tdocs/models.py`, `models/working_groups.py`). Find current ones with `grep -rn "(StrEnum)" src/`.

## CRITICAL: Every Data Output Command Has `--output`

Any command that prints data or results (tables, lists, summaries, dumps) MUST accept `--output` / `-o` typed `OutputFormat` (`OutputFormatOption` in `args.py`, default `OutputFormat.TABLE`) and route through `print_structured_output()` / `format_output()` from `cli/formatting.py`. Machine formats must stay clean: no progress bars or status prose on stdout.

Exceptions (text-only by design): `version`, `open` (launches a file), `config init` (writes a file; its target path is a positional argument), `config docs`, and `crawl tdocs` / `crawl-meetings` (progress and status only).
