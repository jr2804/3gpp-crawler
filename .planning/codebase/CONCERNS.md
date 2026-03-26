# Codebase Concerns

**Analysis Date:** 2026-03-26

## Tech Debt

### Normalization Functions - Potential Duplication
- **Issue:** Multiple normalization implementations across codebase
- **Files:**
  - `src/tdoc_crawler/tdocs/utils.py` - `normalize_tdoc_id()`, `normalize_tdoc_ids()`
  - `src/tdoc_crawler/utils/normalization.py` - `normalize_spec_number()`, `normalize_release()`, `expand_spec_ranges()`
  - `src/tdoc_crawler/meetings/utils.py` - `normalize_portal_meeting_name()`, `normalize_working_group_alias()`, `normalize_subgroup_alias()`
  - `src/tdoc_crawler/tdocs/models.py` - Field validators `_normalize_tdoc_id()`, `_normalize_working_groups()`, `_normalize_subgroups()`
  - `src/tdoc_crawler/meetings/models.py` - Field validators `_normalize_working_groups()`, `_normalize_subgroups()`
- **Impact:** Medium - Code duplication makes maintenance harder, risk of inconsistent behavior
- **Fix approach:** Consolidate normalization logic into `src/tdoc_crawler/utils/normalization.py` as single source of truth. Import from centralized module rather than reimplementing inline.

### WorkspaceStatus Enum - Potentially Unnecessary
- **Issue:** TODO comment indicates this enum may be redundant
- **Files:** `packages/3gpp-ai/threegpp_ai/models.py` (line 72)
- **Impact:** Low - Minor code clarity issue
- **Fix approach:** Evaluate if `WorkspaceStatus` is actually used. If membership state is inferred from `WorkspaceMember.is_active`, consider removing this enum.### Migration module - Potentially Unused
- **Issue:** TODO comment questions need for entire module
- **Files:** `packages/3gpp-ai/threegpp_ai/lightrag/migration.py` (line 11)
- **Impact:** Low - Module exists but may be unnecessary for new workspaces
- **Fix approach:** Keep consolidation function for legacy workspace merging, but evaluate if full migration functionality is needed for new installations.

## Known Bugs

### Broad Exception Handling with Silent Failures
- **Symptoms:** Multiple `except Exception` blocks that catch broad exceptions and silently skip errors
- **Files:**
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (lines 133-140, 214)
  - `src/tdoc_crawler/database/specs.py` (lines 316, 479)
  - `packages/3gpp-ai/threegpp_ai/cli.py` (lines 261, 336, 455)
- **Trigger:** Various error conditions (parsing failures, network errors)
- **Workaround:** None - errors are silently swallowed and logged as warnings
- **Fix approach:** Use more specific exception types, propagate critical errors instead of silently failing

### Linter Issue BLE001 (Broad Exception)
- **Symptoms:** Code catches `Exception` without specifying exception type
- **Files:**
  - `src/tdoc_crawler/database/specs.py` (line 316)
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (lines 323, 361)
  - `src/tdoc_crawler/tdocs/operations/crawl.py` (line 265)
    - `src/tdoc_crawler/specs/downloads.py` (lines 114, 252, 265)
    - `src/tdoc_crawler/clients/portal.py` (lines 219, 244)
    - `src/tdoc_crawler/meetings/operations/crawl.py` (line 168)
    - `src/tdoc_crawler/tdocs/operations/fetch.py` (lines 239, 300)
    - `src/tdoc_crawler/tdocs/sources/portal.py` (lines 73, 83)
    - `src/tdoc_crawler/tdocs/sources/whatthespec.py` (line 152)
    - `src/tdoc_crawler/workers/tdoc_worker.py` (line 52)
    - `src/tdoc_crawler/cli/specs.py` (line 87)
- **Trigger:** Any exception during database or parsing operations
- **Workaround:** None - suppressed with `# noqa: BLE001` comments
- **Fix approach:** Catch specific exception types (`ValueError`, `KeyError`, etc.) or re-raise with additional context using `from exc`

## Security Considerations

### Credentials Handling - Well Designed
- **Risk:** Low - Credentials are properly managed via environment variables
- **Files:** `src/tdoc_crawler/credentials.py`
- **Current mitigation:**
  - Credentials stored in environment variables (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`)
  - Password input hidden via `typer.prompt(..., hide_input=True)`
  - Never logged or persisted to disk
 - Pydantic model `PortalCredentials` for type safety
- **Recommendations:** Current implementation is secure. No changes needed.### LLM API Keys - Properly Managed
- **Risk:** Low - API keys handled via environment variables
- **Files:**
  - `packages/3gpp-ai/threegpp_ai/config.py` (lines 103, 140)
  - `packages/3gpp-ai/threegpp_ai/operations/llm_client.py` (lines 84, 88)
- **Current mitigation:**
  - `TDC_AI_LLM_API_KEY` environment variable
  - API key validated at runtime, warnings logged if missing
  - Never hardcoded in source files
- **Recommendations:** Current implementation is secure. No changes needed.### Hardcoded Paths - Prevented via CacheManager Pattern
- **Risk:** Low - Project enforces CacheManager pattern
- **Files:** `src/tdoc_crawler/config/__init__.py`
- **Current mitigation:**
  - All paths resolved via `CacheManager`
  - Environment variable override support (`TDC_CACHE_DIR`, `TDC_AI_STORE_PATH`)
  - AGENTS.md explicitly prohibits hardcoded paths
  - grep found NO instances of `.3gpp-crawler` or `~/.3gpp` hardcoding in src/
- **Recommendations:** Continue enforcing CacheManager pattern. No changes needed.### TYPE_CHECKING Usage - None Found
- **Risk:** None - No instances of `typing.TYPE_CHECKING` detected
- **Files:** None
- **Recommendations:** Continue avoiding this pattern as documented in AGENTS.md.

## Performance Bottlene

### Database Query Efficiency
- **Problem:** SQLite database operations may become slow with large datasets
- **Files:** `src/tdoc_crawler/database/tdocs.py`, `src/tdoc_crawler/database/specs.py`
- **Cause:** Full table scans for pattern matching queries
- **Improvement path:**
  - Add database indexes on frequently queried columns
  - Consider query optimization for pattern matching
  - Evaluate pagination for large result sets

### Excel Parsing Performance
- **Problem:** Large Excel files may cause memory issues
- **Files:** `src/tdoc_crawler/tdocs/sources/doclist.py`
- **Cause:** Loading entire Excel content into memory before parsing
- **Improvement path:**
  - Stream processing for large files
  - Consider chunked reading for very large document lists

### HTTP Caching Strategy
- **Problem:** HTTP caching configuration affects crawl performance
- **Files:** `src/tdoc_crawler/http_client/session.py`
- **Cause:** Cache TTL and invalidation policies
- **Improvement path:**
  - Configurable cache TTL per resource type
  - Cache warming for frequently accessed resources
  - Evaluate cache hit rates and adjust strategies

## Fragile Areas

### Portal Authentication Flow
- **Files:** `src/tdoc_crawler/clients/portal.py`
- **Why fragile:** Depends on external 3GPP portal behavior that may change
- **Safe modification:** Changes require testing against live portal; use integration tests
- **Test coverage:** Partial - covered by `tests/test_portal_client.py`, `tests/test_portal_auth.py`

### TDoc Metadata Parsing
- **Files:** `src/tdoc_crawler/tdocs/sources/doclist.py`, `src/tdoc_crawler/parsers/portal.py`
- **Why fragile:** Excel format changes, HTML structure variations
- **Safe modification:** Validate parsing with sample documents; add robustness tests
- **Test coverage:** Good - covered by `tests/test_meeting_document_list.py`

### LightRAG Integration
- **Files:** `packages/3gpp-ai/threegpp_ai/lightrag/` directory
- **Why fragile:** External dependency with evolving API
- **Safe modification:** Version pin LightRAG; add compatibility tests
- **Test coverage:** Extensive - multiple test files in `tests/ai/`

## Scaling Limits

### Embedding Storage
- **Current capacity:** File-based NanoVectorDB storage
- **Limit:** Performance degrades with large embedding counts
- **Scaling path:**
  - Migrate to `pg0` backend for PostgreSQL storage
  - Evaluate LanceDB for vector operations
  - Consider distributed embedding storage

### Concurrent Processing
- **Current capacity:** Configurable worker count (default 4)
- **Limit:** Memory overhead with ProcessPoolExecutor (noted in code comments)
- **Scaling path:**
  - Python 3.14+ subinterpreters reduce memory overhead
  - Consider async/await patterns for I/O-bound operations

## Dependencies at Risk

### LiteLLM Version Compatibility
- **Risk:** API changes between versions
- **Impact:** LLM operations may fail with version updates
- **Migration plan:** Version pin in pyproject.toml; test against multiple versions

### LightRAG API Stability
- **Risk:** Experimental library with evolving API
- **Impact:** Breaking changes may affect document processing
- **Migration plan:** Pin version; monitor upstream changes; maintain compatibility layer

### Pandas Excel Engine
- **Risk:** Dependent on `python-calamine` engine
- **Impact:** Excel parsing may fail if engine has issues
- **Migration plan:** Keep engine updated; have fallback parsing strategies

## Missing Critical Features

### Batch Filtering CLI Options
- **Problem:** No CLI options for filter meetings/tdocs by date range, metadata patterns
- **Blocks:** Efficient bulk operations on specific subsets of data
- **Status:** Documented as planned feature in project memory

### Progress Reporting in AI Pipeline
- **Problem:** Progress bar shows elapsed time but not documents processed count
- **Blocks:** User visibility into processing progress
- **Status:** Documented as issue to fix in project memory

## Test Coverage Gaps

### Normalization Functions
- **What's not tested:** Edge cases in spec number normalization
- **Files:** `src/tdoc_crawler/utils/normalization.py`
- **Risk:** Incorrect normalization may cause data inconsistencies
- **Priority:** Medium - Add tests for edge cases (unicode characters, unusual formats)

### Error Recovery Paths
- **What's not tested:** Network failure recovery, timeout handling
- **Files:** `src/tdoc_crawler/tdocs/operations/fetch.py`, `src/tdoc_crawler/http_client/`
- **Risk:** Unhandled failures may leave system in inconsistent state
- **Priority:** Medium - Add integration tests for failure scenarios

### Portal Session Management
- **What's not tested:** Session timeout, re-authentication flows
- **Files:** `src/tdoc_crawler/clients/portal.py`
- **Risk:** Long-running operations may fail due to session expiry
- **Priority:** Low - Portal sessions are typically short-lived

### AI Pipeline Error Cases
- **What's not tested:** Classification failures, extraction failures, embedding errors
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/`
- **Risk:** Errors in AI pipeline may corrupt workspace state
- **Priority:** High - Add comprehensive error handling tests

 ---

*Concerns audit: 2026-03-26*
