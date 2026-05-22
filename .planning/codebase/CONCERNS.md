# Codebase Concerns

**Analysis Date:** 2026-05-22

## Tech Debt

### Dual Path Resolution System (CacheManager vs PathConfig)

- Issue: Two parallel systems resolve file paths. `CacheManager` (`config/cache_manager.py`) is a singleton registered once at startup. `PathConfig` (`config/settings.py`) is a pydantic-settings model that creates a new instance on every `PathConfig()` call. Both define the same defaults (`DEFAULT_DATABASE_FILENAME`, `DEFAULT_HTTP_CACHE_FILENAME`, `DEFAULT_CHECKOUT_DIRNAME`) in separate files.
- Files: `src/tdoc_crawler/config/cache_manager.py`, `src/tdoc_crawler/config/settings.py`
- Impact: Defaults can drift between the two systems. Call sites must choose which system to use, creating inconsistency. `PathConfig()` instantiates a full pydantic-settings model (including env var parsing) just to get a path.
- Fix approach: Migrate all 27+ `PathConfig()` call sites to `resolve_cache_manager()`. Remove duplicated defaults from `settings.py`. Keep `PathConfig` only for config discovery/CLI display, not runtime path resolution.

**Affected call sites (non-exhaustive):**
- `src/tdoc_crawler/http_client/session.py:299` — `PathConfig().http_cache_file`
- `src/tdoc_crawler/config/workspace_registry.py:311,462` — `PathConfig().cache_dir`
- `src/tdoc_crawler/workspaces/utils.py:61,78` — `PathConfig().checkout_dir`, `PathConfig().db_file`
- `src/tdoc_crawler/workspaces/members.py:93,127,178,237,293` — `PathConfig().db_file`
- `src/tdoc_crawler/workspaces/crud.py:43,75,51,50,69` — `PathConfig()` instances
- `src/tdoc_crawler/cli/workspace/process.py:121,223,295` — `PathConfig()`

### Deprecated `TDocCrawlerConfig` Alias Still in Use

- Issue: `TDocCrawlerConfig = ThreeGPPConfig` alias in `config/settings.py:300` with comment "remove after all consumers are updated" is still actively used.
- Files: `src/tdoc_crawler/config/settings.py:300`, `src/tdoc_crawler/cli/crawl.py:48,131,290,399`
- Impact: Code smell — two names for the same class. New contributors may use the wrong name.
- Fix approach: Replace all `TDocCrawlerConfig` imports/usages in `cli/crawl.py` with `ThreeGPPConfig`, then remove the alias from `settings.py`.

### Repeated Full-Table Loads in Database Queries

- Issue: Multiple database query methods load entire tables into Python memory, then filter in-memory instead of using SQL WHERE clauses. This scales linearly with data size and will degrade as the database grows.
- Files: `src/tdoc_crawler/database/tdocs.py`, `src/tdoc_crawler/database/meetings.py`, `src/tdoc_crawler/database/specs.py`
- Impact: With thousands of TDocs and hundreds of meetings, `query_tdocs()` materializes all records into Python lists, applies filters sequentially, then sorts. `get_statistics()` loads three full tables.
- Fix approach: Push filters (working_group, date ranges, patterns that can be expressed as LIKE) to SQL via Oxyde ORM. Add pagination support. Cache meeting map per database session.

**Specific hot spots:**
- `tdocs.py:169` — `query_tdocs()` fetches all TDocMetadata records via ORM `.all()`
- `tdocs.py:177+185` — MeetingMetadata table loaded **twice** in a single `query_tdocs()` call (once for date filtering, once for sorting)
- `meetings.py:144` — `query_meetings()` fetches all meetings then filters in-memory
- `meetings.py:170` — `get_existing_meeting_ids()` loads all meetings
- `meetings.py:238-240` — `get_statistics()` loads TDocMetadata, MeetingMetadata, and CrawlLogEntry fully
- `specs.py:344-345` — `query_specs()` loads all Specification AND all SpecificationSourceRecord records

### Broad `except Exception` Handlers

- Issue: 39 `except Exception` handlers throughout the codebase. Some are appropriate (top-level CLI error boundaries) but many in the database and extraction layers silently swallow specific errors.
- Files: `src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/database/tdocs.py`, `src/tdoc_crawler/database/specs.py`, `src/tdoc_crawler/extraction/convert.py`, `src/tdoc_crawler/workspaces/utils.py`
- Impact: Hard to debug failures — specific error types are lost. For example, `database/base.py:106` catches all exceptions during database init, making schema errors invisible.
- Fix approach: Replace broad handlers with specific exception types (`OSError`, `ValueError`, `sqlite3.OperationalError`). Keep `except Exception` only at CLI boundary layers.

### f-string in Logger Calls

- Issue: 16 logger calls use f-string formatting (`logger.debug(f"..."`) instead of lazy `%s` formatting. Python loggers only format the string when the log level is enabled — f-strings force immediate formatting.
- Files: `src/tdoc_crawler/http_client/session.py:289,335`, `src/tdoc_crawler/tdocs/operations/checkout.py:160,169,171,233,361`, `src/tdoc_crawler/tdocs/sources/doclist.py:122,145,147,150,441`, `src/tdoc_crawler/config/workspace_registry.py:480`
- Impact: Minor performance waste in hot paths (checkout operations, doclist parsing). More importantly, it violates the logging convention used elsewhere in the codebase.
- Fix approach: Replace `logger.debug(f"text {var}")` with `logger.debug("text %s", var)`.

## Known Bugs

### Missing `disable_http3=True` in TDoc Checkout Session

- Symptoms: `MustDowngradeError` from `urllib3-future` when fetching TDoc files from `www.3gpp.org`. ~10 second delay per request as HTTP/3 is advertised but fails.
- Files: `src/tdoc_crawler/tdocs/operations/checkout.py:115`
- Trigger: Any TDoc checkout operation that needs directory listing from 3GPP FTP/HTTP servers.
- Workaround: None. The error is caught and retried, but each retry wastes ~10 seconds.
- Fix: Change `requests.Session()` to `requests.Session(disable_http3=True)`.

## Security Considerations

### Credentials in Environment Variables

- Risk: EOL portal credentials (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`) are stored as plain environment variables or in `.env` files. The `credentials.py` module also sets them directly into `os.environ`.
- Files: `src/tdoc_crawler/credentials.py:23-25`
- Current mitigation: `.env` is in `.gitignore`. `.env.example` documents the variables without values.
- Recommendations: Consider using system keyring or encrypted credential store for long-lived credentials.

### Workspace Registry Not Thread-Safe

- Risk: `WorkspaceRegistry` reads and writes a JSON file without file locking. Concurrent CLI processes (e.g., two terminals running workspace commands) could corrupt `workspaces.json`.
- Files: `src/tdoc_crawler/config/workspace_registry.py:309-322`
- Current mitigation: None.
- Recommendations: Add file-based locking (e.g., `filelock` package) to `save()` and `load()` methods.

### URL Validation Scope

- Risk: SSRF protection (`validate_api_url()`) only validates user-supplied API URLs. Download URLs from 3GPP FTP/HTTP servers are not validated.
- Files: `src/tdoc_crawler/utils/security.py`
- Current mitigation: Download URLs are constructed from constants in `constants/urls.py`, not from user input.
- Recommendations: Current mitigation is sufficient for known use cases. If user-supplied URLs are ever accepted for download, extend validation.

## Performance Bottlenecks

### TDoc Checkout Path Resolution via `rglob`

- Problem: `resolve_tdoc_checkout_path()` uses `checkout_base.rglob("Docs")` to find TDoc directories. This walks the entire checkout tree for every single TDoc lookup.
- Files: `src/tdoc_crawler/workspaces/utils.py:53`
- Cause: The checkout directory structure is `<checkout_base>/<group>/<meeting>/Docs/<tdoc_id>/`. The function doesn't know which meeting a TDoc belongs to, so it searches exhaustively.
- Improvement path: Query the database for the meeting associated with the TDoc, then construct the path directly: `checkout_base / meeting_path / "Docs" / tdoc_id`. Only fall back to `rglob` for TDocs not in the database.

### Bulk Upsert Queries Existing Records One-by-One

- Problem: `bulk_upsert_tdocs()` queries each TDoc individually to check if it exists (`_get_tdoc` per record), then does bulk create/update.
- Files: `src/tdoc_crawler/database/tdocs.py:109-113`
- Cause: Oxyde ORM doesn't have a built-in `bulk_upsert` or `INSERT OR REPLACE`.
- Improvement path: Query all existing TDoc IDs in a single `SELECT tdoc_id FROM tdocs WHERE tdoc_id IN (...)` call, then partition into create/update sets.

### Spec Crawling is Sequential

- Problem: `crawl_specs()` iterates spec numbers sequentially. Each spec fetch involves HTTP requests to multiple sources.
- Files: `src/tdoc_crawler/database/specs.py:391-405`
- Cause: The outer loop over spec numbers is synchronous.
- Improvement path: Use `asyncio.gather` with a semaphore to crawl multiple specs concurrently (like `_crawl_single_spec` already does for sources within a spec).

## Fragile Areas

### Extraction Pipeline

- Files: `src/tdoc_crawler/extraction/convert.py` (499 lines), `src/tdoc_crawler/extraction/docling/pipeline.py`
- Why fragile: Complex multi-step pipeline with external dependencies (LibreOffice for PDF conversion, Docling for structured extraction, pymupdf4llm for markdown). Any external tool failure cascades. The `convert_for_wiki()` function has 5 different code paths based on profile type.
- Safe modification: Test changes with all four extraction profiles (`pdf-only`, `markdown-only`, `default`, `advanced`). Verify `--force` flag behavior.
- Test coverage: None. No tests exist for `extraction/convert.py`, `extraction/docling/pipeline.py`, or `cli/workspace/process.py`.

### Database Migration System

- Files: `src/tdoc_crawler/database/base.py:216-239`
- Why fragile: Migrations are defined as a hardcoded list of `ALTER TABLE ADD COLUMN` statements. Each migration silently catches all exceptions. There's no migration version tracking — migrations re-run on every startup and rely on `PRAGMA table_info` to skip already-applied changes.
- Safe modification: Add new migrations to the end of the list. Always include the `PRAGMA table_info` guard pattern.
- Test coverage: No dedicated migration tests.

### Oxyde ORM Model Coupling

- Files: `src/tdoc_crawler/database/oxyde_models.py`
- Why fragile: All database operations depend on Oxyde ORM, which is a relatively new/uncommon ORM. The `_clone_tdoc()` method at `database/tdocs.py:361-365` manually reconstructs model instances by iterating `__annotations__`, bypassing model validators. If a field is added to the Oxyde model, `_clone_tdoc` must still work.
- Safe modification: When adding fields to Oxyde models, verify `_clone_tdoc` and `_prepare_tdoc` still include the new field in their reconstruction logic.
- Test coverage: Partial — `test_database.py` covers basic operations.

## Scaling Limits

### SQLite Variable Limit (999)

- Current capacity: `SQLITE_MAX_VARS = 999` at `database/tdocs.py:18`. With ~30 columns per TDoc, max batch size is ~33 records.
- Limit: Bulk operations are artificially capped. The code already auto-reduces batch size but logs a warning.
- Scaling path: For large crawls (1000+ TDocs), consider batched INSERT with temporary tables or switch to PostgreSQL.

### In-Memory Filtering

- Current capacity: All query operations load full tables into Python memory before filtering.
- Limit: With 10K+ TDocs and 500+ meetings, memory usage grows significantly. `query_tdocs()` with meeting date filters materializes 3 full table loads.
- Scaling path: Push filtering to SQL. Add LIMIT/OFFSET at the ORM level.

## Dependencies at Risk

### Oxyde ORM

- Risk: Relatively new/uncommon ORM. Version pinned at `>=0.4.0`. Breaking changes in minor versions could affect model definitions, query API, or migration behavior.
- Impact: All database operations would break. No easy migration path to another ORM without rewriting all model definitions.
- Migration plan: If Oxyde becomes unmaintained, consider migrating to SQLAlchemy 2.0 with Pydantic integration, or direct SQLite via `aiosqlite`.

### niquests

- Risk: `niquests` (used as `requests` replacement) is a relatively new HTTP library. Its `urllib3-future` dependency has HTTP/3 issues with 3GPP servers, requiring `disable_http3=True` workarounds.
- Impact: If the `disable_http3` parameter is removed or the Hishel adapter integration breaks, all HTTP operations fail.
- Migration plan: Monitor `niquests` releases. Consider standard `requests` + `urllib3` if HTTP/3 issues persist.

## Missing Critical Features

### No Concurrent Download Protection

- Problem: Multiple CLI processes can run simultaneously, potentially corrupting the SQLite database or HTTP cache.
- Blocks: Parallel crawls of different working groups.

### No Database Backup Before Destructive Operations

- Problem: `clear_tdocs`, `clear_specs`, and `clear_db` delete data permanently without backup.
- Blocks: Safe experimentation with crawl operations.

## Test Coverage Gaps

### Extraction Pipeline

- What's not tested: `extraction/convert.py`, `extraction/docling/pipeline.py`, `extraction/docling/converter.py`, `extraction/docling/filter.py`
- Files: `src/tdoc_crawler/extraction/convert.py`, `src/tdoc_crawler/extraction/docling/`
- Risk: Any regression in document conversion (PDF generation, Docling extraction, markdown output) will only be caught at runtime.
- Priority: High — this is the most complex and least-tested part of the codebase.

### Workspace Processing

- What's not tested: `cli/workspace/process.py` — the `workspace process` command that orchestrates checkout + conversion for all workspace members.
- Files: `src/tdoc_crawler/cli/workspace/process.py`
- Risk: Regressions in member processing, progress tracking, error handling, or skip-existing logic.
- Priority: High — primary user-facing workflow.

### Database Migration Logic

- What's not tested: `_run_migrations()` in `database/base.py` — no tests verify that migrations apply correctly or that already-applied migrations are skipped.
- Files: `src/tdoc_crawler/database/base.py:216-239`
- Risk: Schema changes may silently fail or apply incorrectly on existing databases.
- Priority: Medium — migrations are simple but fragile.

### HTTP/3 Downgrade Handling

- What's not tested: The `_NiquetsCacheAdapter.init_poolmanager()` HTTP/3 disabling logic and the bare `Session()` calls are not tested for correct HTTP/3 behavior.
- Files: `src/tdoc_crawler/http_client/session.py:101-109`, `src/tdoc_crawler/tdocs/operations/checkout.py:115`
- Risk: New Session() calls may be added without `disable_http3=True`.
- Priority: Medium — the AGENTS.md documents this but automated enforcement is missing.

---

*Concerns audit: 2026-05-22*
