# 3gpp-ai

AI-powered document processing for 3GPP TDocs, specs and other documents (knowledge graphs, semantic search, summarization).

## Project Structure

The project structure can be parsed using the following command from the root of the repository:

```shell
rg --files | tree-cli --fromfile
```

## Key Design Patterns

### LightRAG Integration

The 3gpp-ai pipeline uses LightRAG for all document processing:

```python
from tdoc_ai import LightRAGConfig, TDocRAG, TDocProcessor

# Automatically reads TDC_AI_* environment variables
config = LightRAGConfig.from_env()
rag = TDocRAG(config)
await rag.start("my-workspace")
```

### Main APIs

Use `TDocRAG` for workspace-level retrieval and `TDocProcessor` for per-document ingestion.

## Configuration

### LightRAG

Reads from `TDC_AI_*` environment variables (see `.env.example`):

- `TDC_AI_LLM_MODEL` - LLM model in `<provider>/<model>` format (default: `openrouter/openrouter/free`)
- `TDC_AI_LLM_API_BASE` - Custom LLM API base URL (optional)
- `TDC_AI_LLM_API_KEY` - LLM API key (optional, overrides provider-specific env vars)
- `TDC_AI_EMBEDDING_MODEL` - Embedding model ID (default: `sentence-transformers/all-MiniLM-L6-v2`)

LightRAG-specific variables:

- `LIGHTRAG_SHARED_STORAGE` - Enable shared embedding storage (default: `true`)
- `LIGHTRAG_DB_BACKEND` - Storage backend: `file` or `pg0` (default: `file`)

### Path Management

**CRITICAL:** All file paths use `CacheManager` from `tdoc_crawler.config`:

```python
from tdoc_crawler.config import resolve_cache_manager

manager = resolve_cache_manager()
manager.ai_cache_dir       # ~/.3gpp-crawler/lightrag/
manager.ai_embed_dir(model)  # ~/.3gpp-crawler/lightrag/{model}/
```

**NEVER hardcode paths** like `~/.3gpp-crawler` - see root `AGENTS.md` for the full CacheManager pattern.

## Single Source of Truth (SSOT) Principle

**Rule:** Every configuration value, constant, or shared resource must be defined **exactly once** and reused everywhere else.

### What Must Follow SSOT

| Category | Source | Usage |
|----------|--------|-------|
| **Paths** | `CacheManager` | All file/directory paths |
| **API Keys** | Environment variables via `LightRAGConfig` | `config.llm.api_key`, `config.embedding.api_key` |
| **API Base URLs** | Environment variables via `LightRAGConfig` | `config.llm.api_base`, `config.embedding.api_base` |
| **Model Names** | Environment variables via `LightRAGConfig` | `config.llm.model`, `config.embedding.model` |
| **Provider Functions** | `PROVIDERS` registry in `rag.py` | Use `_get_provider(name)` - never inline |
| **Provider Aliases** | `PROVIDER_ALIASES` in `rag.py` | Central mapping (e.g., `zai` → `zhipu`) |
| **Embedding Dimensions** | `EMBEDDING_DIMENSIONS` in `rag.py` or provider config | Never hardcode dimension values |

### Anti-Patterns (NEVER DO)

```python
# ❌ Hardcoded paths
Path.home() / ".3gpp-crawler" / "lightrag"

# ❌ Hardcoded API configuration
api_key = "sk-..."
api_base = "https://api.z.ai/..."

# ❌ Duplicated provider mapping
if provider == "ollama":
    func = ollama_model_complete
elif provider == "zhipu":
    func = zhipu_complete

# ❌ Hardcoded dimension values
if model == "qwen3":
    dim = 1024
```

### Correct Patterns (ALWAYS DO)

```python
# ✅ Paths via CacheManager
manager = resolve_cache_manager()
working_dir = manager.ai_embed_dir(model_name)

# ✅ Configuration via LightRAGConfig
config = LightRAGConfig.from_env()
api_key = config.llm.api_key

# ✅ Provider functions from registry
provider_config = _get_provider(provider_name)
func = provider_config.complete_func

# ✅ Dimensions from config or registry
dim = _get_embedding_dimension(model_name, provider)
```

### Why This Matters

1. **Maintainability**: Change once, update everywhere automatically
1. **Consistency**: No drift between different parts of the code
1. **Testability**: Easy to swap values in tests
1. **Security**: Secrets live in environment variables, not code
1. **DRY**: Eliminates duplicated logic and magic strings/numbers

## Storage Layer

### LightRAG

File-based storage by default:

- NanoVectorDB for embeddings (file-based)
- JsonKVStorage for cache (file-based)
- NetworkX for knowledge graph

Optionally use pg0 for PostgreSQL-backed storage.

## CLI Integration

Exposed via `tdoc-crawler` commands:

```bash
tdoc-crawler ai workspace process
tdoc-crawler ai workspace query "your query"
tdoc-crawler ai workspace status
```

## Import Guidelines

```python
from tdoc_ai import LightRAGConfig, TDocRAG, TDocProcessor
```

## Extraction

LightRAG uses `kreuzberg` for text extraction before chunking and ingestion.

## Deprecated/Removed

- `AiStorage`
- `EmbeddingsManager`
- `create_embeddings_manager()`
- `tdoc_ai.operations.pipeline` (legacy CLASSIFY/EXTRACT/EMBED/GRAPH flow)
- `tdoc_ai.storage.lancedb`
- `sentence-transformers`
- `tokenizers`
- `lancedb`
