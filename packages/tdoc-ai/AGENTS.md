# tdoc-ai

AI-powered document processing for 3GPP TDocs (knowledge graphs, semantic search, summarization).

## Package Structure

```
packages/tdoc-ai/tdoc_ai/
├── __init__.py           # Public API exports
├── config.py             # AiConfig (legacy, for summarize only)
├── context.py            # DocumentContext
├── models.py             # Pydantic models (ProcessingStatus, etc.)
├── storage.py            # AiStorage (legacy, LanceDB-based)
├── lightrag/             # NEW: LightRAG integration
│   ├── __init__.py
│   ├── cli.py            # rag query/status commands
│   ├── config.py         # LightRAGConfig + sub-configs
│   ├── metadata.py       # RAGMetadata, enrich_text()
│   ├── pg0_manager.py   # Pg0Manager
│   ├── processor.py      # TDocProcessor
│   ├── rag.py            # TDocRAG wrapper
│   └── seeder.py        # EntitySeeder
└── operations/
    ├── classify.py       # Document classification
    ├── convert.py        # Document conversion
    ├── embeddings.py     # EmbeddingsManager (legacy)
    ├── extract.py        # Text extraction
    ├── summarize.py      # LLM summarization (LiteLLM)
    ├── workspace_*.py    # Workspace management
```

## Key Design Patterns

### LightRAG Integration (New)

The new pipeline uses LightRAG for knowledge graph construction:

```python
from tdoc_ai import LightRAGConfig, TDocRAG, TDocProcessor

config = LightRAGConfig()
rag = TDocRAG(config)
await rag.start("my-workspace")
```

### Summarization (Legacy, Still Active)

Uses LiteLLM directly for on-demand summaries:

```python
from tdoc_ai import summarize_document

summary = summarize_document("S4-250001", markdown_content)
```

## Configuration

### LightRAG (New)

Environment-based via `LightRAGConfig`:
- `LIGHTRAG_LLM_MODEL` - LLM model (default: `qwen3:8b`)
- `LIGHTRAG_EMBEDDING_MODEL` - Embedding model (default: `qwen3-embedding:0.6b`)
- `LIGHTRAG_WORKING_DIR` - Working directory (default: `~/.3gpp-crawler/lightrag`)

### Summarization (Legacy)

Uses `AiConfig.from_env()`:
- `TDC_AI_LLM_MODEL` - LLM model (default: `openrouter/openrouter/free`)
- `TDC_AI_LLM_API_KEY` - API key for LLM

## Storage Layer

### LightRAG (New)

File-based storage by default:
- NanoVectorDB for embeddings
- JsonKVStorage for cache
- NetworkX for knowledge graph

Optionally use pg0 for PostgreSQL-backed storage.

### Legacy (Still Active)

AiStorage uses LanceDB for status tracking in extract/summarize pipelines.

## CLI Integration

Exposed via `3gpp-ai` commands:

```bash
3gpp-ai rag query "your query"
3gpp-ai rag status
3gpp-ai summarize S4-250001
```

## Import Guidelines

```python
# LightRAG integration (preferred)
from tdoc_ai import (
    LightRAGConfig,
    TDocRAG,
    TDocProcessor,
    RAGMetadata,
    enrich_text,
)

# Document operations (still used)
from tdoc_ai import convert_document, summarize_document

# Workspace management (still used)
from tdoc_ai import create_workspace, list_workspaces
```

## Pipeline Stages (Legacy)

Order: **CLASSIFY** → **EXTRACT** → **EMBED** → **GRAPH**

LightRAG handles embedding and graph construction automatically.

## Deprecated/Removed

- `create_embeddings_manager()` - Removed from public API
- `AiStorage` - Legacy, still used internally by extract/summarize
- `EmbeddingsManager` - Legacy, still used internally
- LanceDB-based storage - Replaced by LightRAG native storage
