# AI Document Processing

The AI module provides intelligent document processing capabilities for TDoc data, including semantic search, knowledge graph construction, and AI-powered summarization.

**Key Features:**

- **Classification** - Identify main documents in multi-file TDoc folders
- **Extraction** - Convert DOCX/PDF to Markdown with keyword extraction and language detection (via Kreuzberg)
- **Embeddings** - Generate semantic vector representations for similarity search
- **Summarization** - Create AI-powered abstracts
- **Knowledge Graph** - Build relationships between TDocs
- **Workspaces** - Organize TDocs into logical groups for focused analysis

______________________________________________________________________

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Workflow Guide](#workflow-guide)
- [CLI Commands](#cli-commands)
- [Model Providers](#model-providers)
- [Python API](#python-api)
- [Troubleshooting](#troubleshooting)

______________________________________________________________________

## Installation

The AI module is available as an optional dependency. Install it with:

```bash
# Install tdoc-crawler with AI support
uv add tdoc-crawler[ai]

# Or install from source
git clone https://forge.3gpp.org/rep/reimes/tdoc-crawler.git
cd tdoc-crawler
uv sync --extra ai
```

All required dependencies (Kreuzberg, LiteLLM, sentence-transformers, LanceDB) are installed automatically.

______________________________________________________________________

## Configuration

### Environment Variables

Configure AI processing via environment variables (see `.env.example`):

```bash
# LLM Configuration
TDC_AI_LLM_MODEL=openrouter/openrouter/free    # Default: free tier via OpenRouter
TDC_AI_LLM_API_KEY=your-api-key                # Required for cloud providers
TDC_AI_LLM_API_BASE=                           # Optional: custom endpoint

# Embedding Model
TDC_AI_EMBEDDING_MODEL=ollama/embeddinggemma   # Default: local Ollama
TDC_AI_EMBEDDING_API_KEY=                      # Not needed for local models

# Storage
TDC_AI_STORE_PATH=                             # Defaults to <cache_dir>/.ai/lancedb
TDC_AI_MAX_CHUNK_SIZE=1000                     # Chunk size for embeddings
TDC_AI_CHUNK_OVERLAP=100                       # Overlap between chunks

# Summary Constraints
TDC_AI_ABSTRACT_MIN_WORDS=150
TDC_AI_ABSTRACT_MAX_WORDS=250

# Processing
TDC_AI_PARALLELISM=4                           # Parallel workers
```

### Model Identifier Format

Both LLM and embedding models use the `<provider>/<model_name>` format:

```bash
# Simple format: provider/model
TDC_AI_LLM_MODEL=openai/gpt-4o-mini

# Nested format: provider/model_group/model (also supported)
TDC_AI_LLM_MODEL=openrouter/anthropic/claude-3-sonnet
TDC_AI_EMBEDDING_MODEL=huggingface/BAAI/bge-small-en-v1.5
```

The provider (first segment) is validated against the supported allowlist. The model name (everything after the first `/`) can contain additional slashes for nested model paths.

______________________________________________________________________

## Workflow Guide

The AI module follows a workspace-based workflow for organizing and querying your document collection:

### 1. Create Workspace

```bash
# Create a new workspace for your project
tdoc-crawler ai workspace create my-project
```

### 2. Add Documents to Workspace

Use the existing `checkout` and `checkout-spec` commands to download documents:

```bash
# Add TDocs to workspace
tdoc-crawler checkout --workspace my-project SP-240001 SP-240002

# Add specifications
tdoc-crawler checkout-spec --workspace my-project 23.501 23.502
```

### 3. Process Documents (Build Knowledge Base)

Process documents to extract content, generate embeddings, and create summaries:

```bash
# Process all documents in workspace
tdoc-crawler ai process-all --workspace my-project

# Or process individual TDoc
tdoc-crawler ai process --tdoc-id SP-240001 --checkout-path /path/to/checkout
```

### 4. Query Your Knowledge Base

Once processed, query your documents using semantic search or graph queries:

```bash
# Semantic search
tdoc-crawler ai query --workspace my-project --query "5G NR architecture" --top-k 5

# Knowledge graph query
tdoc-crawler ai graph --workspace my-project --query "evolution of 5G standards"
```

### 5. Check Status

Monitor processing status:

```bash
# Check status of specific TDoc
tdoc-crawler ai status --tdoc-id SP-240001

# List all processed documents
tdoc-crawler ai status --workspace my-project
```

______________________________________________________________________

## CLI Commands

### Workspace Management

```bash
# Create a new workspace
tdoc-crawler ai workspace create <name>

# List all workspaces
tdoc-crawler ai workspace list

# Get workspace details
tdoc-crawler ai workspace get <name>

# Delete a workspace
tdoc-crawler ai workspace delete <name>
```

### Document Processing

```bash
# Process single TDoc
tdoc-crawler ai process --tdoc-id <TDOC_ID> --checkout-path <PATH>

# Process all TDocs in workspace
tdoc-crawler ai process-all --workspace <NAME>

# Force re-processing
tdoc-crawler ai process --tdoc-id <TDOC_ID> --checkout-path <PATH> --force
```

### Querying

```bash
# Semantic search
tdoc-crawler ai query --workspace <NAME> --query "<SEARCH_QUERY>" --top-k 5

# Knowledge graph query
tdoc-crawler ai graph --workspace <NAME> --query "<GRAPH_QUERY>"
```

### Status

```bash
# Check processing status
tdoc-crawler ai status --tdoc-id <TDOC_ID>

# List all statuses in workspace
tdoc-crawler ai status --workspace <NAME>

# Output as JSON
tdoc-crawler ai status --tdoc-id <TDOC_ID> --json
```

______________________________________________________________________

## Model Providers

### Supported LLM Providers

| Provider | Example Model | API Key Env Var | Notes |
|----------|---------------|-----------------|-------|
| `openai` | `gpt-4o-mini`, `gpt-4o` | `OPENAI_API_KEY` | Industry standard |
| `anthropic` | `claude-3-haiku`, `claude-3-sonnet` | `ANTHROPIC_API_KEY` | High-quality reasoning |
| `openrouter` | `openrouter/free` | `OPENROUTER_API_KEY` | **Recommended** - Free tier available |
| `github_copilot` | `gpt-4o` | `GITHUB_COPILOT_API_KEY` | GitHub Copilot endpoint |
| `nvidia` | `meta/llama3-70b` | `NVIDIA_API_KEY` | NVIDIA NIM platform |
| `google` | `gemini-1.5-flash` | `GOOGLE_API_KEY` | Google AI Studio |
| `azure` | `gpt-4o` | `AZURE_API_KEY` | Azure OpenAI Service |
| `vertex_ai` | `gemini-pro` | `VERTEX_AI_API_KEY` | Google Cloud Vertex |
| `groq` | `llama-3.1-70b` | `GROQ_API_KEY` | Fast inference |
| `mistral` | `mistral-large` | `MISTRAL_API_KEY` | Mistral AI |
| `together_ai` | `meta-llama/Llama-3-70b` | `TOGETHER_API_KEY` | Together AI platform |
| `huggingface` | `mistralai/Mistral-7B` | `HF_API_KEY` | Hugging Face Inference |
| `ollama` | `llama3.2`, `mistral` | *(none)* | **Local** - No API key needed |
| `sambanova` | `Meta-Llama-3.1-70B` | `SAMBANOVA_API_KEY` | SambaNova Cloud |
| `fireworks_ai` | `accounts/fireworks/models/llama-v3-70b` | `FIREWORKS_API_KEY` | Fireworks AI |
| `anyscale` | `meta-llama/Llama-3-70b` | `ANYSCALE_API_KEY` | Anyscale Endpoints |
| `perplexity` | `pplx-7b-chat` | `PERPLEXITY_API_KEY` | Perplexity API |
| `deepinfra` | `meta-llama/Llama-3-70b` | `DEEPINFRA_API_KEY` | DeepInfra |

### Supported Embedding Providers

| Provider | Example Model | API Key Env Var | Notes |
|----------|---------------|-----------------|-------|
| `ollama` | `embeddinggemma`, `nomic-embed-text` | *(none)* | **Recommended** - Local |
| `huggingface` | `BAAI/bge-small-en-v1.5` | `HF_API_KEY` | BGE embeddings |
| `openai` | `text-embedding-3-small` | `OPENAI_API_KEY` | OpenAI embeddings |
| `cohere` | `embed-english-v3.0` | `COHERE_API_KEY` | Cohere embeddings |
| `google` | `text-embedding-004` | `GOOGLE_API_KEY` | Google embeddings |

### Recommended Configuration

**Free/Local Setup (No Cost):**

```bash
TDC_AI_LLM_MODEL=openrouter/openrouter/free
TDC_AI_EMBEDDING_MODEL=ollama/embeddinggemma
OPENROUTER_API_KEY=your-free-api-key
```

**Production Setup (High Quality):**

```bash
TDC_AI_LLM_MODEL=anthropic/claude-3-sonnet
TDC_AI_EMBEDDING_MODEL=openai/text-embedding-3-small
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
```

______________________________________________________________________

## Python API

```python
from tdoc_crawler.ai import (
    process_tdoc,
    process_all,
    get_status,
    query_embeddings,
    query_graph,
    create_workspace,
    get_workspace,
)

# Create workspace
workspace = create_workspace("my-project")

# Process single TDoc
status = process_tdoc("SP-240001", "/path/to/checkout", workspace="my-project")

# Batch processing
results = process_all(
    ["SP-240001", "SP-240002"],
    "/base/checkout/path",
    workspace="my-project"
)

# Get status
status = get_status("SP-240001")

# Semantic search
results = query_embeddings("5G architecture", top_k=5, workspace="my-project")

# Query knowledge graph
graph_data = query_graph("evolution of 5G NR", workspace="my-project")
```

### Models

```python
from tdoc_crawler.ai import (
    ProcessingStatus,
    PipelineStage,
    DocumentClassification,
    DocumentSummary,
    DocumentChunk,
    Workspace,
)
```

## Pipeline Stages

The AI processing pipeline consists of these stages:

1. **CLASSIFY** - Identify main document among multiple files
1. **EXTRACT** - Convert DOCX/PDF to Markdown (via Kreuzberg)
1. **EMBED** - Generate vector embeddings
1. **SUMMARIZE** - Create AI summaries
1. **GRAPH** - Build knowledge graph relationships

## Supported File Types

- **DOCX** - Primary format for extraction (via Kreuzberg)
- **PDF** - Supported via Kreuzberg
- **XLSX** - Handled as secondary files
- **PPTX** - Handled as secondary files

## Testing

Run AI tests:

```bash
# All AI tests
uv run pytest tests/ai -v

# Specific module
uv run pytest tests/ai/test_ai_extraction.py -v
```

Test data is located in `tests/ai/data/`.

______________________________________________________________________

## Troubleshooting

### Installation Issues

**Problem:** `ModuleNotFoundError: No module named 'kreuzberg'`

**Solution:** Install the AI optional dependencies:

```bash
uv add tdoc-crawler[ai]
```

**Problem:** `lancedb not available`

**Solution:** LanceDB is included in the `[ai]` extra. Reinstall:

```bash
uv sync --extra ai
```

### Model Configuration Errors

**Problem:** `ValueError: TDC_AI_LLM_MODEL must be in '<provider>/<model_name>' format`

**Solution:** Ensure your model identifier includes a provider prefix:

```bash
# Wrong
TDC_AI_LLM_MODEL=gpt-4o-mini

# Correct
TDC_AI_LLM_MODEL=openai/gpt-4o-mini
```

**Problem:** `ValueError: provider 'xyz' is not in supported provider allowlist`

**Solution:** Check the provider name spelling. See [Model Providers](#model-providers) for the full list. Provider names are case-insensitive.

### API Key Errors

**Problem:** `litellm.AuthenticationError: Invalid API key`

**Solution:** Verify your API key is set correctly:

```bash
# For OpenAI
export OPENAI_API_KEY=sk-...

# For Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# For OpenRouter
export OPENROUTER_API_KEY=...

# Check if set
echo $OPENAI_API_KEY
```

**Problem:** `Missing API key for provider 'openai'`

**Solution:** LiteLLM expects the API key in a standard environment variable named `<PROVIDER>_API_KEY`. See the [Model Providers](#model-providers) table for the correct variable name for each provider.

### Embedding Model Issues

**Problem:** `OSError: No sentence-transformers model found`

**Solution:** If using a Hugging Face embedding model, ensure `sentence-transformers` is installed:

```bash
uv add sentence-transformers
```

**Problem:** Ollama embedding model not found

**Solution:** Pull the model in Ollama first:

```bash
ollama pull embeddinggemma
```

### Workspace Issues

**Problem:** `Workspace 'my-project' not found`

**Solution:** Create the workspace first:

```bash
tdoc-crawler ai workspace create my-project
```

**Problem:** `No documents found in workspace`

**Solution:** Add documents to the workspace using `checkout` or `checkout-spec` commands, then process them:

```bash
tdoc-crawler checkout --workspace my-project SP-240001
tdoc-crawler ai process-all --workspace my-project
```

### Processing Errors

**Problem:** `TDoc 'SP-240001' not found in checkout path`

**Solution:** Ensure the TDoc has been downloaded to the specified path:

```bash
tdoc-crawler checkout SP-240001
tdoc-crawler ai process --tdoc-id SP-240001 --checkout-path ~/.tdoc-crawler/checkout
```

**Problem:** `LLM API timeout`

**Solution:** Increase timeout or reduce token count:

```bash
# Increase timeout (if supported by provider)
export LITELLM_REQUEST_TIMEOUT=60

# Reduce max tokens
export TDC_AI_LLM_MAX_TOKENS=1000
```

### Performance Issues

**Problem:** Processing is very slow

**Solution:**

1. Increase parallelism:

   ```bash
   export TDC_AI_PARALLELISM=8
   ```

1. Use a faster LLM for summarization (e.g., `gpt-4o-mini` instead of `gpt-4o`)

1. For local models, ensure Ollama is running with GPU acceleration if available

### LanceDB Issues

**Problem:** `lancedb.errors.InternalError: Schema mismatch`

**Solution:** This can occur after upgrading the AI module. The LanceDB schema may need to be recreated. Backup your data and delete the LanceDB directory:

```bash
# Backup first!
cp -r ~/.tdoc-crawler/.ai/lancedb ~/.tdoc-crawler/.ai/lancedb.backup

# Delete and let it recreate
rm -rf ~/.tdoc-crawler/.ai/lancedb
```

**Note:** This will delete all processed embeddings and summaries. You'll need to re-process your documents.

______________________________________________________________________

## Additional Resources

- [LiteLLM Provider Documentation](https://docs.litellm.ai/docs/providers) - Complete list of 100+ supported LLM providers
- [Kreuzberg Documentation](https://docs.kreuzberg.dev/) - Document extraction library
- [LanceDB Documentation](https://lancedb.github.io/lancedb/) - Vector database
