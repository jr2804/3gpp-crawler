# Tasks: GraphRAG Workspace Scoping

**Input**: Design documents from `/specs/001-graphrag-workspaces/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/workspace-api.openapi.yaml`, `quickstart.md`

**Tests**: Tests are REQUIRED by spec/constitution and must be written/approved and verified failing before implementation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare workspace feature scaffolding and test harness updates.

- [x] T001 Review and catalog single-scope assumptions in `src/tdoc_crawler/ai/__init__.py`, `src/tdoc_crawler/ai/storage.py`, `src/tdoc_crawler/ai/operations/pipeline.py`, and `src/tdoc_crawler/cli/ai.py`
- [x] T002 Create workspace operation module scaffold in `src/tdoc_crawler/ai/operations/workspaces.py`
- [x] T003 [P] Add workspace test scaffolding in `tests/ai/test_ai_workspaces.py`

______________________________________________________________________

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Introduce shared workspace data contracts and persistence primitives required by all user stories.

**⚠️ CRITICAL**: No user story implementation starts until this phase is complete.

- [x] T004 [P] Add workspace domain models and normalization helpers in `src/tdoc_crawler/ai/models.py`
- [x] T005 Add workspace tables/schemas and core CRUD APIs in `src/tdoc_crawler/ai/storage.py`
- [x] T006 [P] Implement default workspace resolver/auto-create primitives in `src/tdoc_crawler/ai/operations/workspaces.py`
- [x] T007 Wire workspace APIs into public AI package exports in `src/tdoc_crawler/ai/__init__.py`
- [x] T008 Remove newly introduced ambiguous naming by using generic `source_item` terminology in `src/tdoc_crawler/ai/operations/workspaces.py` and `src/tdoc_crawler/cli/ai.py`
- [x] T009 Implement backward-compatible fallback mapping to `default` for existing unscoped storage reads/writes in `src/tdoc_crawler/ai/storage.py`
- [x] T010 Verify no new core-crawler HTTP source calls are introduced and document AI model-provider exemption path in `specs/001-graphrag-workspaces/research.md`
- [x] T011 Freeze and align workspace logical JSON contract (non-HTTP implementation for this feature) in `specs/001-graphrag-workspaces/contracts/workspace-api.openapi.yaml`

**Checkpoint**: Foundation complete; user stories can now proceed.

______________________________________________________________________

## Phase 3: User Story 1 - Create Isolated Workspaces (Priority: P1) 🎯 MVP

**Goal**: Users can create named workspaces with isolated selected-file corpora.

**Independent Test**: Create two workspaces with different file selections and verify corpus isolation.

### Tests for User Story 1 (REQUIRED) ⚠️

- [x] T012 [P] [US1] Add red tests for workspace create/list/get behavior in `tests/ai/test_ai_workspaces.py`
- [x] T013 [P] [US1] Add red tests for workspace membership isolation in `tests/ai/test_ai_storage.py`
- [x] T014 [P] [US1] Add red CLI tests for workspace management commands in `tests/ai/test_ai_cli.py`
- [ ] T015 [US1] Obtain user approval for failing red-test evidence before starting implementation in `tests/ai/test_ai_workspaces.py`, `tests/ai/test_ai_storage.py`, and `tests/ai/test_ai_cli.py`
- [ ] T016 [US1] Re-run existing-implementation search and record reuse/refactor decisions in `specs/001-graphrag-workspaces/research.md` for `src/tdoc_crawler/ai/storage.py`, `src/tdoc_crawler/ai/operations/pipeline.py`, and `src/tdoc_crawler/cli/ai.py`

### Implementation for User Story 1

- [ ] T017 [US1] Implement create/list/get workspace operations in `src/tdoc_crawler/ai/operations/workspaces.py`
- [ ] T018 [US1] Implement add/remove/list workspace members in `src/tdoc_crawler/ai/operations/workspaces.py`
- [ ] T019 [US1] Persist and query workspace/member data in `src/tdoc_crawler/ai/storage.py`
- [ ] T020 [US1] Add `ai workspace` command group and member management delegation in `src/tdoc_crawler/cli/ai.py`, including `--json` output mode per FR-009
- [ ] T021 [US1] Export workspace management API in `src/tdoc_crawler/ai/__init__.py`
- [ ] T021a [US1] Implement workspace deletion with artifact preservation (deleting workspace X must not remove artifacts from workspace Y) in `src/tdoc_crawler/ai/operations/workspaces.py` and `src/tdoc_crawler/ai/storage.py`

**Checkpoint**: User Story 1 is independently functional and testable.

______________________________________________________________________

## Phase 4: User Story 2 - Use Default Workspace Automatically (Priority: P2)

**Goal**: Omitted workspace always resolves to `default` and auto-creates if missing.

**Independent Test**: Invoke workspace-aware operations without `--workspace` and verify they use/create `default`.

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T022 [P] [US2] Add red library tests for omitted/blank workspace fallback in `tests/ai/test_ai_workspaces.py`
- [ ] T023 [P] [US2] Add red CLI tests for implicit `default` resolution in `tests/ai/test_ai_cli.py`
- [ ] T024 [US2] Obtain user approval for failing red-test evidence before starting implementation in `tests/ai/test_ai_workspaces.py` and `tests/ai/test_ai_cli.py`
- [ ] T025 [US2] Re-run existing-implementation search and record reuse/refactor decisions in `specs/001-graphrag-workspaces/research.md` for `src/tdoc_crawler/ai/__init__.py`, `src/tdoc_crawler/ai/storage.py`, and `src/tdoc_crawler/cli/ai.py`

### Implementation for User Story 2

- [ ] T026 [US2] Implement `default` auto-create and normalization logic in `src/tdoc_crawler/ai/operations/workspaces.py`
- [ ] T027 [US2] Apply fallback behavior in public AI APIs (`process_tdoc`, `process_all`, `get_status`) in `src/tdoc_crawler/ai/__init__.py`
- [ ] T028 [US2] Apply fallback behavior in CLI entrypoints (`process`, `status`, `workspace` commands) in `src/tdoc_crawler/cli/ai.py`
- [ ] T029 [US2] Enforce default fallback for blank/unset workspace values in `src/tdoc_crawler/ai/storage.py`

**Checkpoint**: User Stories 1 and 2 both work independently.

______________________________________________________________________

## Phase 5: User Story 3 - Build Workspace-Specific Knowledge Bases (Priority: P3)

**Goal**: Knowledge-base processing and artifacts are strictly scoped to selected files in the target workspace.

**Independent Test**: Run pipeline for one workspace and confirm outputs exclude other workspace files.

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T030 [P] [US3] Add red pipeline isolation tests for workspace-scoped processing in `tests/ai/test_ai_pipeline.py`
- [ ] T031 [P] [US3] Add red contract tests for workspace-scoped process/status behaviors in `tests/ai/test_ai_workspace_contract.py`
- [ ] T032 [P] [US3] Add red storage scope tests for status/chunk/summary retrieval in `tests/ai/test_ai_storage.py`
- [ ] T033 [US3] Obtain user approval for failing red-test evidence before starting implementation in `tests/ai/test_ai_pipeline.py`, `tests/ai/test_ai_workspace_contract.py`, and `tests/ai/test_ai_storage.py`
- [ ] T034 [US3] Re-run existing-implementation search and record reuse/refactor decisions in `specs/001-graphrag-workspaces/research.md` for `src/tdoc_crawler/ai/operations/pipeline.py`, `src/tdoc_crawler/ai/storage.py`, and `src/tdoc_crawler/cli/ai.py`

### Implementation for User Story 3

- [ ] T035 [US3] Add workspace parameter support to orchestration APIs in `src/tdoc_crawler/ai/operations/pipeline.py`
- [ ] T036 [US3] Scope process-all input resolution to workspace member corpus in `src/tdoc_crawler/ai/operations/pipeline.py` and `src/tdoc_crawler/ai/operations/workspaces.py`
- [ ] T037 [US3] Add workspace association fields/validation to artifact models in `src/tdoc_crawler/ai/models.py`
- [ ] T038 [US3] Persist and filter artifact tables by workspace in `src/tdoc_crawler/ai/storage.py`
- [ ] T039 [US3] Pass workspace scope from CLI process/status/query commands to library in `src/tdoc_crawler/cli/ai.py`
- [ ] T040 [US3] Remove or retire legacy unscoped artifact access paths in `src/tdoc_crawler/ai/storage.py` and `src/tdoc_crawler/ai/operations/pipeline.py`

**Checkpoint**: All user stories are independently functional.

______________________________________________________________________

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency checks, documentation sync, and quality gates.

- [ ] T041 [P] Update workspace quickstart and command examples in `specs/001-graphrag-workspaces/quickstart.md`
- [ ] T042 [P] Update design notes for final naming and compatibility decisions in `specs/001-graphrag-workspaces/research.md`
- [ ] T043 [P] Sync finalized contract examples and non-functional descriptions in `specs/001-graphrag-workspaces/contracts/workspace-api.openapi.yaml`
- [ ] T044 Run Ruff/Ty fixes for touched modules in `src/tdoc_crawler/ai/models.py`, `src/tdoc_crawler/ai/storage.py`, `src/tdoc_crawler/ai/operations/pipeline.py`, `src/tdoc_crawler/ai/operations/workspaces.py`, and `src/tdoc_crawler/cli/ai.py`
- [ ] T045 [P] Execute and stabilize focused AI tests in `tests/ai/test_ai_workspaces.py`, `tests/ai/test_ai_workspace_contract.py`, `tests/ai/test_ai_pipeline.py`, `tests/ai/test_ai_storage.py`, and `tests/ai/test_ai_cli.py`
- [ ] T046 [P] Validate SC-003 performance and scale: generate test dataset (30+ source items across 3+ workspaces, 8+ items per workspace, mixed docx/pdf/md/txt), measure workspace creation + corpus registration time, verify completion under 2 minutes per SC-003

______________________________________________________________________

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2; can run after or alongside late US1 work if no file conflicts.
- **Phase 5 (US3)**: Depends on Phase 2 and requires US1 workspace primitives.
- **Phase 6 (Polish)**: Depends on all selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories (MVP).
- **US2 (P2)**: Depends on foundational workspace primitives from Phase 2; validates default fallback.
- **US3 (P3)**: Depends on US1 workspace membership operations for corpus scoping.

### Within Each User Story

- Test tasks must be created/approved and fail first.
- Library/domain implementation precedes CLI wiring.
- Storage/model changes precede pipeline integration.
- Retire conflicting legacy code paths before story completion.

______________________________________________________________________

## Parallel Execution Examples

### User Story 1

```text
T012 + T013 + T014 can run in parallel (different test files).
T017 and T019 can run in parallel after T015 and T016 are complete.
```

### User Story 2

```text
T022 + T023 can run in parallel.
T027 and T029 can run in parallel after T024 and T025 and T026 are complete.
```

### User Story 3

```text
T030 + T031 + T032 can run in parallel.
T037 and T039 can run in parallel after T033 and T034 and T035 are complete.
```

______________________________________________________________________

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 and Phase 2.
1. Deliver Phase 3 (US1) end-to-end.
1. Validate workspace isolation independently before moving on.

### Incremental Delivery

1. Add US1 (workspace isolation).
1. Add US2 (`default` fallback).
1. Add US3 (workspace-scoped knowledge-base construction).
1. Finish with Phase 6 polish and quality gates.

### Existing Code Consideration

- Reuse existing AI pipeline/storage/CLI modules where possible.
- Remove/retire only conflicting single-scope assumptions.
- Avoid introducing duplicate parallel implementations for workspace behavior.
