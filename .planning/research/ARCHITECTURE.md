# Architecture Patterns

**Domain:** 3gpp-ai wiki-first knowledge pipeline
**Researched:** 2026-04-27

## Recommended Architecture

Replace retrieval-first (traditional RAG) behavior with a wiki-first pipeline that treats extracted artifacts as the source of truth and generates deterministic wiki pages per document and per topic index.

Core principle:

1. Extract once into stable artifact records.
2. Compile those records into wiki nodes (document pages + topic pages + relation edges).
3. Query by traversing wiki graph/page links first, then selectively calling LLM for synthesis over retrieved wiki sections.

This fits the current codebase because extraction and workspace orchestration already exist and are callable from CLI without introducing a new storage root.

## Existing Integration Points (Current Code)

### CLI command surfaces to extend

- `threegpp_ai.cli._workspace_commands.workspace_process`
- `threegpp_ai.cli._commands.ai_summarize` (already supports `--output-mode wiki`)
- `threegpp_ai.cli.__init__` command tree composition
- `threegpp_ai.cli._commands.clear_artifacts` for cleanup/rebuild workflows

### Pipeline operations to reuse

- `threegpp_ai.operations.convert.extract_document_structured_from_tdoc`
- `threegpp_ai.operations.convert.convert_document_to_markdown`
- `threegpp_ai.operations.summarize.summarize_tdoc`
- `threegpp_ai.cli._workspace.process_workspace_members` (current workspace orchestration loop)

### Workspace and state management to keep as SSOT

- `threegpp_ai.operations.workspace_registry.WorkspaceRegistry`
- `threegpp_ai.operations.workspaces.list_workspace_members`
- existing `.ai/` artifact placement under each checked-out document

## Proposed Components

### Component 1: Artifact Normalizer

**What:** Canonicalizes extraction output into stable schema used by wiki compiler.
**New module:** `threegpp_ai.operations.wiki_artifacts`
**Input:** `extract_document_structured_from_tdoc()` result
**Output:** `WikiArtifactBundle` (doc metadata, sections, equations, tables, figures, anchors)

Key requirement: every extracted element gets deterministic IDs (`doc_id`, `section_id`, `artifact_id`) so links remain stable across rebuilds.

### Component 2: Wiki Compiler

**What:** Converts normalized bundles into wiki pages and relation edges.
**New module:** `threegpp_ai.operations.wiki_compiler`
**Output targets:**

- document page: one page per TDoc/spec
- topic pages: synthesized pages grouped by tags/spec numbers/meeting topics
- edge index: references between pages and source artifacts

Storage recommendation: write under each member `.ai/wiki/` plus workspace-level index file managed via workspace name.

### Component 3: Wiki Index Store

**What:** Lightweight local index for page lookup, backlinks, and provenance.
**New module:** `threegpp_ai.operations.wiki_store`
**Format:** JSONL or SQLite-backed records (prefer SQLite if cross-document joins become hot)

Required access patterns:

- list pages by workspace
- resolve page by slug/id
- fetch backlinks and cited source artifacts
- fetch topic neighborhood (for multi-doc synthesis)

### Component 4: Wiki Query Engine

**What:** Query orchestrator that replaces vector-first retrieval with wiki traversal + bounded LLM synthesis.
**New module:** `threegpp_ai.operations.wiki_query`

Query flow:

1. parse user intent
2. resolve candidate wiki pages/topics
3. collect cited source snippets from artifact bundles
4. synthesize answer with citations to page IDs and artifact IDs

### Component 5: CLI adapters

**What:** Add wiki lifecycle commands without breaking current users.
**New command group proposal:** `3gpp-ai wiki ...`

Suggested commands:

- `3gpp-ai wiki build [-w workspace] [--force]`
- `3gpp-ai wiki query "..." [-w workspace]`
- `3gpp-ai wiki status [-w workspace]`
- `3gpp-ai wiki rebuild-topic <topic-slug>`

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Extraction (`convert.py`) | Produce markdown + raw structured artifacts | Artifact Normalizer |
| Artifact Normalizer | Stable canonical schema with IDs | Wiki Compiler, Wiki Query Engine |
| Wiki Compiler | Generate wiki pages and edge records | Wiki Index Store |
| Wiki Index Store | Persist/retrieve pages, links, provenance | Wiki Query Engine, CLI status |
| Wiki Query Engine | Retrieve wiki context and call LLM for synthesis | LiteLLM client, Wiki Store |
| CLI adapters | Trigger build/query/status flows | Workspace APIs + wiki modules |

## Data Flow

### Build flow (workspace-level)

1. `workspace process` continues to drive extraction readiness per member.
2. For each member, call `extract_document_structured_from_tdoc()`.
3. Normalize extraction payload into `WikiArtifactBundle`.
4. Compile bundle into document page + topic candidates + edge records.
5. Persist:
   - document-level wiki artifacts in member `.ai/wiki/`
   - workspace-level page/edge index in workspace registry-adjacent storage.
6. Mark build status/metadata for `wiki status` visibility.

### Query flow (wiki-first)

1. Resolve workspace (active workspace fallback remains unchanged).
2. Query engine reads page/topic index (not vector search).
3. Retrieve top relevant pages via lexical + link-neighborhood ranking.
4. Pull cited artifact snippets.
5. Call LLM once for final synthesis with explicit citation constraints.
6. Return answer + citation table (page IDs, source artifact IDs, paths).

## Integration With Existing Modules

### Minimal-change call sites

- Keep extraction in `threegpp_ai.operations.convert` unchanged initially.
- Extend `threegpp_ai.cli._workspace.process_workspace_members` to optionally trigger wiki compilation per member (feature-flagged).
- Keep `summarize_tdoc` for single-document summaries; optionally route `--output-mode wiki` through wiki page rendering once wiki compiler is stable.
- Reuse `WorkspaceRegistry` for workspace selection and lifecycle; do not create a parallel workspace abstraction.

### Config integration

Extend `AiConfig` with wiki-specific flags while preserving defaults:

- `wiki_enabled: bool` (default false during migration)
- `wiki_build_on_process: bool` (default false initially)
- `wiki_query_max_pages: int`
- `wiki_topic_merge_threshold: float`

## Migration Sequencing

### Phase 1: Foundation (no behavior change)

1. Add `wiki_artifacts` schema + normalizer.
2. Add `wiki_store` read/write APIs.
3. Persist normalized artifacts beside existing `.ai` outputs.

Exit criteria: extraction output can be normalized and stored for existing workspace members with no CLI regressions.

### Phase 2: Wiki build pipeline (opt-in)

1. Add `wiki_compiler` document-page generation.
2. Add `3gpp-ai wiki build` and `wiki status` commands.
3. Wire optional post-process build path from `workspace process`.

Exit criteria: workspace can produce deterministic wiki pages and index successfully.

### Phase 3: Wiki query path (parallel run)

1. Add `wiki_query` engine and `3gpp-ai wiki query` command.
2. Keep old retrieval/query path available for A/B validation.
3. Compare answer quality/citation coverage on representative TDoc sets.

Exit criteria: wiki query reaches agreed quality threshold and stable latency.

### Phase 4: Default switch and RAG deprecation

1. Make wiki query default for knowledge Q&A in CLI.
2. Keep compatibility shim and clear deprecation warnings for old RAG commands.
3. Remove obsolete vector-first code paths after one release window.

Exit criteria: all primary workflows use wiki-first architecture without regressions.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Dual source of truth

**What:** Maintaining wiki content separately from extracted artifacts without stable references.
**Why bad:** drift, stale citations, difficult rebuilds.
**Instead:** extracted artifacts are canonical; wiki pages are compiled projections.

### Anti-Pattern 2: Big-bang replacement

**What:** Removing old query path before parity testing.
**Why bad:** high outage and quality regression risk.
**Instead:** run wiki query in parallel until measurable parity is reached.

### Anti-Pattern 3: Workspace bypass

**What:** Introducing wiki storage not keyed by existing workspace model.
**Why bad:** inconsistent CLI behavior and broken user expectations.
**Instead:** keep workspace as top-level namespace in all wiki components.

## Scalability Considerations

| Concern | At 100 docs | At 10K docs | At 1M docs |
|---------|-------------|-------------|------------|
| Wiki index storage | JSONL acceptable | Prefer SQLite indices | Partitioned store + sharded query service |
| Build throughput | single-process CLI | batched async workers | distributed build pipeline |
| Query latency | direct page scan | indexed retrieval + cached neighborhoods | precomputed topic graphs + service tier |
| Rebuild strategy | full rebuild acceptable | incremental by changed doc | event-driven incremental compiler |

## Sources

- Local codebase integration points in `packages/3gpp-ai/threegpp_ai/cli` and `packages/3gpp-ai/threegpp_ai/operations`
- Local pipeline notes in `packages/3gpp-ai/docs/PIPELINE.md`
