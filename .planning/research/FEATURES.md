# Feature Landscape

**Domain:** 3GPP AI document intelligence (v1.1 llm-wiki milestone)
**Researched:** 2026-04-27

## Scope and Candidate Set

Milestone focus is replacing traditional retrieval-first RAG with a Karpathy-style llm-wiki approach.

Interpreted user candidate list for this milestone:

- Candidate A: Traditional RAG stack (chunk/embedding/vector retrieval + answer synthesis)
- Candidate B: Karpathy llm-wiki stack (deterministic wiki pages as primary knowledge substrate; LLM reasons over curated pages)

## Table Stakes

Features users should expect in v1.1. Missing any of these makes the llm-wiki direction non-credible.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deterministic wiki-page compiler from canonical extraction JSON | llm-wiki requires stable, replayable knowledge pages rather than ad hoc retrieval snippets | High | Must preserve provenance (`doc_id`, page, element IDs) and produce stable page IDs/slugs |
| Source-grounded answer mode with explicit citations | Replacing RAG must not reduce trust or traceability | Medium | Every answer must reference wiki page sections and original source coordinates |
| Incremental workspace rebuilds | Users need fast updates when new TDocs/spec revisions arrive | Medium | Recompile only affected pages; preserve unchanged page hashes |
| Entity/topic index over wiki corpus | Retrieval still exists, but over curated pages not raw chunks | Medium | Search target shifts from vector chunks to canonical wiki topics/entities |
| Quality-gated publishing pipeline | Prevent low-fidelity extraction from contaminating wiki knowledge | Medium | Block publish on failed extraction quality reasons already available in v1.0 |

## Differentiators

Features that create clear value beyond baseline replacement.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dual-view pages (human narrative + machine facts panel) | Serves engineers and downstream automation from one artifact | Medium | Reuse canonical JSON fields for facts panel, no duplicate parsing |
| Conflict-aware synthesis across releases | Helps users understand deltas and contradictions between versions | High | Surface conflicting claims with per-source evidence blocks |
| Auto-generated concept graph from wiki pages | Retains graph navigation benefits without full GraphRAG runtime dependency | High | Build lightweight graph from page links/entities, not from online query-time extraction |
| Task-oriented answer templates (compliance/checklist/spec delta) | Improves consistency for recurring telecom workflows | Medium | Template outputs grounded in wiki pages and deterministic metadata |

## Anti-Features

Explicitly avoid in v1.1 to preserve milestone focus and reduce architecture churn.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Reintroducing embedding/vector infrastructure as primary path | Conflicts with llm-wiki direction and reopens recently decommissioned surface | Keep retrieval over compiled wiki pages and deterministic indices |
| Query-time graph extraction/generation | Adds latency and non-determinism, weakens reproducibility | Precompute links/entities during wiki compile stage |
| Multi-backend retrieval abstraction (pgvector/OpenSearch/etc.) in v1.1 | Premature abstraction before proving llm-wiki fitness | Ship one local-first compile + index path, add adapters later if required |
| Autonomous page rewriting without provenance lock | Risks hallucinated drift from source specs | Enforce provenance-anchored page sections and diff-based updates |

## Requirements Implications (from Candidate List)

Implications derived from Candidate A vs Candidate B evaluation:

1. New requirement class: wiki compilation contracts.
	- Define stable page schema, deterministic slug rules, and provenance mapping guarantees.
2. New requirement class: reproducibility and diffability.
	- Re-running compile on unchanged artifacts must produce byte-stable wiki outputs.
3. New requirement class: governance guardrails.
	- Any synthesized statement must be linkable to specific source spans.
4. Requirement reduction: retrieval-backend configurability is no longer a v1.1 must-have.
	- Move vector-backend flexibility to post-v1.1 unless evidence shows hard blockers.
5. Requirement carryover from v1.0: extraction quality gates become publish gates.
	- Failed extraction quality must block wiki publish for affected pages.

## Framework-Fit Implications (from Candidate List)

| Candidate | Fit With Current 3gpp-ai Baseline | Implication |
|----------|-----------------------------------|-------------|
| Traditional RAG (Candidate A) | Low to medium fit. v1.0 explicitly decommissioned embedding-first modules and reset to extraction-first baseline. | Re-adoption would reintroduce removed surface area and dependency complexity. |
| Karpathy llm-wiki (Candidate B) | High fit. v1.0 already delivers deterministic extraction artifacts, stable IDs, and quality reports needed for wiki compilation. | Build compiler/index/publish layers on top of existing canonical outputs with minimal rollback risk. |

Framework recommendation for v1.1: prioritize Candidate B as the primary architecture; treat Candidate A only as an optional fallback research track if wiki answer quality cannot meet acceptance thresholds.

## MVP Recommendation

Prioritize:

1. Deterministic wiki-page compiler + provenance-preserving schema
2. Citation-grounded query/answer API over wiki pages
3. Incremental rebuild + publish gates tied to extraction quality

Defer:

- Advanced cross-release conflict synthesis (high value, but not required for first viable llm-wiki cut)
- Broad retrieval backend abstraction (not required until scale constraints are validated)

## Sources

- Workspace planning context: `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`, `.planning/milestones/v1.0-ROADMAP.md`
- Package context: `packages/3gpp-ai/AGENTS.md`, `packages/3gpp-ai/README.md`, `packages/3gpp-ai/pyproject.toml`
