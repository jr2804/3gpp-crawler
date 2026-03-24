# PLAN: LightRAG + pg0 Pipeline Replacement

## Goal

Replace the existing 3gpp-ai pipeline with **LightRAG** (Python GraphRAG framework, EMNLP 2025) backed by **pg0** (zero-config embedded PostgreSQL with pgvector). This eliminates custom embedding, graph building, and vector storage code while keeping the entire stack lightweight and Windows-native.

## Context

### Current Architecture (To Be Replaced)

- **Database:** LanceDB (embedded vector store)
- **PDF Conversion:** LibreOffice via convert-lo package (upstream normalization)
- **Extraction:** Kreuzberg text extraction from converted PDF artifacts
- **Embeddings:** sentence-transformers (text only)
- **GraphRAG:** Custom Python implementation with hardcoded regex patterns

### New Architecture

- **GraphRAG Framework:** LightRAG v1.4.11 (Python, 30K+ stars, 233 contributors)
- **KV/Vector/DocStatus Storage:** PostgreSQL 18 + pgvector 0.8.1 via pg0
- **Graph Storage:** NetworkX (file-based, LightRAG default) -- avoids Apache AGE dependency
- **Text Extraction:** Kreuzberg (reuse existing) for PDF->text (post convert-lo)
- **LLM:** Configurable via litellm (Ollama, OpenAI, OpenRouter, etc.)
- **Frontend:** LightRAG WebUI (optional, React + graph visualization)

### Why LightRAG + pg0?

| Feature | Current (3gpp-ai) | LightRAG + pg0 |
|---------|-------------------|----------------|
| Input->Text | Mixed Office/PDF (legacy) | PDF-first (post-convert-lo) via Kreuzberg |
| Knowledge Graph | Custom regex patterns | LLM entity extraction (LightRAG algorithm) |
| Query Modes | Basic vector search | 6 modes (naive, local, global, hybrid, mix, bypass) |
| Vector Storage | LanceDB (embedded) | pgvector via pg0 (embedded) |
| Graph Storage | Custom Python | NetworkX (LightRAG default) |
| LLM Caching | None | Built-in (kv_store_llm_response_cache) |
| Workspace isolation | Manual | Built-in (per-workspace index prefixes) |
| Database | LanceDB file | PostgreSQL 18 via pg0 (single binary, ~50MB) |
| Frontend | CLI only | CLI + optional LightRAG WebUI |
| Reranker | None | Built-in (Cohere, Jina, BAAI) |
| Docker required | No | No |
| Windows support | Yes | Yes (pg0 + pure Python) |

### Key Components

1. **LightRAG** (Python library)
   - `pip install lightrag-hku` / `uv add lightrag-hku`
   - Async-first API (`await rag.ainsert()`, `await rag.aquery()`)
   - LLM-powered entity-relationship extraction with gleaning
   - 6 query modes, citation tracking, workspace isolation
   - Optional REST API server via `lightrag-server`

2. **pg0** (Embedded PostgreSQL)
   - Zero-config, single binary (~50MB)
   - PostgreSQL 18 + pgvector 0.8.1 bundled
   - Python SDK: `from pg0 import Pg0`
   - Data stored in `~/.pg0/instances/<name>/data/`
   - Note: Does NOT include Apache AGE (graph extension)

3. **Storage Split**
   - **pg0 handles:** KV cache, vector embeddings, doc status (3 of 4 storage types)
   - **NetworkX handles:** Entity-relationship graph (file-based, LightRAG default)
   - This avoids the Apache AGE dependency entirely

### Why pg0 Over OpenSearch?

| Aspect | pg0 | OpenSearch |
|--------|-----|-----------|
| Weight | ~50MB single binary | ~500MB+ JVM process, 4GB heap |
| Startup | < 2 seconds | ~15 seconds |
| Windows | Native binary | Zip archive + JDK |
| Extensions | pgvector bundled | k-NN plugin bundled |
| Graph support | No AGE -> use NetworkX | OpenSearchGraphStorage available |
| External process | Small | Heavy |
| Maturity | 42 stars, 1 contributor | Massive project, full ecosystem |
| LightRAG coverage | 3/4 storage types | 4/4 storage types |

**Recommendation:** pg0 for development and small-to-medium datasets (typical 3GPP meeting scope: 100-500 TDocs). OpenSearch remains a viable production alternative if graph query performance on NetworkX becomes a bottleneck.

## Architecture Diagram

```
+---------------------------------------------------------------------------+
|                        3GPP Crawler Application                           |
+---------------------------------------------------------------------------+
|                                                                           |
|  +-----------------+     +-----------------+     +-----------------+      |
|  |   CLI Commands  |     |  Crawler Core   |     |   Database      |      |
|  |  (src/cli/...)  |     |  (src/tdoc_..)  |     |   (SQLite)      |      |
|  +--------+--------+     +-----------------+     +-----------------+      |
|           |                                                               |
|           | 3gpp-ai rag query / status                      |
|           v                                                               |
|  +---------------------------------------------------------------------+ |
|  |                    TDoc Processor (Python)                           | |
|  |  * Text extraction (Kreuzberg) from PDF (post convert-lo)          | |
|  |  * rag.ainsert(text) -- LightRAG handles chunking/embedding/graph   | |
|  |  * Progress tracking & error handling                               | |
|  +---------------------------------------------------------------------+ |
|           |                                                               |
|           | Python async API (no HTTP, no subprocess)                     |
|           v                                                               |
|  +---------------------------------------------------------------------+ |
|  |                    LightRAG (Python library)                         | |
|  |  * Entity extraction (LLM-powered, 7+ types)                        | |
|  |  * Relationship mapping + community detection                       | |
|  |  * 6 query modes (naive, local, global, hybrid, mix, bypass)        | |
|  |  * LLM response caching (avoids repeated API calls)                 | |
|  |  * Workspace isolation                                              | |
|  +---------------------------------------------------------------------+ |
|           |                            |                                  |
|           | asyncpg + pgvector         | NetworkX (file I/O)              |
|           v                            v                                  |
|  +----------------------+    +----------------------+                     |
|  |  pg0 (PostgreSQL 18) |    |  Graph Files          |                    |
|  |  * PGKVStorage       |    |  * NetworkX JSON      |                    |
|  |  * PGVectorStorage   |    |  * Entity nodes       |                    |
|  |  * PGDocStatusStorage|    |  * Relationship edges  |                   |
|  |  * pgvector 0.8.1    |    |  * ~/.lightrag/<ws>/  |                    |
|  +----------------------+    +----------------------+                     |
+---------------------------------------------------------------------------+
```

## Phases

### Phase 0: Feasibility Validation ✅ COMPLETE

**Deliverable:** Confirmed that LightRAG works on Windows with file-based storage.

#### 0.1 Verify lightrag-hku Install ✅

- [x] Install LightRAG into the 3gpp-ai package:

  ```bash
  uv add --package 3gpp-ai lightrag-hku
  ```

- [x] Verify the library is importable:

  ```python
  python -c "from lightrag import LightRAG, QueryParam; print('OK')"
  ```

- [x] Check transitive dependencies don't conflict with existing packages:

  ```bash
  uv pip check
  ```

**Result:** lightrag-hku v1.4.9.3 installed successfully, no conflicts.

#### 0.2 Verify pg0-embedded Install ❌ BLOCKED

- [x] Install pg0-embedded:

  ```bash
  uv add --package 3gpp-ai pg0-embedded
  ```

- [ ] ~~Verify pg0 starts on Windows~~ **BLOCKED: Corrupted bundled PostgreSQL archive**

**Result:** pg0-embedded v0.12.0 installs but fails on Windows with `IO error: invalid gzip header` when extracting the bundled PostgreSQL 18.1.0 binary. The `POSTGRESQL_BUNDLE` embedded in the Windows wheel is corrupted. Even the CLI at `.venv\Lib\site-packages\pg0\bin\pg0.exe` fails.

**Action Required:** User claims to have fixed pg0 CLI but `pg0 start` still fails with same error. Awaiting proper fix.

#### 0.3 LightRAG Smoke Test ✅ (File-based Storage)

- [x] Run LightRAG with file-based storage (NanoVectorDB + NetworkX + JsonKV):

  ```python
  import asyncio
  from lightrag import LightRAG, QueryParam
  from lightrag.llm.ollama import ollama_model_complete, ollama_embed
  from lightrag.kg.shared_storage import initialize_pipeline_status

  async def smoke_test():
      # Embedding function must have embedding_dim attribute
      async def embed_func(texts, **kwargs):
          return await ollama_embed(texts, embed_model='qwen3-embedding:0.6b', host='http://localhost:11434', **kwargs)
      embed_func.embedding_dim = 1024  # qwen3-embedding:0.6b dimension

      rag = LightRAG(
          working_dir="./test_rag",
          llm_model_func=ollama_model_complete,
          llm_model_name='minimax-m2.7:cloud',
          llm_model_kwargs={'host': 'http://localhost:11434'},
          embedding_func=embed_func,
          kv_storage='JsonKVStorage',
          vector_storage='NanoVectorDBStorage',
          doc_status_storage='JsonDocStatusStorage',
          graph_storage='NetworkXStorage',
      )
      await rag.initialize_storages()
      await initialize_pipeline_status()  # Required!

      # Insert a test document
      await rag.ainsert("This is a test TDoc S4-250001 about TS 26.444.")

      # Verify graph was created
      print(f"Entities: {rag.chunk_entity_relation_graph}")

      await rag.finalize_storages()

  asyncio.run(smoke_test())
  ```

- [x] Verify: entities extracted, graph nodes created

**Result:** ✅ Document insertion successful. 2 entities, 1 relation extracted. Graph written with 2 nodes, 1 edge.

#### 0.4 Go/No-Go Decision

- [x] **LightRAG works with file-based storage:** Proceed to Phase 1 with file-based storage
- [x] **pg0 blocked on Windows:** Use file-based storage for development; consider external PostgreSQL for production
- [x] **OpenSearch NOT available in LightRAG:** Removed from alternatives (PLAN.md was incorrect)

### Phase 1: Configuration and Wrapper

**Deliverable:** Pydantic config module and thin LightRAG wrapper with pg0 lifecycle management.

#### 1.1 Install Dependencies

- [ ] Add to 3gpp-ai package:

  ```bash
  uv add --package 3gpp-ai lightrag-hku pg0-embedded
  ```

#### 1.2 Create Configuration Module

- [ ] Create `packages/3gpp-ai/threegpp_ai/lightrag/config.py`:

  ```python
  from pydantic import Field
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class LightRAGConfig(BaseSettings):
      """Configuration for LightRAG integration."""

      # pg0 PostgreSQL settings
      pg0_instance_name: str = Field(default="3gpp-crawler")
      pg0_port: int = Field(default=15432)
      pg0_database: str = Field(default="tdoc")

      # LLM settings
      llm_provider: str = Field(default="ollama")
      llm_model: str = Field(default="qwen3:8b")
      llm_api_key: str | None = Field(default=None)
      llm_host: str = Field(default="http://localhost:11434")

      # Embedding settings
      embedding_model: str = Field(default="qwen3-embedding:0.6b")
      embedding_host: str = Field(default="http://localhost:11434")

      # LightRAG working directory
      working_dir: str = Field(default="~/.3gpp-crawler/lightrag")

      @property
      def pg_uri(self) -> str:
          return f"postgresql://postgres:postgres@localhost:{self.pg0_port}/{self.pg0_database}"

      model_config = SettingsConfigDict(env_prefix="LIGHTRAG_")
  ```

#### 1.3 Create pg0 Manager

- [ ] Create `packages/3gpp-ai/threegpp_ai/lightrag/pg0_manager.py`:

  ```python
  import logging
  from contextlib import contextmanager

  from pg0 import Pg0

  from .config import LightRAGConfig

  logger = logging.getLogger(__name__)


  class Pg0Manager:
      """Manages pg0 PostgreSQL instance for LightRAG storage."""

      def __init__(self, config: LightRAGConfig | None = None):
          self.config = config or LightRAGConfig()
          self._pg: Pg0 | None = None

      def start(self) -> str:
          """Start pg0 and return connection URI."""
          self._pg = Pg0(
              name=self.config.pg0_instance_name,
              port=self.config.pg0_port,
              database=self.config.pg0_database,
          )
          self._pg.start()
          self._pg.execute("CREATE EXTENSION IF NOT EXISTS vector")
          logger.info("pg0 started on port %d with pgvector", self.config.pg0_port)
          return self.config.pg_uri

      def stop(self) -> None:
          """Stop pg0 instance."""
          if self._pg:
              self._pg.stop()
              logger.info("pg0 stopped")

      @contextmanager
      def running(self):
          """Context manager for pg0 lifecycle."""
          try:
              yield self.start()
          finally:
              self.stop()
  ```

#### 1.4 Create LightRAG Wrapper

- [ ] Create `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`:

  ```python
  import logging
  from pathlib import Path

  from lightrag import LightRAG, QueryParam

  from .config import LightRAGConfig
  from .pg0_manager import Pg0Manager

  logger = logging.getLogger(__name__)


  class TDocRAG:
      """Thin wrapper around LightRAG with pg0 lifecycle management."""

      def __init__(self, config: LightRAGConfig | None = None):
          self.config = config or LightRAGConfig()
          self.pg0 = Pg0Manager(self.config)
          self._rag: LightRAG | None = None

      async def start(self, workspace: str = "default") -> None:
          """Start pg0 and initialize LightRAG."""
          self.pg0.start()

          working_dir = Path(self.config.working_dir).expanduser() / workspace
          working_dir.mkdir(parents=True, exist_ok=True)

          self._rag = LightRAG(
              working_dir=str(working_dir),
              workspace=workspace,

              # LLM -- configurable per provider
              llm_model_func=self._get_llm_func(),
              llm_model_name=f"{self.config.llm_provider}/{self.config.llm_model}",

              # Embedding
              embedding_func=self._get_embedding_func(),
              embedding_model_name=f"{self.config.llm_provider}/{self.config.embedding_model}",

              # pg0 for KV, Vector, DocStatus
              kv_storage="PGKVStorage",
              vector_storage="PGVectorStorage",
              doc_status_storage="PGDocStatusStorage",

              # NetworkX for graph (file-based, avoids AGE dependency)
              graph_storage="NetworkXStorage",
          )
          await self._rag.initialize_storages()
          logger.info("LightRAG started for workspace '%s'", workspace)

      async def stop(self) -> None:
          """Finalize LightRAG and stop pg0."""
          if self._rag:
              await self._rag.finalize_storages()
          self.pg0.stop()

      async def insert(self, text: str) -> None:
          """Insert document text into the knowledge graph."""
          await self._rag.ainsert(text)

      async def query(self, query: str, mode: str = "hybrid") -> str:
          """Query the knowledge graph."""
          return await self._rag.aquery(
              query,
              param=QueryParam(mode=mode),
          )

      def _get_llm_func(self):
          from lightrag.llm.openai import openai_complete_if_cache
          return openai_complete_if_cache

      def _get_embedding_func(self):
          from lightrag.llm.openai import openai_embed
          return openai_embed
  ```

#### 1.5 Create Package Init

- [ ] Create `packages/3gpp-ai/threegpp_ai/lightrag/__init__.py`:

  ```python
  """LightRAG integration for 3gpp-ai."""

  from .config import LightRAGConfig
  from .pg0_manager import Pg0Manager
  from .rag import TDocRAG

  __all__ = [
      "LightRAGConfig",
      "Pg0Manager",
      "TDocRAG",
  ]
  ```

### Phase 2: Document Processing Pipeline

**Deliverable:** TDoc documents extracted and inserted into LightRAG.

#### 2.1 Create TDoc Processor

- [x] Create `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`:

  ```python
  import logging
  from pathlib import Path
  from typing import Iterator

  from kreuzberg import extract_file

  from .config import LightRAGConfig
  from .rag import TDocRAG

  logger = logging.getLogger(__name__)

    SUPPORTED_FORMATS = {".pdf"}


  class TDocProcessor:
      """Processes TDoc documents through LightRAG."""

      def __init__(self, config: LightRAGConfig | None = None):
          self.config = config or LightRAGConfig()
          self.rag = TDocRAG(self.config)

      async def process_file(self, file_path: Path, workspace: str) -> dict:
          """Extract text from a file and insert into LightRAG."""
          suffix = file_path.suffix.lower()
          if suffix not in SUPPORTED_FORMATS:
              return {"file": str(file_path), "status": "skipped", "reason": f"unsupported format: {suffix}"}

          try:
              result = await extract_file(file_path)
              text = result.content

              if not text or len(text.strip()) < 50:
                  return {"file": str(file_path), "status": "skipped", "reason": "insufficient content"}

              await self.rag.insert(text)
              return {"file": str(file_path), "status": "success", "chars": len(text)}
          except Exception as e:
              logger.error("Failed to process %s: %s", file_path, e)
              return {"file": str(file_path), "status": "error", "error": str(e)}

      async def process_folder(
          self,
          folder: Path,
          workspace: str,
      ) -> Iterator[dict]:
          """Process all supported documents in a folder."""
          await self.rag.start(workspace)
          try:
              for file_path in sorted(folder.rglob("*")):
                  if file_path.suffix.lower() in SUPPORTED_FORMATS:
                      yield await self.process_file(file_path, workspace)
          finally:
              await self.rag.stop()
  ```

### Phase 3: CLI Integration

**Deliverable:** Updated CLI commands to use LightRAG.

#### 3.1 Create AI CLI Module

- [x] Create `packages/3gpp-ai/threegpp_ai/lightrag/cli.py`:

  ```python
  import asyncio
  import logging
  from pathlib import Path

  import typer
  from rich.console import Console

  from .config import LightRAGConfig
  from .rag import TDocRAG

  app = typer.Typer(name="rag", help="LightRAG knowledge graph commands")
  console = Console()
  logger = logging.getLogger(__name__)


  @app.command("query")
  def query_graph(
      query: str = typer.Argument(..., help="Query string"),
      mode: str = typer.Option("hybrid", "--mode", "-m", help="Query mode: naive, local, global, hybrid, mix, bypass"),
      workspace: str = typer.Option("default", "--workspace", "-w"),
  ):
      """Query the LightRAG knowledge graph."""
      async def _run():
          rag = TDocRAG()
          await rag.start(workspace)
          try:
              result = await rag.query(query, mode=mode)
              console.print(result)
          finally:
              await rag.stop()

      asyncio.run(_run())


  @app.command("status")
  def show_status():
      """Show LightRAG stack status."""
      config = LightRAGConfig()
      console.print(f"[cyan]pg0 instance:[/cyan] {config.pg0_instance_name}")
      console.print(f"[cyan]pg0 port:[/cyan] {config.pg0_port}")
      console.print(f"[cyan]LLM:[/cyan] {config.llm_provider}/{config.llm_model}")
      console.print(f"[cyan]Embedding:[/cyan] {config.embedding_model}")
      console.print(f"[cyan]Working dir:[/cyan] {config.working_dir}")
  ```

#### 3.2 Integrate with Main AI CLI

- [x] Update `src/tdoc_crawler/cli/ai_app.py` to include LightRAG commands:

  ```python
  from tdoc_ai.lightrag.cli import app as rag_app

  app.add_typer(rag_app, name="rag")
  ```

### Phase 4: 3GPP Metadata Enrichment

**Deliverable:** Fixed-key 3GPP metadata is validated, normalized, and deterministically prepended before LightRAG insertion.

#### 4.1 Enrich LightRAG with Structured Metadata

The existing tdoc-crawler already stores structured 3GPP metadata (TDoc IDs, spec references, meeting codes, companies) in SQLite. Since the LightRAG stage receives converted PDF files plus fixed-key metadata dictionaries, enrichment should be schema-first and deterministic instead of ad hoc dictionary lookups.

- [ ] Define a typed metadata contract (Pydantic model) for enrichment with at least:
  - `tdoc_id` (required)
  - `title`, `source`, `meeting` (optional)
  - `spec_refs` (list[str], default empty list)
  - `release`, `wg` (optional, if available from SQLite)

- [ ] Add normalization before enrichment:
  - `tdoc_id` uppercased and stripped
  - `spec_refs` normalized into stable display form
  - missing required fields cause explicit skip/error status

- [ ] Before `rag.ainsert(text)`, prepend a deterministic structured metadata header:

  ```python
  from pydantic import BaseModel, Field

  class RAGMetadata(BaseModel):
      tdoc_id: str
      title: str | None = None
      source: str | None = None
      spec_refs: list[str] = Field(default_factory=list)
      meeting: str | None = None
      release: str | None = None
      wg: str | None = None

  def enrich_text(metadata: RAGMetadata, text: str) -> str:
      """Prepend normalized metadata to document text for deterministic extraction."""
      header_lines = [f"Document: {metadata.tdoc_id}"]
      if metadata.title:
          header_lines.append(f"Title: {metadata.title}")
      if metadata.source:
          header_lines.append(f"Source: {metadata.source}")
      if metadata.spec_refs:
          header_lines.append(f"Related Specifications: {', '.join(metadata.spec_refs)}")
      if metadata.meeting:
          header_lines.append(f"Meeting: {metadata.meeting}")
      if metadata.release:
          header_lines.append(f"Release: {metadata.release}")
      if metadata.wg:
          header_lines.append(f"Working Group: {metadata.wg}")

      header = "\n".join(header_lines)
      return f"{header}\n\n{text}"
  ```

- [ ] Add tests proving deterministic header output for identical metadata input and explicit behavior on missing required keys

- [ ] This ensures LightRAG's LLM extraction picks up exact TDoc IDs, spec references, and meeting associations that regex-based extraction currently handles

#### 4.2 Post-Indexing Entity Seeding (Optional)

LightRAG supports `edit_entity()` and `create_entity()` APIs. For known 3GPP entities not captured by LLM extraction:

- [ ] Evaluate whether post-indexing entity injection improves query quality
- [ ] If beneficial, create a seeding script that reads SQLite metadata and creates entities

### Phase 5: Deprecation and Cleanup

**Deliverable:** Old pipeline code removed, dependencies updated.

#### 5.1 Remove Old Pipeline Code

- [ ] Delete or deprecate:
  - `packages/3gpp-ai/threegpp_ai/operations/pipeline.py`
  - `packages/3gpp-ai/threegpp_ai/operations/embeddings.py`
  - `packages/3gpp-ai/threegpp_ai/operations/graph.py`
  - `packages/3gpp-ai/threegpp_ai/storage.py`
    - `packages/3gpp-ai/threegpp_ai/__init__.py` legacy exports pointing to old pipeline
    - `src/tdoc_crawler/cli/ai_app.py` legacy dynamic loader imports for old pipeline modules

#### 5.2 Update Dependencies

- [ ] Remove from `pyproject.toml`:
  - `lancedb` (replaced by pg0/pgvector)
  - `sentence-transformers` (handled by LightRAG embedding functions)
  - `edgequake-sdk` (dropped)

- [ ] Add to `pyproject.toml`:
  - `lightrag-hku`
  - `pg0-embedded`

#### 5.3 Update Documentation

- [ ] Update `packages/3gpp-ai/README.md`
- [ ] Update CLI help text and examples

### Phase 6: Testing and Validation

**Deliverable:** Tests covering new pipeline, integration verified.

#### 6.1 Unit Tests

- [ ] `packages/3gpp-ai/tests/test_lightrag_config.py`
- [ ] `packages/3gpp-ai/tests/test_pg0_manager.py`
- [ ] `packages/3gpp-ai/tests/test_rag_wrapper.py`
- [ ] `packages/3gpp-ai/tests/test_processor.py`

#### 6.2 Integration Tests

- [ ] Test full pipeline: pg0 start -> insert document -> query -> pg0 stop
- [ ] Test workspace isolation: two workspaces, queries don't cross-contaminate
- [ ] Test LLM response caching: re-inserting same document doesn't call LLM again

#### 6.3 Validation Criteria

- [ ] **Startup:** pg0 + LightRAG initialize within 10 seconds
- [ ] **Ingestion:** 100 TDocs processed (text extraction + LLM extraction + embedding)
- [ ] **Query:** All 6 modes return non-empty results, latency < 2s for hybrid mode
- [ ] **Idempotency:** Re-processing same documents produces same graph

## Alternative Storage: OpenSearch

If pg0 proves insufficient (e.g., fails Windows validation, performance issues with large datasets), OpenSearch provides a unified backend for all 4 LightRAG storage types:

```python
rag = LightRAG(
    kv_storage="OpenSearchKVStorage",
    vector_storage="OpenSearchVectorDBStorage",
    graph_storage="OpenSearchGraphStorage",
    doc_status_storage="OpenSearchDocStatusStorage",
)
```

OpenSearch runs on Windows via zip archive (no Docker). See investigation report for details. The plan's structure remains identical -- only the storage configuration changes.

## Open Questions

1. **LLM Provider Selection:** Default to Ollama (local, free) or require cloud provider?
   - Recommendation: Ollama for development. LightRAG recommends 32B+ models for quality entity extraction. Qwen3-30B or similar.

2. **Embedding Provider:** Use Ollama (local) or sentence-transformers?
   - Recommendation: Ollama with qwen3-embedding:0.6b (available in 3gpp-ai workspace)

3. **Graph Storage Scaling:** NetworkX (file-based) vs. PostgreSQL AGE vs. OpenSearch?
   - Recommendation: Start with NetworkX. For typical 3GPP meeting scope (100-500 TDocs), file-based graph is sufficient. Migrate to OpenSearch only if performance becomes an issue.

4. **Metadata Contract Strictness:** Which metadata keys are required to proceed with insertion?
    - Recommendation: Require `tdoc_id`; treat all other fields as optional but normalized. On missing required fields, emit explicit skip/error result.

5. **LightRAG WebUI:** Deploy alongside CLI?
   - Recommendation: Optional. `lightrag-server` provides an Ollama-compatible REST API + React WebUI for graph visualization. Useful for debugging, not required for pipeline.

## Progress

- [x] (2026-03-23) Created original PLAN.md for EdgeQuake + pg0
- [x] (2026-03-23) Plan review: identified 3 blockers, 7 risks, 5 document errors
- [x] (2026-03-23) Fixed document errors, added Phase 0 feasibility validation
- [x] (2026-03-23) EdgeQuake dropped -- no Windows support
- [x] (2026-03-23) Investigated LightRAG (30K stars, EMNLP 2025, pure Python)
- [x] (2026-03-23) Investigated OpenSearch (Windows zip, unified backend)
- [x] (2026-03-23) Investigated LightRAG PostgreSQL impl (5897 lines) -- AGE required for PGGraphStorage
- [x] (2026-03-23) Determined pg0 can handle 3/4 storage types (KV, Vector, DocStatus), NetworkX for graph
- [x] (2026-03-23) Rewrote PLAN.md for LightRAG + pg0 architecture
- [x] (2026-03-23) Phase 0 complete: LightRAG v1.4.9.3 + qwen3-embedding:0.6b smoke test PASSED (7 entities, 6 relations extracted)
- [x] (2026-03-23) Phase 1 complete: LightRAG package created (config.py, pg0_manager.py, rag.py, dunder init module)
- [x] (2026-03-23) Phase 1 refactored: Config split into LLMConfig, EmbeddingConfig, DatabaseConfig; StorageBackend/QueryMode StrEnums; EMBEDDING_DIMENSIONS dict
- [x] (2026-03-23) Phase 2 complete: TDocProcessor created (processor.py with kreuzberg extraction)
- [x] (2026-03-23) Phase 3 complete: CLI created (cli.py with rag query/status commands)
- [x] (2026-03-23) Phase 3 patch: integrated `ai rag` subcommands into main CLI (ai_app.add_typer)
- [x] (2026-03-23) Workspace propagation fix: `--workspace` now reaches LightRAG start in query and folder processing
- [x] (2026-03-23) Plan refinement: adopted PDF-first ingestion assumption (post convert-lo) and schema-driven Phase 4 metadata enrichment
- [x] (2026-03-23) Phase 4.1 complete: Metadata enrichment (RAGMetadata model, enrich_text(), create_metadata_from_dict())
- [x] (2026-03-23) Phase 4.2 complete: Entity seeder (EntitySeeder with seed_tdoc/seed_spec/seed_meeting/seed_wg)
- [x] (2026-03-23) Phase 5.1 complete: Removed legacy pipeline.py, graph.py
- [x] (2026-03-23) Phase 5.2 complete: Updated pyproject.toml (removed lancedb, sentence-transformers, etc.)
- [x] (2026-03-23) Phase 5.3 complete: Updated __init__.py exports (LightRAG only)
- [x] (2026-03-23) Phase 5.4 complete: Removed broken CLI commands (ai query/process/status)
- [x] (2026-03-23) Phase 6.1 complete: Unit tests (test_lightrag_config.py: 11 tests, test_metadata.py: 11 tests)
- [x] (2026-03-23) Phase 6.2 complete: Integration tests (test_integration.py: 4 async tests)
- [x] (2026-03-23) Phase 6.3 validation: Startup <10s ✓, Insert/query works ✓, Workspace isolation ✓
- [x] (2026-03-23) Rename fix: Updated PLAN.md defaults from `tdoc-crawler` to `3gpp-crawler`
- [ ] Phase 7: 3gpp-ai package cleanup (dead code removal, linter issues)
- [ ] Phase 6.3 validation: Query latency <2s (manual validation needed)
- [ ] Phase 6.3 validation: Idempotency (manual validation needed)

### Phase 7: 3gpp-ai Package Cleanup

**Goal:** Remove dead code from the LightRAG migration, streamline exports, and fix remaining linter issues.

#### 7.1 Dead Code Removal

The following modules are obsolete (replaced by LightRAG pipeline):

| Module | Lines | Reason for Deletion |
|--------|-------|---------------------|
| `tdoc_ai/storage.py` | 558 | LanceDB wrapper - replaced by LightRAG native storage |
| `tdoc_ai/operations/embeddings.py` | 412 | sentence-transformers - replaced by LightRAG embedding functions |
| `tdoc_ai/config.py` | 213 | `AiConfig` - replaced by `LightRAGConfig` with sub-configs |

**Partial deprecation** (retain minimal types, remove rest):
| Module | Action | Lines Saved |
|--------|--------|-------------|
| `tdoc_ai/models.py` | Remove `GraphNode`, `GraphEdge`, `DocumentChunk`, `DocumentClassification` - only keep `ProcessingStatus`, `PipelineStage`, `SourceKind` | ~280 |

#### 7.2 __init__.py Cleanup

Current state exports 40+ symbols including legacy ones. Target: clean separation.

**Remove from exports:**
- `AiConfig` (replaced by `LightRAGConfig`)
- `AiStorage` (LanceDB, dead)
- `EmbeddingsManager` (sentence-transformers, dead)
- `create_embeddings_manager()` (LanceDB factory, dead)
- `DocumentChunk`, `DocumentClassification` (LanceDB schema, dead)
- `GraphNode`, `GraphEdge` (custom graph schema, dead)

**Keep exports:**
```python
# Document operations (still used by both pipelines)
from tdoc_ai.operations.convert import convert_tdoc as convert_document
from tdoc_ai.operations.summarize import SummarizeResult, summarize_tdoc as summarize_document

# Workspace management (still used)
from tdoc_ai.operations.workspace_registry import (
    DEFAULT_WORKSPACE, WorkspaceDisplayInfo, WorkspaceRegistry,
    get_active_workspace, set_active_workspace,
)
from tdoc_ai.operations.workspaces import (
    add_workspace_members, checkout_spec_to_workspace, checkout_tdoc_to_workspace,
    create_workspace, delete_workspace, ensure_ai_subfolder, ensure_default_workspace,
    get_workspace, get_workspace_member_counts, is_default_workspace,
    list_workspace_members, list_workspaces, make_workspace_member,
    normalize_workspace_name, remove_invalid_members,
    resolve_tdoc_checkout_path, resolve_workspace,
)

# LightRAG (new)
from tdoc_ai.lightrag import (
    DatabaseConfig, EmbeddingConfig, LightRAGConfig, LLMConfig,
    Pg0Error, Pg0Manager, ProcessingResult, ProcessingResultStatus,
    QueryMode, RAGMetadata, StorageBackend,
    TDocProcessor, TDocRAG, create_metadata_from_dict, enrich_text,
)

# Shared
from tdoc_ai.context import DocumentContext
from tdoc_ai.models import PipelineStage, ProcessingStatus, SourceKind
from tdoc_crawler.config import CacheManager
```

#### 7.3 Linter Issues

Current: ~108 remaining issues in 3gpp-ai package.

Target: 0 issues (or justified exceptions for test files).

#### 7.4 Additional Rename Work

Due to `tdoc-crawler` → `3gpp-crawler` rename:

| Location | Issue | Fix |
|----------|-------|-----|
| `packages/3gpp-ai/pyproject.toml` | Repository URL still references `tdoc-crawler` | Update to `3gpp-crawler` |
| `packages/3gpp-ai/README.md` | References to `tdoc-crawler` | Update to `3gpp-crawler` |
| `demo.bat` | Uses `tdoc-crawler` CLI | Update to `3gpp-ai` where appropriate |
| `docs/ai.md` | References `tdoc-crawler ai` | Update to `3gpp-ai` |

#### 7.5 Verify No Regressions

Before declaring Phase 7 complete, verify:
- [ ] `3gpp-ai --help` shows all commands
- [ ] `3gpp-ai rag status` works
- [ ] `3gpp-ai rag query "test"` works
- [ ] `3gpp-ai summarize <doc>` still works (uses litellm directly)
- [ ] Workspace operations still work

## Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Drop EdgeQuake | No Windows binary, Rust-only | 2026-03-23 |
| Adopt LightRAG | Pure Python, 30K stars, EMNLP 2025, 6 query modes, async API | 2026-03-23 |
| Use qwen3-embedding:0.6b | Available in Ollama, 1024-dim vectors, works with LightRAG | 2026-03-23 |
| Structured config | Split into LLMConfig, EmbeddingConfig, DatabaseConfig with StrEnums | 2026-03-23 |
| File-based storage first | pg0 still broken on Windows; use NanoVectorDB + JsonKVStorage for now | 2026-03-23 |
| NetworkX for graph | Avoids Apache AGE dependency; sufficient for meeting-scale datasets | 2026-03-23 |
| OpenSearch as fallback | Unified 4/4 backend if file-based storage becomes bottleneck | 2026-03-23 |
| Pre-enrich text with SQLite metadata | Leverages existing structured data without duplicating extraction logic | 2026-03-23 |
| PDF-first ingestion at LightRAG stage | convert-lo pipeline already normalizes documents to PDF artifacts; reduces extractor complexity and ambiguity | 2026-03-23 |
| Schema-driven metadata enrichment | Fixed-key metadata dictionaries should be validated and normalized before deterministic header generation | 2026-03-23 |
| Code quality via cytoscnpy-mcp | Automated analysis for dead code, complexity, maintainability (target MI ≥60, complexity ≤10) | 2026-03-23 |

## References

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG) -- 30K+ stars, 233 contributors
- [LightRAG Paper](https://arxiv.org/abs/2410.05779) -- EMNLP 2025
- [LightRAG PyPI](https://pypi.org/project/lightrag-hku/) -- v1.4.11
- [LightRAG PostgreSQL Implementation](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py) -- 5897 lines, PGKVStorage + PGVectorStorage + PGGraphStorage + PGDocStatusStorage
- [pg0 GitHub](https://github.com/vectorize-io/pg0) -- PostgreSQL 18 + pgvector 0.8.1
- [pg0 PyPI](https://pypi.org/project/pg0-embedded/) -- v0.12.0
- [OpenSearch Windows Install](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/windows/) -- zip archive, no Docker
