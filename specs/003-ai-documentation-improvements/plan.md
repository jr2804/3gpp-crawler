# Implementation Plan: AI Documentation, Configuration & CLI Redesign

**Branch**: `003-ai-documentation-improvements` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-ai-documentation-improvements/spec.md`

## Summary

Four user stories drive the changes: (US1) Quick Start with free `openrouter/openrouter/free` defaults, (US2) streamlined `--auto-build` workspace creation, (US3) correct model configuration with zero hardcoded model identifiers, **(US4) CLI command redesign** to separate single-TDoc operations (summarize, convert) from workspace-based analysis (query with RAG+GraphRAG always enabled).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LiteLLM (LLM routing), Kreuzberg (document extraction), LanceDB (vector store), sentence-transformers (embeddings), Pydantic + pydantic-sqlite (models/DB), Typer + Rich (CLI)
**Storage**: LanceDB at `{cache_dir}/.ai/lancedb`, workspace-scoped tables with `::` delimiter
**Testing**: pytest — 16 test files, 96 tests in `tests/ai/` (expected: ~120 after CLI redesign)
**Target Platform**: Cross-platform CLI (Windows, macOS, Linux)
**Project Type**: Single project, domain-oriented (`tdocs/`, `meetings/`, `specs/`, `ai/`)
**Performance Goals**: N/A (CLI tool, not latency-critical)
**Constraints**: AI model-provider traffic is exempt from caching; breaking CLI changes require removing commands entirely
**Scale/Scope**: ~1500 LOC in `ai/` package, ~370 LOC in `cli/ai.py` (will increase with new commands), 27 FRs to satisfy

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Library-first boundary documented (standalone library + integration points).
  - `ai/` package exposes public API via `__init__.py` (26 symbols). CLI delegates to library
    functions. New `summarize_tdoc()`, `convert_tdoc()` will live in `ai/operations/`, not in CLI.
- [x] CLI contract defined (text input/output + JSON mode).
  - All CLI commands support `--json` output. New commands `ai summarize`, `ai convert` follow same pattern.
- [x] TDD evidence planned (tests written/approved + red phase before implementation).
  - New tests for CLI commands, RAG+GraphRAG integration, summarize/convert operations.
    Tests written first, verified failing (red), then implementation (green).
- [x] Python standards planned (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses where appropriate, Typer CLI).
  - All new code: typed, Ruff-clean, Ty-clean, logging-based, pathlib paths. CLI via Typer.
- [x] Domain placement confirmed (correct domain package; no logic in cli/ or utils/;
  no legacy crawlers/ reference).
  - New operations in `ai/operations/summarize.py`, `ai/operations/convert.py`. CLI only calls library. No `crawlers/` refs.
- [x] DRY validation done (existing code searched; no duplicated logic introduced).
  - Reuse existing `fetch_tdoc()` for remote fetching in summarize. Reuse existing embedding/graph infrastructure for merged RAG+GraphRAG queries.
- [x] Network access plan documented (core crawler source traffic via
  create_cached_session(); any AI model-provider traffic explicitly documented as
  exempt with approved provider/client integration).
  - AI traffic via LiteLLM is exempt (documented in spec FR-019 and AGENTS.md). Remote TDoc fetching for summarize uses WhatTheSpec/Portal with caching.

## Library Boundary & CLI Contract

### Library Module: `tdoc_crawler.ai`

**Public API** (existing + new, from `__init__.py`):

- `create_workspace(storage, name, auto_build=False)` — extended with `auto_build` param
- `AiConfig` — centralized configuration, no hardcoded defaults elsewhere
- `LiteLLMClient.complete(prompt, ..., model=None)` — already fixed, uses `AiConfig().llm_model` fallback
- **NEW**: `summarize_tdoc(tdoc_id, words=200, format='markdown', fetch_remote=True)` — summarize single TDoc
- **NEW**: `convert_tdoc(tdoc_id, output_path=None)` — convert single TDoc to markdown
- **CHANGED**: `query_embeddings(query, workspace, top_k=5)` — workspace-only, no single-TDoc mode
- **REMOVED**: `process_tdoc()` — internal only, called by workspace workflow
- **REMOVED**: `get_status()` — internal only

**New library surface**:

- `Workspace.auto_build: bool = False` — new field on workspace model
- `DocumentSummary.llm_model` — default changed from hardcoded `"ollama/llama3.2"` to
  dynamic `AiConfig().llm_model` via a `default_factory`
- `SummarizeResult` — new model with `summary`, `keywords`, `metadata`, `word_count`
- `QueryResult` — extended to include both embedding results and graph relationships (merged RAG+GraphRAG)

### CLI Contract: `cli/ai.py`

**Removed Commands**:
| Command | Reason | Migration Path |
|---------|--------|----------------|
| `ai process` | Internal operation only | Use `ai workspace create --auto-build` or `ai workspace add-members` (auto-processes) |
| `ai status` | Internal state only | Check workspace member processing status via `ai workspace list-members --workspace X` |
| `ai graph` | Redundant with query | Use `ai query` (automatically includes GraphRAG) |

**New Commands**:
| Command | Change | Text Output | JSON Output |
|---------|--------|-------------|-------------|
| `ai summarize TDOC-ID` | New command | Summary text with word count, keywords | `{"summary": "...", "keywords": [...], "metadata": {...}, "word_count": 185}` |
| `ai convert TDOC-ID` | New command | "Converted TDOC-ID to file.md" | `{"output_path": "file.md", "format": "markdown"}` |

**Modified Commands**:
| Command | Change | Text Output | JSON Output |
|---------|--------|-------------|-------------|
| `ai workspace create NAME` | Add `--auto-build` flag | "Created workspace 'X' (auto-build: on/off)" | `{"name": "X", "auto_build": true, ...}` |
| `ai query QUERY` | Workspace-only, merged RAG+GraphRAG | Answer + sources (merged) | `{"answer": "...", "sources": [...], "graph_relationships": [...]}` |
| `ai query` | Remove `--workspace` optional, make required | Error if no workspace specified | Error object |

**Input**: `--words` (int, default 200), `--format` (markdown/json/yaml, default markdown), `--output` (file path for convert)
**Output**: Summaries include keywords + metadata. Query results include merged RAG+GraphRAG.

## TDD Evidence

### Tests to Write First (Red Phase)

**US3 (Hardcoded Models)**:

1. **`test_no_hardcoded_models`** — Scan all `.py` files in `src/tdoc_crawler/ai/` for string
   literals matching known model patterns (`gpt-4o`, `llama3`, `ollama/llama`). Assert zero
   matches outside of `config.py` (where defaults are defined).

1. **`test_model_config_propagation`** — Verify that `LiteLLMClient.complete()` uses
   `AiConfig().llm_model` when no explicit model is passed. Verify `DocumentSummary`
   default matches `AiConfig().llm_model`.

**US2 (Auto-Build)**:
3\. **`test_workspace_auto_build_flag`** — Create workspace with `auto_build=True`.
Verify the flag persists in storage. Retrieve workspace and assert `auto_build` is `True`.

4. **`test_workspace_auto_build_default_off`** — Create workspace without auto_build.
   Verify default is `False`.

1. **`test_workspace_create_cli_auto_build`** — CLI integration test: invoke
   `ai workspace create --auto-build test-ws` and verify output includes auto-build status.

**US4 (CLI Redesign)**:
6\. **`test_summarize_command_exists`** — Invoke `ai summarize TDOC-ID --words 200 --format markdown`. Verify output contains summary, keywords, metadata. Word count within ±20%.

7. **`test_summarize_fetches_remote`** — Invoke `ai summarize` on TDoc not checked out locally. Verify system fetches from WhatTheSpec/Portal and produces summary.

1. **`test_summarize_output_formats`** — Test all three formats (markdown, json, yaml). Verify JSON/YAML include structured `summary`, `keywords`, `metadata` fields.

1. **`test_convert_command_exists`** — Invoke `ai convert TDOC-ID --output file.md`. Verify markdown file created.

1. **`test_query_workspace_required`** — Invoke `ai query "test"` without `--workspace`. Verify error message requires workspace.

1. **`test_query_merged_rag_graphrag`** — Invoke `ai query` on workspace. Verify results include both embedding-based matches and graph relationships (merged, not separate).

1. **`test_removed_commands_unavailable`** — Invoke `ai process`, `ai status`, `ai graph`. Verify commands don't exist (Typer raises error).

### Red-Green Sequence

1. Write all 12 tests → verify they FAIL (red)
1. Fix `DocumentSummary.llm_model` default → tests 1-2 turn green
1. Add `Workspace.auto_build` field → tests 3-4 turn green
1. Update CLI `workspace_create` → test 5 turns green
1. Implement `ai summarize` command → tests 6-8 turn green
1. Implement `ai convert` command → test 9 turns green
1. Update `ai query` (workspace-only, merged RAG+GraphRAG) → tests 10-11 turn green
1. Remove `ai process`, `ai status`, `ai graph` → test 12 turns green
1. Run full suite: all 96 existing + 12 new = 108 tests pass

## Project Structure

### Documentation (this feature)

```text
specs/003-ai-documentation-improvements/
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
├── ai/
│   ├── __init__.py          # Public API — add summarize_tdoc, convert_tdoc; remove process_tdoc, get_status
│   ├── config.py            # AiConfig — defaults already fixed (FR-002, FR-003)
│   ├── models.py            # Fix DocumentSummary.llm_model; add Workspace.auto_build; add SummarizeResult
│   ├── storage.py           # No changes needed
│   └── operations/
│       ├── pipeline.py      # Verify model propagation
│       ├── summarize.py     # Add summarize_tdoc() with remote fetch, word count, formats
│       ├── convert.py       # NEW: convert_tdoc() for markdown conversion
│       └── workspaces.py    # Accept auto_build param in create_workspace()
├── cli/
│   └── ai.py               # Add --auto-build flag; add summarize/convert commands; remove process/status/graph; update query
└── ...

tests/ai/
├── test_config.py           # Add test_no_hardcoded_models, test_model_config_propagation
├── test_workspace.py        # Add auto_build tests
├── test_cli_ai.py           # Add CLI tests for new commands
├── test_summarize.py        # NEW: summarize operation tests
├── test_convert.py          # NEW: convert operation tests
└── test_query.py            # NEW: workspace-only query tests with merged RAG+GraphRAG
```

**Structure Decision**: Single project, domain-oriented. All changes confined to `ai/` domain
package and its CLI surface `cli/ai.py`. New operations in `ai/operations/`.

## Complexity Tracking

### Hardcoded Model Locations Found

| File | Line | Current Value | Fix |
|------|------|---------------|-----|
| `ai/operations/summarize.py` | 120 | `"gpt-4o-mini"` | ✅ Already fixed — uses `model or AiConfig().llm_model` |
| `ai/models.py` | 268 | `"ollama/llama3.2"` | ❌ **TODO** — change to `default_factory=lambda: AiConfig().llm_model` |

### CLI Command Changes

| Action | Commands | Impact |
|--------|----------|--------|
| **Remove** | `ai process`, `ai status`, `ai graph` | Breaking change — users must migrate to workspace workflow |
| **Add** | `ai summarize`, `ai convert` | New single-TDoc operations |
| **Modify** | `ai query`, `ai workspace create` | Workspace-only query, auto-build flag |

### Constitution Violations

> No violations. All 7 gates pass. CLI redesign maintains library-first boundary (operations in `ai/`, CLI delegates).
