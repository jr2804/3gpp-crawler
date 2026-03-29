# 3GPP-AI Configuration

This document describes configuration for the 3gpp-ai package, which provides AI-powered document processing including embeddings, knowledge graphs, and LLM-based analysis.

## Shared Configuration

The 3gpp-ai package shares cache paths with the main 3gpp-crawler:

| Path | Description |
|------|-------------|
| `<cache_dir>/lightrag/` | AI cache directory |
| `<cache_dir>/lightrag/<model>/` | Embedding model-specific storage |

These paths are managed by `CacheManager` (from `tdoc_crawler.config`) and are the **single source of truth** for all file paths.

**Cache directory:** Determined by `TDC_CACHE_DIR` or `path.cache_dir` in `3gpp-crawler.toml`

## Configuration Methods

The 3gpp-ai package supports two configuration approaches:

### 1. Environment Variables (Default)

3gpp-ai reads `TDC_AI_*` environment variables directly:

| Variable | Description | Default |
|----------|-------------|---------|
| `TDC_AI_LLM_MODEL` | LLM model in `<provider>/<model>` format | `openrouter/openrouter/free` |
| `TDC_AI_LLM_API_BASE` | Custom LLM API base URL | (none) |
| `TDC_AI_LLM_API_KEY` | LLM API key (overrides provider-specific env vars) | (none) |
| `TDC_AI_EMBEDDING_MODEL` | Embedding model ID | `sentence-transformers/all-MiniLM-L6-v2` |
| `TDC_AI_MAX_CHUNK_SIZE` | Max tokens per chunk | `1000` |
| `TDC_AI_CHUNK_OVERLAP` | Token overlap between chunks | `100` |
| `TDC_AI_ABSTRACT_MIN_WORDS` | Minimum abstract word count | `150` |
| `TDC_AI_ABSTRACT_MAX_WORDS` | Maximum abstract word count | `250` |
| `TDC_AI_PARALLELISM` | Parallel workers for processing | `4` |
| `TDC_AI_CONVERT_PDF` | Convert Office docs to PDF | `false` |
| `TDC_AI_CONVERT_MD` | Extract markdown from PDFs | `false` |
| `TDC_AI_VLM` | Enable vision for figure descriptions | `false` |
| `TDC_GRAPH_QUERY_LEVEL` | Graph query level | `simple` |
| `TDC_LIGHTRAG_SHARED_STORAGE` | Shared embedding storage | `true` |

### 2. Config File Approach

You can use `3gpp-crawler.toml` as base config and `3gpp-ai.toml` for AI-specific overrides:

**3gpp-crawler.toml (base):**
```toml
[path]
cache_dir = "~/.3gpp-crawler"

[http]
timeout = 30
```

**3gpp-ai.toml (override):**
```toml
[ai]
llm_model = "openrouter/anthropic/claude-3-sonnet"
embedding_model = "ollama/nomic-embed-text"
```

## Path Configuration

All paths use `CacheManager` from `tdoc_crawler.config`:

```python
from tdoc_crawler.config import resolve_cache_manager

manager = resolve_cache_manager()
manager.ai_cache_dir       # ~/.3gpp-crawler/lightrag/
manager.ai_embed_dir("qwen3-embedding:0.6b")  # ~/.3gpp-crawler/lightrag/qwen3-embedding:0.6b/
```

**NEVER hardcode paths** like `~/.3gpp-crawler` - always use `CacheManager`.

## Model Formats

### LLM Models

Format: `<provider>/<model_name>`

Examples:
- `openrouter/openrouter/free` - Free tier
- `openrouter/anthropic/claude-3-sonnet` - Anthropic via OpenRouter
- `ollama/llama3` - Local Ollama

### Embedding Models

Format: `<provider>/<model_name>`

Examples:
- `sentence-transformers/all-MiniLM-L6-v2` - Default
- `ollama/nomic-embed-text` - Local Ollama
- `ollama/qwen3-embedding:0.6b` - Qwen embedding

## Processing Options

### Document Conversion

| Option | Description |
|--------|-------------|
| `TDC_AI_CONVERT_PDF` | Convert Office docs (Word, Excel, PowerPoint) to PDF |
| `TDC_AI_CONVERT_MD` | Extract markdown from PDFs using Docling |
| `TDC_AI_VLM` | Use vision model for figure descriptions |

### Chunking

| Option | Description | Default |
|--------|-------------|---------|
| `TDC_AI_MAX_CHUNK_SIZE` | Maximum tokens per chunk | 1000 |
| `TDC_AI_CHUNK_OVERLAP` | Overlap between chunks | 100 |

### Graph Query Levels

| Level | Behavior |
|-------|----------|
| `simple` | Return count and list without synthesis |
| `medium` | Parse query keywords, filter nodes, generate simple text summary |
| `advanced` | Use LLM to synthesize answer from graph + embeddings (GraphRAG) |

## Decoupled Design

The 3gpp-ai package is designed to be **independently installable**:

- It reads `TDC_AI_*` env vars directly (not `TDocCrawlerConfig`)
- It uses `CacheManager` from tdoc_crawler for paths only
- This keeps packages decoupled while sharing infrastructure

For shared settings, use the main `3gpp-crawler.toml` file.
For AI-specific settings, use `TDC_AI_*` env vars or `3gpp-ai.toml`.
