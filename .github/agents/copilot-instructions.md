# tdoc-crawler Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-05

## Active Technologies
- Python 3.14 + typer, rich, pydantic, pydantic-sqlite, requests, (001-specs-crawl-query)
- SQLite via pydantic-sqlite (001-specs-crawl-query)
- Python 3.14 (`requires-python = ">=3.14,<4.0"`) + Docling (DOCX-to-Markdown), sentence-transformers (embeddings), LanceDB (vector + graph storage), litellm (LLM abstraction for Ollama/OpenAI-compatible endpoints) (002-ai-document-processing)
- LanceDB file-based tables for embeddings, summaries, graph nodes/edges, and processing status; existing tdoc-crawler SQLite DB is read-only from the AI module (002-ai-document-processing)
- Python 3.14 + typer, rich, pydantic, lancedb, pyarrow, sentence-transformers (001-graphrag-workspaces)
- LanceDB tables under `.ai/lancedb` + workspace file references (001-graphrag-workspaces)

- Python 3.14 + typer, rich, requests, beautifulsoup4, lxml, pydantic, pydantic-sqlite, hishel, zipinspect (001-specs-crawl-query)

## Project Structure

```text
src/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.14: Follow standard conventions

## Recent Changes
- 001-graphrag-workspaces: Added Python 3.14 + typer, rich, pydantic, lancedb, pyarrow, sentence-transformers
- 002-ai-document-processing: Added Python 3.14 (`requires-python = ">=3.14,<4.0"`) + Docling (DOCX-to-Markdown), sentence-transformers (embeddings), LanceDB (vector + graph storage), litellm (LLM abstraction for Ollama/OpenAI-compatible endpoints)
- 001-specs-crawl-query: Added Python 3.14 + typer, rich, pydantic, pydantic-sqlite, requests,


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
