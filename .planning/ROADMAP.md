# Roadmap: v1.1 llm-wiki

## Milestone

**Version:** v1.1
**Name:** llm-wiki
**Status:** Active
**Started:** 2026-04-27
**Goal:** Generate external-app-compatible workspace exports from extraction artifacts, re-integrate 3gpp-ai into main app, and remove in-house wiki-compiler dependencies.

## Phases

- [x] **Phase 07: Framework Selection and Contract Freeze** (superseded — see phase 08)
- [x] **Phase 08: External Workspace Export and Reintegration**
- [x] **Phase 09: Workspace Infrastructure Merge and Export Elimination**

---

## Phase Details

### Phase 07: Framework Selection and Contract Freeze

**Goal:** Finalize framework decision and lock milestone-level technical contracts before implementation.

**Depends on:** v1.0 extraction baseline and v1.1 research outputs

**Requirements:** FRMW-01, FRMW-02

**Success Criteria**:

1. Framework recommendation is ratified with explicit acceptance criteria and fallback policy.
2. Wiki compile/query contract document is frozen for v1.1 scope.
3. CLI/config compatibility boundaries are documented for migration.

**Plans:** 2 plans

**Plan list:**

- [x] 07-01-PLAN.md - Framework selection rubric and decision record
- [x] 07-02-PLAN.md - v1.1 interface/contract freeze (schema, CLI, config)

**Note:** Phase 07 framework additions (llama-index-core, rank-bm25, rapidfuzz, wiki contracts) are reverted in phase 08-01. The strategy shifted to external-app workspace export instead of in-house wiki compilation.

---

### Phase 08: External Workspace Export and Reintegration

**Goal:** Strip 3gpp-ai to extraction-only, add workspace export commands for external wiki apps, and re-integrate into main CLI.

**Depends on:** Phase 07 (revert framework additions)

**Requirements:** REVERT-01, EXPORT-01, REINT-01

**Success Criteria**:

1. No llama-index-core, rank-bm25, or rapidfuzz dependencies remain.
2. Workspace export produces valid file structures for atomicmemory/llm-wiki-compiler and lucasastorian/llmwiki.
3. Workspace init/process/export commands available from main `tdoc-crawler` CLI.
4. Standalone `3gpp-ai` CLI prints deprecation message.
5. All tests pass.

**Plans:** 3 plans

**Plan list:**

- [ ] 08-01-PLAN.md - Revert phase 07 framework additions, strip 3gpp-ai to extraction-only
- [ ] 08-02-PLAN.md - Add workspace export module and CLI commands for external wiki app formats
- [ ] 08-03-PLAN.md - Re-integrate workspace commands into main CLI, deprecate standalone entrypoint

---

### Phase 09: Workspace Infrastructure Merge and Export Elimination

**Goal:** Merge workspace management into the main app as a core concern, eliminate the redundant export step by writing extraction artifacts directly to `.llm-wiki/<workspace>/`, and restructure the 3gpp-ai package to contain only AI extraction pipeline code.

**Depends on:** Phase 08

**Requirements:** MERGE-01, DIRECT-01, CLEANUP-01

**Success Criteria**:

1. Workspace CRUD, registry, and member management live in `src/tdoc_crawler/` (not `packages/3gpp-ai`).
2. Extraction artifacts are written directly to `~/.3gpp-crawler/.llm-wiki/<workspace>/sources/` during `workspace process`.
3. `workspace_export.py` and the `export` CLI command are removed.
4. `CacheManager` exposes `.llm_wiki_dir(workspace_name)` property.
5. `packages/3gpp-ai` contains only: extraction pipeline, LLM client, `AiConfig`.
6. All tests pass.

**Plans:** 3 plans

**Plan list:**

- [ ] 09-01-PLAN.md - Merge workspace infrastructure into main app
- [ ] 09-02-PLAN.md - Eliminate export step, write artifacts directly to .llm-wiki/
- [ ] 09-03-PLAN.md - Restructure 3gpp-ai to extraction-only package

---

## Progress

| Phase | Plans Complete | Status |
|-------|----------------|--------|
| 07. Framework Selection and Contract Freeze | 2/2 | Complete (superseded) |
| 08. External Workspace Export and Reintegration | 3/3 | Complete |
| 09. Workspace Infrastructure Merge and Export Elimination | 3/3 | Complete |

---

## Archive

- [x] Milestone v1.0 Advanced PDF Extraction Pipeline (2026-04-17 to 2026-04-18), archived at .planning/milestones/v1.0-ROADMAP.md

---

*Last updated: 2026-04-27 after phase 08 execution*
