# Phase 3: Quality Gate Framework - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 introduces deterministic extraction quality gates and a status lifecycle for each processed document.

In scope:

- deterministic gate evaluation after extraction
- extraction status assignment (`ok`, `partial`, `failed`)
- explicit reason-code reporting for gate outcomes
- downstream policy handling so consumers can avoid treating degraded extraction as fully valid

Out of scope:

- embedding/retrieval workflows
- non-deterministic AI scoring as the primary gate decision source

</domain>

<decisions>
## Implementation Decisions

### Gate Rule Set and Thresholds

- **D-01:** Use deterministic structural checks as the core gate engine.
- **D-02:** Initial gate checks must include:
  - artifact presence checks (required canonical/manifest outputs exist)
  - metadata completeness checks (document/page/element contract fields)
  - stable ID and provenance integrity checks for tables/figures/equations
  - page coverage consistency checks between extracted artifacts and recorded page metadata

### Reason-Code Taxonomy

- **D-03:** Gate outcomes must emit stable machine-readable reason codes.
- **D-04:** Reason codes should be represented as an enum-like fixed key set (for example: `missing_artifact`, `missing_metadata`, `invalid_provenance`, `coverage_mismatch`), with optional human-readable message fields.

### Downstream Enforcement Policy

- **D-05:** Default consumer policy is:
  - `ok` = allow
  - `partial` = allow with warning
  - `failed` = block by default
- **D-06:** Provide an explicit override path for blocked workflows (one-off flag/config) rather than implicit fallback.

### Quality Report Persistence Contract

- **D-07:** Persist a per-document quality report as JSON next to existing output contracts under `.ai`.
- **D-08:** Use deterministic report naming based on document stem and include status, reason codes, and gate metrics summary fields.

### Operator Control Surface

- **D-09:** Add a small, explicit quality policy surface with three modes: `strict`, `balanced`, `permissive`.
- **D-10:** Support a one-off override flag for execution paths that need to bypass a `failed` default block intentionally.

### the agent's Discretion

- exact numerical thresholds for any ratio-based checks
- exact reason-code key naming (while preserving fixed/stable taxonomy)
- exact quality report filename suffix convention
- exact CLI/config flag names for policy and override

</decisions>

<specifics>
## Specific Ideas

- Keep gate evaluation deterministic and auditable first; AI enrichment can remain supplementary and must not replace deterministic pass/fail logic.
- Make quality outcomes visible in both persisted report files and extraction metadata fields so downstream systems can enforce policy without parsing logs.
- Preserve backward compatibility for existing extraction APIs by adding fields additively.

</specifics>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and requirement scope

- `.planning/ROADMAP.md` — Phase 3 goal, requirements, and success criteria
- `.planning/REQUIREMENTS.md` — `QUAL-01`, `QUAL-02`, `QUAL-03` definitions
- `.planning/PROJECT.md` — extraction-first milestone constraints and non-goals

### Existing extraction output contracts

- `packages/3gpp-ai/threegpp_ai/models.py` — canonical extraction/result data models
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` — canonical JSON, manifest persistence, contract helpers
- `packages/3gpp-ai/threegpp_ai/operations/extraction.py` — extraction orchestration and metadata merge/writes
- `packages/3gpp-ai/threegpp_ai/operations/metrics.py` — operation metrics primitives and tracker model

### Downstream consumer touchpoints

- `packages/3gpp-ai/threegpp_ai/operations/summarize.py` — consumer behavior impacted by quality status policy
- `packages/3gpp-ai/threegpp_ai/operations/convert.py` — TDoc extraction wrapper metadata flow

### Test baselines

- `tests/ai/test_ai_extraction_artifacts.py` — output contract and manifest behavior tests
- `tests/ai/test_extraction_profiles.py` — extraction metadata and cached-path behavior tests
- `tests/ai/test_operations_metrics.py` — metrics behavior guardrails

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `threegpp_ai.operations.extraction_result.persist_output_contracts(...)` already centralizes output contract persistence and can be extended to include quality-report writing.
- `threegpp_ai.operations.metrics.MetricsTracker` provides a reusable structure for capturing gate timing and outcome telemetry.

### Established Patterns

- deterministic filename/persistence patterns are already used for canonical and manifest artifacts in `.ai` output directories.
- extraction metadata is merged and propagated as additive fields across fresh and cached paths.

### Integration Points

- post-extraction completion path in `extract_document_structured(...)` is the natural insertion point for gate evaluation and quality report persistence.
- summarize and other consumers can enforce status policy via persisted status/reason fields in extraction metadata and report JSON.

</code_context>

<deferred>
## Deferred Ideas

- probabilistic or model-scored quality gates as the primary decision source
- richer remediation workflows beyond warn/block policy (for example automatic re-extraction strategies)

</deferred>

---
*Phase: 03-quality-gate-framework*
*Context gathered: 2026-04-18*
