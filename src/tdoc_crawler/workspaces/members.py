"""Workspace member operations."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config.workspace_registry import WorkspaceMember, WorkspaceRegistry
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import SourceKind, WorkspaceNotFoundError, normalize_workspace_name
from tdoc_crawler.utils.normalization import normalize_release_version, normalize_spec_number_compact, normalize_tdoc_id

_logger = get_logger(__name__)


def add_workspace_members(
    workspace: str | None,
    members: list[WorkspaceMember],
) -> int:
    """Register source items in a workspace corpus.

    Args:
        workspace: Workspace name.
        members: List of WorkspaceMember to add.

    Returns:
        Number of members added.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()

    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        registry.create_workspace(normalized_workspace)
        metadata = registry.get_workspace(normalized_workspace)

    if metadata is None:
        return 0

    added_count = 0
    for member in members:
        metadata.add_member(member)
        added_count += 1

    registry.save()
    return added_count


def list_workspace_members(
    workspace: str | None,
    include_inactive: bool = False,
) -> list[WorkspaceMember]:
    """List members for a workspace.

    Args:
        workspace: Workspace name.
        include_inactive: Include inactive members.

    Returns:
        List of WorkspaceMember.

    Raises:
        WorkspaceNotFoundError: If workspace does not exist.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()

    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        raise WorkspaceNotFoundError(f"Workspace '{normalized_workspace}' not found")

    return metadata.list_members(include_inactive=include_inactive)


def get_workspace_member_counts(workspace: str | None) -> dict[str, int]:
    """Get member counts for a workspace.

    Args:
        workspace: Workspace name.

    Returns:
        Dict with counts for 'tdoc', 'spec', 'other', and 'total'.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()

    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        return {"tdoc": 0, "spec": 0, "other": 0, "total": 0}

    return metadata.get_member_counts()


def remove_invalid_members(workspace: str | None) -> int:
    """Remove all inactive members from a workspace.

    Args:
        workspace: Workspace name.

    Returns:
        Number of members removed.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()

    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        return 0

    # Deactivate all inactive members and count them
    removed_count = 0
    active_members = []
    for member_dict in metadata.members:
        if not member_dict.get("is_active", True):
            removed_count += 1
        else:
            active_members.append(member_dict)

    metadata.members = active_members
    registry.save()
    return removed_count


def deactivate_workspace_member(workspace: str | None, source_item_id: str) -> bool:
    """Deactivate a workspace member.

    Args:
        workspace: Workspace name.
        source_item_id: Source item ID to deactivate.

    Returns:
        True if found and deactivated, False otherwise.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    normalized_source_item_id = normalize_tdoc_id(source_item_id)
    if not normalized_source_item_id:
        return False

    registry = _get_registry()
    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        return False

    result = metadata.deactivate_member(normalized_source_item_id)
    if result:
        registry.save()
    return result


def remove_workspace_member(workspace: str | None, source_item_id: str) -> bool:
    """Remove a workspace member.

    Args:
        workspace: Workspace name.
        source_item_id: Source item ID to remove.

    Returns:
        True if found and removed, False otherwise.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    normalized_source_item_id = normalize_tdoc_id(source_item_id)
    if not normalized_source_item_id:
        return False

    registry = _get_registry()
    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        return False

    result = metadata.remove_member(normalized_source_item_id)
    if result:
        registry.save()
    return result


def make_workspace_member(
    source_item_id: str,
    source_path: str | Path,
    source_kind: SourceKind | str,
    added_by: str | None = None,
    release: str | None = None,
) -> WorkspaceMember:
    """Build a normalized workspace member model from raw input.

    For specs with a concrete release, the ``source_item_id`` is constructed
    as ``{compact_spec}-REL{major.minor.patch}`` (e.g. ``26260-REL19.0.0``).
    When no release or a sentinel value (``"latest"``/``"all"``) is given,
    the ID stays as the compact spec number without a ``-REL`` suffix.

    Args:
        source_item_id: Source item ID (spec number, TDoc ID, etc.).
        source_path: Path to the source item.
        source_kind: Kind of source (TDoc, Spec, etc.).
        added_by: Optional identifier of who added this member.
        release: Optional spec release version (e.g. "18", "18.1.0", "latest").

    Returns:
        WorkspaceMember instance.
    """
    kind = SourceKind(source_kind)

    if kind == SourceKind.SPEC:
        compact_spec = normalize_spec_number_compact(source_item_id)
        if release and release.strip().lower() not in ("latest", "all"):
            normalized_release = normalize_release_version(release)
            member_id = f"{compact_spec}-REL{normalized_release}"
        else:
            member_id = compact_spec
    else:
        member_id = normalize_tdoc_id(source_item_id) or source_item_id

    return WorkspaceMember(
        source_item_id=member_id,
        source_path=str(source_path),
        source_kind=kind,
        added_by=added_by or "",
        release=release,
    )


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


__all__ = [
    "add_workspace_members",
    "deactivate_workspace_member",
    "get_workspace_member_counts",
    "list_workspace_members",
    "make_workspace_member",
    "remove_invalid_members",
    "remove_workspace_member",
]
