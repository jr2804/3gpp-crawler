# Phase 3 Research: Quality Gate Framework

**Phase:** 3 - Quality Gate Framework
**Date:** 2026-04-18

## Objective

Define implementation strategy for deterministic extraction quality gates and status lifecycle (`ok|partial|failed`) with explicit reason-code reporting and downstream policy handling.

## Findings

### Current baseline

- Canonical output contracts are already persisted per document (`.canonical.json` and `_manifest.json`) in `operations/extraction_result.py`.
- Extraction metadata already carries additive status-related fields and deterministic config hash plumbing from Phase 2.
- `extract_document_structured(...)` in `operations/extraction.py` is the best insertion point for post-extraction deterministic gate evaluation on both fresh and cached paths.
- Existing `MetricsTracker` in `operations/metrics.py` can be reused for gate timing/outcome telemetry without introducing new infrastructure.
- Summarize flow in `operations/summarize.py` currently does not apply status policy and should be extended for QUAL-03.

### Gaps against requirements

- QUAL-01: no deterministic gate engine currently assigns final status from rule checks.
- QUAL-02: no persisted quality report with explicit reason codes and gate metrics exists yet.
- QUAL-03: no downstream consumer policy layer currently enforces warn/block behavior for partial/failed extraction quality.

### Reusable assets and patterns

- Deterministic artifact persistence and naming conventions already exist in `extraction_result.py` and should be reused for quality report files.
- Additive metadata update pattern in extraction flow should be preserved for backward compatibility.
- Test coverage foundations exist in:
  - `tests/ai/test_ai_extraction_artifacts.py`
  - `tests/ai/test_extraction_profiles.py`
  - `tests/ai/test_operations_metrics.py`

## Recommended implementation sequence

1. Introduce deterministic quality gate domain model and reason-code taxonomy.
2. Implement gate evaluator and quality report persistence (including status + reason codes + metrics summary).
3. Wire evaluation into extraction completion paths (fresh and cache-aware) with additive metadata updates.
4. Add policy surface (`strict|balanced|permissive` + explicit override) in config/CLI.
5. Enforce downstream consumer policy in summarize flow and add warn/block tests.

## Recommended file targets

- `packages/3gpp-ai/threegpp_ai/models.py`
- `packages/3gpp-ai/threegpp_ai/config.py`
- `packages/3gpp-ai/threegpp_ai/args.py`
- `packages/3gpp-ai/threegpp_ai/cli.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- `tests/ai/test_ai_extraction_artifacts.py`
- `tests/ai/test_extraction_profiles.py`
- `tests/ai/test_operations_metrics.py`

## Risks and mitigations

- Risk: gate thresholds too strict for currently valid but sparse documents.
  - Mitigation: include policy modes and deterministic thresholds with tests for each mode.
- Risk: cached-path behavior diverges from fresh extraction behavior.
  - Mitigation: run gate evaluation on both paths and assert parity in tests.
- Risk: downstream blocking creates regressions for existing summarize workflows.
  - Mitigation: default warn policy for `partial`, explicit override for `failed`, and backward-compatible fallback where policy permits.

## Phase requirement mapping

- `QUAL-01`: deterministic gate evaluation + status assignment
- `QUAL-02`: quality report with reason codes and gate metrics
- `QUAL-03`: downstream policy handling for partial/failed outputs
