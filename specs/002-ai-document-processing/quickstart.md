# Quickstart: AI Document Processing

## Prerequisites

1. Install tdoc-crawler with AI extras:

   ```bash
   uv pip install "tdoc-crawler[ai]"
   ```

1. (Optional) Install and start Ollama for summarization:

   ```bash
   # See https://ollama.ai for installation
   ollama pull llama3.2
   ```

## Process a Single TDoc

```bash
# Extract DOCX to Markdown and classify files
tdoc-crawler ai process --tdoc-id SP-123456
```

Output:

```
Processing SP-123456...
  Classifying files... done (1 main, 0 secondary)
  Extracting DOCX to Markdown... done (2.3s)
  Generating embeddings... done (12 chunks)
  Summarizing... done (abstract: 187 words)
  Building graph... done (3 nodes, 5 edges)
Completed SP-123456 in 8.4s
```

## Batch Process All TDocs

```bash
# Process all downloaded TDocs
tdoc-crawler ai process --all

# Process only new (unprocessed) TDocs
tdoc-crawler ai process --all --new-only
```

## Check Status

```bash
# Status for one TDoc
tdoc-crawler ai status --tdoc-id SP-123456

# Status for all TDocs
tdoc-crawler ai status
```

## Semantic Search

```bash
# Search across all processed TDocs
tdoc-crawler ai query "uplink power control enhancements"

# Get results as JSON
tdoc-crawler ai query "uplink power control" --json --top-k 10
```

## Graph Queries

```bash
# Query evolution of a topic across meetings
tdoc-crawler ai graph --query "echo canceller test setup evolution" --from 2024-01-01

# JSON output for programmatic use
tdoc-crawler ai graph --query "history of codec selection" --json
```

## Python API

```python
from tdoc_crawler.ai import process_tdoc, query_embeddings, get_status
from tdoc_crawler.ai.models import AiConfig

# Process with default config
status = process_tdoc("SP-123456")
print(status.current_stage)  # "completed"

# Custom config
config = AiConfig(llm_model="ollama/mistral")
status = process_tdoc("SP-123456", config=config)

# Semantic search
results = query_embeddings("uplink power control", top_k=5)
for chunk, score in results:
    print(f"{chunk.tdoc_id} ({score:.2f}): {chunk.text[:100]}...")

# Check status
status = get_status("SP-123456")
print(f"Stage: {status.current_stage}, Extracted: {status.extracted_at}")
```

## Configuration

The AI pipeline can be configured via environment variables or a config file:

| Variable | Default | Description |
|----------|---------|-------------|
| `TDC_AI_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model name |
| `TDC_AI_LLM_MODEL` | `ollama/llama3.2` | LLM model identifier |
| `TDC_AI_LLM_API_BASE` | None | Override LLM API base URL |
| `TDC_AI_MAX_CHUNK_SIZE` | `1000` | Max tokens per chunk |
| `TDC_AI_PARALLELISM` | `4` | Concurrent TDoc processing |
