"""Workspace helper operations for AI pipeline scoping."""

import logging
from pathlib import Path
from typing import Any

from tdoc_crawler.ai.models import WorkspaceMember
from tdoc_crawler.ai.operations.workspace_registry import DEFAULT_WORKSPACE, WorkspaceRegistry
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.operations.checkout import checkout_specs
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec

_logger = logging.getLogger(__name__)


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


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
    registry = _get_registry()
    if DEFAULT_WORKSPACE not in registry.workspaces:
        registry.save()
    return storage.ensure_workspace(DEFAULT_WORKSPACE)


def resolve_workspace(storage: Any, workspace: str | None) -> Any:
    """Resolve and auto-create a workspace from optional user input."""
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    if normalized_workspace not in registry.workspaces:
        registry.create_workspace(normalized_workspace)
        registry.save()
    return storage.ensure_workspace(normalized_workspace)


def get_workspace(storage: Any, workspace: str | None) -> Any | None:
    """Get a workspace by name if it exists."""
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.get_workspace(normalized_workspace)


def create_workspace(storage: Any, workspace: str | None, auto_build: bool = False, description: str = "") -> Any:
    """Create a workspace entry after canonical normalization.

    Args:
        storage: AiStorage instance.
        workspace: Workspace name to create.
        auto_build: When True, newly added members are automatically processed.
        description: Optional workspace description.

    Returns:
        Created workspace object.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    registry = _get_registry()
    try:
        registry.create_workspace(normalized_workspace, description=description, auto_build=auto_build)
        registry.save()
    except ValueError:
        pass  # Workspace already exists
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

    registry = _get_registry()
    deleted = registry.delete_workspace(normalized_workspace)
    if deleted:
        registry.save()
        return storage.delete_workspace(normalized_workspace, preserve_artifacts=preserve_artifacts)
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


def checkout_tdoc_to_workspace(
    tdoc_id: str,
    checkout_base: Path,
    storage: Any,
    workspace: str | None,
) -> Path | None:
    """Checkout a TDoc and add it to a workspace.

    Args:
        tdoc_id: TDoc identifier
        checkout_base: Base checkout directory
        storage: AiStorage instance
        workspace: Workspace name

    Returns:
        Path to the checked out TDoc folder, or None if checkout failed
    """
    # First check if already checked out
    existing_path = resolve_tdoc_checkout_path(tdoc_id, checkout_base)
    if existing_path:
        _logger.debug(f"TDoc {tdoc_id} already checked out at {existing_path}")
        return existing_path

    # Need to checkout the TDoc
    try:
        # Resolve TDoc metadata
        metadata = resolve_via_whatthespec(tdoc_id)
        if not metadata:
            _logger.warning(f"Could not resolve TDoc {tdoc_id}")
            return None

        # Checkout the TDoc - returns Path directly or raises exception
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
    # First check if already checked out
    specs_dir = checkout_base / "Specs"
    if specs_dir.exists():
        for spec_dir in specs_dir.rglob(f"*{spec_number}*"):
            if spec_dir.is_dir():
                _logger.debug(f"Spec {spec_number} already checked out at {spec_dir}")
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
                _logger.info(f"Checked out spec {spec_number} to {checkout_paths[0]}")
                return checkout_paths[0]

        _logger.warning(f"Failed to checkout spec {spec_number}")
        return None

    except Exception as e:
        _logger.warning(f"Error checking out spec {spec_number}: {e}")
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
    "delete_workspace",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_workspace",
    "is_default_workspace",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "set_active_workspace",
]
