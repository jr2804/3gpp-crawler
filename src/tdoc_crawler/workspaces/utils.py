"""Workspace utility functions."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config.workspace_registry import WorkspaceRegistry
from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)


def _get_registry() -> WorkspaceRegistry:
    """Get the workspace registry singleton."""
    return WorkspaceRegistry.load()


def delete_artifact_folder(artifact_path: Path) -> int:
    """Delete an artifact folder and return count of deleted items.

    Args:
        artifact_path: Path to the artifact folder (e.g., workspace sources dir).

    Returns:
        Count of items deleted.
    """
    if not artifact_path.exists() or not artifact_path.is_dir():
        return 0

    count = 0
    try:
        for item in artifact_path.rglob("*"):
            if item.is_file():
                item.unlink()
                count += 1
        # Remove folder itself
        artifact_path.rmdir()
        count += 1
        _logger.debug("Deleted artifact folder: %s", artifact_path)
    except Exception as e:
        _logger.warning("Failed to delete artifact folder %s: %s", artifact_path, e)
    return count


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
