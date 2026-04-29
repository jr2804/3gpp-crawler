<!-- refreshed: 2026-04-30 -->
# Codebase Concerns

**Analysis Date:** 2026-04-30

## Tech Debt

### Legacy LightRAG-First Code Path Deprecation

**Issue:** Transition from LightRAG (embedding-first) to wiki-first architecture completed in v1.0, but legacy paths still present.

**Files:** 
- `src/tdoc_crawler/cli/crawl.py` — legacy command surface
- `.planning/REQUIREMENTS.md` — MIGR-01 requirement
- `.planning/STATE.md` — Phase 10 deprecation warnings

**Impact:** Users may invoke deprecated commands; backward compatibility maintained but adds maintenance surface. Future removal requires coordinated CLI decommission.

**Fix approach:** 
1. Audit deprecated command invocations in tests and documentation.
2. Plan hard removal in next major version (v2.0).
3. Document migration path in CLI help text.

---

### Incomplete Exception Type Coverage

**Issue:** Broad `except Exception` handlers throughout codebase swallow specific error types and make debugging difficult.

**Files:**
- `src/tdoc_crawler/extraction/convert.py` — lines 105, 119, 133, 303, 437 (generic exception handling)
- `src/tdoc_crawler/extraction/conversion.py` — lines 126, 204
- `src/tdoc_crawler/database/specs.py` — lines 238, 336, 505
- `src/tdoc_crawler/cli/_workspace_commands.py` — lines 114, 178, 200, 248, 288, 535
- `src/tdoc_crawler/clients/portal.py` — lines 223, 248

**Impact:** 
- Silent failures hide underlying root causes (network, malformed data, filesystem errors).
- Telemetry and logging miss specific error context.
- Stack traces are logged but not propagated to caller.

**Fix approach:**
1. Replace `except Exception` with specific exception types (network errors, validation errors, I/O errors).
2. Propagate domain-specific exceptions (e.g., `ConversionError`, `DatabaseError`).
3. Log with full traceback before re-raising for operational visibility.

---

## Async/Concurrency Complexity

### Single-Database Bottleneck with Concurrent Async Access

**Issue:** All database operations use a single SQLite file (`3gpp_crawler.db`) accessed via Oxyde ORM in async context without connection pooling or WAL mode.

**Files:**
- `src/tdoc_crawler/database/base.py` — lines 98-112 (async context manager, single connection)
- `src/tdoc_crawler/database/meetings.py` — lines 53-230 (async upsert operations)
- `src/tdoc_crawler/database/tdocs.py` — bulk operations with sequential upsert loops

**Impact:**
- SQLite single-writer concurrency model means multiple crawl operations will serialize at the DB level.
- Large bulk upsert operations (e.g., 1000+ TDocs) hold write locks sequentially per-record (`src/tdoc_crawler/database/tdocs.py` lines 70-81).
- No retry logic for transient lock contention; operations fail immediately on `database is locked`.
- Each crawl operation is single-threaded at the database layer despite async I/O elsewhere.

**Constraints:**
- SQLite is single-file by design; true parallelism requires migration to PostgreSQL.
- WAL mode (Write-Ahead Logging) mitigates but doesn't eliminate serialization at the application level.
- Current design trades off concurrency for simplicity (acceptable for single-machine use).

**Fix approach:**
1. Enable SQLite WAL mode in database initialization (`PRAGMA journal_mode=WAL`).
2. Add exponential backoff retry logic (with configurable max attempts) for lock timeouts in bulk operations.
3. Add telemetry: measure lock wait times and lock contention events.
4. Future: evaluate PostgreSQL migration for true concurrent writes if multi-machine deployment needed.

---

### Event Loop Boundary Violations

**Issue:** Sync code invoking `asyncio.run()` inside async contexts, particularly in extraction pipeline.

**Files:**
- `src/tdoc_crawler/extraction/convert.py` — line 366 (`asyncio.run(checkout_spec_to_workspace(...))`)
- `src/tdoc_crawler/database/meetings.py` — line 357 (`asyncio.run(_resolve_meeting_short_name(...))`)
- `src/tdoc_crawler/workspaces/utils.py` — lines 260-310 (async checkout within sync context)

**Impact:** 
- Nested event loops will raise `RuntimeError: asyncio.run() cannot be called from a running event loop` if called from async context.
- Crashes extraction for specs during wiki conversion when called from CLI (which uses asyncio event loop).
- Silent failures if not caught properly; error propagation is unclear.

**Trigger:** Running `workspace process` command with spec members — converts to markdown, which calls `convert_for_wiki()` → `checkout_spec_to_workspace()` → `asyncio.run()`.

**Fix approach:**
1. Refactor `convert_for_wiki()` to be fully async or extract spec checkout to pre-conversion step.
2. Use task spawning (`asyncio.create_task()`) instead of `asyncio.run()` for async sub-operations.
3. Add type hints and docstrings to clarify sync/async boundaries for future maintainers.
4. Add integration test that exercises spec extraction to catch this at CI time.

---

## Data Consistency Risks

### Spec Metadata Sync Issues (TS 26.260 Example)

**Issue:** Specifications like TS 26.260 crawled from multiple sources (whatthespec, 3gpp.org, portal) may have conflicting metadata payloads with no canonical truth source or conflict resolution.

**Files:**
- `src/tdoc_crawler/database/specs.py` — lines 380-410 (source fetch aggregation)
- `src/tdoc_crawler/specs/sources/whatthespec.py` — whatthespec client
- `src/tdoc_crawler/specs/sources/threegpp.py` — 3GPP FTP crawler
- `tests/test_specs_database.py` — spec upsert tests

**Impact:**
- If metadata differs (e.g., title, status, latest_version), the first source write wins; later sources overwrite silently with no audit trail.
- No conflict detection or alert mechanism; users have no visibility into data quality issues.
- Spec versions can be queried from one source but not persisted if crawler fails mid-upsert (partial state).
- Example from `demo.bat`: `3gpp-crawler workspace add 26260 --kind spec --release 18.1` + `--release 18.0` + `--release 17` all pointing to same spec but different versions — multiple upserts may race with no ordering guarantee.

**Fix approach:**
1. Implement source-priority policy: define canonical source order (e.g., 3GPP portal → whatthespec → FTP fallback).
2. Log source conflicts at WARN level with specific field differences; alert on major mismatches (e.g., title divergence >50%).
3. Use transaction-scoped atomicity: all versions for a spec must be inserted in a single transaction or rolled back completely.
4. Add audit table tracking source metadata changes over time for debugging.

---

### Cache Invalidation and Workspace Isolation

**Issue:** Extraction artifacts cached under `~/.3gpp-crawler/wiki/<workspace>/sources/` with no explicit cache invalidation strategy. Workspace isolation is filesystem-based only; shared database and HTTP cache.

**Files:**
- `src/tdoc_crawler/extraction/convert.py` — lines 158-167 (cache checking with `force` flag only)
- `src/tdoc_crawler/cli/_workspace_commands.py` — lines 223-293 (workspace process command)
- `src/tdoc_crawler/workspaces/crud.py` — workspace directory structure

**Impact:**
- If two workspaces reference the same TDoc/spec, they will share cached extraction artifacts — changes in one affect the other invisibly.
- No cache versioning; if opendataloader version changes, old cached artifacts become stale but are not invalidated automatically.
- `--force` flag is the only way to re-extract; no time-based, dependency-based, or semantic invalidation.
- Difficult to reason about cache freshness across workspaces.

**Fix approach:**
1. Namespace extraction cache by workspace and extraction profile: `wiki/<workspace>/<profile>/sources/<doc-id>/`.
2. Add cache metadata file (manifest) tracking extraction tool versions, timestamps, input parameters (force, profile).
3. Implement cache TTL or dependency-based invalidation: auto-invalidate if opendataloader version bumped or input file hash changes.
4. Log cache hit/miss to debug coverage.

---

## Performance Bottlenecks

### Large PDF Processing with Memory Unbounded Load

**Issue:** PDF conversion and extraction via opendataloader and LibreOffice processes files entirely in-memory with no streaming, chunking, or resource limits.

**Files:**
- `src/tdoc_crawler/extraction/conversion.py` — lines 167-209 (convert_via_libreoffice, no streaming)
- `src/tdoc_crawler/extraction/convert.py` — lines 138-194 (_ensure_converted, full JSON/MD load)
- `src/tdoc_crawler/extraction/convert.py` — lines 96-132 (extract_tables/figures/formulas, full JSON parse)

**Impact:**
- Large specs (e.g., TS 26.260 is ~500+ pages in PDF, ~50-100MB) may exceed available memory during conversion.
- opendataloader runs synchronously in main process; blocks all other CLI operations during extraction.
- JSON extraction from opendataloader output loads entire file into memory; no streaming parser for large JSON outputs (can be 10-50MB for complex specs).
- No telemetry on extraction time or peak memory usage.

**Benchmark data missing:** No documented limits on PDF size, conversion time per page, or memory usage per document.

**Fix approach:**
1. Add memory limit checks before conversion; fail fast if PDF size exceeds configurable threshold (default: 100MB).
2. Implement streaming JSON parser (e.g., `ijson` library) for large opendataloader outputs.
3. Move LibreOffice conversion to separate worker process with resource limits (memory ceiling, timeout 5min per doc).
4. Add telemetry: track PDF size, conversion time, peak memory per document for future optimization.

---

### Spec Crawl Linear Source Iteration

**Issue:** Spec source crawling (`src/tdoc_crawler/database/specs.py` lines 422-440) iterates sources serially with no parallelism or early termination on success.

**Files:**
- `src/tdoc_crawler/database/specs.py` — lines 422-440 (for loop over sources)
- `src/tdoc_crawler/specs/sources/` — three independent sources (whatthespec, 3gpp, portal)

**Impact:**
- Spec crawl latency = sum of all source latencies (typical: 0.5-2s per source with network latency, 3+ sources = 1.5-6s per spec).
- No concurrent HTTP requests; network I/O is blocking despite async database layer.
- For large spec ranges (e.g., TS 26.260-26.266 = 7 specs × 3 sources = 21 requests sequentially = ~10-50s total crawl time).
- No short-circuit: continues fetching even if first source succeeds.

**Fix approach:**
1. Parallelize source fetches via `asyncio.gather()` with timeout per source (2s).
2. Implement early termination: stop after first source success (skip remaining sources).
3. Add exponential backoff for source failures; skip source if repeated failures indicate downtime.
4. Add cache for source results to reduce redundant crawls within same session.

---

### TDoc Crawl Complexity with Multiple Filter Layers

**Issue:** TDoc crawl applies multiple filter passes sequentially, each scanning full in-memory list of 10K+ records.

**Files:**
- `src/tdoc_crawler/database/tdocs.py` — lines 116-145 (query_tdocs with 6+ filter passes)
- `src/tdoc_crawler/tdocs/operations/crawl.py` — lines 80-160 (crawl with meeting limits applied post-fetch)

**Impact:**
- For 10K+ TDocs, multiple O(n) passes degrade performance (6 passes × 10K records = 60K comparisons).
- Meeting filtering loads entire meeting table into memory for join operations; no indices used.
- All filtering is in-process Python; no push-down to SQL layer for optimization.
- No telemetry on filter selectivity or pass order impact.

**Fix approach:**
1. Consolidate filter logic into single pass where possible (e.g., combine date range + working group filter).
2. Build in-memory indices for hot filters (working_group TBID→set, date ranges into sorted lists).
3. Reorder filters by selectivity: apply most selective filters first to reduce working set early.
4. Push filtering to SQL layer when Oxyde ORM supports complex queries; document current limitations.

---

## Scalability Limits

### Single SQLite Database Backend

**Issue:** Architecture assumes single `3gpp_crawler.db` file on local filesystem. Scaling to multi-tenant, distributed, or cloud scenarios requires database migration.

**Files:**
- `src/tdoc_crawler/config/settings.py` — lines 47-58 (single db_file path)
- `src/tdoc_crawler/database/base.py` — lines 98-112 (single AsyncDatabase instance)

**Constraints:**
- SQLite is file-based; no network replication or sharding.
- Single writer at a time; read replicas are possible but complex to implement.
- Maximum database size ~2TB on most filesystems; more practically 1TB before performance degradation.

**Capacity estimate:**
- Current crawl rate: ~100K-500K TDocs/year depending on working group coverage.
- Typical project lifetime: 10+ years = 1-5M TDocs.
- Per spec: 2-5K versions tracked over 20+ releases.
- Estimate: ~10-50M records (TDocs + meetings + specs + versions) over lifetime.
- SQLite practical limit: ~10M records with indices before query latency becomes problematic (>1s for common queries).

**Future scaling path:**
- Recommendation: Plan PostgreSQL migration for v2.0 if:
  - Crawl volume exceeds 5M cumulative records, OR
  - Multi-machine deployment (distributed crawlers) needed, OR  
  - Query latency exceeds 1s for common queries.

---

### In-Process Extraction Pipeline

**Issue:** All extraction (PDF conversion, opendataloader, JSON parsing) runs synchronously in-process in the main CLI event loop.

**Files:**
- `src/tdoc_crawler/extraction/convert.py` — lines 195-293 (convert_for_wiki runs inline)
- `src/tdoc_crawler/cli/_workspace_commands.py` — lines 224-293 (workspace process command runs conversions sequentially)

**Impact:**
- Single large PDF conversion (e.g., 100MB spec = 30-60s) blocks all other operations (crawl, query, config commands).
- No task queue or worker pool; no ability to offload to separate machine or process.
- CLI becomes completely unresponsive during batch extraction of large workspaces.
- User must plan extraction during off-hours; no background/async extraction from CLI perspective.

**Mitigation in place:** `--limit` flag on workspace process command allows breaking extraction into smaller batches.

**Fix approach:**
1. Decouple extraction into separate CLI task or daemon (e.g., `3gpp-crawler extract --daemon`).
2. Use task queue (e.g., Celery, RQ) for distributed extraction if multi-machine deployment needed.
3. Add progress tracking and cancellation for long-running extractions.
4. For v1.1: implement in-process worker pool (ThreadPoolExecutor) with configurable concurrency.

---

### Workspace Isolation via Filesystem Only

**Issue:** Workspaces are isolated at filesystem level (`wiki/<workspace>/`), but share single database and HTTP cache.

**Files:**
- `src/tdoc_crawler/workspaces/crud.py` — workspace creation (filesystem-based only)
- `src/tdoc_crawler/config/workspace_registry.py` — workspace registry (single file)
- `src/tdoc_crawler/extraction/convert.py` — extraction writes to workspace-scoped directory

**Impact:**
- Multiple workspaces accessing same spec will share cached HTTP responses (no workspace-scoped cache).
- Database queries across workspaces may return overlapping results; no workspace filtering at query layer.
- No multi-workspace transactions; updates to one workspace can affect another via shared database.
- Workspace membership is filesystem-based only; no database enforces workspace boundaries.

**Fix approach:**
1. Implement workspace-scoped database access patterns: add workspace_id foreign key to relevant tables.
2. Add workspace-scoped HTTP cache namespace: `cache/<workspace>/http-cache.sqlite3`.
3. Document workspace isolation guarantees and limitations clearly in API docs.
4. Future: consider workspace-scoped databases (`db/<workspace>/crawler.db`) if isolation becomes critical.

---

## Security Surface

### Credentials Handling in Environment Variables

**Issue:** Portal credentials (username, password) stored in environment variables `TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD` with no encryption or secure storage.

**Files:**
- `src/tdoc_crawler/credentials.py` — lines 5-50 (credential resolution from env)
- `src/tdoc_crawler/config/settings.py` — lines 151-157 (credentials config)
- `docs/config.md` — migration guide (references env vars)

**Impact:**
- Credentials visible in process environment (`ps` output, docker inspect, system logs).
- No credential rotation mechanism; static credentials at risk if machine is compromised.
- .env files may be accidentally committed to version control (protected by .gitignore but not enforced).
- No TTL on credentials; compromised credentials are permanently valid until manually changed.

**Fix approach:**
1. Add optional credential encryption at rest (e.g., via keyring library or OS credential manager).
2. Implement credential TTL and refresh logic if portal supports OAuth or token-based auth.
3. Document secure credential storage best practices in CLI help and docs.
4. Add pre-commit hook to prevent .env files being committed (as additional safety layer).

---

### Input Validation via Normalization

**Issue:** TDoc IDs, spec numbers, and query patterns validated only via regex-based normalization; no schema validation in database layer.

**Files:**
- `src/tdoc_crawler/utils/normalization.py` — regex-based parsing (lines 1-50)
- `src/tdoc_crawler/config/settings.py` — lines 205-215 (SQL LIKE patterns for filters)

**Impact:**
- SQL LIKE patterns accept arbitrary strings; potential for unintended wildcard matches (e.g., `source_pattern="S4-%"` matches all S4 TDocs, not specific pattern).
- Normalization is best-effort; malformed IDs may still reach database and cause silent failures.
- No explicit validation of enum-like fields (e.g., tdoc_type, status) — arbitrary strings accepted.
- LIKE wildcards are not escaped; user input containing `%` or `_` will be interpreted as wildcards.

**Fix approach:**
1. Add Pydantic validators for all query input parameters (TDocQueryConfig, SpecQueryFilters).
2. Escape SQL LIKE wildcards explicitly in query layer; document LIKE syntax constraints in help.
3. Add deny-list for dangerous patterns (e.g., block queries with only "%" or "%_").
4. Validate enum fields against allowed set (TDocType, SpecStatus, etc.); reject unknown values.

---

### API URL Validation and SSRF Protection

**Issue:** PDF converter remote API URL validated via `validate_api_url()`, but validation happens at configuration time only (not per-request).

**Files:**
- `src/tdoc_crawler/utils/security.py` — lines 36-82 (validate_api_url)
- `src/tdoc_crawler/extraction/conversion.py` — lines 47-50 (api_base in config)

**Coverage:** Good SSRF protection (blocks private/loopback IPs, validates scheme), but:
- DNS rebinding attacks possible if resolver is compromised between config validation and request.
- No rate limiting on API calls; remote API could DOS consumer.
- No certificate pinning or hostname validation for TLS connections.

**Fix approach:** Current implementation is adequate for v1.1. Add rate limiting as separate concern for v2.0 if needed.

---

## Maintainability Concerns

### High-Complexity Crawl Operations

**Issue:** TDoc crawl logic combines meeting resolution, document list parsing, pattern matching, and upsert in a single class method with ~300+ LOC and multiple static helper methods.

**Files:**
- `src/tdoc_crawler/tdocs/operations/crawl.py` — lines 43-100 (crawl method)
- Lines 171-200 (_parse_document_list_payload, complex regex/JSON parsing)
- Lines 247-328 (multiple static filter methods)

**Impact:**
- High cyclomatic complexity; difficult to test individual filter paths in isolation.
- Parser logic mixed with crawl orchestration; hard to reuse parsing for incremental updates or recovery.
- No clear separation between data fetching, parsing, and persistence layers.
- Small fixes can cascade across multiple related methods; regression risk is high.

**Fix approach:**
1. Extract document list parsing into dedicated parser module with comprehensive unit tests.
2. Split crawl orchestration into smaller methods (query meetings, fetch documents, prepare records, upsert).
3. Add integration tests for common crawl scenarios (incremental, filtering by date, by working group, meeting limits).
4. Consider visitor pattern or event-based architecture for parse → persist workflow.

---

### Test Fixtures Tied to Real Data

**Issue:** Some tests use fixed TDoc IDs and assume real data availability; may break if external data changes or network is unavailable.

**Files:**
- `tests/test_whatthespec.py` — tests against live whatthespec API
- `tests/test_specs_sources.py` — tests against live spec sources
- `tests/test_meeting_document_list.py` — tests against real 3GPP portal data

**Impact:**
- Flaky tests due to network/external data dependency; CI failures don't indicate code issues.
- Test failures on local machine if network unavailable (e.g., offline development).
- No way to run full test suite reproducibly without external services; makes release validation difficult.

**Fix approach:**
1. Add mock/fixture data for external API responses; generate from real responses once, then version in repo.
2. Use VCR.py or similar to record and replay HTTP interactions; re-record only when intentionally updating fixtures.
3. Mark network-dependent tests with `@pytest.mark.requires_network` for conditional execution.
4. Provide separate CI job for integration tests against real APIs; gate release on unit tests alone.

---

### Singleton CacheManager with Global State

**Issue:** CacheManager uses singleton pattern with global `_instance` state; must be reset between tests via autouse fixture.

**Files:**
- `src/tdoc_crawler/config/__init__.py` — CacheManager singleton
- `tests/conftest.py` — lines 17-26 (autouse fixture to reset singleton)

**Impact:**
- Test order dependency; tests may interfere if singleton not properly reset.
- Difficult to test concurrent cache scenarios (two CLI instances with different cache dirs simultaneously).
- Global state makes code less unit-testable; complicates mocking.
- Autouse fixture hides the dependency; future developers may not realize singleton impact.

**Fix approach:**
1. Dependency-inject CacheManager rather than using singleton pattern.
2. Remove autouse fixture; pass CacheManager explicitly to functions that need it.
3. Add context manager for isolated cache scopes (e.g., `with cache_scope(...): ...`).
4. Document CacheManager lifecycle and thread-safety guarantees.

---

## Known Issues and Gaps

### Milestone Audit Artifact Missing

**Issue:** v1.0 closed without completion of planned milestone audit artifact (`v1.0-MILESTONE-AUDIT.md`).

**Files:** `.planning/STATE.md` — "Deferred Items" section

**Impact:** No structured summary of what was delivered vs. planned; hinders v1.1 planning and retrospective.

**Fix approach:** Generate post-hoc audit in v1.1 Phase 12 if scope allows; capture lessons learned for process improvement.

---

### Unclear Opendataloader Conversion Failure Handling

**Issue:** Opendataloader conversion failures caught generically; no metrics on failure modes or recovery strategies.

**Files:**
- `src/tdoc_crawler/extraction/convert.py` — lines 138-194 (_ensure_converted)
- `src/tdoc_crawler/extraction/convert.py` — lines 303, 437 (exception handlers)
- `tests/convert_lo/test_integration.py` — integration tests present but may not cover all failure cases

**Impact:** 
- Silent extraction failures; no clear signal to user that PDF analysis failed.
- No fallback to plain text or raw PDF if opendataloader fails.
- Difficult to debug extraction issues for specific documents without verbose logging.

**Fix approach:**
1. Log conversion failure details with severity (input file size, opendataloader version, error message).
2. Implement fallback: if extraction fails, fallback to pdf2text (via pdfplumber or similar) or raw PDF copy.
3. Add `--verbose` flag to extraction commands for detailed diagnostic output; log all exceptions with stack traces.
4. Add telemetry: count and classify extraction failures by type (timeout, out-of-memory, format error, etc.).

---

## Deferred Improvements (v1.1+ scope)

### Performance Metrics and Observability

**Issue:** No built-in telemetry for crawl speed, extraction latency, database query performance.

**Files:** `src/tdoc_crawler/extraction/metrics.py` — minimal metrics module

**Recommendation:** Add comprehensive telemetry in v1.1 Phase 12 or v2.0 sprint. Implement OpenTelemetry integration for production observability; log key metrics to stdout/stderr or export to metrics service.

---

### Database Query Optimization

**Issue:** No database indices for common query patterns (working_group, date_range, tdoc_id).

**Files:** `src/tdoc_crawler/database/base.py` — schema creation (lines 185-210)

**Recommendation:** Profile queries under load with 10K+ record dataset; add indices for hot paths:
- `idx_tdocs_wg_date(working_group_tbid, date_retrieved DESC)`
- `idx_meetings_tbid(tbid)`
- `idx_specs_number(spec_number)`

---

### Concurrent Crawl Support

**Issue:** Multiple crawl operations will serialize at the database layer due to SQLite single-writer model.

**Recommendation:** Implement concurrent crawl coordinator for v2.0; can coordinate multiple working groups in parallel if each uses separate database file (e.g., db/S4.db, db/RAN1.db).

---

*Concerns analysis: 2026-04-30 — Comprehensive audit of technical debt, async complexity, data consistency, performance, scalability, security, and maintainability concerns across extraction pipeline, database layer, and CLI interface.*
