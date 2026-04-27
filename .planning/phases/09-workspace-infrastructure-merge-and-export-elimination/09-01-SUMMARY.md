# 09-01 Summary: Merge Workspace Infrastructure into Main App

## What Was Done

Moved workspace management infrastructure from `packages/3gpp-ai` into `src/tdoc_crawler/` as a core concern of the main application.

## Changes

### Files Created

- `src/tdoc_crawler/models/workspaces.py` — Workspace, DocumentClassification, SourceKind, and related models
- `src/tdoc_crawler/config/workspace_registry.py` — WorkspaceRegistry with JSON persistence
- `src/tdoc_crawler/workspaces/__init__.py` — Package re-exports
- `src/tdoc_crawler/workspaces/crud.py` — Workspace CRUD operations
- `src/tdoc_crawler/workspaces/members.py` — Workspace member operations
- `src/tdoc_crawler/workspaces/utils.py` — Workspace utility functions
- `src/tdoc_crawler/cli/_workspace_commands.py` — Workspace CLI commands (moved from 3gpp-ai)
- `tests/test_workspaces.py` — 27 tests for workspace infrastructure

### Files Modified

- `src/tdoc_crawler/cli/tdoc_app.py` — Replaced lazy import with direct import of workspace commands

### Key Design Decisions

1. **Models in `src/tdoc_crawler/models/workspaces.py`** — All workspace-related models (Workspace, SourceKind, DocumentClassification, etc.) live in the main app
2. **Registry in `src/tdoc_crawler/config/workspace_registry.py`** — Uses `PathConfig().ai_workspace_file` for backward compatibility
3. **CRUD in `src/tdoc_crawler/workspaces/`** — Clean separation: crud.py, members.py, utils.py
4. **Circular import avoidance** — `normalize_workspace_name` defined in models, imported by registry and workspaces
5. **Local imports** — `list_workspace_members` imported locally in `delete_workspace` to avoid circular dependencies

## Verification

- ✅ `uv run python -c "from tdoc_crawler.models.workspaces import Workspace, SourceKind; print('models OK')"` — models import
- ✅ `uv run python -c "from tdoc_crawler.config.workspace_registry import WorkspaceRegistry; print('registry OK')"` — registry import
- ✅ `uv run python -c "from tdoc_crawler.workspaces import create_workspace, list_workspaces; print('workspaces OK')"` — workspaces import
- ✅ `uv run python -c "from tdoc_crawler.cli._workspace_commands import app; print('cli OK')"` — CLI import
- ✅ `uv run python -c "from tdoc_crawler.cli.tdoc_app import tdoc_app; print('tdoc_app OK')"` — main app import
- ✅ `uv run pytest tests/test_workspaces.py -v` — 27/27 tests pass

## Deviations

None.

## Next

Proceed to 09-02: Eliminate export step, write artifacts directly to `.llm-wiki/`.
