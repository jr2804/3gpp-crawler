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

Internally, AI capabilities are provided by the optional `tdoc-ai` package, which is pulled in by `tdoc-crawler[ai]`.

______________________________________________________________________

## Configuration

### Environment Variables

Configure AI processing via environment variables (see `.env.example`):

```bash
# LLM Configuration
TDC_AI_LLM_MODEL=openrouter/openrouter/free    # Default: free tier via OpenRouter
TDC_AI_LLM_API_KEY=your-api-key                # Optional: takes precedence over provider-specific keys
TDC_AI_LLM_API_BASE=                           # Optional: custom endpoint

# Embedding Model (HuggingFace sentence-transformers)
TDC_AI_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2   # Default: popular 384-dim model
TDC_AI_EMBEDDING_BACKEND=torch                                  # torch | onnx | openvino (default: torch)

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

**LLMs** use the `<provider>/<model_name>` format (handled by LiteLLM):

```bash
TDC_AI_LLM_MODEL=openai/gpt-4o-mini
TDC_AI_LLM_MODEL=openrouter/anthropic/claude-3-sonnet
```

**Embedding models** use **HuggingFace model IDs** (handled by sentence-transformers):

```bash
TDC_AI_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
TDC_AI_EMBEDDING_MODEL=sentence-transformers/bert-base-nli-mean-tokens
TDC_AI_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Embedding models are **local-only** (downloaded from HuggingFace) and require the model ID to be a valid HuggingFace model that works with sentence-transformers.

______________________________________________________________________

## Workflow Guide

The AI module follows a workspace-based workflow for organizing and querying your document collection:

### 1. Create and Activate Workspace

```bash
# Create a new workspace for your project
tdoc-crawler ai workspace create my-project

# Activate it so you don't need --workspace for other commands
tdoc-crawler ai workspace activate my-project
```

Once activated, all workspace commands use the active workspace by default. No need to pass `-w` every time.

### 2. Add TDocs and Process

After adding TDocs to your workspace, process them to generate RAG/GraphRAG embeddings:

```bash
# Add TDocs to the active workspace
tdoc-crawler ai workspace add-members S4-251971 S4-251972

# Process all TDocs in workspace (only new ones)
tdoc-crawler ai workspace process -w my-project

# Force reprocess all TDocs
tdoc-crawler ai workspace process -w my-project --force
```

Note: If you created the workspace with `--auto-build`, documents are processed automatically when added.

### 3. Query Your Knowledge Base

Once you have a workspace with documents, query using semantic search and knowledge graph (RAG + GraphRAG):

```bash
# Query the active workspace
tdoc-crawler ai query "your query here"

# Or specify a workspace explicitly
tdoc-crawler ai query -w my-project "your query here"
```

Note: Uses active workspace if `-w` is not provided. Results combine vector embeddings (RAG) and knowledge graph (GraphRAG).

### 4. Workspace Maintenance

Keep your workspace clean and manage artifacts:

```bash
# Get detailed workspace information (member counts by type)
tdoc-crawler ai workspace info my-project

# Remove invalid/inactive members
tdoc-crawler ai workspace clear-invalid -w my-project

# Clear all AI artifacts (embeddings, summaries) while preserving members
tdoc-crawler ai workspace clear -w my-project

# After clearing, re-process to regenerate artifacts
tdoc-crawler ai workspace process -w my-project --force
```

### 5. Single TDoc Operations

Process a single TDoc through the pipeline (classification, extraction, embeddings, graph). Use `--accelerate` to choose the sentence-transformers backend.

```bash
tdoc-crawler ai process --tdoc-id SP-240001 --accelerate onnx
```

______________________________________________________________________

## CLI Commands

### Workspace Management

````bash
# Create a new workspace
tdoc-crawler ai workspace create <name> [--auto-build]

Options:
- `name`: Workspace name
- `--auto-build`: Automatically process documents when added to workspace

# List all workspaces
# Shows (*) next to the active workspace
tdoc-crawler ai workspace list

# Activate a workspace (sets as default for workspace commands)
tdoc-crawler ai workspace activate <name>

# Deactivate the active workspace
tdoc-crawler ai workspace deactivate

# Get workspace details (name, status, member counts)
tdoc-crawler ai workspace info <name>

# Remove invalid/inactive members from workspace
tdoc-crawler ai workspace clear-invalid [-w <name>]

# Clear all AI artifacts while preserving members
tdoc-crawler ai workspace clear [-w <name>]

# Delete a workspace
tdoc-crawler ai workspace delete <name>
### Querying

Query the knowledge base using semantic embeddings and knowledge graph (RAG + GraphRAG).

```bash
# Query the active workspace
tdoc-crawler ai query "your query here"

# Query a specific workspace
tdoc-crawler ai query -w <workspace_name> "your query here"

# Specify number of results
tdoc-crawler ai query "your query here" -k 10
````

Note: Uses active workspace if `-w` is not provided. Combines vector embeddings (RAG) and knowledge graph (GraphRAG). The query is a **positional argument** (no `--query` flag needed).

#### Summarize a TDoc

Summarize a single TDoc with specified word count.

```bash
tdoc-crawler ai summarize <tdoc_id> [--words N] [--format markdown|json|yaml] [--json-output]
```

Options:

- `tdoc_id`: TDoc identifier (e.g., "RP-240001")
- `--words N`: Target word count for summary (default: 200)
- `--format`: Output format - markdown (default), json, or yaml
- `--json-output`: Output raw JSON

#### Convert a TDoc

Convert a single TDoc to markdown format.

```bash
tdoc-crawler ai convert <tdoc_id> [--output FILE.md] [--json-output]
```

Options:

- `tdoc_id`: TDoc identifier
- `--output FILE.md`: Write output to file (prints to stdout if not specified)
- `--json-output`: Output raw JSON

### Workspace Members and Processing

Add TDocs to workspaces and process them to generate embeddings and knowledge graph.

```bash
# Add members to the active workspace
tdoc-crawler ai workspace add-members S4-251971 S4-251972

# Add members to a specific workspace
tdoc-crawler ai workspace add-members -w my-project S4-251971 S4-251972

# List members in the active workspace
tdoc-crawler ai workspace list-members

# List members including inactive ones
tdoc-crawler ai workspace list-members --include-inactive

# Process all TDocs in the active workspace
tdoc-crawler ai workspace process

# Process with options
tdoc-crawler ai workspace process -w my-project --force

# Get workspace information with member counts
tdoc-crawler ai workspace info my-project

# Remove invalid members (failed checkouts, etc.)
tdoc-crawler ai workspace clear-invalid -w my-project

# Clear AI artifacts (keep members, remove embeddings/summaries)
tdoc-crawler ai workspace clear -w my-project
```

______________________________________________________________________

## Model Providers

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

The embedding feature uses **sentence-transformers** (local HuggingFace models). This is the only supported approach for embeddings.

| HuggingFace Model | Dimension | Description |
|-------------------|-----------|-------------|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | **Default** - Fast, good quality |
| `sentence-transformers/bert-base-nli-mean-tokens` | 768 | High quality NLI model |
| `BAAI/bge-small-en-v1.5` | 384 | BGE small - strong retriever |
| `BAAI/bge-base-en-v1.5` | 768 | BGE base - higher quality |

**Recommended Models:**

- Original models: <https://huggingface.co/models?num_parameters=min:0,max:3B&library=sentence-transformers,onnx&sort=trending&author=sentence-transformers>
- Community models: <https://huggingface.co/models?num_parameters=min:0,max:3B&library=sentence-transformers,onnx&sort=trending>

### Recommended Configuration

**Free/Local Setup (No API Cost):**

```bash
TDC_AI_LLM_MODEL=openrouter/openrouter/free
TDC_AI_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENROUTER_API_KEY=your-free-api-key
```

**Production Setup (Higher Quality):**

```bash
TDC_AI_LLM_MODEL=anthropic/claude-3-sonnet
TDC_AI_EMBEDDING_MODEL=sentence-transformers/bert-base-nli-mean-tokens
ANTHROPIC_API_KEY=your-key
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

**Alternative:** You can use `TDC_AI_LLM_API_KEY` as a universal API key that takes precedence over provider-specific keys. This is useful when you want to use a single API key across different providers (e.g., via OpenRouter or a proxy service):

```bash
export TDC_AI_LLM_API_KEY=your-key-here
```

If `TDC_AI_LLM_API_KEY` is set, it will be used instead of the provider-specific key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

### Embedding Model Issues

**Problem:** `OSError: No sentence-transformers model found`

**Solution:** If using a Hugging Face embedding model, ensure `sentence-transformers` is installed:

```bash
uv add sentence-transformers
```

### Workspace Issues

**Problem:** `Workspace 'my-project' not found`

**Solution:** Create the workspace first:

```bash
tdoc-crawler ai workspace create my-project
```

**Solution:** Use `ai summarize` or `ai convert` to work with individual TDocs directly. These commands fetch content from configured sources:

```bash
tdoc-crawler ai summarize SP-240001
tdoc-crawler ai convert SP-240001 --output SP-240001.md
```

### Query Errors

**Problem:** `TDoc 'SP-240001' not found`

**Solution:** Ensure the TDoc exists in your workspace or use `ai summarize`/`ai convert` which fetch from external sources:

```bash
tdoc-crawler ai summarize SP-240001 --format markdown
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
