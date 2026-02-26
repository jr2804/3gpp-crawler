# Research: AI Document Processing Pipeline

**Date**: 2026-02-24
**Purpose**: Resolve all NEEDS CLARIFICATION items from Technical Context

## 1. DOCX-to-Markdown Extraction Library

### Decision: Docling

**Rationale**: Docling (v2.74.0) is the most mature and feature-rich document conversion
library available. It supports DOCX, PDF, PPTX, XLSX, HTML, and more — with native
Markdown export. It handles tables, headings, figures, and complex layouts. MIT license,
54k GitHub stars, 182 contributors. Maintained by IBM Research under LF AI & Data.

**Key capabilities for our use case**:

- `DocumentConverter().convert(source).document.export_to_markdown()` — one-call API
- Preserves headings, tables (with structure), figures (with references)
- Unified `DoclingDocument` intermediate representation (lossless JSON available)
- Local execution (no cloud dependency)
- Windows, Linux, macOS support (x86_64 + arm64)
- Python 3.10+ (compatible with our 3.14 requirement — needs verification)

**Alternatives considered**:

| Library | Why Rejected |
|---------|-------------|
| python-docx | Read-only DOCX parsing; no Markdown export; manual table/heading handling required |
| mammoth | DOCX-to-HTML only; no native Markdown; limited table support |
| pandoc (via pypandoc) | External binary dependency; harder to package; less Python-native |
| markitdown (Microsoft) | Newer, less mature; Docling covers more formats and has richer structure extraction |

**Risk**: Docling is a large dependency (~100MB+ with models). Mitigated by making it an
optional extra (`tdoc_crawler[ai]`).

**Python 3.14 compatibility**: Docling uses pydantic v2, uv, ruff — same toolchain as
our project. If 3.14 compatibility is not yet released, we pin to the latest compatible

## 3. DOCX Extraction Migration Strategy: Docling → Kreuzberg

**Decision**: Use Docling for Phases 1-8, migrate to Kreuzberg in Phase 9 with **full refactoring** (no backward compatibility required).

**Rationale**: Kreuzberg is planned as the long-term extraction library starting in Phase 9.
Docling serves as an interim solution to unblock early phase implementation and testing.
Phase 9 migration will refactor the extraction interface to better match Kreuzberg's design
patterns rather than maintaining API compatibility.

**Migration requirements**:
- ✅ Kreuzberg MUST provide equivalent or better DOCX-to-Markdown conversion capabilities
- ✅ The `extract_from_folder()` function signature MAY change to leverage Kreuzberg's native API
- ✅ Internal implementation in extract.py should be refactored to use Kreuzberg idioms
- ✅ Tests in `test_ai_extraction.py` must pass unchanged after migration (black-box behavior preserved)
- ✅ No changes to public API (`process_tdoc()`, `process_all()`) during migration - only internal extraction layer changes

**Phase 9 deliverable**: Complete removal of Docling from all modules. Only Kreuzberg remains with refactored extraction interface.

**Risk mitigation**: Keep both dependencies installed during Phases 1-8 development. Final
migration happens in Phase 9 when Kreuzberg integration is complete and tested.

## 4. Graph Construction Strategy: Hybrid Node/Edge Extraction

**Decision**: Use a hybrid approach combining rule-based and LLM-powered extraction.

**Rule-based extraction (deterministic, fast):**
- TDoc ID patterns: `S[0-9]+-[0-9]+`, `[0-9]{5}-j[0-9]+` (regex matching)
- Meeting codes: `SA4#[0-9]+`, `RP-[0-9]+` (structured identifiers)
- Specification references: `TS [0-9]+.[0-9]+.[0-9]+` (3GPP spec format)
- Explicit cross-references: When TDoc content explicitly mentions another TDoc ID

**LLM-powered extraction (semantic, flexible):**
- Concept extraction: Identify technical concepts from content semantics
- Implicit relationships: Discover connections not explicitly stated (e.g., "similar approach to..." without TDoc ID)
- Work item identification: Map TDocs to work items based on topic discussion
- Relationship typing: Classify edge types (discusses, revises, extends, contradicts)

**Implementation phases:**
1. **Phase 9a**: Implement rule-based extraction first (quick wins, deterministic)
2. **Phase 9b**: Add LLM-powered semantic extraction (comprehensive but slower)
3. **Phase 9c**: Merge both sources with conflict resolution (rules take precedence for structured data)

**Conflict resolution:**
- When rules and LLM disagree on structured data (TDoc IDs, meeting codes) → trust rules
- When LLM identifies implicit relationships → accept unless contradicted by rules
- Log all conflicts for debugging and manual review if needed
**Risk mitigation**: Keep both dependencies installed during Phases 1-8 development. Final
migration happens in Phase 9 when Kreuzberg integration is complete and tested.

**Authorized breaking changes**:
- Function signatures in `src/tdoc_crawler/ai/operations/extract.py`
- Internal data structures and intermediate representations
- Error handling patterns (may adopt Kreuzberg-specific exception types)
- Configuration options specific to extraction stage

## 3. DOCX Extraction Migration Strategy: Docling → Kreuzberg

**Decision**: Use Docling for Phases 1-8, migrate to Kreuzberg in Phase 9.

**Rationale**: Kreuzberg is planned as the long-term extraction library starting in Phase 9.
Docling serves as an interim solution to unblock early phase implementation and testing.

**Migration requirements**:
- Kreuzberg MUST provide equivalent or better DOCX-to-Markdown conversion capabilities
- All imports of `docling.*` modules must be replaced with `kreuzberg.*` equivalents
- The `extract_from_folder()` function signature should remain stable to avoid breaking pipeline.py
- Tests in `test_ai_extraction.py` must pass unchanged after migration (black-box behavior)
- No changes to public API (`process_tdoc()`, `process_all()`) during migration

**Phase 9 deliverable**: Complete removal of Docling from all modules. Only Kreuzberg remains.

**Risk mitigation**: Keep both dependencies installed during Phases 1-8 development. Final
migration happens in Phase 9 when Kreuzberg integration is complete and tested.

## 2. Vector Storage Backend

### Decision: LanceDB

**Rationale**: LanceDB (v0.29.2) is a file-based vector database that requires no server
infrastructure. It stores data as Lance columnar files on the local filesystem, supports
vector similarity search, and integrates with Python's scientific ecosystem. This aligns
perfectly with the spec requirement (FR-018) for separate file-system-based storage.

**Key capabilities**:

- `lancedb.connect("<path>")` — file-based, no server
- Native vector search with IVF-PQ and brute-force modes
- Schema defined via pydantic models or pyarrow schemas
- Full-text search support (hybrid vector + keyword)
- Incremental upserts (add/update without full rebuild)
- Cross-platform (Windows, Linux, macOS)

**Storage layout**:

```
<cache_dir>/.ai/
├── lancedb/           # LanceDB data directory
│   ├── chunks.lance   # DocumentChunk + embeddings
│   ├── summaries.lance
│   ├── graph_nodes.lance
│   ├── graph_edges.lance
│   └── status.lance   # ProcessingStatus per TDoc
```

**Alternatives considered**:

| Backend | Why Rejected |
|---------|-------------|
| sqlite-vec | Good SQLite integration but less mature vector indexing; separate from tdoc-crawler DB requirement makes SQLite advantage irrelevant |
| FAISS | No persistence built-in; requires manual serialization; no metadata storage |
| ChromaDB | Requires server or heavy client; larger footprint than needed |
| Qdrant | Server-based; overkill for local single-user workload |
| zvec | No Windows support; v0.2.0 alpha; insufficient maturity |

**Storage capacity**: LanceDB handles millions of vectors efficiently. Our target of
5000 TDocs x ~50 chunks = 250K vectors is well within capacity.

## 3. LLM Abstraction Layer

### Decision: litellm (SDK only, no proxy server)

**Rationale**: litellm (v1.81.15) provides a unified `completion()` API that works with
100+ LLM providers. We use only the Python SDK (not the proxy server) to call Ollama
locally by default, with the ability to switch to any OpenAI-compatible endpoint via
configuration.

**Key capabilities**:

- `litellm.completion(model="ollama/llama3.2", messages=[...])` — unified API
- Supports Ollama, OpenAI, Anthropic, Azure, Bedrock, and 100+ providers
- Streaming support for real-time output
- OpenAI-compatible error handling
- No server required (SDK-only usage)
- Retry/fallback across multiple deployments

**Usage pattern**:

```python
import litellm

response = litellm.completion(
    model=config.llm_model,  # e.g., "ollama/llama3.2" or "openai/gpt-4o"
    messages=[{"role": "user", "content": prompt}],
)
```

**Alternatives considered**:

| Library | Why Rejected |
|---------|-------------|
| Direct ollama-python | Locks us to Ollama only; no provider switching |
| langchain (LLM wrapper) | Much heavier dependency; brings entire LangChain ecosystem |
| OpenAI SDK directly | Only works with OpenAI-compatible APIs; less flexible for local models |

**Network access note**: LLM calls via litellm do NOT go through `create_cached_session()`
because LLM responses are non-deterministic and should not be HTTP-cached. This is
documented in the Constitution Check. litellm manages its own HTTP connections.

## 4. Embedding Model

### Decision: sentence-transformers with BAAI/bge-small-en-v1.5 (default)

**Rationale**: sentence-transformers is the standard Python library for local embedding
generation. The BAAI/bge-small-en-v1.5 model provides a good balance of quality and
speed for English technical documents, with a small memory footprint (~130MB).

**Key capabilities**:

- `SentenceTransformer("BAAI/bge-small-en-v1.5").encode(texts)` — batch encoding
- 384-dimensional vectors (compact, fast similarity search)
- Runs locally on CPU (no GPU required)
- Model auto-downloaded on first use, cached locally
- Top-ranked on MTEB benchmark for its size class

**Alternatives considered**:

| Model | Why Not Default |
|-------|----------------|
| bge-base-en-v1.5 | 768-dim; 2x storage and slower search; marginal quality gain |
| bge-large-en-v1.5 | 1024-dim; heavy for initial release; available as config option |
| GTE (Alibaba) | Comparable quality but less community adoption |
| OpenAI text-embedding-3-small | Requires API key; violates local-only default |

**Configurable**: The embedding model is a configuration parameter (`AiConfig.embedding_model`).
Users can switch to any sentence-transformers-compatible model.

## 5. Document Chunking Strategy

### Decision: Section-based chunking with paragraph fallback

**Rationale**: 3GPP TDocs have well-defined section structure (headings like 5.3.2.1).
Chunking by section preserves semantic coherence. Paragraphs within long sections are
split at configurable max_chunk_size (default: 1000 tokens).

**Algorithm**:

1. Parse Markdown headings to identify sections
1. Each section becomes a chunk if under `max_chunk_size`
1. Sections exceeding `max_chunk_size` are split at paragraph boundaries
1. Each chunk retains metadata: TDoc ID, section heading, chunk index, character offsets
1. Overlap of `chunk_overlap` tokens (default: 100) between consecutive splits

**Alternatives considered**:

| Strategy | Why Rejected |
|----------|-------------|
| Fixed-size token windows | Breaks mid-sentence/section; loses semantic coherence |
| Recursive character splitting | Generic; ignores document structure |
| Sentence-level | Too granular; creates too many tiny chunks |

**Configuration**: `AiConfig.max_chunk_size` (default 1000), `AiConfig.chunk_overlap`
(default 100), measurable in tokens via the embedding model's tokenizer.

## 6. Temporal Graph Storage

### Decision: LanceDB tables for nodes and edges (same storage as embeddings)

**Rationale**: Rather than introducing a separate graph database (Neo4j, etc.), we store
graph nodes and edges as LanceDB tables. This keeps the storage unified, avoids another
dependency, and supports the queries we need (temporal filtering, relationship traversal
via joins). Full graph database features (Cypher queries, traversal algorithms) are not
needed for the MVP scope.

**Schema**:

- `graph_nodes` table: id, type (TDoc/Meeting/Spec/WorkItem/CR/Company/Concept),
  label, valid_from, valid_to, properties (JSON)
- `graph_edges` table: source_id, target_id, type (discusses/revises/references/
  supersedes/authored_by), weight, temporal_context, provenance

**Query patterns**:

- "Evolution of feature X" → filter edges by concept node, order by temporal_context
- "All TDocs discussing spec Y" → filter edges where target is spec Y, type=discusses
- "Cross-meeting references" → join nodes (type=TDoc) with edges, group by meeting

**Alternatives considered**:

| Storage | Why Rejected |
|---------|-------------|
| Neo4j | Server-based; massive dependency for MVP scope |
| NetworkX (in-memory) | No persistence; doesn't scale to thousands of nodes |
| SQLite (separate) | Then we'd have two storage backends; LanceDB already handles structured data |

**Future upgrade path**: If graph query complexity exceeds what LanceDB joins can handle,
the `graph_nodes` and `graph_edges` models can be migrated to a dedicated graph DB
without changing the rest of the pipeline.

## 7. Python 3.14 Compatibility

### Decision: Verify all AI dependencies against Python 3.14; pin if necessary

**Risk assessment**:

- **Docling**: Uses pydantic/uv/ruff — likely compatible; verify PyPI classifiers
- **LanceDB**: Rust-based core with Python bindings; may need a wheel for 3.14
- **sentence-transformers**: Depends on PyTorch; 3.14 support depends on PyTorch release
- **litellm**: Pure Python; likely compatible immediately

**Mitigation**: If any dependency lacks 3.14 wheels at implementation time, we:

1. Open an issue with the upstream project
1. Use the latest compatible Python version for the `[ai]` extra
1. Document the version constraint in pyproject.toml

This does not block planning or test writing.

## Summary of Decisions

| Area | Decision | Version | License |
|------|----------|---------|---------|
| DOCX Extraction | Docling | 2.74.0 | MIT |
| Vector Storage | LanceDB | 0.29.2 | Apache-2.0 |
| LLM Abstraction | litellm (SDK) | 1.81.15 | MIT |
| Embeddings | sentence-transformers + bge-small-en-v1.5 | latest | Apache-2.0 |
| Chunking | Section-based with paragraph fallback | custom | N/A |
| Graph Storage | LanceDB (same instance) | 0.29.2 | Apache-2.0 |

## FR-011 DRY/Search Evidence

- Reviewed existing code before implementation updates in:
  - `src/tdoc_crawler/cli/ai.py`
  - `src/tdoc_crawler/cli/app.py`
  - `src/tdoc_crawler/ai/{__init__.py,config.py,models.py,storage.py}`
  - `src/tdoc_crawler/ai/operations/{classify.py,extract.py,embeddings.py,summarize.py,graph.py,pipeline.py}`
  - `tests/test_ai*.py`
- Reused existing domain architecture and storage primitives rather than introducing duplicate code paths in CLI modules.
- Kept network-policy enforcement and storage-boundary validation as dedicated foundational tasks (`T016`-`T019`) to avoid scattered duplicate checks.
