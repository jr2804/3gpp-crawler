# 08-03 Summary: Re-integrate Workspace Commands and Deprecate Standalone Entrypoint

## What Was Done

Re-integrated 3gpp-ai workspace commands into the main `tdoc-crawler` CLI and deprecated the standalone `3gpp-ai` entrypoint.

## Changes

### Main pyproject.toml

- Added `[project.optional-dependencies]` with `ai = ["3gpp-ai"]` extra
- Added `3gpp-ai = { workspace = true }` to `[tool.uv.sources]`

### Main CLI (src/tdoc_crawler/cli/tdoc_app.py)

- Added workspace sub-app registration with lazy import:

  ```python
  try:
      from threegpp_ai.cli._workspace_commands import app as workspace_app
      tdoc_app.add_typer(workspace_app, name="workspace", ...)
  except ImportError:
      pass  # 3gpp-ai not installed
  ```

### 3gpp-ai CLI Deprecation

- `packages/3gpp-ai/threegpp_ai/cli.py`: Replaced full CLI with deprecation shim that prints message and exits with code 1
- `packages/3gpp-ai/pyproject.toml`: Commented out `[project.scripts]` entry for `3gpp-ai`

## Verification

- ✅ Optional extra `[ai]` exists in main pyproject.toml
- ✅ Workspace sub-app registered in main CLI (with graceful fallback)
- ✅ Deprecation shim exists in 3gpp-ai cli.py
- ✅ Standalone entrypoint removed from pyproject.toml
- ✅ `uv.sources` includes `3gpp-ai = { workspace = true }`
- ✅ 10 passed in relevant tests

## Deviations

None.

## Next

Phase 08 complete. Update STATE.md and ROADMAP.md.
