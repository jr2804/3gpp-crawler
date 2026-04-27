# Phase 4: Structured Element Fidelity - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 improves extraction fidelity and traceability for tables, figures, and equations in technical PDFs.

In scope:

- strengthen table payload fidelity for reliable downstream reuse
- strengthen figure payload fidelity with robust metadata handling
- strengthen equation payload fidelity with normalized structure
- preserve stable IDs and provenance semantics compatible with prior canonical contracts

Out of scope:

- embedding/retrieval workflows
- schema-breaking rewrites of existing Phase 1-3 contracts

</domain>

<decisions>
## Implementation Decisions

### Table Payload Depth

- **D-01:** Use a hybrid table payload contract.
- **D-02:** Core table fields remain always-on (`cells`, `row_count`, `column_count`, optional `markdown`, page provenance), while cell-level metadata is optional and included when extractor data is available.

### Provenance Granularity

- **D-03:** Provenance must include page plus normalized source-anchor IDs.
- **D-04:** Do not require geometry/bounding boxes in Phase 4 contracts.

### Figure Contract Strictness

- **D-05:** Allow partial figure records.
- **D-06:** Missing figure fields are represented explicitly as null with reason/diagnostic flags rather than dropping the figure record.

### Equation Normalization Shape

- **D-07:** Extend equation payload with normalized fields: `normalized_text`, `equation_type`, and inline/display mode indicator.
- **D-08:** Keep current fields (`latex`, `raw_text`, stable IDs, page mapping) additive and backward compatible.

### Compatibility Policy

- **D-09:** Phase 4 schema evolution is additive-only.
- **D-10:** Existing field names from prior phases must not be renamed or removed.

### the agent's Discretion

- exact field names for new optional cell-level metadata and figure reason flags
- exact normalized source-anchor ID format
- exact enum/key naming for equation type and display mode values
- exact fallback behavior when normalized equation metadata cannot be derived

</decisions>

<specifics>
## Specific Ideas

- Favor preservation over omission: incomplete figure records are still useful when explicitly marked degraded.
- Keep canonical contracts deterministic and traceable, with stable IDs and machine-readable provenance anchors.
- Add fidelity depth in a way that does not break existing summarize and extraction consumers.

</specifics>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and requirement scope

- `.planning/ROADMAP.md` — Phase 4 goal, requirements, and success criteria
- `.planning/REQUIREMENTS.md` — `STRC-01`, `STRC-02`, `STRC-03` definitions
- `.planning/PROJECT.md` — extraction-first milestone constraints and non-goals

### Existing extraction contracts and persistence

- `packages/3gpp-ai/threegpp_ai/models.py` — canonical extraction models and status contracts
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` — canonical contract building and artifact persistence
- `packages/3gpp-ai/threegpp_ai/operations/extraction.py` — extraction orchestration and metadata propagation
- `packages/3gpp-ai/threegpp_ai/operations/convert.py` — TDoc wrapper metadata handoff

### Existing tests and contract guardrails

- `tests/ai/test_ai_extraction_artifacts.py` — artifact persistence and canonical contract behavior
- `tests/ai/test_extraction_profiles.py` — extraction metadata compatibility checks
- `tests/ai/test_operations_metrics.py` — summarize/extraction behavior guardrails

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `build_structured_extraction_result(...)` in `operations/extraction_result.py` already centralizes normalized structured payload creation.
- `persist_output_contracts(...)` in `operations/extraction_result.py` already centralizes deterministic contract persistence and metadata updates.

### Established Patterns

- Artifact persistence uses deterministic naming under `.ai` and contract-first JSON outputs.
- Metadata/schema evolution in phases 1-3 has been additive with backward compatibility.

### Integration Points

- Table/figure/equation fidelity upgrades should be wired through extraction result construction in `operations/extraction_result.py`.
- Quality/status/report behavior from Phase 3 in `persist_output_contracts(...)` must remain compatible with any new STRC fields.

</code_context>

<deferred>
## Deferred Ideas

- Geometry/bounding-box provenance as a required contract field (deferred beyond Phase 4)
- Schema version split (`v2` parallel contracts) for breaking changes (not needed under additive-only policy)

</deferred>

---
*Phase: 04-structured-element-fidelity*
*Context gathered: 2026-04-18*
