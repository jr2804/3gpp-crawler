# Codebase Concerns

**Analysis Date:** 2026-05-03

## Tech Debt

**Path traversal via `LIBREOFFICE_PATH` environment variable:**
- Issue: `packages/convert-lo/convert_lo/locator.py` line 22-24 reads an environment variable and uses it directly as an executable path without validation. An attacker who controls the environment variable can point to an arbitrary binary.
- Files: `packages/convert-lo/convert_lo/locator.py:22-26`
- Impact: Arbitrary code execution if an attacker can set `LIBREOFFICE_PATH` (exploitability score: 87 per static analysis)
- Fix approach: Validate the candidate path resolves to a real `soffice` binary (check filename, verify signature or at minimum that it's an executable file with expected name). Consider restricting to known install locations only.

**Duplicate default constant definitions between `PathConfig` and `CacheManager`:**
- Issue: Default filenames/dirnames are defined independently in `src/tdoc_crawler/config/settings.py` (lines 23-28 as `_DEFAULT_*` module-level strings) and `src/tdoc_crawler/config/cache_manager.py` (lines 28-32 as `DEFAULT_*` constants). If one changes without the other, paths diverge silently.
- Files: `src/tdoc_crawler/config/settings.py:23-28`, `src/tdoc_crawler/config/cache_manager.py:28-32`
- Impact: PathConfig properties may resolve to different paths than CacheManager if defaults drift
- Fix approach: Consolidate into a single `DEFAULTS` module or have `PathConfig` import from `cache_manager`. `CacheManager` is the canonical source of truth per AGENTS.md.

**PLR6301 method-could-be-function in database layer (11 instances):**
- Issue: Multiple database methods don't use `self` beyond accessing `self._database`, making them candidates for static/class methods. Linter flags these as PLR6301.
- Files: `src/tdoc_crawler/database/tdocs.py`, `src/tdoc_crawler/database/specs.py`, `src/tdoc_crawler/database/meetings.py`
- Impact: Low — methods correctly reference `self._database` through the connection property. Refactoring to static methods would break the consistent interface pattern.
- Fix approach: Low priority. Methods use `self._database` through the `connection` property indirection. Keep as-is unless the pattern changes.

**Unused `LibreOfficeFormat` enum values and `convert_batch` method:**
- Issue: The `LibreOfficeFormat` enum in `packages/convert-lo/convert_lo/formats.py` defines 21 format values, but the main codebase only uses `LibreOfficeFormat.PDF`. The `Converter.convert_batch()` method in `packages/convert-lo/convert_lo/converter.py:113-133` is never called.
- Files: `packages/convert-lo/convert_lo/formats.py`, `packages/convert-lo/convert_lo/converter.py:113-133`
- Impact: Dead code increases maintenance surface. Enum values may become stale or inconsistent with actual LibreOffice support.
- Fix approach: Keep the enum and `convert_batch` for API completeness of the shared package, but document which formats are actually used by tdoc-crawler.

**Unused `Runner.start()` context manager pattern and `SerialPoolExecutor.submit` trivial wrapper:**
- Issue: `Runner.start()` in `packages/pool_executors/pool_executors/runner.py:60-66` returns a `_RunnerContextManager` but no caller uses it — the main codebase creates executors via `create_executor()` factory instead. `SerialPoolExecutor.submit()` at `packages/pool_executors/pool_executors/serial.py:77-101` is a trivial delegation to `SerialFuture`.
- Files: `packages/pool_executors/pool_executors/runner.py:60-66`, `packages/pool_executors/pool_executors/serial.py:77-101`
- Impact: Dead code in shared packages. No runtime impact.
- Fix approach: Remove `Runner` class if not used by any consumer. Keep `SerialPoolExecutor.submit` as it implements the `Executor` interface correctly.

**Backward-compatible alias `TDocCrawlerConfig` still in use:**
- Issue: `src/tdoc_crawler/config/settings.py:331` defines `TDocCrawlerConfig = ThreeGPPConfig` as a backward-compatible alias. Comment says "remove after all consumers are updated."
- Files: `src/tdoc_crawler/config/settings.py:331`
- Impact: Naming confusion — two names for the same class.
- Fix approach: Search all consumers, update to `ThreeGPPConfig`, and remove the alias.

**Config file env-var interpolation before TOML parsing:**
- Issue: `src/tdoc_crawler/config/sources.py:171-175` performs `${ENV_VAR}` interpolation on the raw TOML string before parsing. This could break TOML syntax if an env var value contains TOML special characters (quotes, newlines, `[`, etc.).
- Files: `src/tdoc_crawler/config/sources.py:53-77`, `src/tdoc_crawler/config/sources.py:169-175`
- Impact: Config loading crashes or produces incorrect values when env vars contain TOML metacharacters.
- Fix approach: Interpolate after parsing (post-load on individual string values), or escape interpolated values for TOML safety.

## Known Bugs

**Portal authentication duplicate session assignment:**
- Symptoms: In `PortalClient.authenticate()`, the authenticated session is assigned twice at lines 158 and 165, with the comment "Step 3" appearing twice (lines 157 and 164).
- Files: `src/tdoc_crawler/clients/portal.py:157-166`
- Trigger: Calling `PortalClient.authenticate()` — the duplicate assignment is benign but indicates copy-paste error. If the code between the two assignments were changed, only one branch would take effect.
- Workaround: No workaround needed — current behavior is correct but confusing.

**`_filter_by_retrieved_dates` calls `_normalized_bound` twice per comparison:**
- Symptoms: In `TDocDatabase._filter_by_retrieved_dates()`, each filter comparison calls `_normalized_bound()` twice with identical arguments (lines 232-233, 237-238). This is a correctness issue because the function returns a tuple and both elements are compared against each other.
- Files: `src/tdoc_crawler/database/tdocs.py:220-240`
- Trigger: Querying TDocs with `start_date` or `end_date` filters.
- Workaround: None — the current code works because it normalizes both sides and compares. But it's wasteful and confusing.

## Security Considerations

**Path traversal via `LIBREOFFICE_PATH`:**
- Risk: High — arbitrary binary execution if attacker controls environment variable
- Files: `packages/convert-lo/convert_lo/locator.py:22-26`
- Current mitigation: The value must be a valid `Path` that `exists()`, but no further validation is performed
- Recommendations: Validate filename matches expected binary name (`soffice`/`soffice.exe`), reject paths containing `..`, restrict to known LibreOffice install locations

**Credentials stored in environment variables and config files:**
- Risk: Medium — EOL credentials can be stored in config TOML files or env vars. Config file discovery searches multiple locations.
- Files: `src/tdoc_crawler/config/settings.py:158-185` (`CredentialsConfig`), `src/tdoc_crawler/credentials.py`
- Current mitigation: `.env` is in `.gitignore`. Config files support `${ENV_VAR}` interpolation to avoid hardcoding secrets.
- Recommendations: Ensure `.3gpp-crawler.toml` and `3gpp-crawler.toml` are in `.gitignore` at project level. Document that credential values should use env var interpolation, not plaintext.

**Remote PDF converter API key in env var:**
- Risk: Low — `PDF_REMOTE_API_KEY` env var is used for remote conversion fallback.
- Files: `src/tdoc_crawler/extraction/conversion.py:41-56` (`ConverterConfig`)
- Current mitigation: Environment variable only, not committed to code
- Recommendations: None — current approach is standard.

**`subprocess.Popen` with hardcoded binary name:**
- Risk: Low — `opendataloader-pdf-hybrid` subprocess launch uses a hardcoded binary name (not user input), mitigated by `noqa: S603` with justification.
- Files: `src/tdoc_crawler/extraction/hybrid_server.py:155`
- Current mitigation: Binary name is a Python package CLI tool, not user-supplied
- Recommendations: None — acceptable risk for a developer tool.

## Performance Bottlenecks

**Full-table scan for every query:**
- Problem: All database queries load entire tables via `_table_rows()` into Python lists, then filter in-memory. This includes `query_tdocs()`, `query_meetings()`, `query_specs()`, `get_existing_tdoc_ids()`, and `get_statistics()`.
- Files: `src/tdoc_crawler/database/base.py:239-245`, `src/tdoc_crawler/database/tdocs.py:93-132`, `src/tdoc_crawler/database/meetings.py:112-152`, `src/tdoc_crawler/database/specs.py:198-259`
- Cause: Oxyde ORM may not support complex filtering natively; the workaround loads all rows and filters in Python.
- Improvement path: Add database-level filtering (WHERE clauses) for common filters (working group, date range). Cache lookup tables in memory. For `query_tdocs()`, the meeting_map is built on every call — cache it.

**Dual table load for TDoc queries (TDocs + Meetings):**
- Problem: `TDocDatabase.query_tdocs()` at line 106 loads both `TDocMetadata` and `MeetingMetadata` tables for working group and meeting date filtering. For large datasets, this doubles memory usage.
- Files: `src/tdoc_crawler/database/tdocs.py:106`
- Cause: Meeting data is needed to resolve working group and date filters for TDocs.
- Improvement path: Denormalize `tbid` into `TDocMetadata` to avoid the join, or use SQL JOIN.

**Sequential upsert in bulk operations:**
- Problem: `bulk_upsert_tdocs()` and `bulk_upsert_meetings()` iterate one-by-one, calling `upsert_tdoc()`/`upsert_meeting()` for each record sequentially. Each upsert does a SELECT + INSERT/UPDATE.
- Files: `src/tdoc_crawler/database/tdocs.py:63-91`, `src/tdoc_crawler/database/meetings.py:82-110`
- Cause: No batch INSERT/UPDATE support in current ORM usage pattern.
- Improvement path: Batch operations using SQLite's `INSERT OR REPLACE` or `INSERT ... ON CONFLICT UPDATE`.

**Hybrid server startup can take up to 10 minutes:**
- Problem: `_STARTUP_MAX_WAIT = 600` seconds for the hybrid server to become healthy. Model loading can take several minutes.
- Files: `src/tdoc_crawler/extraction/hybrid_server.py:28`
- Cause: Docling model loading is slow on CPU or first-run GPU.
- Improvement path: Keep the hybrid server running as a daemon. Add a `--keep-alive` flag. Pre-warm the model at install time.

## Fragile Areas

**Database class inheritance chain:**
- Files: `src/tdoc_crawler/database/base.py` → `src/tdoc_crawler/database/meetings.py` (`MeetingDatabase`) → `src/tdoc_crawler/database/tdocs.py` (`TDocDatabase`) → `src/tdoc_crawler/database/specs.py` (`SpecDatabase`)
- Why fragile: `TDocDatabase` inherits from `MeetingDatabase` (not compositional), and `SpecDatabase` inherits from `DocDatabase`. The chain makes it hard to test one layer without the others. Adding a new domain (e.g., CRs) requires adding another database class in this hierarchy.
- Safe modification: Test changes against all layers. Prefer adding new database classes that inherit from `DocDatabase` directly rather than extending the chain.
- Test coverage: Integration tests in `tests/test_database.py`, `tests/test_specs_database.py`.

**Workspace registry JSON file:**
- Files: `src/tdoc_crawler/config/workspace_registry.py`, `src/tdoc_crawler/workspaces/crud.py`
- Why fragile: Workspace state is stored in a single JSON file (`workspaces.json`). Concurrent writes could corrupt it. `save()` in `workspace_registry.py:272-285` overwrites the file atomically but uses no file locking. Registry is loaded fresh from disk on every `_get_registry()` call.
- Safe modification: Ensure only one process writes at a time. Consider file locking or a SQLite backend for concurrent access.
- Test coverage: `tests/test_workspaces.py`.

**`CacheManager` singleton lifecycle:**
- Files: `src/tdoc_crawler/config/cache_manager.py`
- Why fragile: `CacheManager` uses a class variable `_instance` singleton. Once registered, it cannot be re-registered. Tests that don't go through CLI entry points may hit `CacheManagerNotRegisteredError`. Some code defensively catches this exception (e.g., `workspaces/crud.py:65-67`) while AGENTS.md says not to.
- Safe modification: Always register CacheManager at test setup. Never add defensive fallbacks per AGENTS.md.
- Test coverage: `tests/test_cache_manager.py`.

**HTTP caching bridge (`_NiquetsCacheAdapter`):**
- Files: `src/tdoc_crawler/http_client/session.py:96-114`
- Why fragile: Bridges niquests `PreparedRequest` to hishel `CacheAdapter` internals. Uses private hishel APIs (`_cache_proxy`, internal `Request`/`Response` models). Any hishel version upgrade could break this bridge.
- Safe modification: Pin hishel version. Add integration tests that exercise cached HTTP flows. Test after any hishel upgrade.
- Test coverage: `tests/test_http_client.py`.

**Oxyde ORM schema auto-creation:**
- Files: `src/tdoc_crawler/database/base.py:140-215`
- Why fragile: `_ensure_tables_exist()` builds raw SQL from schema metadata extracted at runtime. Column type mapping is manual (Python type → SQLite type string). Any Oxyde schema change or new field type may not map correctly.
- Safe modification: Add a test that verifies schema creation for all registered models. Check after Oxyde version upgrades.
- Test coverage: Implicit via database integration tests.

## Scaling Limits

**SQLite single-writer constraint:**
- Current capacity: Single-process writes, multiple readers
- Limit: Concurrent CLI invocations or workspace operations may contend on writes
- Scaling path: WAL mode (already likely enabled by Oxyde), or migrate to PostgreSQL for multi-user scenarios

**In-memory full-table scan for filtering:**
- Current capacity: Works well for tens of thousands of TDocs and hundreds of meetings
- Limit: Queries slow down linearly as table sizes grow. The `_table_rows()` pattern loads entire tables into Python lists.
- Scaling path: Add WHERE-clause filtering using Oxyde's query API. Add database indices on frequently filtered columns (`meeting_id`, `tdoc_id`, `spec_number`, `start_date`).

**Workspace registry single-file JSON:**
- Current capacity: Small workspaces (< 100 members) load/save quickly
- Limit: Large workspaces (1000+ members) cause the entire JSON to be rewritten on every save
- Scaling path: Migrate workspace registry to SQLite table for atomic, concurrent access

## Dependencies at Risk

**hishel (HTTP caching library):**
- Risk: The codebase depends on hishel's internal API (`_core._headers.Headers`, `_core.models.Request/Response`, `_cache_proxy.handle_request`) which are not public API.
- Impact: Breaking changes in hishel minor/patch versions could break the HTTP caching bridge
- Migration plan: Pin hishel version in requirements. If hishel changes internals, evaluate switching to a simpler caching strategy (e.g., requests-cache).

**oxyde (ORM):**
- Risk: Relatively new ORM (`oxyde>=0.4.0`). API may change. The codebase uses it for all database operations.
- Impact: Schema migration, query API changes, or breaking changes could affect the entire database layer
- Migration plan: Pin version. Abstract database operations behind the existing facade classes (`DocDatabase`, `TDocDatabase`, etc.) to ease potential migration.

**opendataloader-pdf (document extraction):**
- Risk: Heavy dependency with hybrid server mode. Depends on docling model loading which is slow and resource-intensive.
- Impact: Conversion pipeline failures if the hybrid server is unavailable or model loading fails
- Migration plan: Keep the abstraction layer in `extraction/convert.py` which wraps opendataloader. Alternative extraction backends can be swapped.

## Missing Critical Features

**No database migration system:**
- Problem: Schema is recreated from Oxyde models on every connection (`_ensure_tables_exist` with `CREATE TABLE IF NOT EXISTS`). No ALTER TABLE support, no migration versioning.
- Impact: Schema changes require manual database deletion or adding migration logic
- Priority: Medium — current approach works for a single-user CLI tool but blocks multi-user or production deployments

**No rate limiting for 3GPP portal requests:**
- Problem: No explicit rate limiting when crawling meetings or fetching TDocs from the 3GPP portal. Relies on HTTP cache and timeout only.
- Impact: May trigger IP blocks or throttling from 3GPP servers during large crawls
- Priority: Medium — current crawl patterns are moderate, but large batch operations could trigger limits

**No workspace locking or concurrent access control:**
- Problem: Workspace registry is a JSON file with no locking mechanism.
- Impact: Two concurrent CLI processes could corrupt the registry
- Priority: Low — single-user CLI tool, concurrent access is rare

## Test Coverage Gaps

**Extraction pipeline (`src/tdoc_crawler/extraction/`):**
- What's not tested: `convert.py` (document-to-markdown conversion), `hybrid_server.py` (server lifecycle), `profiles.py` (extraction profiles), `workspace_utils.py`, `metrics.py`
- Files: `src/tdoc_crawler/extraction/convert.py`, `src/tdoc_crawler/extraction/hybrid_server.py`
- Risk: Conversion failures go undetected until runtime. The hybrid server auto-restart logic is untested.
- Priority: High — conversion is a critical user-facing feature

**CLI command integration tests:**
- What's not tested: End-to-end CLI command flows (`crawl-tdocs`, `crawl-meetings`, `workspace add-members`, `workspace process`)
- Files: `src/tdoc_crawler/cli/tdoc_app.py`, `src/tdoc_crawler/cli/spec_app.py`, `src/tdoc_crawler/cli/_workspace_commands.py`
- Risk: CLI flag parsing or command wiring regressions go undetected
- Priority: Medium — basic CLI tests exist in `tests/test_cli.py` but don't cover full command flows

**Spec checkout and download pipeline:**
- What's not tested: `src/tdoc_crawler/specs/operations/checkout.py`, `src/tdoc_crawler/specs/downloads.py` (download + extract + convert pipeline)
- Files: `src/tdoc_crawler/specs/operations/checkout.py`, `src/tdoc_crawler/specs/downloads.py`
- Risk: Download failures, ZIP extraction errors, and path resolution issues go undetected
- Priority: Medium — tested partially via `tests/test_specs_downloads.py`

**Workspace member processing pipeline:**
- What's not tested: The full add-member → fetch → extract → convert pipeline in workspace context
- Files: `src/tdoc_crawler/workspaces/members.py`, `src/tdoc_crawler/extraction/workspace_utils.py`
- Risk: Integration bugs between workspace management and extraction pipeline
- Priority: Medium

---

*Concerns audit: 2026-05-03*
