# Implementation Plan: AI Document Processing Pipeline

**Branch**: `002-ai-document-processing` | **Date**: 2026-02-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-ai-document-processing/spec.md`

## Summary

Build an AI document processing pipeline as a new `ai/` domain package within
tdoc-crawler. The pipeline converts downloaded 3GPP TDoc DOCX files into Markdown,
classifies multi-file folders, generates vector embeddings, produces LLM summaries, and
constructs a temporal knowledge graph for cross-meeting queries. All AI-generated
data lives in a separate file-system-based store (not the existing SQLite database).
AI dependencies are packaged as optional extras (`tdoc_crawler[ai]`).

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14,<4.0"`)
**Primary Dependencies**: Docling (DOCX-to-Markdown), sentence-transformers (embeddings), LanceDB (vector + graph storage), litellm (LLM abstraction for Ollama/OpenAI-compatible endpoints)
**Storage**: LanceDB file-based tables for embeddings, summaries, graph nodes/edges, and processing status; existing tdoc-crawler SQLite DB is read-only from the AI module
**Testing**: pytest (with pytest-cov, pytest-asyncio)
**Target Platform**: Windows (primary), cross-platform (Linux/macOS)
**Project Type**: Single (new domain package `src/tdoc_crawler/ai/` within existing monorepo)
**Performance Goals**: \<30s per TDoc DOCX extraction; batch 500 TDocs without crash; embedding generation limited by model inference speed
**Constraints**: \<2 GB peak memory for non-LLM stages; local-only by default (no cloud calls unless user configures remote endpoint); AI deps are optional extras
**Scale/Scope**: 500-5000 TDocs per working group; ~7 entities; 6 pipeline stages; 4 CLI subcommands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Library-first boundary documented (standalone library + integration points).
  - `tdoc_crawler.ai` exposes a public API (`process_tdoc()`, `process_all()`,
    `query_embeddings()`, `query_graph()`) that CLI code calls via delegation.
- [x] CLI contract defined (text input/output + JSON mode).
  - `ai` subcommand group with `process`, `status`, `query`, `graph` subcommands.
    All support `--json` flag for structured output. Errors to stderr.
- [x] TDD evidence planned (tests written/approved + red phase before implementation).
  - Tests per stage: extraction, classification, embeddings, summarization, graph.
    Each test suite written and failing before implementation of that stage.
- [x] Python standards planned (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses where appropriate, Typer CLI).
  - All AI models use pydantic for validation. All file paths use pathlib. Logging via
    `logging` module. Optional extras in pyproject.toml. Ruff + Ty clean.
- [x] Domain placement confirmed (correct domain package; no logic in cli/ or utils/;
  no legacy crawlers/ reference).
  - All AI logic in `src/tdoc_crawler/ai/` with `operations/`, `sources/`, `models.py`.
    CLI file `cli/ai.py` delegates only. No crawlers/ references.
- [x] DRY validation done (existing code searched; no duplicated logic introduced).
  - Reuses: `CacheManager` for path resolution, `create_cached_session()` for HTTP,
    existing `TDocDatabase` for reading TDoc metadata. No duplication of existing logic.
- [x] Network access plan documented (all HTTP via create_cached_session(); no direct
  calls to external services).
  - LLM calls go through litellm (local Ollama by default, no 3GPP server calls).
    Embedding model runs locally in-process. No HTTP to 3GPP servers from AI module.
    If remote LLM endpoints are configured, litellm handles the connection (not cached
    via hishel since LLM responses are non-deterministic and should not be cached).

## Library Boundary & CLI Contract

### Library: `tdoc_crawler.ai`

The AI processing pipeline is a standalone domain package at `src/tdoc_crawler/ai/`.
It depends on the existing tdoc-crawler core for reading TDoc metadata (`TDocDatabase`)
and resolving file paths (`CacheManager`), but all AI-specific logic, models, and
storage are self-contained within the `ai/` package.

**Public API** (exposed from `tdoc_crawler.ai`):

| Function | Purpose |
|----------|---------|
| `process_tdoc(tdoc_id, config)` | Run pipeline stages on a single TDoc |
| `process_all(config, new_only)` | Batch process all/new TDocs |
| `get_status(tdoc_id)` | Return processing status for a TDoc |
| `query_embeddings(query, top_k)` | Semantic search over embedded chunks |
| `query_graph(query, temporal_range)` | Query the temporal knowledge graph |

**Integration points** (read-only from core):

- `TDocDatabase` — read TDoc metadata (ID, meeting, title, status)
- `CacheManager` — resolve checkout paths where DOCX files live

**Dependency direction**: `ai/` depends on core; core MUST NOT depend on `ai/`.

### CLI Contract

The `ai` subcommand group is registered in `cli/app.py` and implemented in `cli/ai.py`.
CLI functions only parse arguments and delegate to the library API.

| Command | Input | Text Output | JSON Output |
|---------|-------|-------------|-------------|
| `ai process --tdoc-id <id>` | TDoc ID | Progress + summary line | `{"tdoc_id": ..., "stages": {...}}` |
| `ai process --all [--new-only]` | Flags | Progress bar + counts | `[{"tdoc_id": ..., "stages": {...}}, ...]` |
| `ai status --tdoc-id <id>` | TDoc ID | Stage table | `{"tdoc_id": ..., "stages": {...}}` |
| `ai query "<question>"` | Query text | Answer + source refs | `{"answer": ..., "sources": [...]}` |
| `ai graph --query "<question>"` | Query text | Chronological chain | `{"nodes": [...], "edges": [...]}` |

All commands accept `--json` for structured output. Errors go to stderr.

## TDD Evidence

Each pipeline stage follows the red-green-refactor cycle. Tests are written per stage,
user-approved, verified failing, then implementation proceeds.

| Stage | Test File | Key Test Cases |
|-------|-----------|----------------|
| DOCX Extraction | `tests/test_ai_extraction.py` | Single DOCX -> Markdown; tables preserved; headings preserved; 3GPP section numbering; idempotent re-run; corrupt file handling |
| Document Classification | `tests/test_ai_classification.py` | Single file -> main; two files (cover + contribution); filename heuristics; confidence scoring |
| Embeddings | `tests/test_ai_embeddings.py` | Chunk splitting; vector generation; metadata attachment; skip unchanged; model version tracking |
| Summarization | `tests/test_ai_summarization.py` | Abstract word count 150-250; structured summary fields; skip unchanged; missing LLM config error |
| Graph Construction | `tests/test_ai_graph.py` | Node creation; edge creation (references, revises); temporal fields; incremental update; cross-meeting query |
| Pipeline Orchestration | `tests/test_ai_pipeline.py` | Full pipeline single TDoc; batch processing; resume from failure; incremental (new-only) |
| CLI | `tests/test_ai_cli.py` | `--help` output; `--json` flag; error to stderr; delegation to library API |

**Approach**: For each stage, tests will mock external dependencies (LLM calls, embedding
model inference) using pytest fixtures. Integration tests with real models are marked
`@pytest.mark.integration` and require `tdoc_crawler[ai]` extras installed.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/tdoc_crawler/
├── ai/                        # New AI domain package
│   ├── __init__.py            # Public API: process_tdoc, process_all, query_*, get_status
│   ├── models.py              # Pydantic models: ProcessingStatus, DocumentClassification,
│   │                          #   DocumentChunk, ChunkEmbedding, DocumentSummary,
│   │                          #   GraphNode, GraphEdge, AiConfig
│   ├── storage.py             # LanceDB storage layer: init, read, write, query
│   ├── operations/
│   │   ├── __init__.py
│   │   ├── extract.py         # DOCX-to-Markdown extraction via Docling
│   │   ├── classify.py        # Main document identification heuristics
│   │   ├── embed.py           # Chunking + embedding generation
│   │   ├── summarize.py       # LLM summarization via litellm
│   │   ├── graph.py           # Temporal graph construction + incremental updates
│   │   └── pipeline.py        # Pipeline orchestrator: stage sequencing, resume, batch
│   └── config.py              # AiConfig: model endpoints, chunk params, prompt templates
├── cli/
│   └── ai.py                  # CLI subcommands (delegates to ai/ library)
└── ... (existing packages unchanged)

tests/
├── test_ai_extraction.py
├── test_ai_classification.py
├── test_ai_embeddings.py
├── test_ai_summarization.py
├── test_ai_graph.py
├── test_ai_pipeline.py
├── test_ai_cli.py
└── data/
    └── ai/                    # Test DOCX fixtures, expected Markdown outputs
```

**Structure Decision**: Single domain package `ai/` following the existing pattern of
`tdocs/`, `meetings/`, `specs/`. Operations are split by pipeline stage. Storage is
centralized in `storage.py` since all stages share the same LanceDB instance. Config
is separate from the main `config.py` to avoid coupling AI settings with core settings.

## Complexity Tracking

No constitution violations. All 7 gates pass. No justifications needed.
