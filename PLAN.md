# PLAN: Enhanced RAG Pipeline with Tables, Figures, and Equations

## Goal

Enable the AI pipeline to extract, preserve, and query tables, figures/images, and equations from 3GPP documents with one unified processing model.

User-visible outcome:

- The existing single command `tdoc-crawler ai rag query` can answer from text, tables, figures, and equations.
- Source citations identify element type and location (for example table/figure/equation + page/section).
- `ai convert`, `ai summarize`, and `ai workspace process` use the same extraction primitives (no duplicate structures).

---

## Scope and Principles

### In Scope

- Unified structured extraction model shared across:
  - `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
  - `packages/3gpp-ai/threegpp_ai/operations/convert.py`
  - `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- Rich element ingestion into LightRAG with metadata.
- Query quality improvements through enriched context, while keeping a single query command.

### Out of Scope

- Adding separate CLI commands like `query-tables` or `query-figures`.
- Introducing an independent parallel extraction pipeline.

### Constraints

- Minimize CLI/API churn: keep one user query entrypoint.
- Keep SSOT/DRY: extraction and metadata logic defined once and reused.
- Preserve compatibility with existing workspaces and artifacts.

---

## Current Baseline

### Current Runtime Paths

- Workspace ingestion path: `threegpp_ai/lightrag/processor.py` -> `TDocRAG.insert()`.
- Conversion path: `threegpp_ai/operations/convert.py` (`convert_tdoc_to_markdown`).
- Summarization path: `threegpp_ai/operations/summarize.py` (currently reads markdown/text output).
- Query CLI path: `threegpp_ai/lightrag/cli.py` (`query` command).

### Current Gap

`kreuzberg` extraction currently uses `result.content` only in practice; `result.tables` and `result.images` are not consistently propagated through all paths.

---

## Phase 0: Compatibility and Unification Design

Goal: Lock a safe integration contract before coding.

### Files to touch

1. `packages/3gpp-ai/threegpp_ai/models.py`
2. `packages/3gpp-ai/threegpp_ai/lightrag/config.py`
3. New: `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`

### Implementation

- Define reusable structured models:
  - `ExtractedTableElement`
  - `ExtractedFigureElement`
  - `ExtractedEquationElement`
  - `StructuredExtractionResult` (canonical output shared by process/convert/summarize)
- Add extraction feature toggles to `LightRAGConfig`:
  - `extract_tables: bool = True`
  - `extract_figures: bool = True`
  - `extract_equations: bool = True`
  - `figure_description_enabled: bool = True`
- Keep `ProcessingResult` counters owned by `lightrag/processor.py` (for example `table_count`, `figure_count`, `equation_count`) while using shared element models from `models.py`.

### Provider compatibility matrix (initial)

- Ingestion/query providers currently implemented in `lightrag/rag.py`: `ollama`, `openai`, `zhipu`, `hf`, `jina`.
- Figure-description generation must explicitly handle providers without vision support:
  - If unsupported: skip description generation and log a clear reason.
  - Do not fail full document ingestion for missing vision capability.

---

## Phase 1: Shared Structured Extraction Core

Goal: Build one extraction flow consumed by all three entrypoints.

### Files to modify

1. New: `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
2. `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
3. `packages/3gpp-ai/threegpp_ai/operations/convert.py`
4. `packages/3gpp-ai/threegpp_ai/operations/summarize.py`

### Implementation

- Create one function returning `StructuredExtractionResult` from a source document.
- `processor.py` uses this shared function for workspace ingestion.
- `convert.py` uses the same structured function to generate markdown + optional sidecar artifacts.
- `summarize.py` consumes the same structured payload rather than maintaining separate extraction behavior.
- Keep generated `.ai/` artifact layout consistent across all flows.

### Output contract

- Primary markdown includes stable element markers.
- Optional JSON sidecars for machine-friendly structure:
  - `<doc>_tables.json`
  - `<doc>_figures.json`
  - `<doc>_equations.json`

---

## Phase 2: Table Preservation

Goal: Preserve cell-level semantics for retrieval.

### Files to modify

1. `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
2. `packages/3gpp-ai/threegpp_ai/operations/convert.py`
3. `packages/3gpp-ai/threegpp_ai/operations/chunking.py`

### Implementation

- Convert `result.tables` into structured table elements with IDs, page numbers, dimensions, and normalized cell content.
- Emit table markers in markdown and retain machine-readable JSON sidecar.
- Ensure chunking does not split table blocks arbitrarily.
- Insert table-aware metadata with each chunk/document insertion.

---

## Phase 3: Figure/Image Extraction

Goal: Make figures searchable and grounded.

### Files to modify

1. `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
2. `packages/3gpp-ai/threegpp_ai/operations/convert.py`
3. `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
4. New: `packages/3gpp-ai/threegpp_ai/operations/figure_descriptor.py`

### Implementation

- Extract images from `result.images`, persist under `.ai/figures/`.
- Detect/associate captions (heuristic first pass).
- Generate optional figure descriptions via existing `LiteLLMClient` path used in summarize flow.
- Cache figure descriptions; skip gracefully if provider/model lacks image support.
- Add figure metadata to enriched text before insertion.

---

## Phase 4: Equation Handling and Structural Chunking

Goal: Preserve equation integrity and improve retrieval context.

### Files to modify

1. `packages/3gpp-ai/threegpp_ai/operations/chunking.py`
2. `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
3. `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`

### Implementation

- Detect and preserve equation blocks (`$$`, `\\[ ... \\]`, `\\begin{equation} ...`).
- Introduce structural chunking behavior for tables/figures/equations while preserving existing strategy defaults.
- Do not require immediate new CLI options for chunking; keep API-compatible defaults and wire optional config internally first.
- Pass enriched metadata through `TDocRAG.insert(..., **kwargs)` into LightRAG `ainsert`.

---

## Phase 5: Single-Command Query Enhancement

Goal: Keep one query command while querying all available data.

### Files to modify

1. `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`
2. `packages/3gpp-ai/threegpp_ai/lightrag/cli.py`
3. `packages/3gpp-ai/threegpp_ai/lightrag/metadata.py`

### Implementation

- Keep `tdoc-crawler ai rag query` as the single user-facing query command.
- Improve retrieval context so the default query can use enriched chunks from text, tables, figures, and equations.
- Optionally include richer citation formatting in query output (element type + source + page/section), without introducing separate query commands.

---

## Validation Plan

### Unit/Package Tests

```bash
# Existing tests
uv run pytest packages/3gpp-ai/tests/test_chunking.py -v
uv run pytest packages/3gpp-ai/tests/test_integration.py -v
uv run pytest packages/3gpp-ai/tests/test_metadata.py -v
uv run pytest packages/3gpp-ai/tests/test_lightrag_config.py -v

# New tests to add
uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v
uv run pytest packages/3gpp-ai/tests/test_figure_descriptor.py -v
```

### End-to-End Workflow (current CLI-compatible)

```bash
# 1) Create and activate workspace
uv run tdoc-crawler ai workspace create test-rag-elements
uv run tdoc-crawler ai workspace activate test-rag-elements

# 2) Add members (no dedicated "workspace add" command; use add-members)
uv run tdoc-crawler ai workspace add-members -w test-rag-elements --kind tdoc S4-250638

# 3) Process workspace
uv run tdoc-crawler ai workspace process --workspace test-rag-elements

# 4) Single query command (all data types)
uv run tdoc-crawler ai rag query --workspace test-rag-elements "What are the bit rates in Table 3?"
uv run tdoc-crawler ai rag query --workspace test-rag-elements "Describe the architecture diagram"
uv run tdoc-crawler ai rag query --workspace test-rag-elements "What is the throughput equation?"
```

### Artifact Spot Checks (portable)

```bash
# Discover source paths in workspace
uv run tdoc-crawler ai workspace list-members -w test-rag-elements --json

# Inspect the .ai subfolder under each member's source_path
# Expected artifacts:
# - <doc>.md
# - optional *_tables.json, *_figures.json, *_equations.json
# - optional figures/ directory
```

---

## Design Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-25 | Unify extraction for workspace/convert/summarize | Prevent drift and duplicate structures |
| 2026-03-25 | Keep a single `ai rag query` command | Minimize CLI/API churn |
| 2026-03-25 | Use kreuzberg native tables/images where available | Reuse existing extraction capabilities |
| 2026-03-25 | Store figures under `.ai/figures/` | Clear artifact boundaries and traceability |
| 2026-03-25 | Preserve equations as first-class structural elements | Improve math retrieval fidelity |
| 2026-03-25 | Metadata-first ingestion (element + document metadata) | Better retrieval grounding and citations |

---

## Metadata Contract (Draft)

```python
await rag.insert(
    text,
    metadata={
        "element_type": "table",      # table|figure|equation|text
        "element_id": "table_3",
        "page": 12,
        "section": "4.2",
        "source_doc": "S4-250638",
        "doc_type": "tdoc",
        "meeting": "S4#131-bis",
        "wg": "S4",
    },
)
```

All inserted units should include document metadata plus optional element metadata when relevant.

---

## Concrete Implementation Checklist (PR-Sized Slices)

Execution rule: each PR should be reviewable in isolation, mergeable independently, and include tests.

### PR-01: Shared extraction models and config flags

- [x] Add structured element models and canonical extraction payload.
- [x] Add extraction toggles to LightRAG config with safe defaults.
- [x] Keep existing runtime behavior unchanged when new flags are not used.

Files:

- `packages/3gpp-ai/threegpp_ai/models.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/config.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` (new)
- `packages/3gpp-ai/tests/test_lightrag_config.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_lightrag_config.py -v`

Done criteria:

- New models import cleanly.
- New config fields are readable from env and keep defaults stable.

### PR-02: Unified extraction function used by processor

- [x] Implement one shared extraction function returning `StructuredExtractionResult`.
- [x] Wire `lightrag/processor.py` to use the shared function.
- [x] Add processor-level counters for table/figure/equation extraction.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
- `packages/3gpp-ai/tests/test_integration.py`
- `packages/3gpp-ai/tests/test_extraction_elements.py` (new)

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`

Done criteria:

- Processor receives structured result and inserts text successfully.
- No regressions in current workspace processing tests.

### PR-03: Reuse unified extraction in convert flow

- [x] Refactor convert flow to call the shared extraction function.
- [x] Preserve existing markdown output contract.
- [x] Add optional sidecar JSON artifacts for tables/figures/equations.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/convert.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/tests/test_operations_metrics.py`
- `packages/3gpp-ai/tests/test_extraction_elements.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_operations_metrics.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`

Done criteria:

- `ai convert` still returns markdown.
- Sidecars are generated when structured elements exist.

### PR-04: Reuse unified extraction in summarize flow

- [x] Refactor summarize flow to consume shared structured extraction output.
- [x] Keep summary quality and existing summarize CLI behavior stable.
- [x] Ensure no duplicate extraction logic remains.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/tests/test_integration.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`

Done criteria:

- `ai summarize` path uses unified extraction.
- No duplicated parser/extractor functions in summarize module.

### PR-05: Table semantic preservation and ingestion metadata

- [x] Normalize table elements (ID, page, size, cells).
- [x] Add stable table markers in markdown output.
- [x] Include table-aware metadata in insertion payload.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
- `packages/3gpp-ai/threegpp_ai/operations/convert.py`
- `packages/3gpp-ai/tests/test_extraction_elements.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`

Done criteria:

- Table rows/cells retrievable from sidecar metadata.
- Inserted text contains enough context for table-focused queries.

### PR-06: Figure extraction, storage, and optional description

- [x] Persist extracted figures under `.ai/figures/`.
- [x] Add caption matching heuristics.
- [x] Add cached figure-description module using existing `LiteLLMClient` path.
- [x] Implement graceful skip when provider/model does not support vision.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/figure_descriptor.py` (new)
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/operations/summarize.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
- `packages/3gpp-ai/tests/test_figure_descriptor.py` (new)

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_figure_descriptor.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`

Done criteria:

- Figure artifacts are stored and indexed metadata is present.
- Non-vision providers do not break end-to-end processing.

### PR-07: Equation detection and chunk-protection

- [x] Add equation extraction metadata and markers.
- [x] Prevent equation block splitting in chunking behavior.
- [x] Preserve backward compatibility of default chunking strategy.

Files:

- `packages/3gpp-ai/threegpp_ai/operations/chunking.py`
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
- `packages/3gpp-ai/tests/test_chunking.py`
- `packages/3gpp-ai/tests/test_extraction_elements.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_chunking.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`

Done criteria:

- Equation blocks remain intact through chunking/insertion.
- Existing chunking tests still pass.

### PR-08: Metadata propagation through RAG wrapper

- [x] Standardize metadata passed through `TDocRAG.insert(..., **kwargs)`.
- [x] Ensure insertion path preserves metadata fields for all element types.
- [x] Add/update tests for metadata pass-through.

Files:

- `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/metadata.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`
- `packages/3gpp-ai/tests/test_metadata.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_metadata.py -v`

Done criteria:

- Element metadata appears in inserted payloads consistently.

### PR-09: Single-command query output enrichment

- [x] Keep only `ai rag query` as user query entrypoint.
- [x] Improve output citations with element type and location where available.
- [x] Do not add new query commands.

Files:

- `packages/3gpp-ai/threegpp_ai/lightrag/cli.py`
- `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`
- `packages/3gpp-ai/tests/test_integration.py`

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`

Done criteria:

- Query output can reference table/figure/equation context without command churn.

### PR-10: End-to-end regression and docs sync

- [x] Run targeted package tests.
- [x] Validate workspace add-members/process/query flow end-to-end.
- [x] Update docs to reflect unified extraction behavior and single-query model.

Files:

- `PLAN.md`
- `docs/ai.md`
- `docs/query.md`
- `docs/convert-lo-usage.md` (if behavior or artifacts section needs updates)

Validation:

- `uv run pytest packages/3gpp-ai/tests/test_chunking.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_metadata.py -v`
- `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`
- `uv run tdoc-crawler ai workspace create test-rag-elements`
- `uv run tdoc-crawler ai workspace add-members -w test-rag-elements --kind tdoc S4-250638`
- `uv run tdoc-crawler ai workspace process --workspace test-rag-elements`
- `uv run tdoc-crawler ai rag query --workspace test-rag-elements "What are the bit rates in Table 3?"`

Done criteria:

- Tests pass.
- Documentation matches implemented behavior.
- End-to-end scenario is reproducible from docs.

---

## Progress

- [x] (2026-03-25) Plan aligned with current CLI/file paths and single-query requirement
- [x] (2026-03-25) PR-01 implemented: added structured extraction models and shared extraction payload utility
- [x] (2026-03-25) PR-01 implemented: added `LightRAGConfig` extraction flags (`extract_tables`, `extract_figures`, `extract_equations`, `figure_description_enabled`)
- [x] (2026-03-25) PR-01 validation passed: `uv run pytest packages/3gpp-ai/tests/test_lightrag_config.py -v`
- [x] (2026-03-25) PR-02 implemented: processor now consumes `StructuredExtractionResult` and reports table/figure/equation counters
- [x] (2026-03-25) PR-02 validation passed: `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`
- [x] (2026-03-25) PR-03 implemented: convert flow now uses shared structured extraction and writes optional sidecar JSON files
- [x] (2026-03-25) PR-03 validation passed: `uv run pytest packages/3gpp-ai/tests/test_operations_metrics.py -v`
- [x] (2026-03-25) PR-03 validation passed: `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`
- [x] (2026-03-25) PR-04 implemented: summarize flow now uses `extract_tdoc_structured(...).content`
- [x] (2026-03-25) PR-04 validation passed: `uv run pytest packages/3gpp-ai/tests/test_operations_metrics.py -v`
- [x] (2026-03-25) PR-02 integration validation passed: `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`
- [x] (2026-03-25) PR-05 implemented: structured table markers + table metadata propagation across extraction/processor/convert
- [x] (2026-03-25) PR-05 validation passed: `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`
- [x] (2026-03-25) PR-06 implemented: figure persistence + optional description pipeline with graceful non-vision fallback
- [x] (2026-03-25) PR-06 validation passed: `uv run pytest packages/3gpp-ai/tests/test_figure_descriptor.py -v`
- [x] (2026-03-25) PR-07 implemented: equation markers + structural chunking to preserve equation blocks
- [x] (2026-03-25) PR-07 validation passed: `uv run pytest packages/3gpp-ai/tests/test_chunking.py -v`
- [x] (2026-03-25) PR-08 implemented: metadata pass-through standardized in RAG insert/query path
- [x] (2026-03-25) PR-08 validation passed: `uv run pytest packages/3gpp-ai/tests/test_metadata.py -v`
- [x] (2026-03-25) PR-09 implemented: single-command query enrichment with citation guidance and compatibility-safe query params
- [x] (2026-03-25) PR-09 validation passed: `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`
- [x] (2026-03-25) PR-10 targeted validation passed:
  - `uv run pytest packages/3gpp-ai/tests/test_extraction_elements.py -v`
  - `uv run pytest packages/3gpp-ai/tests/test_chunking.py -v`
  - `uv run pytest packages/3gpp-ai/tests/test_figure_descriptor.py -v`
  - `uv run pytest packages/3gpp-ai/tests/test_operations_metrics.py -v`
  - `uv run pytest packages/3gpp-ai/tests/test_metadata.py -v`
  - `uv run pytest packages/3gpp-ai/tests/test_integration.py -v`
- [x] (2026-03-25) PR-10 docs updated: `docs/ai.md`, `docs/query.md`, `docs/convert-lo-usage.md`
- [x] (2026-03-25) E2E command syntax corrected: `workspace add-members` now documented with positional item args (no `--items` flag)
- [x] (2026-03-25) E2E processing path fixed in CLI: replaced invalid `TDocDatabase.get_tdoc()` call and fixed `_logger` usage in `workspace process`
- [x] (2026-03-25) LightRAG insert compatibility fix: `TDocRAG.insert()` retries without kwargs when runtime `ainsert` rejects metadata kwargs
- [x] (2026-03-25) E2E query blocker fixed: removed query-time model override to preserve LightRAG `hashing_kv` injection and wrapped embeddings with `EmbeddingFunc` for hybrid query compatibility
- [x] (2026-03-25) PR-10 end-to-end flow validated on workspace `test-rag-elements-e2e` (create -> add-members -> process -> rag query)
- [x] Phase 0: Compatibility and Unification Design
- [x] Phase 1: Shared Structured Extraction Core
- [x] Phase 2: Table Preservation
- [x] Phase 3: Figure/Image Extraction
- [x] Phase 4: Equation Handling and Structural Chunking
- [x] Phase 5: Single-Command Query Enhancement
