# AI Document Processing

The AI module provides intelligent document processing capabilities for TDoc data, including:

- **Classification** - Identify main documents in multi-file TDoc folders
- **Extraction** - Convert DOCX to Markdown with keyword extraction and language detection
- **Embeddings** - Generate semantic vector representations
- **Summarization** - Create AI-powered summaries
- **Knowledge Graph** - Build relationships between TDocs

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [CLI Commands](#cli-commands)
- [Python API](#python-api)
- [Environment Variables](#environment-variables)

## Installation

Install required dependencies:

```bash
# Core AI dependencies
uv add kreuzberg[all] sentence-transformers litellm

# Optional: for vector storage
uv add lancedb
```

## Configuration

### Environment Variables

Configure AI processing via environment variables (see `.env.example`):

```bash
# LLM Configuration
TDC_LLM_MODEL=openai/gpt-4o-mini
TDC_LLM_API_KEY=your-api-key
TDC_LLM_BASE_URL=  # For proxy/custom endpoints
TDC_LLM_MAX_TOKENS=2000
TDC_LLM_TEMPERATURE=0.3

# Embedding Model
TDC_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
TDC_EMBEDDING_API_KEY=

# Storage
TDC_LANCEDB_PATH=
TDC_CHUNK_SIZE=500
TDC_CHUNK_OVERLAP=50
```

### Model Format

Both LLM and embedding models use the `<provider>/<model_name>` format:

| Provider | Example Model | Description |
|----------|---------------|-------------|
| `openai` | `gpt-4o-mini`, `gpt-4o` | OpenAI models |
| `anthropic` | `claude-3-haiku`, `claude-3-sonnet` | Anthropic models |
| `azure` | `gpt-4o` | Azure OpenAI |
| `google` | `gemini-1.5-flash` | Google models |
| `cohere` | `command-r` | Cohere models |
| `BAAI` | `bge-small-en-v1.5` | BGE embeddings |
| `ollama` | `llama3`, `mistral` | Local Ollama models |

**Note:** LiteLLM is used as the backend, supporting 100+ providers. See [LiteLLM documentation](https://docs.litellm.ai/) for full list.

## CLI Commands

## AI Commands

### Process a TDoc {#ai-process}

```bash
tdoc-crawler ai process --tdoc-id SP-123456 --checkout-path /path/to/checkout
```

Options:

- `--tdoc-id`: TDoc identifier (e.g., SP-123456)
- `--checkout-path`: Path to TDoc checkout folder
- `--force`: Force re-processing even if completed
- `--json`: Output as JSON

### Get Status
### Get Status {#ai-status}
```bash
tdoc-crawler ai status --tdoc-id SP-123456
```

Options:

- `--tdoc-id`: TDoc identifier
- `--json`: Output as JSON

### Semantic Search

```bash
tdoc-crawler ai query --query "5G architecture overview" --top-k 5
```

Options:

- `--query`: Search query
- `--top-k`: Number of results (default: 5)
- `--json`: Output as JSON

### Knowledge Graph

```bash
tdoc-crawler ai graph --query "evolution of 5G NR"
```

Options:

- `--query`: Graph query
SJ|- `--json`: Output as JSON

### AI Workspace Management

```bash
# Create a new workspace
tdoc-crawler ai workspace create my-workspace

# List all workspaces
tdoc-crawler ai workspace list

# Get workspace details
tdoc-crawler ai workspace get my-workspace

# Add members to a workspace
tdoc-crawler ai workspace add-members --workspace my-workspace SP-123456 SP-123457 --kind tdoc

# List members of a workspace
tdoc-crawler ai workspace list-members --workspace my-workspace

# Delete a workspace
tdoc-crawler ai workspace delete my-workspace
```

Workspace Options:

- `--workspace`: Workspace name (defaults to 'default')
- `--json`: Output as JSON
- `create <name>`: Create a new workspace
- `list`: List all workspaces
- `get <name>`: Get workspace details
- `add-members <items...>`: Add source items to a workspace
- `list-members`: List members of a workspace
- `delete <name>`: Delete a workspace


## Python API

```python
from tdoc_crawler.ai import (
    process_tdoc,
    process_all,
    get_status,
    query_embeddings,
    query_graph,
)

# Process single TDoc
status = process_tdoc("SP-123456", "/path/to/checkout")

# Batch processing
results = process_all(
    ["SP-123456", "SP-123457"],
    "/base/checkout/path"
)

# Get status
status = get_status("SP-123456")

# Semantic search
results = query_embeddings("5G architecture", top_k=5)

# Query knowledge graph
graph_data = query_graph("evolution of 5G NR")
```

### Models

```python
from tdoc_crawler.ai import (
    ProcessingStatus,
    PipelineStage,
    DocumentClassification,
    DocumentSummary,
    DocumentChunk,
)
```

## Pipeline Stages

The AI processing pipeline consists of these stages:

1. **CLASSIFY** - Identify main document among multiple files
1. **EXTRACT** - Convert DOCX to Markdown
1. **EMBED** - Generate vector embeddings
1. **SUMMARIZE** - Create AI summaries
1. **GRAPH** - Build knowledge graph relationships

## Supported File Types

- **DOCX** - Primary format for extraction (via Kreuzberg)
- **XLSX** - Handled as secondary files
- **PPTX** - Handled as secondary files
- **PDF** - Supported via Kreuzberg

## Testing

Run AI tests:

```bash
# All AI tests
uv run pytest tests/ai -v

# Specific module
uv run pytest tests/ai/test_ai_extraction.py -v
```

Test data is located in `tests/ai/data/`.

## Troubleshooting

### Kreuzberg not available

```bash
uv add kreuzberg[all]
```

### Embedding model issues

```bash
uv add sentence-transformers torch
```

### LLM API errors

Check your API key is set correctly:

```bash
export OPENAI_API_KEY=your-key
# or
export ANTHROPIC_API_KEY=your-key
```
