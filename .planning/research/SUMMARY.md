# Project Research Summary

**Project:** v1.1 llm-wiki migration (packages/3gpp-ai)
**Domain:** 3GPP standards intelligence, wiki-first LLM knowledge system
**Researched:** 2026-04-27
**Confidence:** MEDIUM-HIGH

## Executive Summary

This product is a standards intelligence system for 3GPP technical documents, where trust, provenance, and release/version correctness matter more than open-ended generative flexibility. The research converges on a wiki-first architecture: deterministic extraction artifacts become canonical source records, those records compile into stable wiki pages, and query-time LLM synthesis operates only on cited wiki sections rather than raw chunk retrieval.

The primary framework recommendation is **LlamaIndex (core-only profile)** for v1.1 migration. It provides enough indexing/query orchestration to build and query deterministic wiki pages while preserving existing extraction and model layers (`opendataloader-pdf` outputs + `litellm` provider abstraction). Compared with alternatives, this choice minimizes rewrite surface and lock-in risk: **Haystack** is viable but heavier for this codebase, **DSPy** is better as an optimization layer than primary ingestion/index orchestration, and reviving **traditional RAG/LightRAG-first paths** conflicts with milestone intent and reintroduces recently removed complexity.

Key risks are citation drift, release/version mixing, and nondeterministic builds. Mitigation must be structural, not advisory: provenance-anchored schemas, release-scoped indexing/snapshots, strict publish gates, and deterministic compile manifests with stable IDs/hashes.

## Key Findings

### Recommended Stack

The stack should prioritize a lexical/wiki baseline first, then add semantic retrieval only when measured gaps require it. Keep extraction and LLM provider layers stable; limit migration to wiki compile/index/query components.

**Core technologies:**
- `llama-index-core (>=0.11,<0.12)`: wiki page/node/index/query orchestration with low migration risk.
- `rank-bm25 (>=0.2,<0.3)`: strong local lexical ranking over curated wiki pages.
- `rapidfuzz (>=3.0,<4.0)`: robust identifier/topic resolution for spec numbers and TDoc IDs.
- `litellm` (existing): model-provider portability for synthesis without provider lock-in.
- SQLite FTS5 (stdlib): local-first primary retrieval over wiki pages.

**Alternatives and rationale:**
- **Haystack:** production-ready but larger migration and operational surface than needed for v1.1.
- **DSPy + custom retrieval:** useful later for program/prompt optimization, not ideal as primary wiki ingestion/index framework now.
- **Traditional RAG / LightRAG-first continuation:** lowest short-term change but strategically misaligned with wiki-first milestone and provenance goals.

### Expected Features

**Must have (table stakes):**
- Deterministic wiki-page compiler from canonical extraction JSON with stable IDs/slugs.
- Source-grounded answers with explicit section/span-level citations.
- Incremental workspace rebuilds for changed documents only.
- Entity/topic index over wiki corpus (page-first retrieval).
- Quality-gated publish path (failed extraction blocks wiki publish).

**Should have (competitive):**
- Dual-view pages: narrative summary plus machine facts panel.
- Conflict-aware synthesis across releases with evidence blocks.
- Lightweight concept graph from page links/entities.
- Task-oriented output templates (compliance/checklist/spec-delta).

**Defer (v2+):**
- Multi-backend retrieval abstraction (pgvector/OpenSearch class).
- Vector/semantic retrieval as default path.
- Query-time graph extraction and autonomous page rewriting.

### Architecture Approach

Adopt a compile-time wiki architecture: extract once, normalize to canonical artifact schema, compile deterministic pages/topics/edges, then query by page/topic traversal with bounded LLM synthesis.

**Major components:**
1. `wiki_artifacts` normalizer: canonical bundle and deterministic IDs.
2. `wiki_compiler`: document/topic page generation plus relation edges.
3. `wiki_store`: local page/link/provenance index (JSONL early, SQLite as needed).
4. `wiki_query`: retrieval orchestration and citation-constrained synthesis.
5. CLI adapters: `wiki build/query/status` and optional integration with `workspace process`.

### Critical Pitfalls

1. **Citation drift**: block publish when citation coverage or span resolution fails.
2. **Version/release mixing**: enforce release-scoped snapshots and CR/version lineage keys.
3. **Normative-language flattening**: preserve modality fields (`shall/should/may`) and validate no downgrades.
4. **Build nondeterminism**: pin models/deps, stable ordering, checksum manifests, no stochastic compile steps.
5. **Hidden legacy fallback**: expose retrieval mode in response payload and disallow silent vector fallback in strict mode.

## Implications for Requirements and Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Canonical Wiki Foundation
**Rationale:** Determinism/provenance are hard prerequisites for all later quality claims.
**Delivers:** Artifact normalizer, deterministic IDs/slugs, wiki schema contracts, stable manifests/hashes.
**Addresses:** Deterministic compiler, quality-gated publishing prerequisites.
**Avoids:** Citation drift and nondeterminism pitfalls.

### Phase 2: Wiki Build and Index Pipeline
**Rationale:** Build capability must exist before any credible query migration.
**Delivers:** `wiki_compiler`, workspace-scoped `wiki_store`, `wiki build/status`, incremental rebuild logic.
**Uses:** LlamaIndex core orchestration + BM25/FTS lexical index baseline.
**Implements:** Document/topic pages and edge records.

### Phase 3: Citation-Grounded Wiki Query (Parallel Run)
**Rationale:** Query migration should run in parallel with legacy path until measurable parity.
**Delivers:** `wiki_query`, citation-constrained answer mode, response provenance contract, A/B validation harness.
**Addresses:** Table-stakes trust and traceability with explicit references.
**Avoids:** Hidden legacy fallback and premature hard cutover.

### Phase 4: Default Switch and Deprecation
**Rationale:** Switch only after quality and operational thresholds are met.
**Delivers:** Wiki-first default query mode, deprecation warnings for legacy paths, migration docs.
**Addresses:** Milestone objective completion without abrupt regressions.
**Avoids:** Big-bang replacement risk.

### Phase Ordering Rationale

- Dependencies require deterministic schema and build outputs before query behavior change.
- Architecture boundaries naturally group into normalize -> compile/index -> query -> deprecate.
- This order front-loads pitfall mitigations where they are cheapest and most enforceable.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** topic-page merge heuristics and index format breakpoints (JSONL vs SQLite threshold).
- **Phase 3:** acceptance metrics for parity (citation coverage, release-scope correctness, latency SLOs).
- **Phase 4:** deprecation timing and compatibility contracts for existing CLI consumers.

Phases with standard patterns (can largely skip deep research):
- **Phase 1:** deterministic schema/ID/hash pipelines are established engineering patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strongly convergent shortlist with clear migration-fit rationale and low-regret baseline path. |
| Features | HIGH | Clear table stakes vs defer set, aligned with milestone intent and existing v1.0 extraction baseline. |
| Architecture | MEDIUM-HIGH | Detailed component boundaries and sequencing; storage scaling cutovers still require empirical thresholds. |
| Pitfalls | MEDIUM | Risks are well identified, but some thresholds (coverage %, parity bars) need project-specific calibration. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- Define hard acceptance gates for wiki query cutover (quality, latency, provenance metrics).
- Set explicit release/conflict resolution policy (recency vs normative precedence) for merged topic pages.
- Validate when lexical-only retrieval becomes insufficient and semantic add-on should be activated.
- Decide final storage transition criteria from JSONL to SQLite-backed indices.

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` - framework shortlist, dependency strategy, migration compatibility.
- `.planning/research/FEATURES.md` - table stakes, differentiators, anti-features, requirement implications.
- `.planning/research/ARCHITECTURE.md` - component boundaries, data flow, migration sequencing.
- `.planning/research/PITFALLS.md` - critical risks, detection signals, phase warnings.

### Secondary (MEDIUM confidence)
- Local package and workspace context cited by research files (`packages/3gpp-ai/*`, root guidance docs).

### Tertiary (LOW confidence)
- None introduced beyond the four milestone research outputs for this synthesis.

---
*Research completed: 2026-04-27*
*Ready for roadmap: yes*
