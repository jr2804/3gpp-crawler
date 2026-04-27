# Phase 6: Clean Start Remove Embedding Modules - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Prepare a clean extraction-only baseline before the next milestone by removing all current embedding/retrieval module wiring from `3gpp-ai`.

In scope:

- Remove embedding-oriented runtime commands and module wiring.
- Remove embedding/retrieval package-level exports and direct integration points.
- Remove no-longer-needed embedding dependencies and tests tied to removed runtime behavior.
- Preserve extraction and summarize workflows.

Out of scope:

- Building a new retrieval architecture in this phase.
- Re-introducing replacement embedding infrastructure.
</domain>

<decisions>
## Implementation Decisions

### Locked Decisions

- This phase exists to prepare for next-milestone RAG/retrieval by removing existing embedding modules.
- Produce a clean start for future retrieval work rather than keeping partial legacy embedding paths.
- Keep current extraction and summarize value paths operational after cleanup.

### the agent's Discretion

- Exact deletion order to minimize breakage during implementation.
- Which temporary compatibility shims are needed during a single execution pass.
- Final naming/location of cleanup inventory notes generated during execution.
</decisions>

<canonical_refs>

## Canonical References

### Milestone and requirement guardrails

- `.planning/PROJECT.md` - extraction-first value and milestone non-goals
- `.planning/ROADMAP.md` - Phase 6 objective, PREP-01..PREP-03 mapping
- `.planning/REQUIREMENTS.md` - transition requirements for cleanup and baseline readiness

### Embedding/retrieval integration hotspots

- `packages/3gpp-ai/threegpp_ai/cli.py` - workspace query/clear/embed flows and LightRAG command wiring
- `packages/3gpp-ai/threegpp_ai/args.py` - query mode and embedding-related workspace options
- `packages/3gpp-ai/threegpp_ai/__init__.py` - package-level LightRAG exports
- `packages/3gpp-ai/threegpp_ai/config.py` - embedding model/backend fields
- `packages/3gpp-ai/threegpp_ai/config_app.py` - config validation and display for embedding settings
- `packages/3gpp-ai/threegpp_ai/config_exporter.py` - exported embedding/lightRAG config fields
- `packages/3gpp-ai/threegpp_ai/lightrag/` - LightRAG runtime modules
- `packages/3gpp-ai/pyproject.toml` - embedding/retrieval dependencies

### Current tests tied to embedding/retrieval paths

- `tests/ai/test_ai_embeddings.py`
- `tests/ai/test_integration.py`
- `tests/ai/test_metadata.py`
- `tests/ai/test_lightrag_config.py`
- `tests/ai/test_pipeline_errors.py`
- `tests/ai/conftest.py`
</canonical_refs>

<specifics>
## Specific Ideas

- Remove embedding command paths in `workspace` CLI before deleting deeper runtime modules so user-facing behavior fails closed.
- Replace removed runtime references with extraction-only status/help messaging where needed.
- Treat transition docs as implementation artifacts to make next-milestone startup deterministic.
</specifics>

<deferred>
## Deferred Ideas

- New retrieval stack design and implementation.
- Any replacement vector storage abstraction.
- Milestone-level architecture decisions for future RAG execution pipeline.
</deferred>

---
*Phase: 06-clean-start-remove-embedding-modules*
*Context gathered: 2026-04-18*
