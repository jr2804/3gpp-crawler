# Phase 0 Research: GraphRAG Workspace Scoping

## Decision 1: Keep existing AI pipeline and add workspace scoping as an additive layer

- **Decision**: Extend existing `process_tdoc` / `process_all` / `run_pipeline` with workspace context rather than introducing a parallel pipeline.
- **Rationale**: Large portions of the AI pipeline are already implemented and tested; additive changes minimize rework and regression risk.
- **Alternatives considered**:
  - Build an entirely separate GraphRAG workspace pipeline (rejected: duplicates logic and violates DRY).
  - Delay workspace support until a full GraphRAG rewrite (rejected: does not satisfy current feature requirements).

## Decision 2: Mandatory `default` workspace fallback with auto-creation

- **Decision**: Any workspace-optional operation resolves to `default`; if missing, create it on first use.
- **Rationale**: Required by spec and preserves existing behavior for callers that currently provide no workspace.
- **Alternatives considered**:
  - Require explicit workspace argument everywhere (rejected: breaks existing flow and increases friction).
  - Error when workspace is omitted (rejected: conflicts with acceptance criteria).

## Decision 3: Use generic `source item` semantics for workspace membership while preserving legacy `tdoc_id` compatibility

- **Decision**: Introduce workspace member concepts with generic file references; keep existing `tdoc_id` fields where they represent current artifact identity.
- **Rationale**: Feature includes specs and non-TDoc files; full immediate rename of existing AI schema would be high-risk.
- **Alternatives considered**:
  - Rename all existing `tdoc_id` references now (rejected: large migration blast radius across storage/tests/CLI).
  - Keep ambiguous naming only (rejected: remains confusing for multi-source workspace scope).

## Decision 4: Workspace-aware storage keys and filtering

- **Decision**: Add workspace dimension in storage operations/tables for statuses, memberships, and artifact scope.
- **Rationale**: Prevents cross-workspace contamination and satisfies workspace isolation requirements.
- **Alternatives considered**:
  - Separate physical DB per workspace (rejected: operational complexity and poor discoverability).
  - Keep global tables without scope key (rejected: cannot enforce isolation).

## Decision 5: Reuse existing CLI surface and extend with workspace commands/options

- **Decision**: Extend `tdoc-crawler ai` command family with `--workspace` and workspace management subcommands; maintain JSON mode.
- **Rationale**: Constitution requires CLI delegation and JSON support; existing command structure is already established.
- **Alternatives considered**:
  - New top-level CLI namespace for workspaces (rejected: unnecessary churn for users).
  - Library-only workspace management (rejected: violates CLI contract requirements).

## Decision 6: Network-access policy for this feature

- **Decision**: No new core-crawler HTTP source calls are introduced; AI provider calls remain via approved AI integrations and are documented as exempt.
- **Rationale**: Workspace scoping is primarily data-model, storage, and orchestration work.
- **Alternatives considered**:
  - Introduce remote workspace service now (rejected: out of scope and unnecessary complexity).

## Existing Code Reuse/Removal Matrix

- **Reuse**:
  - `src/tdoc_crawler/ai/operations/pipeline.py` stage orchestration
  - `src/tdoc_crawler/ai/storage.py` LanceDB infrastructure
  - `src/tdoc_crawler/cli/ai.py` command delegation patterns
- **Adjust**:
  - `src/tdoc_crawler/ai/__init__.py` API signatures for workspace defaulting
  - `src/tdoc_crawler/ai/models.py` naming and scope models
- **Remove/retire**:
  - Single-scope assumptions that treat `.ai/lancedb` records as globally unscoped
  - Ambiguous naming in newly introduced APIs where `tdoc` is used to mean generic source files

## Single-Scope Assumption Catalog (Phase 1 Setup)

- `src/tdoc_crawler/ai/operations/pipeline.py`
  - `process_all()` assumes folder names map directly to a global TDoc set under one checkout base.
  - `run_pipeline()` reads/writes status without workspace scope dimension.
- `src/tdoc_crawler/ai/storage.py`
  - `get_status()`, `save_status()`, and artifact persistence use `tdoc_id` as global key with no workspace partition.
- `src/tdoc_crawler/ai/__init__.py`
  - Public APIs expose process/status flows with no explicit workspace argument.
- `src/tdoc_crawler/cli/ai.py`
  - CLI `process/status/query` commands assume one global corpus and do not pass workspace context.

## Resolved Clarifications

All technical unknowns for planning are resolved. No `NEEDS CLARIFICATION` items remain.
