# Phase 2: Canonical Output Contracts - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning
**Source:** Auto context from roadmap and requirements (`/gsd-plan-phase 2 --auto`)

<domain>
## Phase Boundary

Phase 2 delivers a stable output contract for extraction artifacts:

- every extraction run emits both Markdown and canonical JSON artifacts
- canonical JSON must include document-level, page-level, and element-level metadata
- table/figure/equation elements must keep stable IDs and page provenance
- a manifest file must inventory generated artifacts and extraction status

Phase 2 must remain extraction-only and must not reintroduce embedding or retrieval paths.
</domain>

<decisions>
## Implementation Decisions

### Locked Decisions

- Canonical JSON is the machine source of truth; Markdown remains the human-readable projection.
- All four Phase 2 requirements (`OUTP-01`..`OUTP-04`) are mandatory in this phase.
- Stable element identifiers and provenance fields are required for future summarize/wiki compatibility.
- Existing extraction API contracts should remain backward compatible for current CLI/process flows.

### the agent's Discretion

- Exact JSON schema layout and helper function boundaries.
- Manifest file naming and field naming choices.
- Whether to add schema fields in existing models or introduce dedicated contract models.
</decisions>

<canonical_refs>

## Canonical References

### Planning and requirements

- `.planning/ROADMAP.md` — phase goal, requirements, and success criteria
- `.planning/REQUIREMENTS.md` — requirement definitions `OUTP-01`..`OUTP-04`
- `.planning/PROJECT.md` — milestone scope and non-goals

### Current extraction implementation

- `packages/3gpp-ai/threegpp_ai/models.py` — canonical extraction models
- `packages/3gpp-ai/threegpp_ai/operations/extraction.py` — extraction orchestration and metadata merge
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` — artifact persistence/readback helpers
- `packages/3gpp-ai/threegpp_ai/operations/convert.py` — conversion entry points that feed extraction

### Existing tests and behavior constraints

- `tests/ai/test_ai_extraction_artifacts.py` — artifact persistence and cache reconstruction
- `tests/ai/test_extraction_profiles.py` — metadata persistence expectations from Phase 1
- `tests/ai/test_operations_metrics.py` — processing metrics behavior guardrails
</canonical_refs>

<specifics>
## Specific Ideas

- keep per-artifact JSON files for traceability, but add a deterministic manifest index for downstream consumers
- persist page metadata even when specific artifact types are absent on some pages
- include extraction status and profile/config snapshot hash in manifest entries
</specifics>

<deferred>
## Deferred Ideas

- quality gates and reason-code policy (`QUAL-*`) belong to Phase 3
- structured fidelity improvements (`STRC-*`) belong to Phase 4
- summarize contract changes (`SUMM-*`, `WIKI-*`) belong to Phase 5
</deferred>

---
*Phase: 02-canonical-output-contracts*
*Context gathered: 2026-04-18 via auto planning path*
