"""Workspace CRUD operations."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.logging import get_logger

from threegpp_ai.operations.workspace_names import DEFAULT_WORKSPACE, normalize_workspace_name
from threegpp_ai.operations.workspace_registry import WorkspaceRegistry

from .members import list_workspace_members
from .utils import _get_registry, delete_ai_folder

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


def create_workspace(workspace: str | None, auto_build: bool = False, description: str = "") -> WorkspaceRegistry:
    """Create a workspace entry after canonical normalization.

    Args:
        workspace: Workspace name to create.
        auto_build: When True, newly added members are automatically processed.
        description: Optional workspace description.

    Returns:
        WorkspaceRegistry with created workspace.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    try:
        registry.create_workspace(normalized_workspace, description=description, auto_build=auto_build)
        registry.save()
    except ValueError:
        pass  # Workspace already exists
    return registry


def list_workspaces() -> list[WorkspaceRegistry]:
    """List all known workspaces."""
    ensure_default_workspace()
    registry = _get_registry()
    return list(registry.workspaces.values())


def delete_workspace(workspace: str | None, *, delete_artifacts: bool = False) -> bool:
    """Delete a workspace and optionally delete all .ai artifacts for its members.

    Args:
        workspace: Workspace name to delete.
        delete_artifacts: If True, delete all .ai processing folders for workspace members
            in the checkout directory.

    Returns:
        True if deleted, False if not found or if attempting to delete default.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        _logger.warning("Cannot delete the default workspace")
        return False

    # Get members before deleting workspace
    members = list_workspace_members(normalized_workspace, include_inactive=True)

    registry = _get_registry()
    deleted = registry.delete_workspace(normalized_workspace)
    if not deleted:
        return False

    registry.save()

    # Delete .ai artifacts if requested
    if delete_artifacts and members:
        _logger.info("Deleting .ai artifacts for %d members", len(members))
        for member in members:
            source_path = Path(member.source_path)
            # Check if source_path is already the .ai folder (ends with .ai as directory)
            if source_path.name == ".ai":
                # Source path is the .ai folder itself
                delete_ai_folder(source_path)
            else:
                # Source path is the document folder - delete .ai subfolder
                delete_ai_folder(source_path / ".ai")

    _logger.info("Deleted workspace '%s' (delete_artifacts=%s)", normalized_workspace, delete_artifacts)
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
