# Tasks: AI Documentation, Configuration & CLI Redesign

**Feature**: AI Documentation Improvements & CLI Redesign
**Spec**: `specs/003-ai-documentation-improvements/spec.md`
**Plan**: `specs/003-ai-documentation-improvements/plan.md`
**Branch**: `003-ai-documentation-improvements`

**Priority**: US3 (hardcoded models) → US2 (auto-build) → US4 (CLI redesign) → US1 (documentation)
**Rationale**: US3 is highest priority because it blocks correctness. US4 (CLI redesign) is a breaking change that affects user experience but doesn't block code correctness.

**Total new tests**: 12. **Expected final count**: 108 tests (96 existing + 12 new).

______________________________________________________________________

## Phase 1: Setup

**Goal**: Project already initialized — no setup tasks needed.

**Checklist**:

- [x] Repository cloned, branch created
- [x] Virtual environment activated
- [x] Dependencies installed
- [x] Existing tests passing (96 tests in `tests/ai/`)

______________________________________________________________________

## Phase 2: Foundational — TDD Red Phase (Blocks All Implementation)

**Goal**: Write all new tests first, verify they FAIL (red phase). Constitution Gate 3 requires TDD evidence.

### US3 Tests (Hardcoded Models)

- [ ] T001 [P] [US3] Write `test_no_hardcoded_models` in `tests/ai/test_config.py` — Scan all `.py` files in `src/tdoc_crawler/ai/` for string literals matching known model patterns (`gpt-4o`, `llama3`, `ollama/llama`, `gpt-4o-mini`). Assert zero matches outside of `config.py` (where defaults are defined). **Expected: FAIL** (DocumentSummary.llm_model has hardcoded `"ollama/llama3.2"`).

- [ ] T002 [P] [US3] Write `test_model_config_propagation` in `tests/ai/test_config.py` — Verify that `LiteLLMClient.complete()` uses `AiConfig().llm_model` when no explicit model is passed. Verify `DocumentSummary` default matches `AiConfig().llm_model`. **Expected: FAIL** (DocumentSummary has hardcoded default).

### US2 Tests (Auto-Build)

- [ ] T003 [P] [US2] Write `test_workspace_auto_build_flag` in `tests/ai/test_workspace.py` — Create workspace with `auto_build=True`. Verify the flag persists in storage. Retrieve workspace and assert `auto_build` is `True`. **Expected: FAIL** (field doesn't exist).

- [ ] T004 [P] [US2] Write `test_workspace_auto_build_default_off` in `tests/ai/test_workspace.py` — Create workspace without auto_build. Verify default is `False`. **Expected: FAIL** (field doesn't exist).

- [ ] T005 [P] [US2] Write `test_workspace_create_cli_auto_build` in `tests/ai/test_cli_ai.py` — CLI integration test: invoke `ai workspace create --auto-build test-ws` via Typer `CliRunner`. Verify output includes auto-build status and JSON output includes `"auto_build": true`. **Expected: FAIL** (flag doesn't exist).

### US4 Tests (CLI Redesign)

- [ ] T006 [P] [US4] Write `test_summarize_command_exists` in `tests/ai/test_cli_ai.py` — Invoke `ai summarize TDOC-ID --words 200 --format markdown`. Verify output contains summary, keywords, metadata. Word count within ±20%. **Expected: FAIL** (command doesn't exist).

- [ ] T007 [P] [US4] Write `test_summarize_fetches_remote` in `tests/ai/test_cli_ai.py` — Invoke `ai summarize` on TDoc not checked out locally. Verify system fetches from WhatTheSpec/Portal and produces summary. **Expected: FAIL** (command doesn't exist).

- [ ] T008 [P] [US4] Write `test_summarize_output_formats` in `tests/ai/test_cli_ai.py` — Test all three formats (markdown, json, yaml). Verify JSON/YAML include structured `summary`, `keywords`, `metadata` fields. **Expected: FAIL** (command doesn't exist).

- [ ] T009 [P] [US4] Write `test_convert_command_exists` in `tests/ai/test_cli_ai.py` — Invoke `ai convert TDOC-ID --output file.md`. Verify markdown file created. **Expected: FAIL** (command doesn't exist).

- [ ] T010 [P] [US4] Write `test_query_workspace_required` in `tests/ai/test_cli_ai.py` — Invoke `ai query "test"` without `--workspace`. Verify error message requires workspace. **Expected: FAIL** (query still allows single-TDoc mode).

- [ ] T011 [P] [US4] Write `test_query_merged_rag_graphrag` in `tests/ai/test_cli_ai.py` — Invoke `ai query` on workspace. Verify results include both embedding-based matches and graph relationships (merged, not separate). **Expected: FAIL** (GraphRAG not integrated).

- [ ] T012 [P] [US4] Write `test_removed_commands_unavailable` in `tests/ai/test_cli_ai.py` — Invoke `ai process`, `ai status`, `ai graph`. Verify commands don't exist (Typer raises error). **Expected: FAIL** (commands still exist).

### Red Phase Verification

- [ ] T013 Verify all 12 new tests FAIL (red phase complete). Run `uv run pytest tests/ai/test_config.py tests/ai/test_workspace.py tests/ai/test_cli_ai.py -v --tb=short` and confirm failures on T001-T012 while existing tests still pass.

**Checkpoint**: All 12 new tests written, verified failing. Red phase complete.
Existing 96 tests still pass. Implementation can begin.

**Total new tests**: 12 (T001-T012). **Expected final count**: 108 tests (96 + 12).

______________________________________________________________________

## Phase 3: US3 — No Hardcoded Models (Priority: P3 → Implemented First)

**Goal**: Fix hardcoded model identifiers to use `AiConfig()` defaults.

- [ ] T014 [US3] Fix `DocumentSummary.llm_model` default in `src/tdoc_crawler/ai/models.py` line 268 — Change from `Field("ollama/llama3.2", ...)` to `Field(default_factory=lambda: AiConfig().llm_model, description="...")`. Import `AiConfig` at top of file.

- [ ] T015 [US3] Verify model propagation in `summarize.py` — Confirm `LiteLLMClient.complete()` uses `model or AiConfig().llm_model`. Should already be fixed from earlier work. Add comment documenting the behavior.

- [ ] T016 [US3] Run T001, T002 tests → verify they PASS (green). Run `uv run pytest tests/ai/test_config.py -v`. Both tests should now pass.

**Checkpoint**: US3 complete. Zero hardcoded model identifiers (outside config.py defaults).

______________________________________________________________________

## Phase 4: US2 — Auto-Build Workspace (Priority: P2)

**Goal**: Add `--auto-build` flag to workspace creation.

### Flag Storage

- [ ] T017 [US2] Add `auto_build: bool = Field(False, ...)` field to `Workspace` model in `src/tdoc_crawler/ai/models.py`. Add description: "When True, newly added workspace members are automatically processed."

- [ ] T018 [US2] Update `create_workspace()` in `src/tdoc_crawler/ai/operations/workspaces.py` — Add `auto_build: bool = False` parameter. Pass it to `Workspace(...)` constructor. Ensure the field is persisted to LanceDB storage.

- [ ] T019 [US2] Update `create_workspace` re-export in `src/tdoc_crawler/ai/__init__.py` — Ensure the new `auto_build` param is visible in the public API signature.

- [ ] T020 [US2] Add `--auto-build` flag to `workspace_create` CLI command in `src/tdoc_crawler/cli/ai.py` — Add `auto_build: bool = typer.Option(False, "--auto-build", help="Automatically process documents added to this workspace")`. Pass to `create_workspace(storage, name, auto_build=auto_build)`. Update text output to show auto-build status. Update JSON output to include `auto_build` field.

### Auto-Build Processing Trigger

- [ ] T021 [US2] Add auto-build processing trigger in `add_workspace_members()` in `src/tdoc_crawler/ai/operations/workspaces.py` — When workspace has `auto_build=True` and `is_active=True`, after adding members, call `process_tdoc()` or appropriate pipeline function for each newly added member. Use parallelism from config. Handle errors gracefully (log but continue).

- [ ] T022 [US2] Write `test_auto_build_triggers_processing` in `tests/ai/test_workspace.py` — Create auto-build workspace, add a mock TDoc member, verify processing was triggered (mock the pipeline). Assert processing status is created for the added member.

- [ ] T023 [US2] Write `test_auto_build_off_no_processing` in `tests/ai/test_workspace.py` — Create workspace with `auto_build=False`, add a member, verify NO processing was triggered.

- [ ] T024 [US2] Run T003, T004, T005, T022, T023 tests → verify they PASS (green). Run `uv run pytest tests/ai/test_workspace.py tests/ai/test_cli_ai.py -v`. All US2 tests should now pass. Run full suite: `uv run pytest tests/ai/ -v` — all 101 tests pass (96 existing + 5 US2/US3 tests).

**Checkpoint**: US2 complete. `--auto-build` flag works end-to-end AND triggers auto-processing.

______________________________________________________________________

## Phase 5: US4 — CLI Redesign (Priority: P1)

**Goal**: Restructure CLI commands to separate single-TDoc operations from workspace analysis.

### New Single-TDoc Commands

- [ ] T025 [US4] Create `src/tdoc_crawler/ai/operations/summarize.py` — Implement `summarize_tdoc(tdoc_id, words=200, format='markdown', fetch_remote=True)`:

  - Fetch TDoc if not local (via WhatTheSpec/Portal)
  - Extract content using Kreuzberg
  - Generate summary with LiteLLM using word count constraint (±20%)
  - Extract keywords (use LLM or simple NLP)
  - Return `SummarizeResult(summary, keywords, metadata, word_count)`
  - Support markdown (default), JSON, YAML output formats

- [ ] T026 [US4] Create `src/tdoc_crawler/ai/operations/convert.py` — Implement `convert_tdoc(tdoc_id, output_path=None)`:

  - Fetch TDoc if not local
  - Extract content using Kreuzberg
  - Convert to markdown format
  - Write to `output_path` or return markdown string

- [ ] T027 [US4] Export new operations in `src/tdoc_crawler/ai/__init__.py` — Add `summarize_tdoc`, `convert_tdoc`, `SummarizeResult` to public API.

- [ ] T028 [US4] Add `ai summarize` CLI command in `src/tdoc_crawler/cli/ai.py`:

  - `@ai_app.command("summarize")`
  - Parameters: `tdoc_id: str`, `words: int = 200`, `format: str = "markdown"`, `output: Path | None = None`
  - Call `summarize_tdoc(tdoc_id, words=words, format=format, fetch_remote=True)`
  - Format output based on `--format` flag
  - Write to file if `--output` specified, otherwise print to stdout

- [ ] T029 [US4] Add `ai convert` CLI command in `src/tdoc_crawler/cli/ai.py`:

  - `@ai_app.command("convert")`
  - Parameters: `tdoc_id: str`, `output: Path`
  - Call `convert_tdoc(tdoc_id, output_path=output)`
  - Print confirmation message

### Workspace Query Modifications

- [ ] T030 [US4] Modify `ai query` command in `src/tdoc_crawler/cli/ai.py`:

  - Make `--workspace` required (not optional)
  - Remove single-TDoc query mode
  - Integrate GraphRAG: call both `query_embeddings()` and `query_graph()`, merge results
  - Update output to show merged RAG+GraphRAG results

- [ ] T031 [US4] Update `query_embeddings()` in `src/tdoc_crawler/ai/operations/embeddings.py` — Remove single-TDoc query mode, workspace-only.

- [ ] T032 [US4] Update `query_graph()` in `src/tdoc_crawler/ai/operations/graph.py` — Ensure it returns results compatible with merging into embedding query results.

### Remove Deprecated Commands

- [ ] T033 [US4] Remove `ai process` command from `src/tdoc_crawler/cli/ai.py` — Delete the entire command function. Update any internal calls to use workspace workflow instead.

- [ ] T034 [US4] Remove `ai status` command from `src/tdoc_crawler/cli/ai.py` — Delete the entire command function.

- [ ] T035 [US4] Remove `ai graph` command from `src/tdoc_crawler/cli/ai.py` — Delete the entire command function. Update documentation to direct users to `ai query`.

- [ ] T036 [US4] Remove internal functions from `src/tdoc_crawler/ai/__init__.py` — Remove `process_tdoc`, `get_status` exports (keep internal if needed for workspace workflow).

### US4 Test Verification

- [ ] T037 [US4] Run T006, T007, T008, T009, T010, T011, T012 tests → verify they PASS (green). Run `uv run pytest tests/ai/test_cli_ai.py -v`. All US4 tests should now pass. Run full suite: `uv run pytest tests/ai/ -v` — all 108 tests pass (96 existing + 12 new).

**Checkpoint**: US4 complete. CLI redesigned: summarize/convert for single TDocs, query (workspace-only with RAG+GraphRAG), process/status/graph removed.

______________________________________________________________________

## Phase 6: US1 — Documentation Verification (Priority: P1)

**Goal**: Verify documentation reflects all changes.

- [ ] T038 [US1] Verify `docs/ai.md` reflects CLI redesign:

  - Remove `ai process`, `ai status`, `ai graph` from command reference
  - Add `ai summarize` with examples (--words, --format, --output)
  - Add `ai convert` with examples
  - Update `ai query` to show workspace-only usage with RAG+GraphRAG
  - Update `ai workspace create` to show `--auto-build` flag
  - Update workflow order: workspace creation → add members → query

- [ ] T039 [P] [US1] Verify `.env.example` matches code defaults — Confirm `TDC_AI_LLM_MODEL=openrouter/openrouter/free` and `TDC_AI_EMBEDDING_MODEL=ollama/embeddinggemma` match `config.py` defaults.

- [ ] T040 [P] [US1] Verify `README.md` AI feature mention is still accurate — Quick check that the AI feature bullet in README matches the current state.

- [ ] T041 [P] [US1] Verify documentation completeness — Grep `docs/ai.md` for: (a) 10+ LLM providers in provider table, (b) CLI commands in workflow order, (c) 8+ troubleshooting scenarios. Assert all present.

**Checkpoint**: US1 complete. Documentation is consistent with redesigned CLI.

______________________________________________________________________

## Phase 7: Polish

**Goal**: Final verification, linting, and merge.

- [ ] T042 Run `mise lint-fix` and fix remaining linter issues (skip PLR0915). Run `ruff check src/ tests/` and verify clean.

- [ ] T043 Run `uv run pytest tests/ai/ -v` — Full AI test suite: all 108 tests pass (96 existing + 12 new). No deleted tests.

- [ ] T044 [P] Run `uv run pytest -v` — Full project test suite passes. No regressions outside `ai/`.

- [ ] T045 Verify success criteria from spec.md:

  - SC-002: Zero hardcoded model identifiers (code search verified)
  - SC-003: 10+ LLM providers in docs (T041 verified)
  - SC-004: CLI commands in workflow order (T038 verified)
  - SC-005: 96+ tests pass (108 expected)
  - SC-006: auto-build workspace works (T022, T023 verified)
  - SC-007: Troubleshooting 8+ scenarios (T041 verified)
  - SC-009: Ruff clean
  - SC-010: No deleted tests
  - SC-011: .env.example matches docs (T039 verified)
  - SC-012: CLI command structure is intuitive (T038 verified)
  - SC-013: `ai summarize` produces all three formats (T008 verified)
  - SC-014: `ai query` uses RAG+GraphRAG (T011 verified)
  - SC-015: Deprecated commands removed (T012 verified)

______________________________________________________________________

## Task Dependencies

**Sequential Dependencies**:

- **Phase 1 (Setup)**: No dependencies — already complete
- **Phase 2 (Tests)**: No dependencies — start immediately (TDD red phase)
- **Phase 3 (US3)**: Depends on Phase 2 completion (tests must exist and fail first)
- **Phase 4 (US2)**: Depends on Phase 2 completion; T017-T020 (flag storage) must complete before T021 (auto-build trigger)
- **Phase 5 (US4)**: Depends on Phase 2 completion; T025-T027 (library operations) must complete before T028-T029 (CLI commands)
- **Phase 6 (US1)**: Depends on Phase 5 completion (need final CLI structure to document)
- **Phase 7 (Polish)**: Depends on all phases complete

**Parallel Opportunities**:

- T001, T002 (US3 tests) can run in parallel — different test functions, same file
- T003, T004, T005 (US2 tests) can run in parallel — different test functions
- T006-T012 (US4 tests) can run in parallel — different test functions
- All Phase 2 tests [P] can be written simultaneously
- T017, T018, T019 (US2 flag storage) can run in parallel — different files
- T025, T026 (US4 operations) can run in parallel — different files
- T038, T039, T040, T041 (US1 verification) can run in parallel — different files
- T042, T044 (lint + full tests) can run in parallel

## Notes

- **Breaking Change**: Removing `ai process`, `ai status`, `ai graph` commands is a breaking change. Users will need to migrate to workspace-based workflow.
- **Word Count Enforcement**: `ai summarize --words 200` uses soft target ±20% (160-240 words acceptable)
- **Remote Fetching**: `ai summarize` fetches TDocs remotely if not local (via WhatTheSpec/Portal)
- **Merged Results**: `ai query` merges RAG embeddings + GraphRAG relationships in same response
- **Output Formats**: `ai summarize` supports markdown (default), JSON, YAML
