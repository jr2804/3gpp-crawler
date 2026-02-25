# Feature Specification: GraphRAG Workspace Scoping

**Feature Branch**: `001-graphrag-workspaces`
**Created**: 2026-02-25
**Status**: Draft
**Input**: User description: "Regarding the later construction of GraphRAG knowledge bases, it should be possible to define separate projects or workspaces for different topics/aspects/work items/etc. and which contain selected tdocs/specifications/other files. if no project/workspace is provided, always use one named default"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Create Isolated Workspaces (Priority: P1)

As a user building GraphRAG knowledge bases, I want to create named workspaces that contain only selected source files, so each topic or work item has an isolated, relevant corpus.

**Why this priority**: Workspace isolation is foundational; without it, all later retrieval and graph building mixes unrelated documents.

**Independent Test**: Can be fully tested by creating two workspaces with different selected files and verifying each workspace only exposes its own files.

**Acceptance Scenarios**:

1. **Given** a repository containing multiple TDocs/specs/files, **When** a workspace is created with a selected subset, **Then** only that subset is registered in the workspace corpus.
1. **Given** two workspaces with different file selections, **When** each workspace is queried for its corpus members, **Then** no file appears in a workspace unless it was selected for that workspace.

### User Story 1.1 - Workspace Name Normalization (Priority: P1)

As a user, I want workspace names to be normalized consistently regardless of casing, so I can reliably reference workspaces without worrying about exact capitalization.

**Normalization Rule**: All workspace names MUST be converted to lowercase before storage and comparison. For example, "MyProject", "myproject", and "MYPROJECT" all refer to the same workspace.

**Independent Test**: Can be tested by creating workspaces with different casing variants and verifying they resolve to the same lowercase identifier.

**Acceptance Scenarios**:

1. **Given** a workspace name with mixed-case characters (e.g., "MyWorkspace"), **When** the workspace is created, **Then** it is stored as "myworkspace".
1. **Given** a request for workspace "MyWorkspace", **When** querying for workspace "myworkspace", **Then** both resolve to the same normalized identifier.

______________________________________________________________________

### User Story 2 - Use Default Workspace Automatically (Priority: P2)

As a user running GraphRAG commands without specifying a workspace, I want the system to automatically use a workspace named `default`, so basic workflows work without extra setup.

**Why this priority**: This is the required fallback behavior and prevents friction for existing and quick-start usage.

**Independent Test**: Can be tested independently by invoking workspace-aware operations without a workspace argument and verifying they resolve to `default`.

**Acceptance Scenarios**:

1. **Given** no workspace name is provided, **When** a workspace-scoped command is executed, **Then** the command targets `default`.
1. **Given** `default` does not yet exist, **When** the first workspace-scoped command runs without a workspace name, **Then** `default` is created and used.

______________________________________________________________________

### User Story 3 - Build Workspace-Specific Knowledge Bases (Priority: P3)

As a user, I want knowledge-base construction to run within a chosen workspace scope, so embeddings/graph artifacts are aligned to the selected files for that workspace.

**Why this priority**: This ensures downstream GraphRAG quality and avoids cross-topic contamination.

**Independent Test**: Can be tested independently by running knowledge-base construction for one workspace and verifying outputs are linked only to that workspace.

**Acceptance Scenarios**:

1. **Given** a workspace with selected files, **When** knowledge-base construction runs for that workspace, **Then** produced artifacts are associated with that workspace identifier.
1. **Given** another workspace exists, **When** construction runs for the first workspace, **Then** files from the other workspace are excluded.

______________________________________________________________________

### Edge Cases

- Workspace name is empty or whitespace and must resolve to `default` rather than creating invalid identifiers.
- Workspace name conflicts in casing (for example `Default` vs `default`) and must resolve consistently.
- Selected file list includes missing, unreadable, or duplicate entries.
- A file is intentionally included in multiple workspaces and must remain independently tracked per workspace.
- Deleting or resetting one workspace must not remove artifacts belonging to other workspaces.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support creation and management of named GraphRAG workspaces/projects.
- **FR-002**: Each workspace MUST maintain a selected-file corpus containing TDocs, specifications, and other supported files.
- **FR-003**: Any workspace-scoped operation executed without an explicit workspace name MUST use `default`.
- **FR-004**: If `default` does not exist when needed, the system MUST create and use it automatically.
- **FR-005**: Knowledge-base construction MUST be scoped to a single workspace at a time and MUST only process that workspace’s selected files.
- **FR-006**: Workspace identity MUST be attached to produced knowledge artifacts so retrieval and graph operations can enforce scope boundaries.
- **FR-007**: The system MUST provide a way to list and inspect workspace definitions and selected-file membership.
- **FR-008**: Every feature MUST begin as a standalone library with a defined public
  interface before application integration.
- **FR-009**: Every library MUST expose a CLI that accepts text input and emits text
  output, and MUST provide a JSON output mode for structured data.
- **FR-010**: Unit tests MUST be written, user-approved, and verified failing before
  implementation begins.
- **FR-011**: Python implementations MUST use `pyproject.toml` with `uv`, include type
  hints and Google-style docstrings for public code, use `logging` instead of `print`,
  rely on `pathlib` for file paths, and keep Ruff and Ty checks clean without
  suppressions unless explicitly approved.
- **FR-012**: All new code MUST be placed in the correct domain package (`tdocs/`,
  `meetings/`, `specs/`, or `ai/`); domain logic MUST NOT appear in `cli/`,
  `parsers/`, or `utils/`; the legacy `crawlers/` package MUST NOT be referenced.
- **FR-013**: Before implementing any new functionality, existing code MUST be searched
  for equivalent implementations; CLI code MUST only delegate to core library functions
  and MUST NOT duplicate domain logic.
- **FR-014**: For core crawler source traffic (3GPP/WhatTheSpec/portal), all HTTP
  requests MUST use `create_cached_session()` from `tdoc_crawler.http_client`; direct
  HTTP calls to those sources are prohibited. AI model-provider traffic MAY be exempt,
  but the feature MUST explicitly document the exemption and approved client path.

### Key Entities *(include if feature involves data)*

- **Workspace**: Named scope for GraphRAG processing, including workspace name, creation/update timestamps, and lifecycle state.
- **WorkspaceMember**: Mapping between one workspace and one selected source item, including inclusion status and provenance.
- **KnowledgeArtifactScope**: Association record linking generated embeddings/graph/index artifacts to exactly one workspace.

### Assumptions

- Workspace and project are treated as the same concept in this feature.
- `WorkspaceMember` is the canonical membership term; `corpus entry` is only a narrative alias.
- `default` is a reserved workspace name for implicit fallback usage.
- Existing single-workspace behavior is represented by the new `default` workspace.
- Standard test dataset profile for SC-003:
  - at least 30 total source items across at least 3 workspaces,
  - each workspace contains at least 8 source items,
  - file mix includes at least `docx`, `pdf`, and `md`/`txt`,
  - includes at least 1 missing or unreadable path case for validation behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of workspace-scoped operations without an explicit workspace name resolve to `default`.
- **SC-002**: At least 95% of workspace-isolation validation runs show zero cross-workspace file contamination.
- **SC-003**: Users can create a workspace and register a selected-file corpus in under 2 minutes for a standard test dataset.
- **SC-004**: Workspace listing and membership inspection return complete results for 100% of created workspaces in acceptance tests.
