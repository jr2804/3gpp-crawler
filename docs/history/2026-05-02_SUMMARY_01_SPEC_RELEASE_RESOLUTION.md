# Summary - 2026-05-02 - SPEC_RELEASE_RESOLUTION

## Problem

When adding a spec to a workspace multiple times with different releases (e.g. `--release latest` then `--release 18.0`), both workspace source directories ended up containing **identical files** from the wrong release. For example, `26261-REL18.0.0/` and `26261-REL19.0.0/` both contained REL19 files.

## Root Cause

Two bugs in the spec fetch pipeline:

1. **`fetch_spec_files()` ignored the requested release when scanning local files.** The spec checkout directory (`checkout/Specs/archive/{series}/{spec}/`) is shared across all releases. After REL19 was downloaded, requesting REL18 triggered a local scan of the entire tree, which returned REL19 files without checking the release.

2. **`_download_spec()` discarded the version-specific extracted directory path.** `checkout_specs_async()` returns `list[Path]` of version-specific subdirectories (e.g. `26261-i00/` for REL18), but the return value was ignored. The subsequent full-tree scan could return files from any release.

## Changes

### 1. Early Release Resolution at Add-Time

Added `resolve_spec_release()` in `specs/operations/checkout.py` — resolves ambiguous release selectors (`"latest"`, `"18"`, `"18.0"`) to full 3-part versions (e.g. `"18.0.0"`) via database lookup before the workspace member is created.

- Added `AutoCrawlSpecsOption` (`--auto-crawl-specs/--no-auto-crawl-specs`) to `cli/args.py`.
- Updated `workspace_add` in `cli/_workspace_commands.py` to resolve spec releases at add-time.
- Workspace member IDs now always contain a concrete release: `26261-REL18.0.0`.

Impacted files: `specs/operations/checkout.py`, `cli/args.py`, `cli/_workspace_commands.py`.

### 2. Version-Specific File Fetching

Fixed `fetch_spec_files()` in `extraction/fetch_spec.py` to respect concrete release versions:

- `_download_spec()` now returns the version-specific extracted directory `Path` (e.g. `.../26261-i00/`) instead of discarding it.
- `fetch_spec_files()` skips the local tree scan for concrete releases, downloads the correct version, and scans only the version-specific extracted directory.
- Local-first scan is preserved for generic selectors (`"latest"`, `"all"`, `None`).

Impacted file: `extraction/fetch_spec.py`.

## Design Principle

See `docs/development.md` — "Spec Release Resolution Must Be Concrete":

- **Resolve early**: Pin concrete version at add-time via `resolve_spec_release()`.
- **Respect downstream**: Fetch/convert functions must scan only version-specific directories, never the shared checkout tree.

## Verification

- Ruff lint: all checks passed.
- Pyright: no new diagnostics.
- 79/79 tests passed.
