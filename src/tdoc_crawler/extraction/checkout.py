"""Workspace item checkout and registration logic.

Handles the checkout phase of workspace item management:
downloading/fetching documents and creating workspace member records.

This module is intentionally free of document processing logic
(PDF conversion, markdown extraction, VLM). That responsibility
belongs in the `workspace process` command exclusively.
"""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.config.workspace_registry import WorkspaceMember
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.normalization import normalize_release_version
from tdoc_crawler.workspaces import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    make_workspace_member,
    resolve_spec_release_from_db,
)

_logger = get_logger(__name__)


async def checkout_single_item(
    *,
    item: str,
    workspace: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    path_config: PathConfig,
) -> tuple[WorkspaceMember | None, str | None]:
    """Checkout a single workspace item and create a member record.

    Downloads the document if checkout is enabled and returns a
    WorkspaceMember ready for registration.

    Args:
        item: Item ID to checkout (TDoc ID, spec number, or path).
        workspace: Target workspace name.
        source_kind: Type of source (TDOC, SPEC, OTHER).
        checkout: Whether to download/fetch the document.
        release: Spec release version (only applies to SPEC kind).
        path_config: PathConfig for file system paths.

    Returns:
        Tuple of (member, skip_reason):
        - member: WorkspaceMember if successful, None if skipped.
        - skip_reason: Reason if skipped, None if successful.
    """
    source_path: str = item

    if checkout:
        checkout_path: Path | None = None

        if source_kind == SourceKind.TDOC:
            checkout_path = await checkout_tdoc_to_workspace(
                item,
                path_config.checkout_dir,
                db_file=path_config.db_file,
            )
            if checkout_path is None:
                return None, "TDoc not found in database or meeting not crawled"

        elif source_kind == SourceKind.SPEC:
            checkout_path = await checkout_spec_to_workspace(
                item,
                path_config.checkout_dir,
                release or "latest",
                db_file=path_config.db_file,
            )
            if checkout_path is None:
                return None, "Spec not found in database"

        if checkout_path is not None:
            source_path = str(checkout_path)

    # Resolve release for spec member IDs (always resolve for specs)
    resolved_release: str | None = None
    if source_kind == SourceKind.SPEC:
        resolved_release, _ = await resolve_spec_release_from_db(item, release or "latest")

    source_item_id = f"{item}-REL{normalize_release_version(resolved_release)}" if resolved_release else item
    member = make_workspace_member(source_item_id, source_path, source_kind)
    return member, None


__all__ = ["checkout_single_item"]
