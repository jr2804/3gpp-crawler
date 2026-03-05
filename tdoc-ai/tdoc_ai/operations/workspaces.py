"""Workspace helper operations for AI pipeline scoping."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tdoc_ai.operations.workspace_names import DEFAULT_WORKSPACE, is_default_workspace, normalize_workspace_name
from tdoc_ai.operations.workspace_registry import (
    WorkspaceMember,
    WorkspaceRegistry,
)
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.base import TDocSourceConfig
from tdoc_crawler.tdocs.sources.portal import PortalSource
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec

_logger = logging.getLogger(__name__)


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


def ensure_default_workspace() -> WorkspaceRegistry:
    """Ensure the reserved default workspace exists."""
    registry = _get_registry()
    if DEFAULT_WORKSPACE not in registry.workspaces:
        registry.create_workspace(DEFAULT_WORKSPACE)
        registry.save()
    return registry


def resolve_workspace(workspace: str | None) -> WorkspaceRegistry:
    """Resolve and auto-create a workspace from optional user input.

    Args:
        workspace: Optional workspace name.

    Returns:
        WorkspaceRegistry with the workspace ensured to exist.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    if normalized_workspace not in registry.workspaces:
        registry.create_workspace(normalized_workspace)
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


def delete_workspace(workspace: str | None, preserve_artifacts: bool = True) -> bool:
    """Delete a workspace while preserving artifacts from other workspaces.

    Note: Artifacts in LanceDB are now scoped by workspace name in the document_id.
    When a workspace is deleted, its artifacts become orphaned (not associated with
    any active workspace) but are preserved.

    Args:
        workspace: Workspace name to delete.
        preserve_artifacts: If True (default), keep artifacts. If False, also delete
                          artifacts for this workspace (not implemented - artifacts are
                          always preserved to prevent data loss).

    Returns:
        True if deleted, False if not found or if attempting to delete default.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        _logger.warning("Cannot delete the default workspace")
        return False

    registry = _get_registry()
    deleted = registry.delete_workspace(normalized_workspace)
    if deleted:
        registry.save()
        _logger.info(f"Deleted workspace '{normalized_workspace}' (artifacts preserved)")
        return True
    return False


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
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()

    metadata = registry.get_workspace(normalized_workspace)
    if metadata is None:
        return []

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
    normalized_source_item_id = source_item_id.strip().upper()
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
    normalized_source_item_id = source_item_id.strip().upper()
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
    workspace: str | None,
    source_item_id: str,
    source_path: str | Path,
    source_kind: Any,
    added_by: str | None = None,
) -> WorkspaceMember:
    """Build a normalized workspace member model from raw input.

    Args:
        workspace: Workspace name.
        source_item_id: Source item ID.
        source_path: Path to the source item.
        source_kind: Kind of source (TDoc, Spec, etc.).
        added_by: Optional identifier of who added this member.

    Returns:
        WorkspaceMember instance.
    """
    normalize_workspace_name(workspace)
    return WorkspaceMember(
        source_item_id=source_item_id,
        source_path=str(source_path),
        source_kind=source_kind,
        added_by=added_by or "",
    )


def resolve_tdoc_checkout_path(tdoc_id: str, checkout_base: Path) -> Path | None:
    """Resolve a TDoc ID to its checkout path.

    The checkout path follows the 3GPP FTP structure:
    <checkout_base>/<group>/<meeting>/Docs/<tdoc_id>/

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-251971")
        checkout_base: Base checkout directory

    Returns:
        Path to the TDoc checkout folder if found, None otherwise
    """
    # Search for the TDoc in the checkout directory
    # The structure is: <checkout_base>/*/*/Docs/<tdoc_id>/
    for docs_dir in checkout_base.rglob("Docs"):
        tdoc_path = docs_dir / tdoc_id
        if tdoc_path.exists() and tdoc_path.is_dir():
            return tdoc_path
    return None


# TODO: This function is doing a lot - consider breaking it up into smaller steps or helper functions for clarity and testability.
def checkout_tdoc_to_workspace(
    tdoc_id: str,
    checkout_base: Path,
    workspace: str | None,
    db_file: Path | None = None,
) -> Path | None:
    """Checkout a TDoc and add it to a workspace.

    Uses a fallback chain to resolve TDoc metadata:
    1. Check if already checked out to disk
    2. Check local database for existing metadata with URL
    3. Try WhatTheSpec API (unauthenticated)
    4. Try 3GPP Portal (requires credentials)

    Args:
        tdoc_id: TDoc identifier
        checkout_base: Base checkout directory
        workspace: Workspace name
        db_file: Optional path to database file for metadata lookup

    Returns:
        Path to the checked out TDoc folder, or None if checkout failed
    """
    # First check if already checked out
    existing_path = resolve_tdoc_checkout_path(tdoc_id, checkout_base)
    if existing_path:
        _logger.debug(f"TDoc {tdoc_id} already checked out at {existing_path}")
        return existing_path

    # Need to checkout the TDoc - use fallback chain
    metadata: TDocMetadata | None = None

    # Step 1: Check database for existing metadata
    if db_file is not None and db_file.exists():
        try:
            with TDocDatabase(db_file) as db:
                metadata = db._get_tdoc(tdoc_id)
                if metadata and metadata.url:
                    _logger.debug(f"Found TDoc {tdoc_id} in database with URL")
        except Exception as e:
            _logger.debug(f"Database lookup failed for {tdoc_id}: {e}")

    # Step 2: Try WhatTheSpec API if not found in database
    if metadata is None:
        _logger.debug(f"Trying WhatTheSpec API for {tdoc_id}")
        try:
            metadata = resolve_via_whatthespec(tdoc_id)
            if metadata:
                _logger.info(f"Resolved TDoc {tdoc_id} via WhatTheSpec API")
        except Exception as e:
            _logger.debug(f"WhatTheSpec lookup failed for {tdoc_id}: {e}")

    # Step 3: Try 3GPP Portal as final fallback (requires credentials)
    if metadata is None:
        _logger.debug(f"Trying 3GPP Portal for {tdoc_id}")
        try:
            config = TDocSourceConfig(timeout=30)
            with PortalSource(config) as portal_source:
                metadata = portal_source.fetch_by_id(tdoc_id, db_file=db_file)
                if metadata:
                    _logger.info(f"Resolved TDoc {tdoc_id} via 3GPP Portal")
        except Exception as e:
            _logger.debug(f"Portal lookup failed for {tdoc_id}: {e}")

    # Check if we successfully resolved metadata
    if metadata is None:
        _logger.warning(f"Could not resolve TDoc {tdoc_id} via any source")
        return None

    # Checkout the TDoc - returns Path directly or raises exception
    try:
        checkout_path = checkout_tdoc(metadata, checkout_base)
        if checkout_path and checkout_path.exists():
            _logger.info(f"Checked out TDoc {tdoc_id} to {checkout_path}")
            return checkout_path

        _logger.warning(f"Checkout returned invalid path for TDoc {tdoc_id}")
        return None
    except FileNotFoundError as e:
        _logger.warning(f"TDoc {tdoc_id} not found or withdrawn: {e}")
        return None
    except Exception as e:
        _logger.warning(f"Error checking out TDoc {tdoc_id}: {e}")
        return None


def checkout_spec_to_workspace(
    spec_number: str,
    checkout_base: Path,
    workspace: str | None,
    release: str = "latest",
) -> Path | None:
    """Checkout a spec and add it to a workspace.

    Args:
        spec_number: Spec number (e.g., "26260" for 26.260)
        checkout_base: Base checkout directory
        workspace: Workspace name
        release: Spec release version (e.g., "16.3.0", "17.0.0") or "latest"

    Returns:
        Path to the checked out spec folder, or None if checkout failed
    """
    # First check if already checked out with the SAME release version
    specs_dir = checkout_base / "Specs"
    if specs_dir.exists():
        # Search for spec with matching release version
        for spec_dir in specs_dir.rglob(f"*{spec_number}*"):
            if spec_dir.is_dir():
                # Check if release version matches
                dir_name = spec_dir.name
                if release != "latest" and release not in dir_name:
                    continue
                _logger.debug(f"Spec {spec_number} (release {release}) already checked out at {spec_dir}")
                return spec_dir

    # Need to checkout the spec
    try:
        # Open the spec database
        db_path = checkout_base.parent / "specs.db"
        with SpecDatabase(db_path) as db:
            # Checkout the spec
            checkout_paths = checkout_specs(
                spec_numbers=[spec_number],
                checkout_dir=checkout_base,
                database=db,
                release=release,
            )

            if checkout_paths and checkout_paths[0] and checkout_paths[0].exists():
                _logger.info(f"Checked out spec {spec_number} (release {release}) to {checkout_paths[0]}")
                return checkout_paths[0]

        _logger.warning(f"Failed to checkout spec {spec_number} (release {release})")
        return None

    except Exception as e:
        _logger.warning(f"Error checking out spec {spec_number} (release {release}): {e}")
        return None


def ensure_ai_subfolder(checkout_path: Path) -> Path:
    """Ensure the .ai subfolder exists for processed outputs.

    Args:
        checkout_path: Path to the checked out document folder

    Returns:
        Path to the .ai subfolder
    """
    ai_folder = checkout_path / ".ai"
    ai_folder.mkdir(parents=True, exist_ok=True)
    return ai_folder


__all__ = [
    "DEFAULT_WORKSPACE",
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "create_workspace",
    "deactivate_workspace_member",
    "delete_workspace",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_workspace",
    "get_workspace_member_counts",
    "is_default_workspace",
    "list_workspace_members",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "remove_invalid_members",
    "remove_workspace_member",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "set_active_workspace",
]
