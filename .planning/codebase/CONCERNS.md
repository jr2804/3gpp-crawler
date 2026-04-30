<!-- refreshed: 2026-04-30 -->
# Codebase Concerns

**Analysis Date:** 2026-04-30
**Source files:** 101 Python files in `src/tdoc_crawler/`
**Latest ruff:** 462 errors fixed, 306 remaining across 6 rule categories

---

## 1. Performance Concerns

### 1.1 Row-by-Row Bulk Upsert (No Transaction Wrapping)

Both `bulk_upsert_tdocs` and `bulk_upsert_meetings` iterate records
sequentially with individual `await` calls, each issuing a separate
DB transaction.

**Evidence:**
- `src/tdoc_crawler/database/tdocs.py:86-93` - for loop with individual upsert calls
- `src/tdoc_crawler/database/meetings.py:128-135` - same pattern for meetings

**Impact:** For 1000+ TDocs, this issues 1000+ individual SQL transactions.
No `atomic()` wrapper. No `bulk_create()` or `INSERT ... ON CONFLICT`.

**Severity:** Medium.

### 1.2 In-Memory Filtering (No SQL Push-Down)

`query_tdocs` loads ALL records into Python memory, then applies
6+ filter passes sequentially on the full list.

**Evidence:**
- `src/tdoc_crawler/database/tdocs.py:105` - `_table_rows(TDocMetadata)` loads everything
- `src/tdoc_crawler/database/tdocs.py:116-145` - 6+ sequential filter passes
- `src/tdoc_crawler/database/meetings.py:147-148` - same pattern

**Impact:** For 10K+ records, 6 passes x 10K = 60K comparisons.
No database indices used for filtering.

**Severity:** Medium.

### 1.3 SQLite Without WAL Mode

No `PRAGMA journal_mode=WAL` in any database init code.
`src/tdoc_crawler/database/base.py:103-104` creates `AsyncDatabase()` with no pragma config.

**Impact:** Read operations block during writes. Contention increases with concurrent access.

**Severity:** Low for single-user CLI.

### 1.4 Serial Spec Source Iteration (FIXED)

`src/tdoc_crawler/database/specs.py:427` now uses
`asyncio.gather(*fetch_tasks)` with `asyncio.to_thread`.

---

## 2. Error Handling Gaps

### 2.1 Broad `except Exception` Blocks (32 instances, 19 files)

**Intentional Wrapping (acceptable):**
- database/base.py:106, database/specs.py:341 -> DatabaseError
- specs/downloads.py:131 -> returns None
- extraction/conversion.py:207, extraction/convert.py:457 -> ConversionError
- clients/portal.py:231 -> PortalParsingError

**Should Be Narrowed:**
- cli/_workspace_commands.py:88,114,180,252,294
- cli/specs.py:94, cli/config.py:50, cli/config_app.py:150,220
- clients/portal.py:248, workspaces/crud.py:63

**Defensive Network (acceptable):**
- tdocs/operations/crawl.py:275, workers/tdoc_worker.py:54

**Swallow-and-Continue (risky):**
- tdocs/sources/portal.py:77,87
- specs/downloads.py:261,273

**Missing `raise ... from` Chain (Ruff B904 - 12 instances):**
- cli/_workspace_commands.py:246,256,324,330
- cli/config_app.py:69,149,152,161,219,222
- cli/specs.py:96, utils/security.py:77

### 2.2 Ruff TRY300 (5 instances)
cli/_workspace_commands.py:87, cli/config.py:48, cli/config_app.py:86,
config/workspace_registry.py:430, extraction/conversion.py:203,245

### 2.3 Ruff TRY401 (~10 instances)
cli/_workspace_commands.py:298, cli/utils.py:40
database/base.py:240,281, database/specs.py:341,514
config/workspace_registry.py:433, specs/downloads.py:131,274
tdocs/sources/doclist.py:450, tdocs/sources/portal.py:87

---

## 3. Architecture Concerns

### 3.1 Raw SQL Mixed with ORM

`src/tdoc_crawler/database/base.py:278` - `execute_raw(f"DELETE FROM {table_name}")`
flagged S608. Table names from hardcoded dict (safe) but pattern is fragile.

### 3.2 Async/Sync Boundary

`run_async()` helper at utils/async_helpers.py:17-37 handles both `asyncio.run()`
and running-loop fallback. Used 15+ times in CLI layer, 3 times in extraction.

**Risk:** Library functions using `run_async()` become uncallable from async context.

### 3.3 Configuration Complexity (17 functions with 8-25 args)

Ruff PLR0913 = 17 functions with >5 args:
- cli/crawl.py:100 = 25 args, cli/query.py:99 = 19 args
- cli/crawl.py:267 = 19 args, cli/_workspace_commands.py:335 = 10, :443 = 13
- Plus 7 more in extraction, specs, database modules

### 3.4 Singleton CacheManager with Global State

`CacheManager._instance` at config/cache_manager.py:131,134.
Test conftest.py must reset via autouse fixture.
workspaces/crud.py:63 has defensive fallback despite AGENTS.md prohibition.

### 3.5 Boolean Positional Arguments (~40 FBT violations)

Examples: cli/_shared.py:25-27 (3 bool positional defaults),
cli/crawl.py:107-115 (6 bool positional defaults).

---

## 4. Technical Debt

### 4.1 Ruff Lint Profile - 306 Remaining Errors

| Rule | Count | Description |
|------|-------|-------------|
| PLR0913 | ~17 | Too many function arguments |
| FBT001/2 | ~40 | Boolean positional arguments |
| BLE001 | ~12 | Blind except Exception |
| B904 | ~12 | Missing raise ... from |
| TRY300 | ~5 | Statement in else block |
| TRY401 | ~10 | Redundant exc in logging |
| G004 | ~6 | Logging f-string |
| SLF001 | ~6 | Private member access |
| DTZ005/7 | ~5 | Naive datetime |
| PLR2004 | ~12 | Magic value comparison |
| ARG001/2 | ~5 | Unused args |
| S608 | 1 | Possible SQL injection |
| ERA001 | ~3 | Commented-out code |
| C901 | ~3 | Function too complex |
| D100-D107 | ~15 | Missing docstrings |

Critical: BLE001 (blind exceptions), B904 (missing chain), S608 (injection).

### 4.2 Unused Function Arguments (9)

- cli/query.py:118 (graph_rag), extraction/checkout.py:37 (workspace)
- extraction/convert.py:314 (output_file)
- tdocs/sources/portal.py:57-58 (db_file, timeout)
- tdocs/sources/whatthespec.py:138 (db_file)
- tdocs/operations/fetch.py:101 (session)
- specs/operations/checkout.py:39 (cache_manager_name)
- tdocs/operations/checkout.py:239 (cache_manager_name)
- utils/normalization.py:62 (spec_input)

### 4.3 Commented-Out Code (3)

- config/env_vars.py:39, logging/__init__.py:31-32, tdocs/sources/doclist.py:195

### 4.4 Missing Docstrings (~15)

utils/__init__.py, utils/date_parser.py, utils/parse.py (public modules)
database/base.py:81,100,113, config/sources.py:47
config/workspace_registry.py:121,132,157,222, database/errors.py:9,14
extraction/convert.py:54, meetings/operations/crawl.py:43
tdocs/operations/crawl.py:41, specs/downloads.py:29,34

### 4.5 Test Suite - 71 Failed + 25 Errors

Current: 386 passed, 71 failed, 12 skipped, 25 errors (40.46s).

Categories:
- pydantic-sqlite API changes (~50 failures)
- CLI command tests (~15 from refactoring)
- WhatTheSpec live API (~10)
- pydantic init errors (~25 ERRORs)

### 4.6 SpecQueryFilters Validation

SpecQueryFilters accepts arbitrary strings without Pydantic validators.

### 4.7 Function Complexity (C901 - 3 functions)

- cli/_workspace_commands.py:228 - workspace_process (11)
- workspaces/utils.py:64 - resolve_spec_release_from_db (11)
- workspaces/utils.py:154 - checkout_tdoc_to_workspace (12)

---

## 5. Security Considerations

### 5.1 Input Validation - normalize_tdoc_id

Used in 12 files. Regex + .upper() only. No length checks or char whitelisting.

### 5.2 Credential Handling - resolve_credentials

Resolves from CLI, config, env vars, prompt. Credentials visible in process output.
Guard: sys.stdin.isatty() at credentials.py:49.

### 5.3 SQL Injection - Raw Table Name

database/base.py:278 flagged S608. Safe (hardcoded dict) but fragile pattern.

### 5.4 SSRF Protection (ADEQUATE)

validate_api_url() at utils/security.py:39-84 validates scheme, resolves DNS,
blocks private/loopback/reserved/multicast IPs.

### 5.5 No TLS Pinning

Standard HTTPS trust only. No certificate pinning for 3GPP endpoints.
Acceptable for CLI tool.

---

## 6. Already Fixed (Reference)

### 6.1 Spec Source Crawl Parallelization (FIXED)
specs.py:427 asyncio.gather + asyncio.to_thread

### 6.2 SQL LIKE Injection (CONFIRMED SAFE)
Uses fnmatch, not SQL LIKE

### 6.3 --cache-dir (REMOVED)

### 6.4 Event Loop Guards (IN PLACE)
run_async() handles both scenarios

### 6.5 Exception Narrowing (PARTIAL)
10+ blocks narrowed, 32 remain

### 6.6 Dead Code Removal (PARTIAL)
Unused funcs/enums/tests removed. 9 unused args remain

### 6.7 Complexity Reduction (PARTIAL)
_apply_meeting_filters decomposed. 3 funcs still too complex

---

## 7. Summary

### Critical (fix immediately):
None. No code-execution or data-exfiltration vulnerabilities.

### High Priority (next sprint):
- Test suite: 71 failures + 25 errors (pydantic-sqlite API changes)
- except Exception narrowing: 12 BLE001 instances in CLI layer

### Medium Priority:
- Missing raise ... from: 12 B904 violations
- WAL mode: one-line change for concurrent reads during writes
- Commented-out code: 3 blocks
- Boolean positional args: ~40 FBT violations
- Unused args: 9 ARG001/ARG002 violations

### Low Priority:
- Magic values: ~12 PLR2004 violations
- Naive datetime: 5 DTZ005/DTZ007 violations
- Logging f-strings: 6 G004 violations
- Docstrings: ~15 missing on public API surface

---

Concerns analysis: 2026-04-30 - Fresh ruff lint run, exception audit,
async/sync boundary analysis, test status, and security review.
306 ruff issues remain post-refactoring.