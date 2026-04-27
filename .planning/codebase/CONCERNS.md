# Codebase Concerns

**Analysis Date:** 2026-04-27

## Tech Debt

**Monolithic CLI/operation modules:**

- Issue: Large command modules combine orchestration, I/O resolution, conversion, extraction, and error normalization in single files, increasing change risk and review overhead.
- Files: `packages/3gpp-ai/threegpp_ai/cli.py`, `src/tdoc_crawler/cli/crawl.py`, `src/tdoc_crawler/tdocs/sources/doclist.py`, `src/tdoc_crawler/database/specs.py`
- Impact: Small feature changes can create behavioral regressions across unrelated command paths.
- Fix approach: Split command handlers from operational services, then isolate filesystem/network adapters behind small interfaces.

**Version/test-matrix drift:**

- Issue: Runtime requirement is Python >=3.14, while tox still targets py39-py313.
- Files: `pyproject.toml`, `tox.ini`
- Impact: CI intent is ambiguous; some matrix entries cannot represent supported runtime behavior.
- Fix approach: Align tox envlist to supported versions and add explicit compatibility policy comments.

**Broad exception handling footprint:**

- Issue: Repository currently contains many `except Exception` handlers in control and integration code (41 matches measured across `src/`, `packages/`, `tests/`).
- Files: `src/tdoc_crawler/database/base.py`, `src/tdoc_crawler/database/specs.py`, `src/tdoc_crawler/tdocs/operations/crawl.py`, `packages/3gpp-ai/threegpp_ai/cli.py`
- Impact: Root causes are flattened into generic errors; debugging and observability degrade under failures.
- Fix approach: Narrow catches to expected exception classes and standardize structured error payloads.

## Known Bugs

**Pool executor import guard catches only `ImportError`:**

- Symptoms: Fallback logic is written as `except ImportError, AttributeError:` and does not actually catch `AttributeError`.
- Files: `packages/pool_executors/pool_executors/factory.py`
- Trigger: Environments where `InterpreterPoolExecutor` path raises attribute-level access issues.
- Workaround: Replace with tuple form `except (ImportError, AttributeError):`.

**AI workspace tests intentionally misaligned with implementation:**

- Symptoms: Multiple tests are skipped with explicit API-mismatch reason.
- Files: `tests/ai/test_ai_workspaces.py`
- Trigger: Running AI workspace test module.
- Workaround: None in tests themselves; update tests to current workspace API contract.

## Security Considerations

**Desktop file launching via subprocess/os shell integration:**

- Risk: Opening user-provided paths through OS launch mechanisms can execute unintended handlers if upstream validation is weak.
- Files: `src/tdoc_crawler/cli/utils.py`
- Current mitigation: Uses argument lists (not shell strings) and checks file existence before launch.
- Recommendations: Add explicit allowlist for launchable extensions and safer path provenance checks in calling commands.

**Hybrid server lifecycle relies on external binary trust:**

- Risk: Runtime launches `opendataloader-pdf-hybrid` from PATH; compromised PATH or binary replacement can alter behavior.
- Files: `packages/3gpp-ai/threegpp_ai/operations/hybrid_server.py`
- Current mitigation: Health checks and process status checks.
- Recommendations: Resolve binary from configured absolute path and verify version/signature on startup.

## Performance Bottlenecks

**Repeated recursive file scanning during workspace processing:**

- Problem: `_resolve_process_file()` performs `rglob` per extension and can be invoked repeatedly per member.
- Files: `packages/3gpp-ai/threegpp_ai/cli.py`
- Cause: Repeated cold directory traversal in conversion/extraction loops.
- Improvement path: Cache candidate files per workspace member and reuse resolved paths across pipeline stages.

**DataFrame row iteration for large meeting doclists:**

- Problem: Excel parse path iterates row-by-row with per-row exception handling and dynamic column probing.
- Files: `src/tdoc_crawler/tdocs/sources/doclist.py`
- Cause: Python-level row processing with many fallback branches.
- Improvement path: Pre-normalize column map once and reduce per-row branching; add lightweight vectorized prefilters.

## Fragile Areas

**Crawl orchestration stop-conditions and cancellation behavior:**

- Files: `src/tdoc_crawler/tdocs/operations/crawl.py`
- Why fragile: Limit, target depletion, timeout, future cancellation, and parse failures intersect in one control loop.
- Safe modification: Add targeted tests for each early-stop reason and one combined-case test before changing loop logic.
- Test coverage: No dedicated failure-matrix tests for all stop-condition permutations.

**Spec metadata merge and source-difference comparison:**

- Files: `src/tdoc_crawler/database/specs.py`
- Why fragile: Source payload can be `str|dict` with JSON decode fallback and normalization rules in-line.
- Safe modification: Extract payload normalization into pure helper functions with focused unit tests.
- Test coverage: Limited explicit tests for malformed metadata payload structures.

## Scaling Limits

**Sequential workspace member processing path:**

- Current capacity: Processes members one-by-one in `_process_workspace_members`.
- Limit: Throughput degrades linearly as workspace size grows.
- Scaling path: Introduce bounded parallel extraction workers with backpressure and per-member retry policy.

**In-memory accumulation during crawl:**

- Current capacity: Collected TDocs are buffered before bulk upsert.
- Limit: Memory pressure increases with large meeting sets and broad crawl windows.
- Scaling path: Stream batched upserts and periodically flush intermediate results.

## Dependencies at Risk

**Git-sourced `doc2txt` dependency:**

- Risk: Dependency is pinned to a Git source rather than a stable release channel.
- Impact: Reproducibility and supply-chain stability can change with upstream repo state.
- Migration plan: Pin immutable commit hash and maintain lockfile validation in CI.

**External hybrid extraction binary:**

- Risk: `opendataloader-pdf-hybrid` availability/version directly controls AI extraction behavior.
- Impact: Missing or incompatible binary causes feature degradation or skipped processing.
- Migration plan: Add startup preflight checks and explicit compatibility matrix in package docs.

## Missing Critical Features

**Graph integration path not implemented but anticipated by tests/docs:**

- Problem: Graph build/insert flows are asserted as future behavior and not available yet.
- Blocks: End-to-end AI workspace graph enrichment and related resilience tests.

**Contract-level error taxonomy across CLI boundaries:**

- Problem: Many command paths still return mixed sentinel values (`None`, `[]`, `{}`); 99 sentinel returns matched across `src/` and `packages/`.
- Blocks: Reliable machine-consumable automation and consistent error handling in higher-level orchestration.

## Test Coverage Gaps

**AI test suite is excluded from default collection:**

- What's not tested: Routine runs of `tests/ai/` in core pytest execution.
- Files: `tests/conftest.py`, `tests/ai/test_ai_workspaces.py`
- Risk: AI-specific regressions can pass unnoticed in normal test runs.
- Priority: High

**Skipped tests document unimplemented graph and workspace behaviors:**

- What's not tested: Intended LightRAG error handling and aligned workspace API behavior.
- Files: `tests/test_graph_errors.py`, `tests/ai/test_ai_workspaces.py`
- Risk: Feature contracts remain implicit and may drift from implementation.
- Priority: Medium

**Network-bound auth and portal flows are conditionally skipped:**

- What's not tested: Real portal authentication and external network paths in constrained environments.
- Files: `tests/test_portal_auth.py`, `tests/test_http_client.py`
- Risk: Production failures may emerge only under live conditions.
- Priority: Medium

---

*Concerns audit: 2026-04-27*
