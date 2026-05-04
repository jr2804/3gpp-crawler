"""Workspace CRUD operations."""

from __future__ import annotations

import shutil

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.config.workspace_registry import WorkspaceRegistry
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import DEFAULT_WORKSPACE, normalize_workspace_name

_logger = get_logger(__name__)


def ensure_default_workspace() -> WorkspaceRegistry:
    """Ensure the reserved default workspace exists."""
    registry = _get_registry()
    if DEFAULT_WORKSPACE not in registry.workspaces:
        registry.create_workspace(DEFAULT_WORKSPACE)
        registry.save()
    return registry


def get_workspace(workspace: str | None) -> WorkspaceRegistry | None:
    """Get a workspace by name if it exists.

    Args:
        workspace: Workspace name.

    Returns:
        WorkspaceRegistry if workspace exists, None otherwise.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    return registry.get_workspace(normalized_workspace)


def create_workspace(
    workspace: str | None,
    auto_build: bool = False,
    description: str = "",
    workspace_dir: str | None = None,
    sources_dirname: str | None = None,
) -> WorkspaceRegistry:
    """Create a workspace entry after canonical normalization.

    Args:
        workspace: Workspace name to create.
        auto_build: When True, newly added members are automatically processed.
        description: Optional workspace description.
        workspace_dir: Custom workspace data directory path.
        sources_dirname: Custom sources subdirectory name (default: "sources").

    Returns:
        WorkspaceRegistry with created workspace.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    try:
        registry.create_workspace(
            normalized_workspace,
            description=description,
            auto_build=auto_build,
            workspace_dir=workspace_dir,
            sources_dirname=sources_dirname,
        )
        registry.save()
    except ValueError:
        pass  # Workspace already exists

    # Create workspace directory structure
    try:
        manager = resolve_cache_manager()
        ws_dir = manager.workspace_llm_wiki_dir(normalized_workspace)
        ws_dir.mkdir(parents=True, exist_ok=True)

        sources_dir = manager.workspace_sources_dir(normalized_workspace)
        sources_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # CacheManager may not be registered in all contexts (e.g., tests without CLI entry)
        _logger.debug("Skipping workspace directory creation: CacheManager not available")

    return registry


def list_workspaces() -> list[WorkspaceRegistry]:
    """List all known workspaces."""
    ensure_default_workspace()
    registry = _get_registry()
    return list(registry.workspaces.values())


def delete_workspace(workspace: str | None, delete_artifacts: bool = False) -> bool:
    """Delete a workspace.

    Args:
        workspace: Workspace name to delete.
        delete_artifacts: When True, remove workspace directory and files.

    Returns:
        True if deleted, False if not found or if attempting to delete default.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        _logger.warning("Cannot delete the default workspace")
        return False

    registry = _get_registry()
    if normalized_workspace not in registry.workspaces:
        _logger.warning("Workspace '%s' not found — nothing to delete", normalized_workspace)
        return False

    if delete_artifacts:
        try:
            manager = resolve_cache_manager()
            ws_dir = manager.workspace_llm_wiki_dir(normalized_workspace).parent
            if ws_dir.exists():
                shutil.rmtree(ws_dir)
                _logger.info("Deleted workspace artifacts at '%s'", ws_dir)
        except Exception:
            _logger.debug("Skipping artifact deletion: CacheManager not available")

    deleted = registry.delete_workspace(normalized_workspace)
    if not deleted:
        return False

    registry.save()
    _logger.info("Deleted workspace '%s'", normalized_workspace)
    return deleted


def get_active_workspace() -> str:
    """Get the name of the active workspace."""
    registry = _get_registry()
    return registry.active


def set_active_workspace(workspace: str | None) -> None:
    """Set the active workspace.

    Args:
        workspace: Workspace name to set as active.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    registry.set_active(normalized_workspace)
    registry.save()


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


__all__ = [
    "create_workspace",
    "delete_workspace",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_workspace",
    "list_workspaces",
    "set_active_workspace",
]
