# Codebase Concerns

**Analysis Date:** 2026-05-03

## Known Bugs

### Python 2 Exception Syntax (`except X, Y`)

**Symptoms:** Only `OSError` is caught. `ValueError` and `json.JSONDecodeError` pass through unhandled, potentially crashing the caller.

**Files:**
- `src/tdoc_crawler/extraction/workspace_utils.py:39` — `except OSError, ValueError:`
- `src/tdoc_crawler/cli/_workspace_commands.py:234` — `except json.JSONDecodeError, OSError:`

**Trigger:** Any `ValueError` inside `check_pdf_status()` (e.g., invalid path string) or any `OSError` inside `_read_json_profile()` (e.g., file not found).

**Workaround:** None. These are silently swallowing only `OSError` (first case) or only `json.JSONDecodeError` (second case), aliasing the exception instance to the second name.

**Fix:** Replace `except OSError, ValueError:` with `except (OSError, ValueError):` and `except json.JSONDecodeError, OSError:` with `except (json.JSONDecodeError, OSError):`.

### Stale Config Reference to Non-Existent Package

**Symptoms:** `ruff` per-file-ignore references `packages/3gpp-ai/threegpp_ai/cli.py` which does not exist in this repository.

**Files:**
- `ruff.toml:71` — `"packages/3gpp-ai/threegpp_ai/cli.py" = ["E402"]`

**Impact:** Linting works but the configuration is misleading. If the `3gpp-ai` package is re-added, E402 violations in its CLI will be silently ignored.

**Fix:** Either remove the stale entry or verify the 3gpp-ai package has been intentionally separated into a different repository and remove the reference.

## Tech Debt

### Widespread Bare `except Exception` Usage

**Issue:** 45 instances of bare `except Exception` across the codebase. Many swallow errors with a `logger.warning()` and continue, potentially masking bugs.

**Files (representative):**
- `src/tdoc_crawler/extraction/convert.py:121,135,149,365,534`
- `src/tdoc_crawler/cli/_workspace_commands.py:156,180,278,312,383,461,533`
- `src/tdoc_crawler/database/base.py:61,241,270`
- `src/tdoc_crawler/database/specs.py:96,194,477`
- `src/tdoc_crawler/clients/portal.py:219,244`
- `src/tdoc_crawler/workspaces/crud.py:65,120`
- `src/tdoc_crawler/tdocs/sources/doclist.py:172,225,240,265,304,344,364,368`
- `src/tdoc_crawler/extraction/conversion.py:140,218`

**Impact:** Exceptions in these blocks are caught and logged, but program state may be left inconsistent. Real bugs can be hidden for months.

**Fix approach:** Audit each bare `except Exception` and determine if it should:
1. Catch a more specific exception type
2. Re-raise after logging
3. Clean up state before continuing

Priority: `doclist.py` (8 instances), `_workspace_commands.py` (6 instances), `convert.py` (5 instances)

### Near-Duplicate Extraction Functions

**Issue:** Three functions in `extraction/convert.py` share identical structure — only the `type` filter differs:
- `_extract_tables_from_opendataloader_json` (line 112) — filters `type == "table"`
- `_extract_figures_from_opendataloader_json` (line 126) — filters `type in ("image", "figure")`
- `_extract_formulas_from_opendataloader_json` (line 140) — filters `type == "formula"`

**Files:** `src/tdoc_crawler/extraction/convert.py`

**Fix approach:** Extract a single `_extract_items_from_opendataloader_json(json_path, accepted_types)` function.

### `ConversionError` is an Empty Exception Class

**Issue:** `ConversionError` in `src/tdoc_crawler/extraction/convert.py:48-51` has a `pass` body. It carries no structured error information (file path, document ID, error type).

**Impact:** Callers cannot distinguish between "file not found", "conversion timeout", or "bad input" without parsing the string message.

**Fix approach:** Add attributes for `document_id`, `reason`, and optionally the `source_file` path.

### `CacheManagerNotRegisteredError` Has No Context

**Issue:** `src/tdoc_crawler/config/cache_manager.py:35-38` — exception class with `pass` body. Provides no hint about when/where registration was expected.

**Impact:** Users debugging a library integration get "CacheManager not registered" with no guidance.

**Fix approach:** Add a `recommendation` attribute or descriptive message suggesting `CacheManager(cache_dir).register()`.

### Direct `os.environ` Mutation in Credential Module

**Issue:** `src/tdoc_crawler/credentials.py:23-27` — `set_credentials()` directly writes to `os.environ` as a side effect.

```python
os.environ["TDC_EOL_USERNAME"] = username
os.environ["TDC_EOL_PASSWORD"] = password
```

**Impact:** Mutating global process state makes testing harder, can cause subtle interactions between components reading environment variables at different times, and bypasses the `ThreeGPPConfig` / `CredentialsConfig` abstraction.

**Fix approach:** Deprecate `set_credentials()` in favor of `ThreeGPPConfig.from_settings()` with explicit credential parameters. If environment variable mutation is required for subprocess spawning, isolate it to the CLI entry point only.

### Hardcoded Env Var String Literals in Credential Resolution

**Issue:** `src/tdoc_crawler/credentials.py:54-55,64` uses string literals `"TDC_EOL_USERNAME"`, `"TDC_EOL_PASSWORD"`, `"TDC_EOL_PROMPT"` instead of the `ConfigEnvVar` enum.

**Files:** `src/tdoc_crawler/credentials.py`

**Impact:** If env var names change, this module won't be updated. Inconsistent with the rest of the config system which uses `ConfigEnvVar`.

**Fix approach:** Replace with `ConfigEnvVar.TDC_EOL_USERNAME.name`, etc.

### `CredentialsConfig.password` Lacks Sensitive Marking

**Issue:** `src/tdoc_crawler/config/settings.py:167-170` — `CredentialsConfig.password` is a plain `str | None` field with no `SecretStr` wrapper.

**Impact:** The password appears in plain text in logs, tracebacks, and serialized config output. The `noqa: S105` suppression on `env_vars.py:37` confirms this was flagged but suppressed.

**Fix approach:** Use `pydantic.SecretStr` for the password field. Modify `env_vars.py` to handle serialization correctly.

## Security Considerations

### API Key Read Outside Configuration System

**Risk:** `src/tdoc_crawler/extraction/conversion.py:54-55` reads `PDF_REMOTE_API_KEY` directly via `os.getenv()`, bypassing the centralized `ThreeGPPConfig` and `ConfigEnvVar` system.

**Files:** `src/tdoc_crawler/extraction/conversion.py:46-56`

**Current mitigation:** The API key is only used for the remote PDF converter backend (LibreOffice is default). However, there is no validation, no masking in logs, and no integration with the config file system.

**Recommendation:** Add `ConverterConfig` fields to `ThreeGPPConfig` (e.g., `conversion.pdf_remote_api_key: SecretStr | None`) or provide a dedicated `ConverterConfig` dataclass that accepts the key from the config system rather than reading os.environ directly.

### Config File Environment Variable Interpolation

**Risk:** `src/tdoc_crawler/config/sources.py:53-77` — `_interpolate_env_vars()` replaces `${ENV_VAR}` patterns in config files with environment variable values. If a malicious config file contains `${PATH}` or `${HOME}`, those values are injected into the config.

**Files:** `src/tdoc_crawler/config/sources.py`

**Current mitigation:** Config files must be writable by the user running the tool. This is a low-risk concern for a CLI tool but could be relevant in shared environments.

**Recommendation:** Document the interpolation behavior. Consider adding an allowlist of interpolatable variable names.

### Pre-Commit Lacks Dedicated Security Scanning

**Issue:** The pre-commit config (`pre-commit-config.yaml`) enables ruff's `S` (bandit) rules, but has no standalone `bandit` hook or `detect-secrets` hook. Relies entirely on ruff's bandit implementation.

**Files:** `.pre-commit-config.yaml`

**Recommendation:** Ruff's S rules cover common patterns. No immediate action needed, but consider adding `detect-secrets` for credential scanning.

## Performance Bottlenecks

### Sequential Workspace Processing

**Problem:** `src/tdoc_crawler/cli/_workspace_commands.py:338-360` processes workspace members one at a time in a sequential `for` loop.

**Files:** `src/tdoc_crawler/cli/_workspace_commands.py`

**Cause:** No parallelism in the workspace `process` command. Each member's PDF conversion, OpenDataLoader extraction, and metadata enrichment run serially.

**Improvement path:** Use `concurrent.futures.ThreadPoolExecutor` or process pool for parallel member processing, similar to the `TDocCrawler._crawl_meetings()` pattern in `src/tdoc_crawler/tdocs/operations/crawl.py`.

### Synchronous `asyncio.run()` in a Loop

**Problem:** `src/tdoc_crawler/extraction/convert.py:307` calls `asyncio.run(_lookup_tdoc_in_db(...))` synchronously. When processing multiple documents, each one spawns and tears down a new event loop.

**Files:** `src/tdoc_crawler/extraction/convert.py:307`

**Improvement path:** Batch database lookups or reuse a single event loop context.

### Large Single-File Modules

**Problem:** Several files exceed 300 lines and handle multiple responsibilities:
- `extraction/convert.py` — 589 lines (TDoc conversion, spec conversion, OpenDataLoader integration, hybrid server management, metadata enrichment)
- `cli/_workspace_commands.py` — 534 lines (all workspace CLI commands in one file)
- `database/specs.py` — 494 lines (spec DB ops, version resolution, crawling)
- `config/workspace_registry.py` — 461 lines (registry CRUD, TypedDict definitions, serialization)

**Improvement path:** Split `extraction/convert.py` into separate modules for spec vs. TDoc conversion, OpenDataLoader wrapper, and metadata enrichment. Split `_workspace_commands.py` into per-command modules.

## Fragile Areas

### `extraction/convert.py` — High Coupling Module

**Files:** `src/tdoc_crawler/extraction/convert.py` (589 lines)

**Why fragile:** This module imports from 15+ internal modules (fetch_tdoc, fetch_spec, hybrid_server, profiles, database, whatthespec, normalization, etc.) and handles conversion for both TDocs and Specs with different code paths. Changes in any dependency ripple through here.

**Safe modification:** Before modifying, run the full test suite focused on extraction:
```bash
uv run pytest tests/convert_lo/ tests/test_checkout.py -v
```

**Test coverage:** Convert-lo tests exist (`tests/convert_lo/`) but may not cover the spec conversion path or metadata enrichment logic.

### `cli/_workspace_commands.py` — God Command File

**Files:** `src/tdoc_crawler/cli/_workspace_commands.py` (534 lines)

**Why fragile:** Contains 6 Typer commands (`create`, `list`, `activate`, `deactivate`, `delete`, `members`, `process`, `add`) plus helper functions in a single file. Any change risks breaking unrelated commands.

**Safe modification:** Split one command at a time into submodules. Run `uv run pytest tests/test_workspaces.py -v` after each split.

**Test coverage:** `tests/test_workspaces.py` covers workspace CRUD but likely does not exercise the full `process` pipeline.

### `config/workspace_registry.py` — JSON File as Database

**Files:** `src/tdoc_crawler/config/workspace_registry.py` (461 lines)

**Why fragile:** Workspace metadata is stored in a single JSON file (`workspaces.json`). Concurrent access from multiple CLI invocations can corrupt the file. No file locking, no atomic writes.

**Safe modification:** Ensure `_save_registry()` always uses atomic write (write to temp file, then rename).

**Fix approach:** Implement atomic file writes using `tempfile.NamedTemporaryFile` + `os.replace()`. Consider migrating to SQLite for the registry.

### `tdocs/sources/doclist.py` — Heavy Exception Swallowing

**Files:** `src/tdoc_crawler/tdocs/sources/doclist.py` (372 lines)

**Why fragile:** 8 bare `except Exception` blocks that catch any error and return `None`. If a parsing bug is introduced, it silently fails instead of raising.

**Safe modification:** Add specific exception types. At minimum, log the full traceback with `logger.exception()` instead of just the message.

### `http_client/session.py` — hishel Internal API Dependency

**Files:** `src/tdoc_crawler/http_client/session.py` (348 lines)

**Why fragile:** Imports from `hishel._core._headers` and `hishel._core.models` — these are internal (underscore-prefixed) hishel modules, not part of the public API. Any hishel upgrade can break these imports.

**Safe modification:** Pin hishel version tightly. Consider wrapping hishel access behind an adapter that isolates the internal imports.

**Fix approach:** Submit upstream PR to hishel to expose the needed types from the public API, or vendor the minimal necessary types.

## Scaling Limits

### SQLite for Multi-User / Concurrent Access

**Current capacity:** Single-user CLI tool with SQLite backend.

**Limit:** SQLite does not handle concurrent writes well. If multiple CLI invocations (`tdoc-crawler crawl` simultaneously), one will get `database is locked` errors.

**Scaling path:** The application is currently designed as a single-user CLI. If multi-user access is needed, migrate to PostgreSQL or add WAL mode + busy timeout to SQLite. The Oxyde ORM abstracts the backend, making migration feasible.

### Workspace Registry JSON File

**Current capacity:** Single JSON file for all workspace metadata.

**Limit:** With hundreds of workspaces each containing hundreds of members, the JSON file can grow to multiple megabytes. Loading and saving the entire file for every add/remove operation becomes slow.

**Scaling path:** Migrate workspace members to SQLite (same database as crawl metadata) or use a per-workspace JSON file instead of a single global file.

### In-Memory TDoc Collection During Crawl

**Files:** `src/tdoc_crawler/tdocs/operations/crawl.py:74`

**Limit:** All crawled TDoc metadata is accumulated in a `list[TDocMetadata]` before bulk upsert. With `limit_tdocs=10000`, this represents ~100MB of in-memory data.

**Scaling path:** Stream TDocs to the database in batches (e.g., 500 at a time) rather than collecting all before inserting.

## Dependencies at Risk

### hishel Internal API Usage

**Package:** `hishel>=1.1.8`

**Risk:** `src/tdoc_crawler/http_client/session.py` imports from `hishel._core._headers` and `hishel._core.models` — private modules that can change without notice.

**Impact:** A hishel minor version update could break the entire HTTP caching layer, halting all crawl operations.

**Migration plan:** Pin to exact hishel version in `pyproject.toml`. Long-term: abstract the cache adapter behind a stable interface or vendor the needed conversion utilities.

### niquests (Alternative HTTP Library)

**Package:** `niquests>=3.18.4`

**Risk:** The project uses `niquests` instead of the more standard `requests` library. While niquests is API-compatible, it has a smaller community and may lag in security patches.

**Impact:** If niquests development slows, the project may need to migrate back to `requests` or `httpx`.

**Migration plan:** The codebase wraps niquests through `http_client/session.py`. The adapter pattern makes migration feasible if needed.

### opendataloader-pdf Hybrid Mode Dependency

**Package:** `opendataloader-pdf[hybrid]>=2.2.0`

**Risk:** The hybrid server (Java-based) is started as a subprocess (`src/tdoc_crawler/extraction/hybrid_server.py`). Server failures trigger automatic restarts, but this adds complexity and external process management.

**Impact:** If the hybrid server cannot start (missing Java, port conflict, incompatible version), document extraction falls back to the native pipeline only, producing lower-quality output.

**Migration plan:** The fallback mechanism helps. Consider adding a health check that validates the hybrid server at startup.

## Missing Critical Features

### No Retry Logic for Document Download Failures

**Problem:** `src/tdoc_crawler/tdocs/operations/checkout.py` downloads TDoc files but does not implement retry with backoff for transient network failures.

**Blocks:** Bulk document download in unstable network conditions can produce many "file not found" errors that would succeed on retry.

**Fix approach:** Add exponential backoff retry to `download_to_file()` in `http_client/session.py`, or use the existing `HttpConfig.max_retries` setting consistently.

### No Progress Persistence for Workspace Processing

**Problem:** If `workspace process` is interrupted (Ctrl+C, crash, power loss), there is no way to resume. All processing starts from scratch.

**Blocks:** Large workspaces with hundreds of documents. An interruption at 95% means full restart.

**Fix approach:** Record per-member processing state in the workspace registry. On resume, skip members whose artifacts already exist and match the requested profile level (the `--skip-existing` flag partially addresses this but requires manual opt-in).

### No Dry-Run for Crawl Operations

**Problem:** There is no way to preview what a crawl command will do before executing it. `--dry-run` exists for workspace add but not for crawl.

**Blocks:** Safe exploration of crawl filters. Users must commit to a full crawl to see what would be collected.

**Fix approach:** Add `--dry-run` to `crawl` and `crawl-meetings` commands that shows meeting count, estimated TDoc count, and filter summary without performing downloads.

## Test Coverage Gaps

### Extraction Pipeline

**What's not tested:** `extraction/convert.py` — `convert_for_wiki()`, `_run_opendataloader()`, `_ensure_converted()`, metadata enrichment, spec conversion path.

**Files:** `src/tdoc_crawler/extraction/convert.py`

**Risk:** Changes to the conversion pipeline can break workspace processing silently. The hybrid server restart logic is particularly hard to test and verify manually.

**Priority:** High

### Workspace Processing End-to-End

**What's not tested:** Full `workspace process` pipeline from member list → fetch → PDF conversion → OpenDataLoader → Wiki output.

**Files:** `src/tdoc_crawler/cli/_workspace_commands.py`, `src/tdoc_crawler/extraction/convert.py`

**Risk:** Integration failures between components may not surface until runtime. The sequential processing loop has no unit test coverage for error handling paths.

**Priority:** Medium

### Database Spec Operations

**What's not tested:** `database/specs.py` — `crawl_specs()`, version resolution from multiple sources, bulk upsert logic.

**Files:** `src/tdoc_crawler/database/specs.py` (494 lines)

**Risk:** Spec crawling is complex (multiple sources, version deduplication). Breaking changes may not be caught.

**Priority:** Medium

### Portal Authentication Edge Cases

**What's not tested:** Session expiration handling, credential rotation, concurrent portal sessions, non-JSON login responses.

**Files:** `src/tdoc_crawler/clients/portal.py`

**Risk:** Portal authentication failures manifest as cryptic parsing errors rather than clear auth failure messages.

**Priority:** Low (covered by integration tests when credentials are available)

---

*Concerns audit: 2026-05-03*
