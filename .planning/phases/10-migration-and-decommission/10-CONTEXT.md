# Phase 10: Migration and Decommission — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning
**Source:** Requirements traceability + ROADMAP analysis

<domain>
## Phase Boundary

Phase 10 addresses the migration and decommission requirements for the v1.1 llm-wiki milestone. After Phases 07-09 established the workspace infrastructure, extraction pipeline, and wiki directory structure, Phase 10 handles:

1. **Deprecating legacy LightRAG-first command paths** with clear migration guidance
2. **Updating documentation** to describe the wiki-first architecture
3. **Adding opt-in fallback mode** with telemetry for non-wiki paths
4. **CLI status reporting** for wiki build health

This phase does NOT implement wiki compilation (WIKI-01–04) or wiki query (QUERY-01–04) — those are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Migration

- **MIGR-01**: Legacy LightRAG-first command paths must be deprecated with clear migration guidance and compatibility warnings. Deprecation warnings should appear on stderr when deprecated commands are invoked.
- **MIGR-02**: Documentation must be updated to remove default RAG/embedding-first language and describe the wiki-first architecture. This includes README.md, docs/ai.md, and any CLI help text.
- **MIGR-03**: Any retained fallback mode requires explicit opt-in (flag or config) and emits telemetry/metadata indicating non-wiki path usage.

### Quality

- **QUAL-03**: CLI status output must report wiki build health — counts of pages, failed pages, and last compile hash.

### Claude's Discretion

- Exact format of deprecation warnings (stderr vs console)
- Where to store wiki build health metadata
- How to implement the opt-in fallback flag
- Whether to add a new CLI command or extend existing `stats` command for wiki health

</decisions>

<canonical_refs>

## Canonical References

### Current CLI structure

- `src/tdoc_crawler/cli/tdoc_app.py` — Main TDoc CLI app
- `src/tdoc_crawler/cli/spec_app.py` — Spec CLI app
- `src/tdoc_crawler/cli/mgmt_app.py` — Management CLI app (config + workspace)
- `src/tdoc_crawler/cli/_workspace_commands.py` — Workspace CLI commands
- `src/tdoc_crawler/cli/config_app.py` — Config CLI commands

### Workspace infrastructure

- `src/tdoc_crawler/workspaces/` — Workspace CRUD, members, registry
- `src/tdoc_crawler/config/workspace_registry.py` — Workspace registry JSON persistence
- `src/tdoc_crawler/config/cache_manager.py` — CacheManager with wiki path methods

### Documentation

- `docs/ai.md` — AI document processing docs (needs migration update)
- `docs/query.md` — Query docs (needs migration update)
- `docs/index.md` — Documentation index
- `README.md` — Project README

</canonical_refs>

<specifics>
## Specific Ideas

- The `stats` command in `tdoc_app.py` could be extended to show wiki build health
- Deprecation warnings should follow Python's `warnings.warn()` pattern or use `console.print("[yellow]...[/yellow]")`
- The opt-in fallback flag could be `--legacy-rag` on relevant commands or a config setting
- Wiki health metadata could be stored in the workspace registry JSON or a separate file in `wiki/<workspace>/`

</specifics>

<deferred>
## Deferred Ideas

- WIKI-01–04 (wiki compilation) — separate phase
- QUERY-01–04 (wiki query) — separate phase
- QUAL-01–02 (quality gates for wiki publish) — separate phase

</deferred>

---

*Phase: 10-migration-and-decommission*
*Context gathered: 2026-04-28 via requirements analysis*
