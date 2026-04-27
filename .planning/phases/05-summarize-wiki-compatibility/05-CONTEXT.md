# Phase 5 Context: Summarize + Wiki Compatibility

## Source Requirements

- SUMM-01: Integrate structured extraction output (tables, figures, equations) into summarize prompt context
- SUMM-02: Surface provenance references (element IDs, page numbers) within summary sections
- SUMM-03: Implement structured-first fallback policy (canonical artifacts preferred, markdown as last resort)
- WIKI-01: Add mode selector CLI flag to switch output shape between standard and wiki-ready

## Decisions

### D-01: Structured Context Depth in Prompt Assembly
**Decision:** Balanced structured context.  
Include key metadata summaries plus truncated representative elements (tables, equations, figures) in the summarize prompt. Do not include full raw content of every element. Prioritize high-signal elements (first few tables, equations with normalized text, figures with captions) within a token budget.  
**Rationale:** Full inclusion would explode prompt size with no proportional quality gain; markdown-only provides no structured signal. Balanced gives LLM meaningful structural awareness.

### D-02: Structured-vs-Markdown Fallback Policy
**Decision:** Structured-first; fallback to markdown only if canonical extraction artifacts are missing or corrupt.  
**Rationale:** Canonical structured artifacts are the ground truth; markdown is a degraded view. Fallback should be transparent and logged.

### D-03: Summary Artifact Shape
**Decision:** Preserve current `SummarizeResult` response shape. Add light metadata references (element IDs, page numbers) as optional fields or inline within existing section text. No new separate wiki artifact file.  
**Rationale:** Avoids breaking existing callers; wiki-ready output is a rendering concern, not a schema concern.

### D-04: Provenance / Citation Granularity
**Decision:** Inline citations to element IDs and page numbers within relevant summary sections.  
Example: "The handover procedure is described in Table T-03 (p. 12) and Equation EQ-07 (p. 14)."  
**Rationale:** Consumers (wiki editors, reviewers) can directly navigate to source material.

### D-05: CLI Surface for Output Shape
**Decision:** Add a mode selector flag for output shape (standard vs wiki-ready).  
**Rationale:** Wiki-ready formatting (section headers, citation anchors) is useful for downstream tooling but not appropriate for all callers.

## Deferred Ideas

- Full embedding-based structured context retrieval (RAG over extracted elements) — out of scope for Phase 5
- Separate `WikiExtractionResult` artifact file — D-03 explicitly excludes this
- Auto-generation of wiki page templates — future phase

## Agent's Discretion

The following are left to the planner/executor:
- Exact structured context assembly logic (how to serialize truncated elements for the prompt)
- Exact citation inline format (e.g., `[Table T-03, p.12]` vs `(Table T-03, p. 12)`)
- Exact CLI flag name for the mode selector (e.g., `--output-mode`, `--wiki`, `--format`)
- Fallback corruption detection threshold (what counts as "corrupt" for D-02)
- Token budget strategy for structured context inclusion (hard cap, soft cap, priority queue)

## Canonical References

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/PROJECT.md`
- `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- `packages/3gpp-ai/threegpp_ai/models.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/docs/PIPELINE.md`
- `tests/ai/test_operations_metrics.py`
