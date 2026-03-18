# tdoc-ai

AI-powered document processing for 3GPP TDocs (embeddings, knowledge graphs, semantic search).

## Package Structure

See `src/tdoc-ai/tdoc_ai/` for full module layout.

## Key Design Patterns

### Factory Pattern for EmbeddingsManager

Breaks circular dependency between config, storage, and embeddings:

```python
from tdoc_ai import create_embeddings_manager
manager = create_embeddings_manager()
storage = manager.storage  # Access via property
```

### Pipeline Stages

Order: **CLASSIFY** → **EXTRACT** → **EMBED** → **GRAPH**

**Note:** Summarization is NOT in pipeline. Use `ai summarize <doc_id>` for on-demand LLM summaries.

### Separation: Pipeline vs CLI Summarize

| Command | Purpose | LLM Required |
|---------|---------|--------------|
| `ai workspace process` | Embed documents | No |
| `ai summarize <doc>` | Generate LLM summary | Yes |

## Configuration

Environment-based via `AiConfig.from_env()`:
- `EMBEDDING_MODEL` - Sentence transformer (default: `all-MiniLM-L6-v2`)
- `EMBEDDING_DIMENSION` - Vector dimension (default: 384)
- `LLM_MODEL` - LLM for summarization (default: `openai/gpt-4o-mini`)

## Storage Layer

AiStorage uses LanceDB:
- Embeddings with document metadata
- Workspace-scoped storage
- Status tracking (classified, extracted, embedded, graphed)

## CLI Integration

Exposed via `tdoc-crawler ai` commands. See `src/tdoc_crawler/cli/ai.py`.

## Import Guidelines

```python
# Public API (preferred)
from tdoc_ai import create_embeddings_manager, process_document, query_graph

# Internal operations when needed
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.pipeline import run_pipeline
```

## Lessons Learned

1. **No LLM in Pipeline**: Runs completely locally with sentence transformers
2. **Factory Pattern**: `from_config()` loads model once, extracts dimension, creates storage
3. **Workspace Isolation**: All operations support optional `workspace` parameter
4. **Status Tracking**: `ProcessingStatus` tracks completed stages for resume capability
