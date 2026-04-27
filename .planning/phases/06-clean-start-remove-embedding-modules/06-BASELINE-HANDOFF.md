# Phase 6 Baseline Handoff

Generated: 2026-04-18

## Outcome

The `3gpp-ai` package now runs in extraction-first mode without active embedding/retrieval runtime modules.

## What Was Removed

- Workspace retrieval commands and embedding insertion paths from the top-level CLI.
- Embedding/retrieval exports from package public API.
- LightRAG runtime package modules under `packages/3gpp-ai/threegpp_ai/lightrag/`.
- Embedding-focused dependencies (`lightrag-hku[offline]`, `pg0-embedded`).
- Embedding-focused test suites tied to LightRAG runtime behavior.

See detailed dispositions in:

- `.planning/phases/06-clean-start-remove-embedding-modules/06-EMBEDDING-DECOMMISSION-INVENTORY.md`

## Extraction-Only Baseline

Retained value paths:

- `3gpp-ai convert`
- `3gpp-ai summarize`
- `3gpp-ai workspace add-members`
- `3gpp-ai workspace process` (extraction artifacts generation)
- Workspace registry and document checkout/member lifecycle operations

Configuration surface retained:

- LLM settings (`llm_model`, `llm_api_base`, `llm_api_key`)
- Extraction/runtime controls (`convert_pdf`, `convert_md`, `vlm`, `device`, `num_threads`, `batch_size`, extraction element toggles)

## Extension Points For Next Milestone

Use these seams for the new RAG/information retrieval system:

1. Add a new dedicated retrieval runtime package under `threegpp_ai/` (do not resurrect deleted LightRAG modules).
2. Introduce retrieval command surface as a separate explicit CLI group after architecture decisions are finalized.
3. Keep extraction artifact contracts as canonical inputs for any future indexing/retrieval pipeline.

## Guardrails

- Do not re-introduce deleted `threegpp_ai.lightrag.*` modules.
- Do not re-add removed LightRAG dependencies without an approved next-milestone design.
- Any new retrieval stack must consume existing extraction artifacts and preserve summarize compatibility.
