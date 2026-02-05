---

description: "Task list for crawl and query specs feature"
---

# Tasks: Crawl and Query Specs

**Input**: Design documents from `/specs/001-specs-crawl-query/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED by constitution (TDD gate).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create specs module layout under src/tdoc_crawler/specs/
- [ ] T002 [P] Add new spec models stub file in src/tdoc_crawler/models/specs.py
- [ ] T003 [P] Add specs database helpers stub in src/tdoc_crawler/database/connection.py
- [ ] T004 [P] Add CLI args stubs for specs commands in src/tdoc_crawler/cli/args.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement spec number normalization utilities in src/tdoc_crawler/specs/normalization.py
- [ ] T006 Implement spec Pydantic models and enums in src/tdoc_crawler/models/specs.py
- [ ] T007 Implement specs database tables and upsert/query helpers in src/tdoc_crawler/database/connection.py
- [ ] T007a Implement crawl/download outcome logging for specs in src/tdoc_crawler/database/connection.py
- [ ] T008 Implement spec source fetchers (3GPP + whatthespec) in src/tdoc_crawler/specs/sources/
- [ ] T009 Implement SpecCatalog facade in src/tdoc_crawler/specs/catalog.py
- [ ] T010 Implement specs query filters and result shaping in src/tdoc_crawler/specs/query.py
- [ ] T011 Implement specs download helpers (doc-only, fallback) in src/tdoc_crawler/specs/downloads.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Crawl spec metadata from both sources (Priority: P1)

**Goal**: Crawl and store normalized spec metadata from 3GPP.org and whatthespec.net.

**Independent Test**: Run crawl-specs for a known spec and verify stored metadata and source attribution.

### Tests for User Story 1 (REQUIRED) ⚠️

- [ ] T012 [P] [US1] Add normalization tests in tests/test_specs_normalization.py
- [ ] T013 [P] [US1] Add source parsing tests in tests/test_specs_sources.py
- [ ] T014 [P] [US1] Add database upsert/query tests in tests/test_specs_database.py

### Implementation for User Story 1

- [ ] T015 [US1] Implement SpecCatalog crawl flow in src/tdoc_crawler/specs/catalog.py
- [ ] T016 [US1] Wire crawl-specs CLI in src/tdoc_crawler/cli/app.py
- [ ] T017 [US1] Add crawl-specs output formatting in src/tdoc_crawler/cli/printing.py

**Checkpoint**: User Story 1 should be fully functional and independently testable

---

## Phase 4: User Story 2 - Checkout or open spec documents (Priority: P2)

**Goal**: Download, extract, and open spec documents with doc-only support.

**Independent Test**: Checkout a known spec revision in doc-only mode and confirm document path.

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T018 [P] [US2] Add doc-only selection tests in tests/test_specs_downloads.py
- [ ] T019 [P] [US2] Add checkout/open CLI tests in tests/test_specs_cli.py

### Implementation for User Story 2

- [ ] T020 [US2] Implement checkout-spec command in src/tdoc_crawler/cli/app.py
- [ ] T021 [US2] Implement open-spec command in src/tdoc_crawler/cli/app.py
- [ ] T022 [US2] Add checkout/open result formatting in src/tdoc_crawler/cli/printing.py
- [ ] T023 [US2] Wire doc-only and release handling in src/tdoc_crawler/specs/downloads.py

**Checkpoint**: User Story 2 should be fully functional and independently testable

---

## Phase 5: User Story 3 - Query spec catalog by key attributes (Priority: P3)

**Goal**: Query specs by number, title, working group, and status.

**Independent Test**: Query by spec number and verify record contents and sources.

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T024 [P] [US3] Add query filter tests in tests/test_specs_database.py
- [ ] T025 [P] [US3] Add query CLI output tests in tests/test_specs_cli.py

### Implementation for User Story 3

- [ ] T026 [US3] Implement query-specs logic in src/tdoc_crawler/specs/query.py
- [ ] T027 [US3] Wire query-specs CLI in src/tdoc_crawler/cli/app.py
- [ ] T028 [US3] Add query-specs output formatting in src/tdoc_crawler/cli/printing.py

**Checkpoint**: User Story 3 should be fully functional and independently testable

---

## Phase 6: User Story 4 - Inspect source discrepancies (Priority: P4)

**Goal**: Expose per-source differences for specs with multiple source records.

**Independent Test**: Query a spec that exists in both sources and verify differences are visible.

### Tests for User Story 4 (REQUIRED) ⚠️

- [ ] T029 [P] [US4] Add discrepancy view tests in tests/test_specs_database.py

### Implementation for User Story 4

- [ ] T030 [US4] Extend query results to expose per-source differences in src/tdoc_crawler/specs/query.py
- [ ] T031 [US4] Add discrepancy rendering in src/tdoc_crawler/cli/printing.py

**Checkpoint**: User Story 4 should be fully functional and independently testable

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T032 [P] Update docs/QUICK_REFERENCE.md for new specs commands
- [ ] T033 [P] Update README.md with specs commands usage
- [ ] T034 [P] Run Ruff and Ty, fix lint/type errors
- [ ] T035 Run quickstart.md validation in specs/001-specs-crawl-query/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P2)**: Can start after Foundational (Phase 2)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2)
- **User Story 4 (P4)**: Can start after Foundational (Phase 2)

### Within Each User Story

- Tests MUST be written, user-approved, and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- Foundational tasks can run in parallel where files do not conflict
- Tests within each story can be parallelized

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Add normalization tests in tests/test_specs_normalization.py"
Task: "Add source parsing tests in tests/test_specs_sources.py"
Task: "Add database upsert/query tests in tests/test_specs_database.py"

# Launch implementation for User Story 1 after tests are green:
Task: "Implement SpecCatalog crawl flow in src/tdoc_crawler/specs/catalog.py"
Task: "Wire crawl-specs CLI in src/tdoc_crawler/cli/app.py"
Task: "Add crawl-specs output formatting in src/tdoc_crawler/cli/printing.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
   - Developer D: User Story 4
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
