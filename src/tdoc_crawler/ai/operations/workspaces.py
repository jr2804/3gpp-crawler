"""Workspace helper operations for AI pipeline scoping."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tdoc_crawler.ai.models import WorkspaceMember

DEFAULT_WORKSPACE = "default"

_logger = logging.getLogger(__name__)


def normalize_workspace_name(workspace: str | None) -> str:
    """Normalize workspace input to a canonical name.

    Args:
        workspace: Optional workspace name from API/CLI.

    Returns:
        Canonical workspace name. Empty values map to ``default``.
    """
    if workspace is None:
        return DEFAULT_WORKSPACE

    normalized = workspace.strip().lower()
    if not normalized:
        return DEFAULT_WORKSPACE
    return normalized


def is_default_workspace(workspace: str | None) -> bool:
    """Check whether a workspace resolves to the default workspace.

    Args:
        workspace: Optional workspace name.

    Returns:
        ``True`` when the normalized workspace is ``default``.
    """
    return normalize_workspace_name(workspace) == DEFAULT_WORKSPACE


def ensure_default_workspace(storage: Any) -> Any:
    """Ensure the reserved default workspace exists."""
    return storage.ensure_workspace(DEFAULT_WORKSPACE)


def resolve_workspace(storage: Any, workspace: str | None) -> Any:
    """Resolve and auto-create a workspace from optional user input."""
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.ensure_workspace(normalized_workspace)


def get_workspace(storage: Any, workspace: str | None) -> Any | None:
    """Get a workspace by name if it exists."""
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.get_workspace(normalized_workspace)


def create_workspace(storage: Any, workspace: str | None, auto_build: bool = False) -> Any:
    """Create a workspace entry after canonical normalization.

    Args:
        storage: AiStorage instance.
        workspace: Workspace name to create.
        auto_build: When True, newly added members are automatically processed.

    Returns:
        Created workspace object.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.create_workspace(normalized_workspace, auto_build=auto_build)


def list_workspaces(storage: Any) -> list[Any]:
    """List all known workspaces."""
    ensure_default_workspace(storage)
    return storage.list_workspaces()


def delete_workspace(storage: Any, workspace: str | None, preserve_artifacts: bool = True) -> bool:
    """Delete a workspace while preserving artifacts from other workspaces.

    Args:
        storage: AiStorage instance.
        workspace: Workspace name to delete.
        preserve_artifacts: If True (default), keep artifacts (they become orphaned).
                           If False, also delete artifacts for this workspace.

    Returns:
        True if deleted, False if not found or if attempting to delete default.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        _logger.warning("Cannot delete the default workspace")
        return False
    return storage.delete_workspace(normalized_workspace, preserve_artifacts=preserve_artifacts)


def add_workspace_members(
    storage: Any,
    workspace: str | None,
    source_items: list[Any],
) -> int:
    """Register source items in a workspace corpus."""
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.add_workspace_members(normalized_workspace, source_items)


def make_workspace_member(
    workspace: str | None,
    source_item_id: str,
    source_path: str | Path,
    source_kind: Any,
    added_by: str | None = None,
) -> Any:
    """Build a normalized workspace member model from raw input."""
    normalized_workspace = normalize_workspace_name(workspace)
    return WorkspaceMember(
        workspace_name=normalized_workspace,
        source_item_id=source_item_id,
        source_path=str(source_path),
        source_kind=source_kind,
        added_by=added_by,
    )


__all__ = [
    "DEFAULT_WORKSPACE",
    "add_workspace_members",
    "create_workspace",
    "delete_workspace",
    "ensure_default_workspace",
    "get_workspace",
    "is_default_workspace",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "resolve_workspace",
]
