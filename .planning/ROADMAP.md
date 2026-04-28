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
- [x] **Phase 10: Migration and Decommission**

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
3. Workspace init/process/export commands available from main \	doc-crawler\ CLI.
4. Standalone \3gpp-ai\ CLI prints deprecation message.
5. All tests pass.

**Plans:** 3 plans

**Plan list:**

- [x] 08-01-PLAN.md - Revert phase 07 framework additions, strip 3gpp-ai to extraction-only
- [x] 08-02-PLAN.md - Add workspace export module and CLI commands for external wiki app formats
- [x] 08-03-PLAN.md - Re-integrate workspace commands into main CLI, deprecate standalone entrypoint

---

### Phase 09: Workspace Infrastructure Merge and Export Elimination

**Goal:** Merge workspace management into the main app as a core concern, eliminate the redundant export step by writing extraction artifacts directly to \wiki/<workspace>/\, and restructure the 3gpp-ai package to contain only AI extraction pipeline code.

**Depends on:** Phase 08

**Requirements:** MERGE-01, DIRECT-01, CLEANUP-01

**Success Criteria**:

1. Workspace CRUD, registry, and member management live in \src/tdoc_crawler/\ (not \packages/3gpp-ai\).
2. Extraction artifacts are written directly to \~/.3gpp-crawler/wiki/<workspace>/sources/\ during \workspace process\.
3. \workspace_export.py\ and the \xport\ CLI command are removed.
4. \CacheManager\ exposes \workspace_llm_wiki_dir(workspace_name)\ property.
5. \packages/3gpp-ai\ contains only: extraction pipeline, LLM client, \AiConfig\.
6. All tests pass.

**Plans:** 3 plans

**Plan list:**

- [x] 09-01-PLAN.md - Merge workspace infrastructure into main app
- [x] 09-02-PLAN.md - Eliminate export step, write artifacts directly to .llm-wiki/
- [x] 09-03-PLAN.md - Restructure 3gpp-ai to extraction-only package

---

### Phase 10: Migration and Decommission

**Goal:** Deprecate legacy LightRAG-first command paths, update documentation for wiki-first architecture, add opt-in fallback mode with telemetry, and implement CLI wiki build health reporting.

**Depends on:** Phase 09

**Requirements:** MIGR-01, MIGR-02, MIGR-03, QUAL-03

**Success Criteria**:

1. Legacy LightRAG-first commands emit deprecation warnings with migration guidance.
2. Documentation (README.md, docs/ai.md, docs/query.md) describes wiki-first architecture.
3. Fallback mode requires explicit opt-in and emits telemetry.
4. \stats\ or equivalent CLI command reports wiki build health (page counts, failed pages, last compile hash).
5. All tests pass.

**Plans:** 2 plans

**Plan list:**

- [x] 10-01-PLAN.md - Deprecate legacy paths and update documentation
- [x] 10-02-PLAN.md - Add fallback mode and wiki health reporting

---

### Phase 11: Extraction Profiles for Wiki Ingestion

**Goal:** Define three extraction profiles (pdf-only, default, advanced) enabling LLM-wiki ingestion workflows with appropriate processing levels per use case.

**Depends on:** Phase 10

**Requirements:** WIKI-01, WIKI-02, WIKI-03

**Success Criteria**:

1. \ExtractionProfile\ enum with PDF_ONLY, DEFAULT, ADVANCED values available.
2. pdf-only profile delivers raw PDF to wiki directory via \nsure_pdf()\.
3. default/advanced profiles use opendataloader hybrid mode with structured JSON+markdown output.
4. \--profile\ CLI flag on \workspace process\ command with validation.
5. All tests pass.

**Plans:** 2 plans

**Plan list:**

- [x] 11-01-PLAN.md — Define ExtractionProfile enum and implement pdf-only profile
- [x] 11-02-PLAN.md — Wire --profile CLI flag to workspace process command

---

## Progress

| Phase | Plans Complete | Status |
|-------|----------------|--------|
| 07. Framework Selection and Contract Freeze | 2/2 | Complete (superseded) |
| 08. External Workspace Export and Reintegration | 3/3 | Complete |
| 09. Workspace Infrastructure Merge and Export Elimination | 3/3 | Complete |
| 10. Migration and Decommission | 2/2 | Complete |
| 11. Extraction Profiles for Wiki Ingestion | 2/2 | Complete |

---

*Last updated: 2026-04-28 after phase 11 execution*
