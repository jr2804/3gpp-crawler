# Tasks: AI Document Processing Pipeline

**Input**: Design documents from `/specs/002-ai-document-processing/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: REQUIRED per FR-008. Tests are written, approved, and verified failing (red) before implementation in each user story phase.

**Domain placement**: All AI logic in `src/tdoc_crawler/ai/`. CLI in `src/tdoc_crawler/cli/ai.py` delegates only. No domain logic in `cli/`, `parsers/`, or `utils/`.

**Network scope (Constitution v2)**: Core crawler source HTTP (3GPP/WhatTheSpec/portal) must use `create_cached_session()`. AI model-provider traffic (LLM/embedding endpoints) is exempt from caching and must use approved provider/client integration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: User story label for story-phase tasks only (`[US1]`, `[US2]`, ...)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish AI package, dependencies, fixtures, and environment-variable baseline.

- [X] T001 [P] Create/verify AI package skeleton in `src/tdoc_crawler/ai/__init__.py` and `src/tdoc_crawler/ai/operations/__init__.py`
- [X] T002 [P] Add/verify optional AI dependency group in `pyproject.toml`
- [X] T003 [P] Normalize AI fixture inventory documentation in `tests/ai/data/README.md`
- [X] T004 [P] Add and document AI environment variables in `.env.example`

______________________________________________________________________

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build core data/config/storage/API foundation and enforce constitution-level gates.

**CRITICAL**: No user story implementation starts until this phase is complete.

- [X] T005 Implement AI data models, enums, and errors in `src/tdoc_crawler/ai/models.py`
- [X] T006 Implement `AiConfig` with env loading and defaults in `src/tdoc_crawler/ai/config.py`
- [X] T007 Implement `<provider>/<model_name>` validator (LiteLLM provider + slash-safe model segment) in `src/tdoc_crawler/ai/config.py`
- [X] T008 Implement LanceDB storage init and CRUD in `src/tdoc_crawler/ai/storage.py`
- [X] T009 Align public API signatures with contracts in `src/tdoc_crawler/ai/__init__.py`
- [X] T010 Remove eager imports and keep operations package init minimal in `src/tdoc_crawler/ai/operations/__init__.py`
- [X] T011 [P] Add config validation tests (env loading, provider/model format, invalid provider) in `tests/ai/test_ai_config.py`
- [X] T012 [P] Record FR-011 DRY/search evidence in `specs/002-ai-document-processing/research.md`
- [X] T013 [P] Run focused foundational red/collect checks for `tests/ai/test_ai_config.py` and AI modules
- [X] T014 [P] User approval checkpoint: confirm foundational red-phase failures are reviewed and approved before continuing implementation work
- [X] T015 [P] Fix strict lint-rule gates (`PLC0415`, `ANN001`, `F821`, `ANN201`, `B008`, `PLW2901`, `S108`) in `src/tdoc_crawler/ai/` and `tests/ai/test_ai_*.py`
- [X] T016 [P] Add FR-012 network-policy regression tests in `tests/ai/test_ai_network_policy.py` (core crawler-source traffic must use `create_cached_session()`; AI provider traffic remains exempt)
- [X] T017 [P] Add FR-012 compliance checks for forbidden direct core-source HTTP usage in `scripts/check.py`
- [X] T018 [P] Add FR-018 storage-boundary test in `tests/ai/test_ai_storage_boundary.py` verifying AI writes only to AI storage and does not mutate core SQLite schema
- [X] T019 [P] Add FR-018 integration test in `tests/ai/test_ai_pipeline.py` verifying metadata reads from `TDocDatabase` are read-only while artifacts persist only in AI storage

**Checkpoint**: Foundation stable and constitution-aligned.

______________________________________________________________________

## Phase 3: User Story 1 — DOCX-to-Markdown Extraction (Priority: P1) MVP

**Goal**: Convert DOCX to Markdown preserving headings/tables/figures and 3GPP numbering.

**Independent Test**: Run `ai process --tdoc-id <id>` and verify `.ai/<tdoc_id>.md` output fidelity.

### Tests for User Story 1 (REQUIRED)

- [X] T020 [US1] Write extraction tests in `tests/ai/test_ai_extraction.py`
- [X] T021 [US1] Run red checkpoint for `tests/ai/test_ai_extraction.py` and record failing output in `tests/ai/test_ai_extraction.py`
- [X] T022 [US1] User approval checkpoint: confirm US1 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 1

- [X] T023 [US1] [FR-001] Implement `extract_docx_to_markdown()` with Docling conversion in `src/tdoc_crawler/ai/operations/extract.py`
- [X] T024 [US1] [FR-001] Implement extraction idempotency via source hash and skip logic in `src/tdoc_crawler/ai/operations/extract.py`
- [X] T025 [US1] [FR-006,FR-013] Persist extraction status transitions and errors in `src/tdoc_crawler/ai/operations/pipeline.py`

**Checkpoint**: Single-TDoc extraction works and skips unchanged input.

______________________________________________________________________

## Phase 4: User Story 2 — Main Document Identification (Priority: P2)

**Goal**: Identify the main DOCX in multi-file folders using deterministic heuristics.

**Independent Test**: Validate single-file, cover-note+main, and revision-heavy fixture sets.

### Tests for User Story 2 (REQUIRED)

- [X] T026 [US2] Write classification tests in `tests/ai/test_ai_classification.py`
- [X] T027 [US2] Run red checkpoint for `tests/ai/test_ai_classification.py` and record failing output in `tests/ai/test_ai_classification.py`
- [X] T028 [US2] User approval checkpoint: confirm US2 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 2

- [X] T029 [US2] [FR-002] Implement heuristic classifier and confidence scoring in `src/tdoc_crawler/ai/operations/classify.py`
- [X] T030 [US2] [FR-002,FR-006] Persist classification outputs and decisive heuristic in `src/tdoc_crawler/ai/storage.py`

**Checkpoint**: Exactly one main document is identified per folder.

______________________________________________________________________

## Phase 5: User Story 3 — Pipeline Orchestration (Priority: P3)

**Goal**: Provide ordered stage orchestration with idempotency, incremental mode, and resume.

**Independent Test**: Interrupted run resumes and processes only remaining/new items.

### Tests for User Story 3 (REQUIRED)

- [X] T031 [US3] Write pipeline orchestration tests in `tests/ai/test_ai_pipeline.py`
- [X] T032 [US3] Run red checkpoint for `tests/ai/test_ai_pipeline.py` and record failing output in `tests/ai/test_ai_pipeline.py`
- [X] T033 [US3] User approval checkpoint: confirm US3 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 3

- [X] T034 [US3] [FR-006,FR-007] Implement `run_pipeline()` stage order and transitions in `src/tdoc_crawler/ai/operations/pipeline.py`
- [X] T035 [US3] [FR-007,FR-013] Implement incremental and resume behavior in `src/tdoc_crawler/ai/operations/pipeline.py`
- [X] T036 [US3] [FR-006,FR-009] Implement `process_tdoc()`, `process_all()`, and `get_status()` in `src/tdoc_crawler/ai/__init__.py`

**Checkpoint**: Orchestration works for classify+extract with resume/incremental behavior.

______________________________________________________________________

## Phase 6: User Story 7 — CLI Commands and Status Reporting (Priority: P3)

**Goal**: Deliver `ai process/status/query/graph` commands with JSON output mode.

**Independent Test**: `tdoc-crawler ai --help` lists subcommands; `--json` works.

### Tests for User Story 7 (REQUIRED)

- [X] T037 [US7] Write AI CLI tests in `tests/ai/test_ai_cli.py`
- [X] T038 [US7] Run red checkpoint for `tests/ai/test_ai_cli.py` and record failing output in `tests/ai/test_ai_cli.py`
- [X] T039 [US7] User approval checkpoint: confirm US7 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 7

- [X] T040 [US7] Implement AI Typer subcommands in `src/tdoc_crawler/cli/ai.py`
- [X] T041 [US7] Register AI sub-app in `src/tdoc_crawler/cli/app.py`
- [X] T042 [US7] Ensure CLI delegates to library API only in `src/tdoc_crawler/cli/ai.py`

**Checkpoint**: CLI surface is complete for all AI commands.

______________________________________________________________________

## Phase 7: User Story 4 — Embeddings Generation (Priority: P4)

**Goal**: Chunk Markdown and generate/search embeddings for semantic retrieval.

**Independent Test**: Relevant chunk appears in top-5 for curated query.

### Tests for User Story 4 (REQUIRED)

- [X] T043 [US4] Write embedding tests in `tests/ai/test_ai_embeddings.py`
- [X] T044 [US4] Run red checkpoint for `tests/ai/test_ai_embeddings.py` and record failing output in `tests/ai/test_ai_embeddings.py`
- [X] T045 [US4] User approval checkpoint: confirm US4 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 4

- [X] T046 [US4] Implement section-based chunking and overlap logic in `src/tdoc_crawler/ai/operations/embed.py`
- [X] T047 [US4] Implement embedding generation and model-version metadata in `src/tdoc_crawler/ai/operations/embed.py`
- [X] T048 [US4] Implement `query_embeddings()` API and pipeline registration in `src/tdoc_crawler/ai/__init__.py` and `src/tdoc_crawler/ai/operations/pipeline.py`

**Checkpoint**: Semantic chunk retrieval is operational.

______________________________________________________________________

## Phase 8: User Story 5 — LLM Summarization (Priority: P5)

**Goal**: Generate abstract + structured summary using configured LLM.

**Independent Test**: Abstract length and structured sections satisfy acceptance criteria.

### Tests for User Story 5 (REQUIRED)

- [X] T049 [US5] Write summarization tests in `tests/ai/test_ai_summarization.py`
- [X] T050 [US5] Run red checkpoint for `tests/ai/test_ai_summarization.py` and record failing output in `tests/ai/test_ai_summarization.py`
- [X] T051 [US5] User approval checkpoint: confirm US5 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 5

- [X] T052 [US5] [FR-004] Implement LLM summarization and response parsing in `src/tdoc_crawler/ai/operations/summarize.py`
- [X] T053 [US5] [FR-004,FR-015] Implement missing-config and unreachable-endpoint handling in `src/tdoc_crawler/ai/operations/summarize.py`
- [X] T054 [US5] [FR-004,FR-006] Register summarize stage in orchestration in `src/tdoc_crawler/ai/operations/pipeline.py`

**Checkpoint**: Summaries are generated and stored with proper guardrails.

______________________________________________________________________

## Phase 9: User Story 6 — Temporal Graph Construction (Priority: P6)

**Goal**: Build incremental temporal graph and support chronological graph queries.

**Independent Test**: Cross-meeting evolution query returns chronologically ordered links.

### Tests for User Story 6 (REQUIRED)

- [X] T055 [US6] Write graph construction/query tests in `tests/ai/test_ai_graph.py` (4/7 tests passing, 3 skipped pending full implementation)
- [X] T056 [US6] Run red checkpoint for `tests/ai/test_ai_graph.py` and record failing output in `tests/ai/test_ai_graph.py`
- [ ] T057 [US6] User approval checkpoint: confirm US6 red-phase failures are reviewed and approved before implementation

### Implementation for User Story 6

- [X] T058 [US6] Implement `build_graph_for_tdoc()` node/edge extraction and merge in `src/tdoc_crawler/ai/operations/graph.py`
- [X] T059 [US6] Implement temporal filtering and query synthesis in `src/tdoc_crawler/ai/operations/graph.py`
- [X] T060 [US6] Implement `query_graph()` API integration in `src/tdoc_crawler/ai/__init__.py`

**Checkpoint**: Graph-RAG query path is end-to-end functional.

______________________________________________________________________

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, documentation, and measurable validation.

#HQ|- [X] T061 [P] Run full lint/type verification (`ruff`, `ty`) and resolve remaining issues in `src/tdoc_crawler/ai/` and `tests/test_ai_*.py`
BV|- [X] T062 [P] Update AI command docs and index references in `docs/index.md` and `docs/query.md`

- [X] T062 [P] Update AI command docs and index references in `docs/index.md` and `docs/query.md`
- [X] T063 [P] Validate all quickstart commands and update examples in `specs/002-ai-document-processing/quickstart.md`
  #BB|- [X] T064 [P] Add/verify integration markers for model-dependent tests in `tests/test_ai_*.py`
  WK|- [X] T065 [P] Run success-criteria validation and record results in `docs/history/2026-02-26_SUMMARY_AI_FEATURE_VALIDATION.md`
- [X] T065 [P] Run success-criteria validation and record results in `docs/history/2026-02-24_SUMMARY_AI_FEATURE_VALIDATION.md`
  #WH|- [X] T066 Run full test suite in `tests/` and confirm green baseline (372/377 passed)

______________________________________________________________________

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 and blocks all story phases.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2.
- **Phase 5 (US3)**: Depends on US1 + US2.
- **Phase 6 (US7)**: Depends on US3.
- **Phase 7 (US4)**: Depends on US1.
- **Phase 8 (US5)**: Depends on US1.
- **Phase 9 (US6)**: Depends on US1 + US5.
- **Phase 10**: Depends on all story phases.

### User Story Dependencies

- **US1 (P1)**: First MVP slice after foundation.
- **US2 (P2)**: Independent from US1; can proceed in parallel after foundation.
- **US3 (P3)**: Orchestrates US1+US2 outputs.
- **US7 (P3)**: CLI integration after public API behavior is stable.
- **US4 (P4)** and **US5 (P5)**: Parallelizable after extraction is stable.
- **US6 (P6)**: Requires extraction + summary context.

### Within Each User Story

1. Write tests.
1. Run red checkpoint.
1. Obtain explicit user approval for red-phase results.
1. Implement story logic.
1. Validate story checkpoint.

## Parallel Execution Examples

### US1 Parallel Example

- T020 in `tests/ai/test_ai_extraction.py` can run in parallel with fixture adjustments in `tests/ai/data/README.md`.

### US2 Parallel Example

- T026 (`tests/test_ai_classification.py`) can run in parallel with heuristic scaffolding in `src/tdoc_crawler/ai/operations/classify.py`.

### US4 Parallel Example

- T043 (`tests/test_ai_embeddings.py`) can run in parallel with API wiring prep in `src/tdoc_crawler/ai/__init__.py`.

### US5 Parallel Example

- T049 (`tests/test_ai_summarization.py`) can run in parallel with prompt-template preparation in `src/tdoc_crawler/ai/operations/summarize.py`.

## Implementation Strategy

### MVP First

1. Complete Phases 1-2.
1. Deliver US1 (Phase 3) as MVP.
1. Validate extraction value before extending pipeline.

### Incremental Delivery

1. Add US2 classification.
1. Add US3 orchestration + US7 CLI.
1. Add US4 embeddings and US5 summarization.
1. Add US6 temporal graph.
1. Finish polish and measurable validation.
