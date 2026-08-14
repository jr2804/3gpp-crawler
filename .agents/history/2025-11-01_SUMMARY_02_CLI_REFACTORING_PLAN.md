# CLI Refactoring Implementation Plan

## Overview

Refactor `src/tdoc_crawler/cli/` to contain only CLI-specific functionality, moving library functions to the core package. This enables `tdoc_crawler` to be used as a standalone library.

## Phase 1: Fix Fetching.py Duplication (CRITICAL)

### Issue #1: Remove Duplicate fetch_tdoc() from cli/fetching.py

**Priority:** High
**Complexity:** Low

**Steps:**

1. Remove `fetch_tdoc()` function from `src/tdoc_crawler/cli/fetching.py`
1. Import `fetch_tdoc` from `tdoc_crawler.fetching` at the top of the file
1. Update imports in `src/tdoc_crawler/cli/app.py` if needed
1. Run tests to verify functionality

**Files Changed:**

- `src/tdoc_crawler/cli/fetching.py`

______________________________________________________________________

## Phase 2: Move Library Functions from cli/helpers.py

### Issue #2: Move normalize_portal_meeting_name() to specs/normalization.py

**Priority:** Medium
**Complexity:** Low

**Steps:**

1. Add `normalize_portal_meeting_name()` function to `src/tdoc_crawler/specs/normalization.py`
1. Update import in `src/tdoc_crawler/cli/helpers.py` to import from core
1. Update any other files that import from `cli.helpers`
1. Run tests to verify

**Files Changed:**

- `src/tdoc_crawler/specs/normalization.py`
- `src/tdoc_crawler/cli/helpers.py`

______________________________________________________________________

### Issue #3: Move resolve_meeting_id() to database module

**Priority:** Medium
**Complexity:** Medium

**Steps:**

1. Add `resolve_meeting_id()` function to `src/tdoc_crawler/database/__init__.py` or a new helper module
1. Update `src/tdoc_crawler/cli/fetching.py` to import from database module
1. Remove function from `src/tdoc_crawler/cli/helpers.py`
1. Run tests to verify

**Files Changed:**

- `src/tdoc_crawler/database/__init__.py` (or new file)
- `src/tdoc_crawler/cli/helpers.py`
- `src/tdoc_crawler/cli/fetching.py`

______________________________________________________________________

### Issue #4: Move download_to_path() to http_client module

**Priority:** Medium
**Complexity:** Low

**Steps:**

1. Add `download_to_path()` function to `src/tdoc_crawler/http_client.py`
1. Update `src/tdoc_crawler/cli/helpers.py` to import from core
1. Update `src/tdoc_crawler/checkout.py` to import from core (it already imports from cli.helpers for this function)
1. Run tests to verify

**Files Changed:**

- `src/tdoc_crawler/http_client.py`
- `src/tdoc_crawler/cli/helpers.py`
- `src/tdoc_crawler/checkout.py`

______________________________________________________________________

### Issue #5: Move prepare_tdoc_file() to checkout module

**Priority:** Medium
**Complexity:** Medium

**Steps:**

1. Add `prepare_tdoc_file()` function to `src/tdoc_crawler/checkout.py`
1. Update `src/tdoc_crawler/cli/helpers.py` to import from checkout module
1. Update `src/tdoc_crawler/cli/app.py` if needed
1. Run tests to verify

**Files Changed:**

- `src/tdoc_crawler/checkout.py`
- `src/tdoc_crawler/cli/helpers.py`
- `src/tdoc_crawler/cli/app.py`

______________________________________________________________________

### Issue #6: Move database_path() to database module

**Priority:** Low
**Complexity:** Low

**Steps:**

1. Add `database_path()` function to `src/tdoc_crawler/database/connection.py` or `__init__.py`
1. Update all files importing from `cli.helpers` to import from database module
1. Remove function from `src/tdoc_crawler/cli/helpers.py`
1. Run tests to verify

**Files Changed:**

- `src/tdoc_crawler/database/connection.py`
- `src/tdoc_crawler/cli/helpers.py`
- All files that import `database_path` from `cli.helpers`

______________________________________________________________________

## Phase 3: Final Cleanup

### Issue #7: Update AGENTS.md with Final Classification

**Priority:** Low
**Complexity:** Low

**Steps:**

1. Update `src/tdoc_crawler/cli/AGENTS.md` to reflect completed refactoring
1. Document any remaining functions in `cli/helpers.py` and their classification

______________________________________________________________________

### Issue #8: Run Full Test Suite

**Priority:** Critical
**Complexity:** Low

**Steps:**

1. Run full test suite: `uv run pytest -v`
1. Verify all tests pass
1. Fix any regressions introduced by refactoring

______________________________________________________________________

## Dependency Order

1. **Issue #1** (fetch_tdoc duplication) - Can be done independently
1. **Issue #4** (download_to_path) - Checkout.py depends on it
1. **Issue #5** (prepare_tdoc_file) - Depends on download_to_path
1. **Issue #2** (normalize_portal_meeting_name) - Independent
1. **Issue #3** (resolve_meeting_id) - Independent
1. **Issue #6** (database_path) - Depends on understanding all imports
1. **Issue #7** (Update AGENTS.md) - After all refactoring
1. **Issue #8** (Full test suite) - After all refactoring

## Estimated Effort

| Issue | Complexity | Files Changed | Estimated Time |
|-------|------------|---------------|----------------|
| #1 fetch_tdoc | Low | 2 | 15 min |
| #2 normalize_portal_meeting_name | Low | 2 | 15 min |
| #3 resolve_meeting_id | Medium | 3 | 30 min |
| #4 download_to_path | Low | 3 | 15 min |
| #5 prepare_tdoc_file | Medium | 3 | 30 min |
| #6 database_path | Low | 4 | 20 min |
| #7 Update AGENTS.md | Low | 1 | 10 min |
| #8 Full test suite | Low | 1 | 10 min |
| **Total** | - | **~15 files** | **~2.5 hours** |
