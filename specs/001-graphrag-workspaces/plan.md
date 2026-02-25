# Implementation Plan: GraphRAG Workspace Scoping

**Branch**: `001-graphrag-workspaces` | **Date**: 2026-02-25 | **Spec**: `specs/001-graphrag-workspaces/spec.md`
**Input**: Feature specification from `specs/001-graphrag-workspaces/spec.md`

## Summary

Add workspace/project scoping to AI/GraphRAG processing with mandatory `default` fallback.
The implementation extends existing AI pipeline/storage/CLI code to support isolated
workspace corpora and workspace-scoped artifact generation, while reusing current
pipeline stages and removing/adjusting single-workspace assumptions already present in
`src/tdoc_crawler/ai` and `src/tdoc_crawler/cli/ai.py`.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: typer, rich, pydantic, lancedb, pyarrow, sentence-transformers
**Storage**: LanceDB tables under `.ai/lancedb` + workspace file references
**Testing**: pytest (`uv run pytest`), focused AI tests under `tests/ai/`
**Target Platform**: Cross-platform CLI (Windows/Linux/macOS)
**Project Type**: Single Python repository (library + CLI)
**Performance Goals**: Workspace resolution and membership filtering add negligible overhead (target \<10% vs current single-scope flow)
**Constraints**: Maintain backward-compatible default behavior via `default` workspace; avoid breaking completed AI pipeline stages
**Scale/Scope**: Multiple workspaces per repository, each with selected subsets of TDocs/specs/other files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Library-first boundary documented (standalone library + integration points).
- [x] CLI contract defined (text input/output + JSON mode).
- [x] TDD evidence planned (tests written/approved + red phase before implementation).
- [x] Python standards planned (type hints, logging, uv/pyproject, Ruff, Ty, pathlib,
  dataclasses where appropriate, Typer CLI).
- [x] Domain placement confirmed (correct domain package; no logic in cli/ or utils/;
  no legacy crawlers/ reference).
- [x] DRY validation done (existing code searched; no duplicated logic introduced).
- [x] Network access plan documented (core crawler source traffic via
  create_cached_session(); any AI model-provider traffic explicitly documented as
  exempt with approved provider/client integration).

## Library Boundary & CLI Contract

**Library boundary (new/extended in `src/tdoc_crawler/ai/`)**

- Extend AI domain APIs to include explicit `workspace` context with default fallback.
- Reuse existing orchestration (`process_tdoc`, `process_all`, `run_pipeline`) and
  extend signatures to accept workspace/project scoping.
- Add workspace management library operations (create/list/get/add-members/remove-members)
  in AI domain package.
- Keep domain logic in `src/tdoc_crawler/ai/`; CLI remains delegation-only.

**CLI contract (`src/tdoc_crawler/cli/ai.py`)**

- Workspace-aware options on relevant commands: `--workspace` (optional, default resolves to `default`).
- Add workspace management command group (text output via rich; JSON via `--json`).
- Preserve existing text output for human use and JSON mode for automation.
- The OpenAPI document in `contracts/` is a logical payload contract for CLI JSON
  request/response semantics in this feature; it does NOT require implementing an
  HTTP server in this increment.

**Existing-code consideration/removal scope**

- Keep existing single-scope flows functionally equivalent by mapping them to `default`.
- Remove implicit assumptions that a global `.ai/lancedb` is unscoped by introducing
  workspace-aware filtering/keys.
- Rename newly introduced generic interfaces to `source_item`/`workspace member` where
  semantics include non-TDoc files; keep legacy `tdoc_id` fields only where tied to existing
  pipeline identity and backward compatibility.

## TDD Evidence

For each user story, tests are written and approved first, then run red before code changes:

- **US1 (workspace isolation)**: tests for workspace creation, membership registration,
  and isolation across two workspaces.
- **US2 (`default` fallback)**: tests for omitted workspace argument resolving to
  auto-created `default` in library + CLI paths.
- **US3 (workspace-scoped KB build)**: tests that process/build operations only use
  selected members from target workspace and never cross-contaminate artifacts.

Red evidence is captured by running focused tests (e.g., `tests/ai/test_ai_workspaces*.py`,
updated `tests/ai/test_ai_cli.py`, `tests/ai/test_ai_pipeline.py`) before implementation,
then green after implementation.

## Project Structure

### Documentation (this feature)

```text
specs/001-graphrag-workspaces/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── tdoc_crawler/
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── storage.py
│   │   └── operations/
│   │       ├── pipeline.py
│   │       ├── extract.py
│   │       └── ...
│   └── cli/
│       ├── ai.py
│       └── app.py

tests/
└── ai/
    ├── test_ai_cli.py
    ├── test_ai_pipeline.py
    ├── test_ai_storage.py
    └── (new) test_ai_workspaces.py
```

**Structure Decision**: Extend existing AI domain and AI CLI modules in-place; add
workspace-specific models/operations without creating parallel subsystems.

## Complexity Tracking

No constitution violations identified.

## Post-Design Constitution Re-Check

- [x] Library-first boundary remains intact after design artifacts.
- [x] CLI text/JSON contract is preserved in contract and quickstart artifacts.
- [x] TDD-first flow remains mandatory in quickstart/test plan.
- [x] Python standards/tooling expectations remain unchanged.
- [x] Domain placement keeps logic in AI domain and CLI delegation-only.
- [x] DRY strategy is explicit (reuse existing pipeline/storage/CLI; avoid parallel systems).
- [x] Network policy remains compliant (no new core-crawler HTTP sources introduced).
