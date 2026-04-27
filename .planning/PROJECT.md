# 3GPP AI Document Intelligence

## What This Is

A brownfield extension of 3gpp-ai that compiles deterministic extraction artifacts from TDocs/specs into a provenance-grounded llm-wiki, then answers queries from curated wiki pages instead of traditional vector-first RAG paths.

## Core Value

Extract technically accurate, traceable document structure and meaning from complex PDFs into deterministic Markdown and canonical JSON artifacts.

## Current Milestone: v1.1 llm-wiki

**Goal:** Replace the traditional RAG pipeline in packages/3gpp-ai with a Karpathy-style llm-wiki architecture that ingests existing extracted artifacts and serves citation-grounded answers.

**Target features:**

- Deterministic wiki-page compiler and publish contracts from canonical extraction artifacts.
- Citation-grounded wiki query mode with release-aware provenance constraints.
- Framework decision and implementation baseline for llm-wiki (primary recommendation: llama-index-core profile).
- Migration/deprecation path for remaining LightRAG-first surfaces.

## Requirements

### Validated

- [x] Deterministic extraction profile policy and persisted effective config snapshots. - v1.0
- [x] Canonical JSON + Markdown dual-output contracts with stable provenance IDs. - v1.0
- [x] Deterministic extraction quality gate lifecycle and reason-coded reporting. - v1.0
- [x] Structured-first summarize context assembly with markdown fallback compatibility. - v1.0
- [x] Embedding module surface decommission for extraction-only baseline. - v1.0
- [x] Framework selection and contract freeze for wiki-first v1.1 baseline. - phase 07

### Active

- [ ] WIKI-01: Compile deterministic wiki pages from canonical artifacts with stable IDs/slugs.
- [ ] WIKI-02: Persist release-aware provenance mappings for every wiki section.
- [ ] QUERY-01: Serve citation-grounded answers from wiki-first retrieval.
- [ ] MIGR-01: Deprecate legacy LightRAG-first command surfaces safely.

### Out of Scope

- Reintroducing embedding/vector infrastructure as default retrieval path in v1.1 - conflicts with milestone intent and recent decommission.
- Multi-backend retrieval abstraction (pgvector/opensearch/others) in v1.1 - defer until wiki baseline quality and scaling thresholds are measured.
- Autonomous wiki page rewrites without provenance lock - unacceptable for standards-traceability requirements.

## Context

- Latest shipped milestone: v1.0 Advanced PDF Extraction Pipeline, archived in .planning/milestones/v1.0-ROADMAP.md and .planning/milestones/v1.0-REQUIREMENTS.md.
- v1.1 research outputs generated under .planning/research/ with stack/features/architecture/pitfalls synthesis.
- Research recommendation for primary framework selection: llama-index-core for core orchestration, with lexical wiki retrieval baseline and optional semantic add-ons deferred.
- User direction: traditional RAG pipeline in packages/3gpp-ai will be removed/replaced by llm-wiki approach.

## Constraints

- **Architecture**: Keep extraction outputs as source-of-truth inputs to wiki compile - avoid reintroducing extract-time embedding branches.
- **Traceability**: All generated wiki claims must map to source coordinates (doc/page/element IDs) - needed for standards-grade trust.
- **Compatibility**: Preserve stable CLI ergonomics where practical during migration - reduce operational breakage for existing users.
- **Determinism**: Wiki build output must be reproducible for unchanged inputs - required for auditability and diff-based workflows.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use llm-wiki as v1.1 target architecture | Aligns with extraction-first baseline and user direction to replace traditional RAG | ✓ Good |
| Primary framework baseline: llama-index-core profile | Best fit from milestone research for migration risk, orchestration needs, and minimal lock-in | — Pending |
| Start with lexical wiki retrieval and citations, defer semantic default | Preserves determinism and limits complexity while quality baselines are established | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via /gsd-transition):

1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. What This Is still accurate? -> Update if drifted

**After each milestone** (via /gsd-complete-milestone):

1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-27 after new milestone initialization (v1.1 llm-wiki)*
