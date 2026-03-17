# Assistant Rules for tdoc-ai Package

## Overview

The `tdoc-ai` package provides AI-powered document processing for 3GPP TDocs. It handles embeddings, knowledge graphs, summarization, and semantic search. This package is integrated into the main `tdoc-crawler` CLI under the `ai` command group.

## Package Structure

```
src/tdoc-ai/tdoc_ai/
├── __init__.py           # Public API exports, factory functions
├── config.py             # AiConfig (environment-based configuration)
├── models.py             # Pydantic models (ProcessingStatus, DocumentSummary, etc.)
├── storage.py            # AiStorage (LanceDB-based vector storage)
├── operations/
│   ├── pipeline.py       # Main processing pipeline (CLASSIFY → EXTRACT → EMBED → GRAPH)
│   ├── embeddings.py     # EmbeddingsManager (local embedding generation)
│   ├── classify.py       # Document classification
│   ├── extract.py        # DOCX to Markdown extraction
│   ├── summarize.py      # LLM-based summarization
│   ├── graph.py          # Knowledge graph operations
│   ├── convert.py        # Document conversion
│   ├── workspaces.py     # Workspace member management
│   └── workspace_registry.py  # Workspace CRUD
```

## Key Design Patterns

### Factory Pattern for EmbeddingsManager

The `EmbeddingsManager` uses a factory pattern to break the circular dependency between config, storage, and embeddings:

```python
# CORRECT: Use factory method
from tdoc_ai import create_embeddings_manager
manager = create_embeddings_manager()  # or with explicit config
storage = manager.storage  # Access storage via property

# DEPRECATED: Direct instantiation requires careful ordering
from tdoc_ai.operations.embeddings import EmbeddingsManager
manager = EmbeddingsManager.from_config(config)
```

### Pipeline Stages

The processing pipeline runs in order:

1. **CLASSIFY** - Identify main document among multiple files
2. **EXTRACT** - Convert DOCX to Markdown
3. **EMBED** - Generate vector embeddings (local, no LLM required)
4. **GRAPH** - Build knowledge graph

**Note:** Summarization is NOT part of the pipeline. Use `ai summarize <doc_id>` command for on-demand LLM-based summarization.

### Separation: Pipeline vs CLI Summarize

| Command | Purpose | LLM Required |
|---------|---------|--------------|
| `ai workspace process` | Embed documents for semantic search | No |
| `ai summarize <doc>` | Generate LLM summary | Yes |

## Configuration

All configuration is environment-based via `AiConfig.from_env()`:

- `EMBEDDING_MODEL` - Sentence transformer model (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `EMBEDDING_DIMENSION` - Vector dimension (default: 384)
- `LLM_MODEL` - LLM model for summarization (default: `openai/gpt-4o-mini`)
- `LanceDB path` - Storage location

## Storage Layer

AiStorage uses LanceDB for vector storage:
- Embeddings are stored with document metadata
- Supports workspace-scoped storage
- Provides status tracking (classified, extracted, embedded, graphed)

## CLI Integration

The `tdoc-ai` package is exposed via `tdoc-crawler ai` commands:
- `ai summarize <doc>` - LLM summarization
- `ai query <text>` - Semantic search
- `ai workspace process` - Batch embedding
- `ai workspace list-members` - List workspace contents

## Import Guidelines

```python
# Public API (preferred)
from tdoc_ai import (
    create_embeddings_manager,
    process_document,
    process_all,
    get_status,
    query_graph,
    summarize_document,
)

# Internal operations when needed
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.pipeline import run_pipeline

# Models
from tdoc_ai.models import ProcessingStatus, PipelineStage
```

## Common Tasks

### Processing Documents
```python
from tdoc_ai import process_document
status = process_document("SP-123456", Path("./checkouts/SP-123456"))
```

### Querying
```python
from tdoc_ai import query_graph
results = query_graph("What is the status of 5G NR?", workspace="my_ws")
```

### Creating Embeddings
```python
from tdoc_ai import create_embeddings_manager
manager = create_embeddings_manager()
manager.generate_embeddings(doc_id, artifact_path)
```

## Lessons Learned

1. **No LLM in Pipeline**: The process pipeline runs completely locally using sentence transformers. LLM access is only needed for summarization, which is a separate command.

2. **Factory Pattern**: EmbeddingsManager uses `from_config()` factory to load the embedding model once, extract the dimension, create storage, then return the manager.

3. **Workspace Isolation**: All operations support optional `workspace` parameter for multi-tenant isolation.

4. **Status Tracking**: Each document has a ProcessingStatus tracking completed stages for resume capability.
