# Engineering Standards (Agent Notes)

This document contains the non-domain engineering rules that agents must follow in this repository.

## Repository workflow

- Use git, but do not run `git commit` or `git push` unless explicitly requested.
- Do not commit `.env` files.

## Dependency management

- Use `uv` for environments and dependency management.
- Prefer `uv run ...` over invoking Python directly.

## Python standards

- Use type hints everywhere.
- Prefer `pathlib.Path` over `os.path`.
- Prefer f-strings.
- Avoid `Optional[T] = None` type hints; use `T | None = None`.

## Code size constraints

Keep modules and symbols small to preserve maintainability:

- Modules (single `.py` file): < 250 lines (exception: CLI command registration file can be larger)
- Functions: < 75 lines
- Classes: < 200 lines

## Formatting and linting

After significant changes, run the project’s configured formatters/linters.

(Use the repo’s documented tooling; do not introduce new formatters without a strong reason.)

## Comment policy

- Comments should explain intent or subtle constraints, not restate names.
- Avoid decorative headings.
- Do not number “step” comments.

## Temporary files

If you need temporary artifacts during development, keep them out of the repo root.

See [docs/agents-md/100_Tool_Usage.md](100_Tool_Usage.md) for the expected temp directory convention.
