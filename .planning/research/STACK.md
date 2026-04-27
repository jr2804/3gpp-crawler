# Technology Stack

**Project:** packages/3gpp-ai
**Researched:** 2026-04-27
**Milestone Focus:** Replace traditional RAG pipeline with a Karpathy-style LLM Wiki approach over pre-extracted structured outputs from TDocs/specs/extra docs.

## Recommended Stack

### Primary Framework Choice (Recommended)

**Primary framework: LlamaIndex (core-only profile).**

Why this is the primary choice:
- Fits the target architecture: ingest structured extraction artifacts first, then build wiki-like knowledge pages with explicit sections/citations, then query over compact indexed representations.
- Offers enough orchestration primitives (document/node/index/query workflow) without forcing a heavyweight agent runtime.
- Minimizes migration risk because existing extraction and model layers can be preserved (OpenDataLoader outputs + LiteLLM provider abstraction).
- Supports incremental adoption: start with lexical+metadata retrieval, add vector/hybrid only where needed.

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| llama-index-core | >=0.11,<0.12 | Indexing/query orchestration for wiki pages and structured nodes | Best migration path from current RAG-oriented code to wiki-first retrieval without rewriting extraction pipeline |
| litellm (existing) | keep current pin strategy | Unified LLM provider access for generation/synthesis | Already integrated in package; keeps provider portability |
| pydantic-settings (existing) | keep current pin strategy | Config and feature flag rollout | Compatible with staged migration and dual-run mode |

### Retrieval Layer (Wiki-first)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sqlite FTS5 (stdlib sqlite3) | built-in | Primary lexical retrieval over generated wiki pages | Karpathy-style wiki retrieval is text-first; avoids vector lock-in for MVP |
| rank-bm25 | >=0.2,<0.3 | Lightweight BM25 reranking for candidate pages/chunks | Strong lexical baseline, fast local performance |
| rapidfuzz | >=3.0,<4.0 | Title/entity/fuzzy lookup routing | Improves wiki page targeting for spec/tdoc identifiers |

### Optional Semantic Add-on (Phase 2+)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| llama-index vector adapters (optional) | match core minor | Selective semantic retrieval for long-tail queries | Add only if lexical baseline misses target recall |
| qdrant-client (optional) | >=1.0,<2.0 | External vector backend when corpus scale requires it | Keeps storage decoupled from framework and supports growth |

## Ranked Shortlist (Candidate Frameworks)

Based on repository context and migration constraints for this milestone, shortlist ranking:

1. **LlamaIndex (core-only profile)**
   - Best fit for wiki-first document graph + retrieval orchestration.
   - Easiest compatibility path with existing extraction artifacts and LiteLLM usage.
2. **Haystack**
   - Strong production pipeline model and observability, but heavier migration surface for this codebase.
3. **DSPy (+ custom retrieval stack)**
   - Excellent for prompt/program optimization, weaker as a primary ingestion/index framework for this specific migration.
4. **Keep/extend LightRAG path**
   - Lowest short-term change, but misaligned with milestone intent to move away from traditional RAG-first architecture.

## Stack Additions and Removals

### Add
- `llama-index-core` as the primary orchestration layer for wiki-page ingestion and query flow.
- `rank-bm25` for robust lexical ranking over wiki pages and section nodes.
- `rapidfuzz` for resolver/routing on spec numbers, TDoc IDs, aliases, and near matches.

### Keep
- `opendataloader-pdf[hybrid]` for extraction (already produces structured artifacts needed by wiki builder).
- `litellm` and existing provider strategy.
- Current config model approach (`pydantic-settings`) and CacheManager path discipline.

### Remove / De-emphasize
- LightRAG/GraphRAG-specific wording, config flags, and migration assumptions as default architecture.
- Any default dependency path that assumes vector-first retrieval for all queries.

## Dependency Strategy

1. Introduce dependencies in two groups:
   - Required now: `llama-index-core`, `rank-bm25`, `rapidfuzz`
   - Optional later: vector backend adapters (`qdrant-client`, matching LlamaIndex vector plugin)
2. Keep extraction and LLM layers unchanged initially to reduce moving parts.
3. Avoid transitive lock-in by preferring core modules over meta-packages.
4. Use feature flags for rollout:
   - `TDC_AI_QUERY_MODE=wiki_lexical` (new default for milestone)
   - `TDC_AI_QUERY_MODE=hybrid_semantic` (opt-in)
   - Keep legacy mode behind explicit compatibility flag until cutover.

## Migration Compatibility Plan

### Data Compatibility
- Reuse existing structured extraction artifacts (markdown/json/tables/figures/equations).
- Add deterministic wiki-page materialization step:
  - one page per canonical concept/spec section,
  - backlinks to source document + page/element IDs,
  - stable deterministic page IDs for reproducible indexing.

### Runtime Compatibility
- Preserve existing CLI surface where possible (`workspace process/query/status`).
- Internally route query command to new wiki retrieval engine when mode is `wiki_lexical`.
- Keep old retrieval path temporarily for A/B verification during transition window.

### Configuration Compatibility
- Keep existing config keys operational.
- Mark LightRAG-centric keys as deprecated in docs first, then code warnings, then removal in later milestone.

## Framework Selection Criteria (for final gate)

Use these weighted criteria to confirm framework decision before implementation freeze:

| Criterion | Weight | Target |
|-----------|--------|--------|
| Migration effort from current 3gpp-ai code | 30% | Minimal rewrites outside query/index path |
| Wiki-first retrieval quality on spec/tdoc corpus | 30% | High precision on identifier-rich technical queries |
| Operational simplicity (local/dev/prod) | 20% | Works without mandatory external vector DB |
| Extensibility for phase-2 semantic add-ons | 10% | Clean optional vector/hybrid path |
| Dependency and vendor lock-in risk | 10% | Core modules, swappable storage |

**Recommendation outcome:** Choose **LlamaIndex (core-only profile)** as the primary framework for this milestone.

## Suggested Dependency Delta (packages/3gpp-ai)

```toml
# Add (required)
llama-index-core>=0.11,<0.12
rank-bm25>=0.2,<0.3
rapidfuzz>=3.0,<4.0

# Optional later
# qdrant-client>=1.0,<2.0
# llama-index vector plugin matching llama-index-core minor
```

## Sources

- Repository context:
  - `packages/3gpp-ai/pyproject.toml`
  - `packages/3gpp-ai/threegpp_ai/*`
  - `packages/3gpp-ai/AGENTS.md`
  - `3gpp-ai.toml`
- Framework docs:
  - https://docs.llamaindex.ai/en/stable/
  - https://haystack.deepset.ai/
  - https://docs.haystack.deepset.ai/docs/intro
