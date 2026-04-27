# Phase 5 Research: Summarize + Wiki Compatibility

## Scope

Phase 5 goal from roadmap: ensure summarize consumes structured extraction and stays future-ready for wiki compile workflows.

Requirements in scope:

- SUMM-01
- SUMM-02
- SUMM-03
- WIKI-01

Context lock-ins from 05-CONTEXT.md:

- D-01 balanced structured context depth in prompt assembly
- D-02 structured-first fallback policy
- D-03 preserve SummarizeResult response shape
- D-04 inline provenance citations with element IDs and page numbers
- D-05 add CLI mode selector for output shape

## Current Code Reality

### summarize path

- `threegpp_ai/operations/summarize.py::summarize_tdoc` already uses `extract_tdoc_structured` and quality policy checks.
- Prompt input currently uses only `extraction.content` (markdown-like text).
- No structured table/figure/equation context is currently serialized into prompt text.
- Metadata returned in `SummarizeResult.metadata` currently includes quality status fields but no structured provenance summary.

### extraction contracts already available

- `StructuredExtractionResult` already provides `tables`, `figures`, `equations` with stable `element_id` and `page_number`.
- Table/figure/equation additive fidelity fields from phase 4 are present, including `source_anchor_id`, normalized equation fields, and partial diagnostics.

### CLI surface

- `threegpp_ai/cli.py::ai_summarize` forwards summarize arguments and prints plain text summary.
- `threegpp_ai/args.py` has summarize options for words/force/quality policy only.
- No output-shape selector (standard/wiki-ready) exists today.

## Recommended Implementation Direction

### 1) Structured-first prompt assembly (SUMM-01, SUMM-02, SUMM-03)

Implement a deterministic structured context builder in summarize operations:

- Build concise sections for tables/equations/figures from canonical artifacts.
- Include truncated high-signal entries only (D-01).
- Keep hard character budget for structured context and degrade gracefully by priority order (equations with normalized_text, then tables with dimensions/caption, then figures with caption/description).
- If canonical artifacts are missing or malformed, log warning and use markdown-only prompt source (D-02).

### 2) Provenance-aware summary guidance (SUMM-02, WIKI-01)

Inject explicit citation guidance into prompt templates:

- Ask model to reference element IDs and page numbers when claiming technical details.
- Reuse existing canonical IDs, no new ID system.
- Keep citations inline in generated text (D-04).

### 3) Preserve API shape while extending metadata lightly (D-03)

Do not add new top-level fields to `SummarizeResult`.
Allowed additions:

- Optional metadata keys under existing `metadata` dict (for example, selected artifact counts, fallback mode indicator).

### 4) CLI output mode switch (WIKI-01, D-05)

Add summarize option to select output mode:

- `standard`: existing behavior
- `wiki`: same summary payload, rendered with wiki-friendly section framing and citation note
No separate artifact file.

## Risks and Mitigations

1. Risk: prompt bloat from structured artifacts

- Mitigation: strict structured context budget and deterministic truncation ordering.

1. Risk: malformed canonical artifacts crash summarize

- Mitigation: treat malformed structured segments as fallback trigger to markdown-only path with warning.

1. Risk: wiki mode introduces schema drift

- Mitigation: wiki mode must be pure rendering in CLI layer; `SummarizeResult` model unchanged.

## Test Strategy

Targeted tests (fast, deterministic):

- Structured context builder includes IDs/page provenance and respects truncation budget.
- Summarize falls back to markdown-only when structured payload is missing/corrupt.
- CLI summarize help exposes mode flag.
- Wiki mode output formatting differs from standard while using same summarize operation return type.

Recommended commands:

- `uv run pytest tests/ai/test_operations_metrics.py -v`
- `uv run pytest tests/ai/test_cli_aggregator.py -v`
- `uv run pytest tests/ai/test_summarize_structured_context.py -v`

## Decision Log

- Use existing extraction contracts and additive metadata from phase 4; no schema redesign.
- Keep wiki compatibility as output/rendering concern in phase 5.
- Prioritize deterministic behavior and fallback clarity over aggressive context packing.
