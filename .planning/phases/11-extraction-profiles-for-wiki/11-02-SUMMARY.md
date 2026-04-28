# Plan 11-02 SUMMARY — Wire --profile CLI Flag

**Phase:** 11-extraction-profiles-for-wiki
**Plan:** 02
**Executed:** 2026-04-28

## Changes Made

### Task: Add --profile CLI flag to workspace process command
- **`src/tdoc_crawler/cli/_workspace_commands.py`:** Added:
  - `profile: str = typer.Option(DEFAULT_EXTRACTION_PROFILE.value, "--profile", ...)` parameter
  - Profile validation logic: converts string to `ExtractionProfile` enum, exits with error for invalid values
  - Passes profile to `convert_for_wiki()` function

## Files Modified
- `src/tdoc_crawler/cli/_workspace_commands.py` — Added `--profile` flag with validation

## Verification
- `uv run 3gpp-crawler workspace process --help` shows `--profile` option with choices: pdf-only, default, advanced
- All 30 CLI tests pass

## Requirements Addressed
- **WIKI-03**: Profile selection via CLI flag on workspace process command