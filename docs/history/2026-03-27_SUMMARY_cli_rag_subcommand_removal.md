# CLI: Remove rag subcommand and consolidate under workspace

**Date:** 2026-03-27

**Goal:** Simplify CLI by removing redundant `rag` subcommand and consolidating RAG functionality under `workspace`.

## Changes

### Removed Commands

- `3gpp-ai rag migrate` - Removed migration functionality entirely
- `3gpp-ai rag query` - Moved to `workspace query`
- `3gpp-ai rag status` - Moved to `workspace status`

### New Commands (under workspace)

- `3gpp-ai workspace query` - Query the LightRAG knowledge graph
- `3gpp-ai workspace status` - Show LightRAG configuration and status

### Files Modified

- `packages/3gpp-ai/threegpp_ai/cli.py`

  - Removed `rag_app` import and `app.add_typer(rag_app, name="rag")`
  - Added `workspace query` command
  - Added `workspace status` command
  - Added help strings to all workspace commands
  - Added imports: `Annotated`, `QueryMode`, `StorageBackend`, `TDocRAG`

- `packages/3gpp-ai/threegpp_ai/lightrag/cli.py`

  - Removed migrate command
  - Removed migration imports
  - Marked module as deprecated

- `packages/3gpp-ai/threegpp_ai/lightrag/migration.py` - Deleted

### New CLI Structure

```
3gpp-ai --help
├── summarize   (existing)
├── convert     (existing)
├── workspace   (enhanced)
│   ├── create
│   ├── list
│   ├── query   (NEW - was rag query)
│   ├── status  (NEW - was rag status)
│   ├── info
│   ├── activate
│   ├── deactivate
│   ├── clear-invalid
│   ├── clear
│   ├── add-members
│   ├── list-members
│   ├── process
│   └── delete
└── providers   (existing)
```

## Rationale

The `rag` subcommand was redundant since RAG functionality is workspace-centric. Moving `query` and `status` under `workspace` provides a cleaner command hierarchy and aligns with the workspace-based architecture.

The migration functionality was removed as it was deemed unnecessary for the current workflow - shared storage is the default behavior for new workspaces.
