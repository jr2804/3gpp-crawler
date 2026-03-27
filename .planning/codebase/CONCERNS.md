# Codebase Concerns

**Analysis Date:** 2026-03-27

## Tech Debt

### Inline `.strip().upper()` Instead of Centralized Normalization

- **Severity:** MEDIUM
- **Issue:** 22 instances of inline `str.strip().upper()` across 15 files instead of using the centralized `normalize_tdoc_id()` from `src/tdoc_crawler/tdocs/utils.py`. This creates inconsistent normalization behavior.
- **Files:**
  - `src/tdoc_crawler/cli/tdoc_app.py` (lines 81, 131)
  - `src/tdoc_crawler/cli/app.py` (lines 84, 134)
  - `packages/3gpp-ai/threegpp_ai/operations/convert.py` (lines 134, 196, 235)
  - `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (lines 302, 328)
  - `packages/3gpp-ai/threegpp_ai/operations/summarize.py` (line 318)
  - `packages/3gpp-ai/threegpp_ai/lightrag/seeder.py` (lines 144, 284)
  - `packages/3gpp-ai/threegpp_ai/lightrag/metadata.py` (line 72)
  - `src/tdoc_crawler/database/tdocs.py` (line 215)
  - `src/tdoc_crawler/models/crawl_log.py` (line 32)
  - `src/tdoc_crawler/meetings/utils.py` (lines 60, 98)
  - `src/tdoc_crawler/database/meetings.py` (line 108)
  - `src/tdoc_crawler/tdocs/sources/whatthespec.py` (line 74)
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (lines 179, 194, 233, 251, 270)
- **Impact:** Inconsistent normalization — some paths validate format, others just strip/uppercase. A malformed ID like `s4-250001` gets `.upper()` but not format validation.
- **Fix approach:** Replace all inline `.strip().upper()` on TDoc IDs with `normalize_tdoc_id()`. For working group codes, introduce a `normalize_wg_code()` utility.

### Duplicated Scope Display Block in `crawl_tdocs()`

- **Severity:** MEDIUM
- **Issue:** Lines 152–177 in `src/tdoc_crawler/cli/crawl.py` contain an exact copy of the scope display logic from lines 136–163. The same `if meetings / elif subgroups / else` block appears twice.
- **Files:** `src/tdoc_crawler/cli/crawl.py` (lines 152–177 duplicate lines 136–163)
- **Impact:** Confusing for maintainers; scope_parts may contain duplicate entries.
- **Fix approach:** Remove the duplicated block entirely.

### Scattered Normalization Functions Across Modules

- **Severity:** MEDIUM
- **Issue:** Normalization functions live in 5 separate modules rather than a single canonical location.
- **Files:**
  - `src/tdoc_crawler/tdocs/utils.py` — `normalize_tdoc_id()`, `normalize_tdoc_ids()`
  - `src/tdoc_crawler/utils/normalization.py` — `normalize_spec_number()`, `normalize_release()`, `expand_spec_ranges()`
  - `src/tdoc_crawler/meetings/utils.py` — `normalize_portal_meeting_name()`, `normalize_working_group_alias()`, `normalize_subgroup_alias()`
  - `packages/3gpp-ai/threegpp_ai/lightrag/metadata.py` — `normalize_release_label()`
  - `packages/3gpp-ai/threegpp_ai/operations/workspace_names.py` — `normalize_workspace_name()`
- **Impact:** Developers must know which module to import from; risk of creating yet another normalization function.
- **Fix approach:** Keep domain-specific normalizers in their domain modules (meeting utils for meetings, tdoc utils for tdocs), but add cross-references in `src/tdoc_crawler/utils/normalization.py` docstring. The AI package's `normalize_release_label()` duplicates release normalization already in `utils/normalization.py`.

### WorkspaceStatus Enum — Potentially Unnecessary

- **Severity:** LOW
- **Issue:** TODO comment at line 72 indicates this enum may be redundant.
- **Files:** `packages/3gpp-ai/threegpp_ai/models.py` (line 72)
- **Impact:** Minor code clarity issue; dead enum with only one value (`ACTIVE`).
- **Fix approach:** Evaluate if `WorkspaceStatus` is used anywhere beyond the model. If membership state is inferred from `WorkspaceMember.is_active`, remove this enum.

### Migration Module — Possibly Dead Code

- **Severity:** LOW
- **Issue:** TODO comment at line 11 questions the need for this entire module.
- **Files:** `packages/3gpp-ai/threegpp_ai/lightrag/migration.py`
- **Impact:** Module ships in production but may never be called by users.
- **Fix approach:** Keep `consolidate_workspaces()` if users have legacy data, but remove `migrate_to_shared_storage()` and its dead import paths.

### Hardcoded Specs Directory Path

- **Severity:** MEDIUM
- **Issue:** `specs_dir` is constructed from raw `checkout_base` instead of being resolved via `CacheManager`, contradicting the project's single-source-of-truth path pattern. The TODO at line 539 acknowledges this.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (line 539)
- **Impact:** If the checkout directory structure changes, this path breaks silently.
- **Fix approach:** Resolve `specs_dir` through `CacheManager.checkout_dir / "Specs"` or accept it as a parameter from the caller.

### Duplicated `parse_partial_date()` Expressions

- **Severity:** LOW
- **Issue:** The expression `parse_partial_date(start_date, is_end=False) if start_date and start_date.strip() else None` appears 6 times in `src/tdoc_crawler/cli/crawl.py` (lines 122, 123, 147, 148, 226, 227, 350, 351).
- **Files:** `src/tdoc_crawler/cli/crawl.py`
- **Impact:** Verbosity and potential for inconsistency if the parsing logic changes.
- **Fix approach:** Extract into a helper like `_optional_parse_date(date_str: str | None, *, is_end: bool) -> date | None`.

## Architecture Concerns

### Large CLI Module (894 lines)

- **Severity:** MEDIUM
- **Issue:** `packages/3gpp-ai/threegpp_ai/cli.py` is 894 lines — far above the 500-line threshold for maintainability. It contains all AI-related CLI commands.
- **Files:** `packages/3gpp-ai/threegpp_ai/cli.py` (894 lines)
- **Impact:** Hard to navigate; changes to one command risk affecting others.
- **Fix approach:** Split into domain-specific submodules (e.g., `cli_workspace.py`, `cli_rag.py`, `cli_convert.py`) and use Typer's `app.add_typer()` for composition.

### Large Extraction Result Module (467 lines)

- **Severity:** LOW
- **Issue:** `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` handles table detection, figure extraction, equation parsing, and marker generation all in one file.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` (467 lines)
- **Impact:** Mixed responsibilities make testing and refactoring harder.
- **Fix approach:** Separate equation detection, table extraction, and marker generation into distinct modules.

### Monolithic Workspaces Module (637 lines)

- **Severity:** MEDIUM
- **Issue:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` handles workspace CRUD, member management, TDoc/spec checkout resolution, path scanning (`rglob`), and AI subfolder management — all in a single module.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (637 lines)
- **Impact:** Tight coupling between workspace registry operations and checkout file system logic.
- **Fix approach:** Extract checkout path resolution and file system operations into a separate `checkout_utils.py` module.

### 3GPP AI Package Depends on TDoc Crawler Internals

- **Severity:** LOW
- **Issue:** The `packages/3gpp-ai` package directly imports from `src/tdoc_crawler` internals (`config`, `database`, `tdocs.models`, `utils.normalization`), creating a cross-package dependency that couples the AI module tightly to the crawler's internal structure.
- **Files:**
  - `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` — imports `tdoc_crawler.config`, `tdoc_crawler.database`, `tdoc_crawler.tdocs.operations.checkout`
  - `packages/3gpp-ai/threegpp_ai/models.py` — imports `tdoc_crawler.tdocs.utils`
  - `packages/3gpp-ai/threegpp_ai/config.py` — reads `TDC_AI_*` env vars
- **Impact:** Changes to crawler internals can break the AI package; the AI package cannot be used standalone.
- **Fix approach:** Define a stable interface layer or shared types package. Accept this coupling for now but document it as intentional.

### Duplicate Response Check in Portal Authentication

- **Severity:** LOW
- **Issue:** Lines 152–158 in `src/tdoc_crawler/clients/portal.py` check `response_text.lower() == "failed"` twice — once on line 152 and again on line 157.
- **Files:** `src/tdoc_crawler/clients/portal.py` (lines 152–158)
- **Impact:** The second check is dead code; confusing for readers.
- **Fix approach:** Remove the duplicate check on line 157.

## Reliability Concerns

### Broad Exception Handling (56 `except Exception` blocks)

- **Severity:** MEDIUM
- **Issue:** 56 instances of `except Exception` across `src/` and `packages/`. Many catch-all blocks silently swallow errors and return `None` or empty collections, masking real failures.
- **Files (worst offenders):**
  - `src/tdoc_crawler/database/base.py` (lines 55, 187) — bare `except Exception:` returns `[]`
  - `src/tdoc_crawler/database/specs.py` (lines 97, 188, 317, 479) — 4 catch-all blocks
  - `src/tdoc_crawler/tdocs/sources/doclist.py` (lines 78, 133, 140, 214, 357, 430) — 6 catch-all blocks
  - `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (lines 43, 161, 412, 422, 434, 476, 557, 595) — 8 catch-all blocks
  - `packages/3gpp-ai/threegpp_ai/operations/summarize.py` (lines 146, 158, 336, 346) — 4 catch-all blocks
- **Impact:** Errors are silently swallowed. Database corruption, network failures, and data integrity issues may go undetected. Debugging production issues is extremely difficult.
- **Fix approach:** Replace catch-all blocks with specific exception types. For operations where `None` return is acceptable (e.g., optional lookups), catch `KeyError`, `ValueError`, `json.JSONDecodeError`. For critical operations, let exceptions propagate or wrap in domain-specific exceptions with `from exc`.

### Silent Return of Empty Results on Database Errors

- **Severity:** MEDIUM
- **Issue:** `_table_rows()` in `database/base.py` (line 187) and `get_spec_versions()` in `database/specs.py` (line 188) return empty lists on any database error, making it indistinguishable from "no data found."
- **Files:**
  - `src/tdoc_crawler/database/base.py` (line 187): `except Exception: return []`
  - `src/tdoc_crawler/database/specs.py` (line 188): `except Exception: return []`
- **Impact:** A corrupted database file or schema mismatch silently produces empty results instead of surfacing the actual error.
- **Fix approach:** Log the exception at WARNING or ERROR level before returning. Consider raising `DatabaseError` for unexpected failures.

### Portal Authentication State Not Reset on Failure

- **Severity:** LOW
- **Issue:** `PortalClient.authenticate()` sets `self._authenticated = True` only on success, but never resets it. If a subsequent operation detects session expiry (line 262 sets `_authenticated = False`), there is no automatic re-authentication mechanism.
- **Files:** `src/tdoc_crawler/clients/portal.py` (lines 105–163, 260–262)
- **Impact:** Long-running crawl sessions may fail mid-way when portal session expires.
- **Fix approach:** Add re-authentication retry logic in `fetch_tdoc_metadata()` when `PortalAuthenticationError` is raised.

### External Service Dependency — 3GPP Portal and FTP

- **Severity:** LOW
- **Issue:** All crawling operations depend on external 3GPP servers (portal.3gpp.org, ftp.3gpp.org). No circuit breaker or rate limit detection.
- **Files:** `src/tdoc_crawler/clients/portal.py`, `src/tdoc_crawler/specs/downloads.py`, `src/tdoc_crawler/tdocs/sources/doclist.py`
- **Impact:** Portal maintenance or FTP outages halt all crawl operations.
- **Fix approach:** Add configurable retry with exponential backoff (partially done via `hishel`), detect 429/503 responses, and provide graceful degradation messages.

## Security Considerations

### Credentials — Well Managed

- **Severity:** NONE (well handled)
- **Files:** `src/tdoc_crawler/credentials.py`
- **Current mitigation:** Credentials stored in environment variables (`TDC_EOL_USERNAME`, `TDC_EOL_PASSWORD`); password input hidden via `typer.prompt(..., hide_input=True)`; never logged or persisted to disk; Pydantic model `PortalCredentials` for type safety.
- **Status:** No action needed.

### LLM API Keys — Properly Managed

- **Severity:** NONE (well handled)
- **Files:** `packages/3gpp-ai/threegpp_ai/config.py`, `packages/3gpp-ai/threegpp_ai/operations/llm_client.py`
- **Current mitigation:** `TDC_AI_LLM_API_KEY` environment variable; runtime validation with warnings if missing; never hardcoded.
- **Status:** No action needed.

### pg0 Default Credentials

- **Severity:** LOW
- **Issue:** `Pg0Manager` in `packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py` hardcodes default PostgreSQL credentials in the connection URI: `postgresql://postgres:postgres@localhost:{port}/{database}` (line 93).
- **Files:** `packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py` (line 93)
- **Impact:** pg0 is a local-only embedded database, so the risk is minimal. However, if the URI is ever exposed to logs or network, credentials leak.
- **Fix approach:** Accept credentials as optional constructor parameters with these defaults. Ensure the URI is never logged.

### Path Traversal in `rglob` Checkout Search

- **Severity:** LOW
- **Issue:** `resolve_tdoc_checkout_path()` in `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (lines 386–389) uses `checkout_base.rglob("Docs")` and then constructs paths from user-provided `tdoc_id`. A malicious `tdoc_id` containing `../` could traverse outside the checkout directory.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (line 387)
- **Impact:** Low — `tdoc_id` is validated by `normalize_tdoc_id()` upstream (regex check), which rejects path separators. But the pattern is still fragile.
- **Fix approach:** Add explicit `resolve()` and check that the resulting path is still within `checkout_base`.

### SQL Injection — Low Risk

- **Severity:** LOW
- **Issue:** `database/base.py` uses f-string table names in SQL (lines 153, 207, 209) with `# noqa: S608`. Table names are validated against a whitelist (`model_map`), so injection is prevented.
- **Files:** `src/tdoc_crawler/database/base.py` (lines 153, 207, 209)
- **Current mitigation:** Table names restricted to `model_map` keys; user data always parameterized.
- **Status:** Acceptable for now. Consider using explicit SQL templates if more queries are added.

## Performance Concerns

### `resolve_tdoc_checkout_path()` Uses `rglob` — O(n) File System Scan

- **Severity:** MEDIUM
- **Issue:** `resolve_tdoc_checkout_path()` recursively searches the entire checkout directory tree for a `Docs` subfolder matching a TDoc ID. With thousands of checked-out TDocs, this becomes slow.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (lines 384–390)
- **Impact:** O(n) scan on every checkout call. With large checkouts (>1000 directories), each resolution takes seconds.
- **Fix approach:** Build an in-memory index mapping TDoc IDs to checkout paths (populated once from the database). Cache the index.

### Spec Version Release Resolution — Multiple DB Opens

- **Severity:** LOW
- **Issue:** `checkout_spec_to_workspace()` opens `SpecDatabase` twice — once in `resolve_spec_release_from_db()` (line 37) and again in `checkout_specs()` (line 579) — each with its own connection.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (lines 31–45, 574–597)
- **Impact:** Unnecessary overhead of opening/closing SQLite connections.
- **Fix approach:** Pass the database instance or the resolved release data through the call chain instead of re-querying.

### `_table_rows()` Loads Entire Tables into Memory

- **Severity:** LOW
- **Issue:** `_table_rows()` in `database/base.py` fetches all rows from a table and converts them to Pydantic models. For tables with thousands of rows (e.g., `tdocs`, `spec_versions`), this is memory-intensive.
- **Files:** `src/tdoc_crawler/database/base.py` (lines 146–188)
- **Impact:** Memory spikes when querying large tables; `query_specs()` loads all specs then filters in Python.
- **Fix approach:** Add WHERE clauses for common queries instead of loading full tables. Use generators or pagination for large result sets.

## Maintainability Concerns

### TODO/FIXME Markers

- **Severity:** LOW
- **Issue:** 5 TODO markers found in source code.
- **Files:**
  - `packages/3gpp-ai/threegpp_ai/models.py` (line 72): `# TODO: Unnecessary?`
  - `packages/3gpp-ai/threegpp_ai/lightrag/migration.py` (line 11): `# TODO: Is this module needed at all?`
  - `packages/3gpp-ai/threegpp_ai/operations/workspaces.py` (line 539): `# TODO: resolve specs_dir from cache_manager!`
- **Impact:** Technical debt accumulates when TODOs are not tracked.
- **Fix approach:** Resolve or convert to tracked issues.

### Inconsistent Logging Module Usage

- **Severity:** LOW
- **Issue:** Core package uses `from tdoc_crawler.logging import get_logger` while the AI package uses `import logging` with `logging.getLogger(__name__)`.
- **Files:**
  - `src/tdoc_crawler/` — uses custom `get_logger(__name__)`
  - `packages/3gpp-ai/threegpp_ai/` — uses `logging.getLogger(__name__)`
- **Impact:** Different log format and configuration between packages. AI package logs may not respect the CLI's verbosity settings.
- **Fix approach:** Have the AI package import and use the same `get_logger` from `tdoc_crawler.logging`, or ensure the AI package's logging is configured to respect root-level settings.

### LiteLLM Singleton Pattern

- **Severity:** LOW
- **Issue:** `LiteLLMClient` in `packages/3gpp-ai/threegpp_ai/operations/llm_client.py` uses `__new__` singleton but has an empty `__init__`. The singleton prevents testing with different configurations.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/llm_client.py` (lines 24–33)
- **Impact:** Tests cannot inject mock configurations; global state persists between test runs.
- **Fix approach:** Convert to a factory function or accept configuration via parameters instead of relying on `AiConfig.from_env()` inside each method.

### Inconsistent Error Module Across Packages

- **Severity:** LOW
- **Issue:** The AI package defines its own exceptions (`AiError`, `ConversionError`, etc.) in `threegpp_ai/models.py` while the crawler uses `DatabaseError` from `tdoc_crawler/database/errors.py`. Cross-package error handling is inconsistent.
- **Files:**
  - `packages/3gpp-ai/threegpp_ai/models.py` (lines 87–113)
  - `src/tdoc_crawler/database/errors.py`
- **Impact:** Callers catching exceptions need to know which package's exception hierarchy to use.
- **Fix approach:** Document the exception hierarchy for each package. Consider a shared exceptions module if the coupling is acceptable.

## Test Coverage Gaps

### AI Pipeline Error Recovery

- **Severity:** HIGH
- **What's not tested:** Classification failures, extraction failures, embedding failures, graph building failures, and their impact on workspace state.
- **Files:** `packages/3gpp-ai/threegpp_ai/operations/` (extraction.py, conversion.py, figure_descriptor.py)
- **Risk:** Errors in AI pipeline may corrupt workspace state or leave documents in a half-processed state.
- **Priority:** Add tests that verify workspace state remains consistent after partial failures.

### Error Recovery Paths for Network Operations

- **Severity:** MEDIUM
- **What's not tested:** Network failure recovery, timeout handling, retry logic for HTTP requests.
- **Files:** `src/tdoc_crawler/tdocs/operations/fetch.py`, `src/tdoc_crawler/http_client/session.py`
- **Risk:** Unhandled network failures may leave the system in an inconsistent state (partial downloads, stale cache entries).
- **Priority:** Add integration tests with mocked network failures.

### Normalization Edge Cases

- **Severity:** MEDIUM
- **What's not tested:** Edge cases in spec number normalization (unicode characters, unusual formats like `TS26.444` with spaces, trailing dots).
- **Files:** `src/tdoc_crawler/utils/normalization.py`
- **Risk:** Incorrect normalization may cause data inconsistencies across the database.
- **Priority:** Tests exist (`tests/test_specs_normalization.py`) but may not cover all edge cases.

### Portal Session Expiry and Re-authentication

- **Severity:** LOW
- **What's not tested:** Session timeout detection, automatic re-authentication, concurrent session usage.
- **Files:** `src/tdoc_crawler/clients/portal.py`
- **Risk:** Long-running operations may fail when the portal session expires mid-crawl.
- **Priority:** Low — Portal sessions are typically short-lived in crawl operations.

### `SpecCrawlSourceOutcome` Error Branch

- **Severity:** LOW
- **What's not tested:** The `source.status == "error"` branch in `crawl_single_spec()` where all sources fail.
- **Files:** `src/tdoc_crawler/database/specs.py` (lines 314–327)
- **Risk:** Error aggregation for multi-source spec crawls may not propagate correctly.
- **Priority:** Low.

______________________________________________________________________

*Concerns audit: 2026-03-27*
