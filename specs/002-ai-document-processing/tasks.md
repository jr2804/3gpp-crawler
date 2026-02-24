# Tasks: AI Document Processing Pipeline

**Input**: Design documents from `/specs/002-ai-document-processing/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: REQUIRED per FR-008. Tests are written and verified failing before implementation in each user story phase.

**Domain placement**: All AI logic in `src/tdoc_crawler/ai/`. CLI in `src/tdoc_crawler/cli/ai.py` delegates only. No logic in `cli/`, `parsers/`, or `utils/`. LLM calls use litellm directly (not cached via hishel — non-deterministic responses). All other HTTP through `create_cached_session()`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story (US1-US7) from spec.md
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the ai/ package skeleton, declare AI dependencies, and prepare test fixtures

- [x] T001 [P] Create ai/ package structure with `__init__.py` in src/tdoc_crawler/ai/ and src/tdoc_crawler/ai/operations/
- [x] T002 [P] Add optional `[ai]` dependency group (docling, lancedb, litellm, sentence-transformers) to pyproject.toml
- [x] T003 [P] Create test fixture directory tests/data/ai/ with sample DOCX files (single-file TDoc, multi-file TDoc with cover note, corrupt/empty file)

______________________________________________________________________

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, configuration, and storage layer that all user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement all pydantic models, enums (PipelineStage, GraphNodeType, GraphEdgeType), and error types (AiError, TDocNotFoundError, ExtractionError, LlmConfigError, AiConfigError, EmbeddingDimensionError) per data-model.md in src/tdoc_crawler/ai/models.py
- [x] T005 [P] Implement AiConfig configuration model with environment variable loading and defaults per data-model.md in src/tdoc_crawler/ai/config.py
- [x] T006 Implement AiStorage class with LanceDB connection, table initialization (processing_status, classifications, chunks, summaries, graph_nodes, graph_edges), and all CRUD methods per contracts/api.md in src/tdoc_crawler/ai/storage.py
- [x] T007 Create public API module with stub functions (process_tdoc, process_all, get_status, query_embeddings, query_graph) per contracts/api.md in src/tdoc_crawler/ai/**init**.py

**Checkpoint**: Foundation ready — user story implementation can now begin

______________________________________________________________________

## Phase 3: User Story 1 — DOCX-to-Markdown Extraction (Priority: P1) MVP

**Goal**: Convert downloaded DOCX files to clean Markdown preserving headings, tables, and figure references via Docling

**Independent Test**: Run `ai process --tdoc-id SP-123456` on a TDoc with at least one table and heading hierarchy. Verify `.ai/<tdoc_id>.md` is created with matching structure.

### Tests for User Story 1 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T008 [US1] Write extraction tests (single DOCX to Markdown, table preservation, heading hierarchy, 3GPP section numbering, idempotent re-run skips unchanged, corrupt file raises ExtractionError, no-DOCX folder logs warning) in tests/test_ai_extraction.py

### Implementation for User Story 1

- [ ] T009 [US1] Implement extract_docx_to_markdown() using Docling DocumentConverter with source_hash change detection and idempotent skip logic in src/tdoc_crawler/ai/operations/extract.py

**Checkpoint**: A single TDoc DOCX can be converted to Markdown and the result is persisted. Re-running skips unchanged files.

______________________________________________________________________

## Phase 4: User Story 2 — Main Document Identification (Priority: P2)

**Goal**: Automatically determine which DOCX file in a multi-file TDoc folder is the "main" document vs. secondary (cover notes, drafts)

**Independent Test**: Prepare 3 test folders (single file, two files with cover note, three files with revision). Run classification and verify the main document is correctly identified in each case.

### Tests for User Story 2 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [US2] Write classification tests (single file gets confidence 1.0, two files picks larger/structured one, filename heuristics for final/draft, revision preference, confidence scoring range) in tests/test_ai_classification.py

### Implementation for User Story 2

- [ ] T011 [US2] Implement classify_tdoc_files() with filename heuristics, file size comparison, structure analysis, confidence scoring, and decisive_heuristic audit trail in src/tdoc_crawler/ai/operations/classify.py

**Checkpoint**: Multi-file TDoc folders are classified with exactly one main document identified. Classification results stored via AiStorage.

______________________________________________________________________

## Phase 5: User Story 3 — Pipeline Orchestration (Priority: P3)

**Goal**: Execute AI stages in order (classify, extract, then later embed/summarize/graph) with resume-from-failure and incremental processing

**Independent Test**: Process 5 TDocs, interrupt after 3, re-run and verify only remaining 2 are processed. Check all 5 show completed in status.

### Tests for User Story 3 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [US3] Write pipeline tests (full single-TDoc pipeline, batch processing, resume from interrupted stage, incremental new-only mode, failed TDoc does not block others, progress callback invocation) in tests/test_ai_pipeline.py

### Implementation for User Story 3

- [ ] T013 [US3] Implement run_pipeline() with ordered stage execution (classify then extract), ProcessingStatus tracking, resume logic via stage timestamps, and per-TDoc error isolation in src/tdoc_crawler/ai/operations/pipeline.py
- [ ] T014 [US3] Implement process_tdoc(), process_all(), get_status() public API functions delegating to run_pipeline() and AiStorage in src/tdoc_crawler/ai/**init**.py

**Checkpoint**: `process_tdoc()` and `process_all()` work end-to-end for classify + extract stages. Status tracking and resume work correctly.

______________________________________________________________________

## Phase 6: User Story 7 — CLI Commands and Status Reporting (Priority: P3)

**Goal**: Provide `ai process`, `ai status`, `ai query`, and `ai graph` CLI subcommands following existing tdoc-crawler patterns

**Independent Test**: Run `tdoc-crawler ai --help` and verify all subcommands listed. Run `ai status --tdoc-id <id>` on a processed TDoc and verify stage output.

### Tests for User Story 7 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T015 [US7] Write CLI tests (--help lists all subcommands, process delegates to process_tdoc/process_all, status delegates to get_status, --json flag produces valid JSON, errors go to stderr) in tests/test_ai_cli.py

### Implementation for User Story 7

- [ ] T016 [US7] Implement ai Typer sub-app with process, status, query, and graph commands per contracts/cli.md in src/tdoc_crawler/cli/ai.py
- [ ] T017 [US7] Register ai_app Typer sub-app on the main app in src/tdoc_crawler/cli/app.py

**Checkpoint**: All 4 AI subcommands are accessible via CLI. `ai process` and `ai status` are fully functional. `ai query` and `ai graph` exist but return empty results until Phases 7 and 9.

______________________________________________________________________

## Phase 7: User Story 4 — Embeddings Generation (Priority: P4)

**Goal**: Chunk extracted Markdown by section and generate vector embeddings for semantic search across the TDoc corpus

**Independent Test**: Process 3 TDocs through extraction, run embeddings stage, query "uplink power control" and verify relevant chunks in top-5 results.

### Tests for User Story 4 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [US4] Write embedding tests (section-based chunking splits at headings, paragraph fallback for long sections, chunk metadata includes TDoc ID and section, vector dimensions match model, skip unchanged TDoc, model version recorded, embedding dimension mismatch detected) in tests/test_ai_embeddings.py

### Implementation for User Story 4

- [ ] T019 [US4] Implement chunk_and_embed() with Markdown heading-based section splitting, configurable max_chunk_size/chunk_overlap, and sentence-transformers vector encoding in src/tdoc_crawler/ai/operations/embed.py
- [ ] T020 [US4] Implement query_embeddings() with query vector encoding and AiStorage.search_chunks() delegation in src/tdoc_crawler/ai/**init**.py, and register embed stage in src/tdoc_crawler/ai/operations/pipeline.py

**Checkpoint**: Extracted Markdown is chunked and embedded. `ai query` returns semantically relevant chunks ranked by similarity.

______________________________________________________________________

## Phase 8: User Story 5 — LLM Summarization (Priority: P5)

**Goal**: Generate 150-250 word abstracts and structured summaries (key points, action items, decisions, affected specs) using a configurable LLM

**Independent Test**: Process a known TDoc through extraction, run summarization, verify abstract is 150-250 words and mentions the TDoc's key topic.

### Tests for User Story 5 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T021 [US5] Write summarization tests (abstract word count 150-250, structured summary has key_points/action_items/decisions/affected_specs, skip unchanged TDoc, missing LLM config raises LlmConfigError, Change Request TDoc includes affected spec and rationale) in tests/test_ai_summarization.py

### Implementation for User Story 5

- [ ] T022 [US5] Implement summarize_tdoc() with litellm prompt construction, response parsing into DocumentSummary fields, and LLM availability check in src/tdoc_crawler/ai/operations/summarize.py, and register summarize stage in src/tdoc_crawler/ai/operations/pipeline.py

**Checkpoint**: Processed TDocs have LLM-generated abstracts and structured summaries stored in LanceDB. Pipeline runs summarization after extraction.

______________________________________________________________________

## Phase 9: User Story 6 — Temporal Graph Construction (Priority: P6)

**Goal**: Build a knowledge graph connecting TDocs, meetings, specs, work items, and concepts with temporal validity for cross-meeting evolution queries

**Independent Test**: Process 10 TDocs from 3 meetings discussing the same work item. Build graph. Query evolution and verify chronologically ordered TDoc chain.

### Tests for User Story 6 (REQUIRED)

> **Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T023 [US6] Write graph tests (node creation for TDoc/Meeting/Spec/Concept types, edge creation for discusses/revises/references relationships, temporal validity fields populated, incremental update adds without rebuild, cross-meeting query returns chronological order, explicit TDoc-ID reference creates references edge) in tests/test_ai_graph.py

### Implementation for User Story 6

- [ ] T024 [US6] Implement build_graph_for_tdoc() with entity extraction from Markdown and summary, relationship mapping to GraphEdge types, and temporal context from meeting metadata in src/tdoc_crawler/ai/operations/graph.py, and register graph stage in src/tdoc_crawler/ai/operations/pipeline.py
- [ ] T025 [US6] Implement query_graph() with temporal range filtering, node type filtering, and answer synthesis in src/tdoc_crawler/ai/**init**.py

**Checkpoint**: Full pipeline runs all 6 stages. `ai graph --query` returns chronologically ordered results with meeting context.

______________________________________________________________________

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality, documentation, and validation across all stories

- [ ] T026 [P] Run Ruff and Ty checks, fix all lint and type errors across src/tdoc_crawler/ai/ and tests/test_ai\_\*.py
- [ ] T027 [P] Update docs/index.md and relevant docs/ files with AI commands reference documentation
- [ ] T028 Run quickstart.md validation: execute all CLI examples from specs/002-ai-document-processing/quickstart.md and verify outputs
- [ ] T028b Run success criteria validation against spec.md success criteria and record outcomes in docs/history/
- [ ] T029 [P] Add @pytest.mark.integration markers for tests requiring real AI models (Docling, sentence-transformers, litellm) in tests/
- [ ] T030 Run full test suite with uv run pytest -v and verify all tests pass

______________________________________________________________________

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 Extraction (Phase 3)**: Depends on Phase 2
- **US2 Classification (Phase 4)**: Depends on Phase 2
- **US3 Pipeline (Phase 5)**: Depends on Phase 3 + Phase 4 (orchestrates classify + extract)
- **US7 CLI (Phase 6)**: Depends on Phase 5 (needs public API to delegate to)
- **US4 Embeddings (Phase 7)**: Depends on Phase 3 (needs extracted Markdown)
- **US5 Summarization (Phase 8)**: Depends on Phase 3 (needs extracted Markdown)
- **US6 Graph (Phase 9)**: Depends on Phase 3 + Phase 8 (needs Markdown + summary for entity hints)
- **Polish (Phase 10)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no dependencies on other stories
- **US2 (P2)**: After Phase 2 — no dependencies on other stories. **Can run in parallel with US1.**
- **US3 (P3)**: After US1 + US2 — orchestrates both stages
- **US7 (P3)**: After US3 — CLI delegates to public API from US3
- **US4 (P4)**: After US1 — needs extracted Markdown as input. **Can run in parallel with US5.**
- **US5 (P5)**: After US1 — needs extracted Markdown as input. **Can run in parallel with US4.**
- **US6 (P6)**: After US1 + US5 — needs Markdown and DocumentSummary for entity hints

### Within Each User Story

1. Tests MUST be written and verified FAILING before implementation
1. Models/storage integration before operation logic
1. Operation module before public API integration
1. Story complete and checkpoint verified before moving to next priority

### Parallel Opportunities

- **Phase 1**: All tasks (T001, T002, T003) can run in parallel
- **Phase 2**: T005 (config.py) can run in parallel with T004 (models.py)
- **Phase 3 + Phase 4**: US1 and US2 can run in parallel (independent stories)
- **Phase 7 + Phase 8**: US4 and US5 can run in parallel (both depend only on US1)
- **Phase 10**: T026, T027, T029 can run in parallel

## Implementation Strategy

### MVP Scope

**Phases 1-3** (T001-T009, 9 tasks) deliver a working DOCX-to-Markdown extraction pipeline — the single highest-value capability.

### Incremental Delivery

| Milestone | Phases | Capability |
|-----------|--------|------------|
| MVP | 1-3 | Extract single TDoc DOCX to Markdown |
| Classification | +4 | Multi-file TDoc main document identification |
| Batch Processing | +5-6 | Full pipeline orchestration + CLI |
| Semantic Search | +7 | Embeddings + `ai query` command |
| Summaries | +8 | LLM-generated abstracts and structured summaries |
| Knowledge Graph | +9 | Temporal graph + `ai graph` command |
| Release | +10 | Full polish, docs, and validation |
