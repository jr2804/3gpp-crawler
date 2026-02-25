# Data Model: GraphRAG Workspace Scoping

## Terminology

- Canonical term: `WorkspaceMember`
- Narrative alias: `corpus entry`

## Entity: Workspace

- **Description**: Logical project/workspace boundary for GraphRAG processing.
- **Fields**:
  - `workspace_name` (string, required, normalized)
  - `created_at` (datetime, required)
  - `updated_at` (datetime, required)
  - `is_default` (bool, required)
  - `status` (enum: `active`, `archived`)
- **Validation rules**:
  - Empty/whitespace workspace names resolve to `default`.
  - Name normalization is case-insensitive (`Default` and `default` map to same identity).
  - `default` is reserved and cannot be deleted while fallback behavior is enabled.

## Entity: WorkspaceMember

- **Description**: One selected source item assigned to one workspace corpus.
- **Fields**:
  - `workspace_name` (string, required)
  - `source_item_id` (string, required, stable identifier)
  - `source_path` (string/path, required)
  - `source_kind` (enum: `tdoc`, `spec`, `other`)
  - `added_at` (datetime, required)
  - `added_by` (string, optional)
  - `is_active` (bool, required)
- **Validation rules**:
  - `source_path` must exist/readable at registration time or be marked invalid explicitly.
  - Duplicate active membership (`workspace_name`, `source_item_id`) is disallowed.
  - Same `source_item_id` may exist in multiple workspaces.

## Entity: ArtifactScope

- **Description**: Links generated pipeline artifacts to one workspace.
- **Fields**:
  - `workspace_name` (string, required)
  - `artifact_type` (enum: `status`, `classification`, `chunk`, `summary`, `graph_node`, `graph_edge`)
  - `artifact_id` (string, required)
  - `source_item_id` (string, optional)
  - `created_at` (datetime, required)
- **Validation rules**:
  - Every generated artifact must map to exactly one workspace.
  - Cross-workspace artifact references are invalid.

## Backward-Compatible Existing Entities (extended)

### ProcessingStatus (existing)

- **Current key**: `tdoc_id`
- **Planned extension**: add `workspace_name` dimension for scoped reads/writes.
- **Compatibility**: operations with omitted workspace map to `workspace_name='default'`.

### DocumentClassification / DocumentChunk / DocumentSummary (existing)

- **Current key context**: primarily `tdoc_id`
- **Planned extension**: add workspace association for filtering and artifact isolation.
- **Compatibility**: keep current `tdoc_id` field semantics for existing pipeline identity.

## Relationships

- Workspace `1 -> N` WorkspaceMember
- Workspace `1 -> N` ArtifactScope
- WorkspaceMember `1 -> N` ArtifactScope (optional linkage by source item)

## State Transitions

- Workspace: `active -> archived`
- WorkspaceMember: `is_active=true -> is_active=false` (soft removal)
- ArtifactScope: immutable after creation; superseded by newer artifacts if reprocessed.
