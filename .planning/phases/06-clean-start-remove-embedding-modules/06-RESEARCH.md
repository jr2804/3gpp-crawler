# Phase 6 Research: Clean Start Remove Embedding Modules

**Phase:** 6 - Clean Start Remove Embedding Modules
**Date:** 2026-04-18

## Objective

Research the safest execution sequence for removing embedding/retrieval modules while preserving extraction and summarize functionality.

## Findings

### Code surface currently coupled to embedding/retrieval

- `threegpp_ai/cli.py` imports and invokes `LightRAGConfig`, `TDocRAG`, `DocumentProcessor`, and workspace commands for query/clear/embed workflows.
- `threegpp_ai/__init__.py` re-exports multiple LightRAG types (`TDocRAG`, `LightRAGConfig`, `EmbeddingConfig`, query/storage enums).
- `threegpp_ai/config.py`, `config_app.py`, and `config_exporter.py` include embedding model/backend/API fields and validation/output sections.
- `threegpp_ai/lightrag/` contains dedicated retrieval runtime modules (`rag.py`, `processor.py`, `metadata.py`, shared storage helpers).
- AI tests include direct embedding/retrieval expectations under `tests/ai/`.

### Dependency-level coupling

`packages/3gpp-ai/pyproject.toml` currently includes retrieval stack dependencies used primarily by LightRAG workflows. Removal requires synchronized dependency pruning to avoid stale transitive runtime assumptions.

### Preservation constraints

- `threegpp_ai/operations/summarize.py` currently uses structured extraction and LLM prompts and does not require direct LightRAG runtime calls for core summarization path.
- Workspace membership and document conversion/extraction flows should remain operational after embedding path removal.

## Recommended implementation sequence

1. Remove user-facing embedding/retrieval command paths and options from CLI/args to establish extraction-only interface boundary.
2. Remove package-level exports and config surfaces that expose embedding/retrieval runtime fields.
3. Delete `threegpp_ai/lightrag/` runtime modules and update imports/callers.
4. Prune no-longer-needed dependencies from `packages/3gpp-ai/pyproject.toml`.
5. Replace/remove embedding-specific tests and add extraction-only regression checks for preserved workflows.
6. Write post-removal baseline notes for the next milestone handoff.

## Risks and mitigations

- Risk: hidden import chains still referencing removed LightRAG symbols.
  - Mitigation: run targeted grep/import checks and focused AI test subset after each removal wave.
- Risk: CLI UX regressions for existing users expecting `workspace query` and embed behavior.
  - Mitigation: provide explicit command removal messaging/changelog entries in docs and help text updates.
- Risk: over-pruning shared dependencies accidentally needed for extraction/summarize.
  - Mitigation: dependency diff only after runtime import graph cleanup and targeted command tests.

## Phase requirement mapping

- PREP-01: inventory and explicit removal scope for embedding/retrieval modules
- PREP-02: runtime/path export cleanup and dependency removal with extraction/summarize preservation
- PREP-03: documented extraction-only baseline and handoff points for next milestone
