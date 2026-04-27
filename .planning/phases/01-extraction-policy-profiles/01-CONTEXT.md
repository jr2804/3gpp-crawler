# Phase 1: Extraction Policy Profiles - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement profile policy for extraction routing and configurability in `3gpp-ai`:

- auto/deterministic profile selection for `default`, `balanced`, `optimum`
- explicit user override through CLI/config
- `custom` profile with per-step extraction toggles/configuration
- persist effective profile/config in extraction metadata

Phase 1 does not include embeddings/RAG/query orchestration.
</domain>

<decisions>
## Implementation Decisions

### Locked Decisions

- Use profile names exactly: `default`, `balanced`, `optimum`, `custom`.
- Keep milestone strictly extraction-only. No embedding/RAG work.
- Output interface remains Markdown + JSON.
- Structured extraction artifacts must stay compatible with summarize and future wiki compilation.

### the agent's Discretion

- Exact complexity scoring heuristic for deterministic auto-routing.
- Exact field names for custom profile toggles (must be explicit and testable).
- Which command path(s) expose profile override first (workspace process + extraction API).
</decisions>

<canonical_refs>

## Canonical References

### Current milestone scope

- `.planning/ROADMAP.md` — Phase 1 goal, requirements, success criteria
- `.planning/REQUIREMENTS.md` — EXTR-01..EXTR-04 requirement language
- `.planning/PROJECT.md` — milestone constraints and non-goals

### Existing extraction implementation

- `packages/3gpp-ai/threegpp_ai/operations/extraction.py` — current conversion/pipeline orchestration
- `packages/3gpp-ai/threegpp_ai/config.py` — AI config model and env aliases
- `packages/3gpp-ai/threegpp_ai/args.py` — CLI option registry
- `packages/3gpp-ai/threegpp_ai/cli.py` — workspace process command entry point
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py` — consumer of extraction API

### Existing tests and patterns

- `tests/ai/test_extraction_elements.py` — extraction result behavior and processor integration
- `tests/ai/test_ai_extraction_artifacts.py` — artifact persistence behavior
</canonical_refs>

<specifics>
## Specific Ideas

- Keep auto-routing deterministic and auditable (documented complexity signals, no stochastic model choice).
- Persist extraction profile and effective runtime config in extraction metadata for later quality/debug analysis.
- Add profile override at CLI level to support user-controlled runs.
</specifics>

<deferred>
## Deferred Ideas

- Any vector indexing, retrieval orchestration, or wiki compiler execution.
- Weekly ecosystem research automation (tracked as future requirement RSCH-01).
</deferred>

---
*Phase: 01-extraction-policy-profiles*
*Context gathered: 2026-04-17*
