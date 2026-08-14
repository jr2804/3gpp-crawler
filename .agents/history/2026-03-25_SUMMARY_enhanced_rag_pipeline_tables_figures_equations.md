# Enhanced RAG Pipeline with Tables, Figures, and Equations

**Date:** 2026-03-25

## Summary

Implemented a comprehensive enhancement to the RAG pipeline enabling extraction, preservation, and querying of tables, figures/images, and equations from 3GPP documents. Previously, only plain text was indexed—rich structural elements were either lost or converted to unstructured markdown without semantic preservation.

## Key Achievements

- **Unified Extraction Model**: Created `StructuredExtractionResult` shared across workspace ingestion, conversion, and summarization flows
- **Table Structure Preservation**: Cell-level table extraction with metadata and JSON sidecars
- **Figure Extraction**: Image persistence with optional vision-based descriptions using existing `LiteLLMClient`
- **Equation Handling**: LaTeX preservation with structural chunking protection
- **Single Query Command**: Maintained `ai rag query` as the sole user-facing query entrypoint
- **Metadata-First Ingestion**: All elements include document metadata (source, meeting, WG, etc.)

## Implementation Phases

### Phase 0: Compatibility and Unification Design

- Defined reusable structured models (`ExtractedTableElement`, `ExtractedFigureElement`, `ExtractedEquationElement`)
- Added extraction feature toggles to `LightRAGConfig`
- Established provider compatibility matrix for vision capabilities

### Phase 1: Shared Structured Extraction Core

- Created unified extraction function returning `StructuredExtractionResult`
- Integrated with `processor.py`, `convert.py`, and `summarize.py`
- Established consistent `.ai/` artifact layout

### Phase 2: Table Preservation

- Converted `result.tables` into structured elements with IDs, page numbers, dimensions
- Added stable table markers in markdown output
- Created JSON sidecars for machine-readable structure

### Phase 3: Figure/Image Extraction

- Persisted extracted figures under `.ai/figures/`
- Implemented caption matching heuristics
- Added cached figure description via `LiteLLMClient` with graceful non-vision fallback

### Phase 4: Equation Handling and Structural Chunking

- Detected and preserved equation blocks (`$$`, `\[ ... \]`, `\begin{equation} ...`)
- Introduced structural chunking respecting table/figure/equation boundaries
- Standardized metadata propagation through `TDocRAG.insert()`

### Phase 5: Single-Command Query Enhancement

- Maintained `tdoc-crawler ai rag query` as the single query command
- Improved retrieval context using enriched chunks from all element types
- Enhanced citation formatting with element type and location

## Files Modified

- `packages/3gpp-ai/threegpp_ai/models.py` - Added structured element models
- `packages/3gpp-ai/threegpp_ai/lightrag/config.py` - Added extraction feature toggles
- `packages/3gpp-ai/threegpp_ai/lightrag/processor.py` - Integrated structured extraction
- `packages/3gpp-ai/threegpp_ai/lightrag/rag.py` - Metadata propagation
- `packages/3gpp-ai/threegpp_ai/lightrag/cli.py` - Query output enrichment
- `packages/3gpp-ai/threegpp_ai/operations/convert.py` - Unified extraction usage
- `packages/3gpp-ai/threegpp_ai/operations/summarize.py` - Unified extraction usage
- `packages/3gpp-ai/threegpp_ai/operations/chunking.py` - Structural chunking
- `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` - New shared extraction module
- `packages/3gpp-ai/threegpp_ai/operations/figure_descriptor.py` - New figure description module
- `docs/ai.md`, `docs/query.md`, `docs/convert-lo-usage.md` - Documentation updates

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Reuse `LiteLLMClient` for vision | Avoids duplicating LLM infrastructure; litellm supports multimodal |
| Store figures under `.ai/figures/` | Clear artifact boundaries and traceability |
| Preserve equations as LaTeX | Standard format for mathematical notation |
| Single `ai rag query` command | Minimize CLI/API churn |
| Metadata-first ingestion | Better retrieval grounding and citations |
| Unified extraction across flows | Prevent drift and duplicate structures |

## Validation

All PRs validated through:

- Unit tests: `uv run pytest packages/3gpp-ai/tests/test_*.py -v`
- End-to-end workflow: workspace create → add-members → process → rag query
- Artifact verification: `.ai/` folder contains markdown, JSON sidecars, and figures

## CLI Usage

```bash
# Create and populate workspace
uv run tdoc-crawler ai workspace create test-rag-elements
uv run tdoc-crawler ai workspace add-members -w test-rag-elements --kind tdoc S4-250638

# Process with full extraction
uv run tdoc-crawler ai workspace process --workspace test-rag-elements

# Single query command for all data types
uv run tdoc-crawler ai rag query --workspace test-rag-elements "What are the bit rates in Table 3?"
uv run tdoc-crawler ai rag query --workspace test-rag-elements "Describe the architecture diagram"
uv run tdoc-crawler ai rag query --workspace test-rag-elements "What is the throughput equation?"
```

## Related Documentation

- Original plan: `PLAN.md` (archived as this document)
- Pipeline documentation: `packages/3gpp-ai/docs/PIPELINE.md`
- LightRAG configuration: `packages/3gpp-ai/AGENTS.md`
