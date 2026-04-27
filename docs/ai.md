# AI Document Processing

The AI module provides intelligent document processing capabilities for 3GPP document data, including semantic search, knowledge graph construction, and AI-powered summarization.

**Key Features:**

- **Classification** - Identify main documents in multi-file TDoc folders
- **Extraction** - Convert DOCX/PDF to Markdown with keyword extraction and language detection (via Docling)
- **Structured Elements** - Preserve tables, figures, and equations with stable markers and metadata
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
# Install 3gpp-crawler with AI support
uv add 3gpp-crawler[ai]

# Or install from source
git clone https://forge.3gpp.org/rep/reimes/3gpp-crawler.git
cd 3gpp-crawler
uv sync --extra ai
```

All required dependencies (Docling, LiteLLM, sentence-transformers, LanceDB) are installed automatically.

Internally, AI capabilities are provided by the optional `3gpp-ai` package, which is pulled in by `3gpp-crawler[ai]`.

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

All examples below use the `3gpp-ai` CLI entrypoint. AI commands are provided by the standalone `3gpp-ai` package (installed via `3gpp-crawler[ai]`).

### 1. Create and Activate Workspace

```bash
# Create a new workspace for your project
3gpp-ai workspace create my-project

# Activate it so you don't need --workspace for other commands
3gpp-ai workspace activate my-project
```

Once activated, all workspace commands use the active workspace by default. No need to pass `-w` every time.

### 2. Add TDocs and Process

After adding TDocs to your workspace, process them to generate RAG/GraphRAG embeddings:

```bash
# Add TDocs to the active workspace
3gpp-ai workspace add-members --kind tdoc S4-251971 S4-251972

# Process all TDocs in workspace (only new ones)
3gpp-ai workspace process -w my-project

# Force reprocess all TDocs
3gpp-ai workspace process -w my-project --force
```

Note: If you created the workspace with `--auto-build`, documents are processed automatically when added.

### 3. Query Your Knowledge Base

Once you have a workspace with documents, query using the single RAG command that searches enriched text plus preserved table/figure/equation context:

```bash
# Query a workspace
3gpp-ai workspace query --workspace my-project "What are the bit rates in Table 3?"

# Same command for figure/equation questions
3gpp-ai workspace query --workspace my-project "Describe the architecture figure"
3gpp-ai workspace query --workspace my-project "What is the throughput equation?"
```

Note: `workspace query` is the only query entrypoint. Do not use separate table/figure/equation query commands.

### 4. Workspace Maintenance

Keep your workspace clean and manage artifacts:

```bash
# Get detailed workspace information (member counts by type)
3gpp-ai workspace info my-project

# Remove invalid/inactive members
3gpp-ai workspace clear-invalid -w my-project

# Clear all AI artifacts (embeddings, summaries) while preserving members
3gpp-ai workspace clear -w my-project

# After clearing, re-process to regenerate artifacts
3gpp-ai workspace process -w my-project --force
```

### 5. Single TDoc Operations

Process a single TDoc through the pipeline (classification, extraction, embeddings, graph). Use `--accelerate` to choose the sentence-transformers backend.

```bash
3gpp-ai convert SP-240001 --output ./SP-240001.md
3gpp-ai summarize SP-240001 --words 200
```

When structured extraction is enabled, conversion and workspace processing may generate sidecars next to markdown artifacts:

- `*_tables.json`
- `*_figures.json`
- `*_equations.json`

### VLM Features (Optional)

The AI module supports optional Vision-Language Model (VLM) features for enhanced document processing. These features are disabled by default and must be explicitly enabled.

#### What VLM Provides

| Feature | Description | Model |
|---------|-------------|-------|
| **Picture Description** | Generates detailed natural language descriptions of figures and diagrams | Granite Docling VLM |
| **Formula Enrichment** | Provides enhanced LaTeX/MathML representation of mathematical formulas | Granite Docling VLM |

#### GPU Requirements

VLM features require a GPU with sufficient VRAM. If no GPU is available, the processing will fail or run very slowly. The standard pipeline (without VLM) works on CPU.

#### Enabling VLM

Use the `--vlm` flag with the workspace process command:

```bash
# Process with VLM features enabled
3gpp-ai workspace process -w my-project --vlm

# Force reprocess with VLM
3gpp-ai workspace process -w my-project --vlm --force
```

When `--vlm` is specified, both `enable_picture_description` and `enable_formula_enrichment` are activated.

#### Standard vs VLM Pipeline

| Aspect | Standard Pipeline | VLM Pipeline |
|--------|-------------------|--------------|
| Table Detection | ✅ Enabled (Docling) | ✅ Enabled |
| Formula Enrichment | ✅ Basic (CodeFormula) | ✅ Enhanced (VLM) |
| Picture Description | ❌ Not available | ✅ VLM-generated descriptions |
| GPU Required | No | Yes |
| Processing Speed | Faster | Slower |

______________________________________________________________________

## CLI Commands

### Workspace Management

````bash
# Create a new workspace
3gpp-ai workspace create <name> [--auto-build]

Options:
- `name`: Workspace name
- `--auto-build`: Automatically process documents when added to workspace

# List all workspaces
# Shows (*) next to the active workspace
3gpp-ai workspace list

# Activate a workspace (sets as default for workspace commands)
3gpp-ai workspace activate <name>

# Deactivate the active workspace
3gpp-ai workspace deactivate

# Get workspace details (name, status, member counts)
3gpp-ai workspace info <name>

# Remove invalid/inactive members from workspace
3gpp-ai workspace clear-invalid [-w <name>]

# Clear all AI artifacts while preserving members
3gpp-ai workspace clear [-w <name>]

# Delete a workspace
3gpp-ai workspace delete <name>
### Querying

Query the knowledge base using semantic embeddings and knowledge graph (RAG + GraphRAG).

```bash
# Query a specific workspace (single query command)
3gpp-ai workspace query --workspace <workspace_name> "your query here"
````

Note: Keep `workspace query` as the single query interface. The query is a positional argument (no `--query` flag).

#### Summarize a TDoc

Summarize a single TDoc with specified word count.

```bash
3gpp-ai summarize <tdoc_id> [--words N] [--format markdown|json|yaml] [--json-output]
```

Options:

- `tdoc_id`: TDoc identifier (e.g., "RP-240001")
- `--words N`: Target word count for summary (default: 200)
- `--format`: Output format - markdown (default), json, or yaml
- `--json-output`: Output raw JSON

#### Convert a TDoc

Convert a single TDoc to markdown format.

```bash
3gpp-ai convert <tdoc_id> [--output FILE.md] [--json-output]
```

Options:

- `tdoc_id`: TDoc identifier
- `--output FILE.md`: Write output to file (prints to stdout if not specified)
- `--json-output`: Output raw JSON

### Workspace Members and Processing

Add TDocs to workspaces and process them to generate embeddings and knowledge graph.

```bash
# Add members to the active workspace
3gpp-ai workspace add-members --kind tdoc S4-251971 S4-251972

# Add members to a specific workspace
3gpp-ai workspace add-members -w my-project --kind tdoc S4-251971 S4-251972

# List members in the active workspace
3gpp-ai workspace list-members

# List members including inactive ones
3gpp-ai workspace list-members --include-inactive

# Process all TDocs in the active workspace
3gpp-ai workspace process

# Process with options
3gpp-ai workspace process -w my-project --force

# Process with VLM features (requires GPU)
3gpp-ai workspace process -w my-project --vlm

# Get workspace information with member counts
3gpp-ai workspace info my-project

# Remove invalid members (failed checkouts, etc.)
3gpp-ai workspace clear-invalid -w my-project

# Clear AI artifacts (keep members, remove embeddings/summaries)
3gpp-ai workspace clear -w my-project
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

Legacy batch-processing helpers are removed. Use the LightRAG interfaces exposed by the
`threegpp_ai` package for workspace processing and querying.

## Supported File Types

- **DOCX** - Primary format for extraction (via Docling)
- **PDF** - Supported via Docling
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

**Problem:** `ModuleNotFoundError: No module named 'opendataloader_pdf'`

**Solution:** Install the AI optional dependencies:

```bash
uv add 3gpp-crawler[ai]
```

**Problem:** `Java not found` or `opendataloader_pdf requires Java 11+`

**Solution:** Install Java 11 or later and ensure it's on your system PATH. Download from https://adoptium.net/ or use your system's package manager.

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
3gpp-ai workspace create my-project
```

**Solution:** Use `summarize` or `convert` to work with individual TDocs directly. These commands fetch content from configured sources:

```bash
3gpp-ai summarize SP-240001
3gpp-ai convert SP-240001 --output SP-240001.md
```

### Query Errors

**Problem:** `TDoc 'SP-240001' not found`

**Solution:** Ensure the TDoc exists in your workspace or use `summarize`/`convert` which fetch from external sources:

```bash
3gpp-ai summarize SP-240001 --format markdown
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
cp -r ~/.3gpp-crawler/.ai/lancedb ~/.3gpp-crawler/.ai/lancedb.backup

# Delete and let it recreate
rm -rf ~/.3gpp-crawler/.ai/lancedb
```

**Note:** This will delete all processed embeddings and summaries. You'll need to re-process your documents.

______________________________________________________________________

## Additional Resources

- [LiteLLM Provider Documentation](https://docs.litellm.ai/docs/providers) - Complete list of 100+ supported LLM providers
- [OpenDataLoader PDF Documentation](https://github.com/opendataloader-project/opendataloader-pdf) - PDF extraction library (#1 in benchmarks)
- [LanceDB Documentation](https://lancedb.github.io/lancedb/) - Vector database
