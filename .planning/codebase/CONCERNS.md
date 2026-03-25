# Codebase Concerns

**Analysis Date:** 2026-03-25

## Tech Debt

### SQL Injection Potential via f-string Table Names
- **Issue:** Dynamic SQL queries using f-strings with table names bypass parameterized query protection
- **Files:** `src/tdoc_crawler/database/base.py`
  - Line 153: `cursor = self.connection._db.execute(f"SELECT * FROM {table}")`
  - Line 207: `cursor = self.connection._db.execute(f"SELECT COUNT(*) FROM {table}")`
  - Line 209: `self.connection._db.execute(f"DELETE FROM {table}")`
- **Impact:** While tables are whitelisted via `model_map`, the pattern is fragile and could be copied elsewhere without proper safeguards
- **Current mitigation:** Whitelist check in `model_map` dictionary
- **Fix approach:** Use parameterized queries or a dedicated query builder that enforces whitelist at compile time

### Broad Exception Handling
- **Issue:** Multiple `except Exception` blocks swallow specific error information
- **Files:** 
  - `src/tdoc_crawler/database/base.py` (lines 55, 187)
  - `src/tdoc_crawler/database/specs.py` (lines 187, 316, 478)
  - `src/tdoc_crawler/clients/portal.py` (lines 219, 244)
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (lines 78, 133, 140, 214, 323, 361, 434)
  - `src/tdoc_crawler/tdocs/operations/fetch.py` (lines 239, 300)
  - `src/tdoc_crawler/tdocs/sources/portal.py` (lines 73, 83)
  - `src/tdoc_crawler/tdocs/sources/whatthespec.py` (line 152)
  - `src/tdoc_crawler/workers/tdoc_worker.py` (line 52)
  - `src/tdoc_crawler/meetings/operations/crawl.py` (line 168)
  - `src/tdoc_crawler/specs/downloads.py` (lines 114, 252, 265)
  - `src/tdoc_crawler/cli/specs.py` (line 87)
  - `src/tdoc_crawler/tdocs/operations/crawl.py` (line 265)
- **Impact:** Debugging difficulty, potential silent failures, loss of error context
- **Fix approach:** Catch specific exception types, log with full context, re-raise with `from exc`

### Unused WorkspaceStatus Enum
- **Issue:** `WorkspaceStatus` enum has only `ACTIVE` value, with TODO comment questioning its necessity
- **Files:** `packages/3gpp-ai/threegpp_ai/models.py` (line 72-77)
- **Impact:** Dead code, confusion about intended functionality
- **Fix approach:** Either remove if truly unnecessary, or implement full lifecycle (ACTIVE, ARCHIVED, DELETED)

## Known Bugs

### Duplicate Login Check in Portal Client
- **Symptoms:** Redundant authentication failure check
- **Files:** `src/tdoc_crawler/clients/portal.py` (lines 152-158)
- **Trigger:** Authentication flow always
- **Details:** The same check `response_text.lower() == "failed"` is performed twice consecutively
- **Workaround:** None needed - second check is unreachable
- **Fix approach:** Remove duplicate check at line 157-158

## Security Considerations

### Subprocess Security (noqa: S603, S606)
- **Risk:** Shell command execution without full validation
- **Files:** `src/tdoc_crawler/cli/utils.py` (lines 25, 29, 36)
- **Current mitigation:** Commands use hardcoded paths (`/usr/bin/open`, `/usr/bin/xdg-open`)
- **Recommendations:** Consider using `shutil.which()` to verify command existence before execution

### Environment Variable Credential Handling
- **Risk:** Credentials stored in environment variables may leak via process listing
- **Files:** `src/tdoc_crawler/credentials.py`
- **Current mitigation:** Uses `hide_input=True` for password prompts
- **Recommendations:** Document that credentials should be set via secure credential managers in production

### HTTP Session Cookie Handling
- **Risk:** Authentication session uses non-cached session for cookies
- **Files:** `src/tdoc_crawler/clients/portal.py` (lines 121-122, 298-307)
- **Current mitigation:** Separate session for auth vs. cached requests
- **Recommendations:** Good pattern - document the rationale in code comments

## Performance Bottlenecks

### In-Memory Table Scanning for Queries
- **Problem:** Spec queries load all records then filter in Python
- **Files:** `src/tdoc_crawler/database/specs.py` (lines 190-250)
- **Cause:** `_table_rows()` fetches entire table, then filters with list comprehensions
- **Improvement path:** Add parameterized SQL WHERE clauses for filtering before loading data

### Document List Parsing
- **Problem:** Large Excel files parsed entirely in memory
- **Files:** `src/tdoc_crawler/tdocs/sources/doclist.py`
- **Cause:** Pandas loads entire Excel file before processing
- **Improvement path:** Consider streaming parsers for very large meeting document lists

### Console.print() Usage Over Logging
- **Problem:** 71 `console.print()` calls throughout CLI instead of structured logging
- **Files:** 
  - `src/tdoc_crawler/cli/query.py` (26 occurrences)
  - `src/tdoc_crawler/cli/printing.py` (5 occurrences)
  - `src/tdoc_crawler/cli/_shared.py` (6 occurrences)
  - `src/tdoc_crawler/cli/crawl.py` (10 occurrences)
  - `src/tdoc_crawler/cli/tdoc_app.py` (14 occurrences)
  - `src/tdoc_crawler/cli/specs.py` (4 occurrences)
- **Cause:** Direct console output bypasses logging infrastructure
- **Improvement path:** Acceptable for CLI output, but ensure error cases use `logger` for debuggability

## Fragile Areas

### NotImplementedError in Source Classes
- **Files:** 
  - `src/tdoc_crawler/specs/sources/base.py` (lines 16, 20)
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (line 404)
  - `src/tdoc_crawler/tdocs/sources/portal.py` (line 105)
  - `src/tdoc_crawler/tdocs/sources/whatthespec.py` (line 174)
- **Why fragile:** Abstract methods raise `NotImplementedError` - indicates incomplete interface implementation
- **Safe modification:** Check all subclasses implement required interface methods before modifying base class
- **Test coverage:** Limited - these error paths may not be covered by tests

### Multi-Package Workspace Dependencies
- **Files:** 
  - `packages/3gpp-ai/` depends on `src/tdoc_crawler/`
  - `packages/convert-lo/` is a workspace dependency
  - `packages/pool_executors/` is a workspace dependency
- **Why fragile:** Changes to core `tdoc_crawler` may break AI package without clear boundaries
- **Safe modification:** Run full test suite including AI tests when modifying core package
- **Test coverage:** AI tests exist in `tests/ai/`

## Scaling Limits

### SQLite Concurrency
- **Current capacity:** Single-file database with pydantic-sqlite
- **Limit:** Write concurrency limited; concurrent crawls may conflict
- **Scaling path:** Consider PostgreSQL for high-volume crawling scenarios

### HTTP Cache Size
- **Current capacity:** Single SQLite file for HTTP cache (`~/.3gpp-crawler/http-cache.sqlite3`)
- **Limit:** Large crawl sessions may create multi-GB cache files
- **Scaling path:** Implement cache rotation/compaction, or use redis for distributed caching

### Subinterpreter Worker Pool
- **Current capacity:** Configurable via `TDC_WORKERS` env var (default: 4)
- **Limit:** Each worker has full Python runtime overhead
- **Scaling path:** Consider async/await patterns with httpx for better I/O-bound scaling

## Dependencies at Risk

### doc2txt Git Dependency
- **Risk:** Git dependency for doc2txt may fail in restricted environments
- **Files:** `packages/3gpp-ai/pyproject.toml` (lines 49)
- **Impact:** Installation failures in air-gapped or proxy-restricted environments
- **Migration plan:** Consider vendoring a simplified local copy as suggested in the comment

### LightRAG Version Pinning
- **Risk:** `lightrag-hku[offline]>=1.4.9.3` - loose version constraint
- **Impact:** Breaking changes in LightRAG updates may break the pipeline
- **Migration plan:** Pin to specific version, test before upgrading

### charset_normalizer and chardet Redundancy
- **Risk:** Both included explicitly due to requests v2.32.5 compatibility
- **Files:** `pyproject.toml` (lines 30-31, with comment at line 17)
- **Impact:** Increased dependency footprint
- **Migration plan:** Monitor requests releases for when these can be removed

## Missing Critical Features

### Workspace Lifecycle Management
- **Problem:** No workspace archival/deletion functionality
- **Files:** `packages/3gpp-ai/threegpp_ai/models.py`
- **Blocks:** Long-term workspace management, storage cleanup

### TDoc Version History
- **Problem:** No version tracking for TDoc content changes
- **Files:** `src/tdoc_crawler/tdocs/models.py`
- **Blocks:** Diff viewing, change history, revision tracking

## Test Coverage Gaps

### Integration Tests Marked but Not Separated
- **What's not tested:** Integration tests run with full suite, no dedicated CI separation
- **Files:** `tests/` - uses `pytest.mark.integration` marker
- **Risk:** Slow integration tests may slow down CI feedback loop
- **Priority:** Medium

### AI Module Edge Cases
- **What's not tested:** LLM provider failures, embedding dimension mismatches
- **Files:** `packages/3gpp-ai/threegpp_ai/`
- **Risk:** Production failures may be silent or poorly diagnosed
- **Priority:** High

### Error Path Coverage
- **What's not tested:** Many `except Exception` blocks have no corresponding test cases
- **Files:** Throughout `src/tdoc_crawler/database/`, `src/tdoc_crawler/tdocs/sources/`
- **Risk:** Silent failures may go undetected
- **Priority:** Medium

## Code Quality Issues

### Print Statements in Production Code
- **Files:** `src/tdoc_crawler/cli/query.py`, `src/tdoc_crawler/cli/crawl.py`
- **Pattern:** 71 `console.print()` calls throughout CLI
- **Impact:** Not a bug but indicates CLI uses Rich for output rather than logging
- **Note:** This is intentional for CLI output, but error handling should prefer logging

### # noqa Comments Present
- **Files:** 
  - `src/tdoc_crawler/database/base.py` (S608 - SQL injection)
  - `src/tdoc_crawler/database/specs.py` (BLE001 - blind exception)
  - `src/tdoc_crawler/cli/utils.py` (S603, S606 - subprocess security)
- **Impact:** Suppressed linter warnings indicate known issues that need addressing
- **Priority:** Low (current suppressions are justified, but should be documented)

---

*Concerns audit: 2026-03-25*
