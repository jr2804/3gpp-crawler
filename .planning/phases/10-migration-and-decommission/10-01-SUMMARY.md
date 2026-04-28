# Plan 10-01 SUMMARY — Deprecate Legacy Paths and Update Documentation

**Phase:** 10-migration-and-decommission
**Plan:** 01
**Executed:** 2026-04-28

## Changes Made

### Task 1: Add deprecation warnings to legacy CLI commands

- **Result:** No-op — CLI files (`tdoc_app.py`, `spec_app.py`, `mgmt_app.py`) contained no references to "rag", "lightrag", "embedding", or "vector". Phase 08 already cleaned these up.
- **Files checked:** `src/tdoc_crawler/cli/tdoc_app.py`, `src/tdoc_crawler/cli/spec_app.py`, `src/tdoc_crawler/cli/mgmt_app.py`

### Task 2: Update documentation for wiki-first architecture

- **`docs/ai.md`:** Added "## Current Architecture" section describing wiki-first architecture after the deprecation notice. Changed "provides" to "previously provided".
- **`docs/index.md`:** Updated AI entry to mention wiki-first architecture.
- **`README.md`:** Added "Wiki-First Architecture" to Features list.
- **`docs/query.md`:** Already had deprecation notice — no additional changes needed.

## Files Modified

- `docs/ai.md` — Added Current Architecture section
- `docs/index.md` — Updated AI entry description
- `README.md` — Added wiki-first feature entry

## Verification

- All 30 CLI tests pass
- All 25 cache manager + wiki path tests pass
- Syntax verified on all modified files

## Requirements Addressed

- **MIGR-01**: Legacy paths checked — no legacy references remain in CLI code
- **MIGR-02**: Documentation updated to describe wiki-first architecture
