"""Workspace item checkout and registration logic.

Handles the checkout phase of workspace item management:
downloading/fetching documents and creating workspace member records.

This module is intentionally free of document processing logic
(PDF conversion, markdown extraction, VLM). That responsibility
belongs in the `workspace process` command exclusively.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.config.workspace_registry import WorkspaceMember
from tdoc_crawler.http_client.session import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.normalization import url_to_safe_stem
from tdoc_crawler.workspaces import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    make_workspace_member,
    resolve_spec_release_from_db,
)

_logger = get_logger(__name__)


def _is_url(value: str) -> bool:
    """Return True if value looks like an HTTP(S) URL."""
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


async def _sniff_content_type(url: str) -> str:
    """Sniff Content-Type via HEAD request."""
    try:
        with create_cached_session() as session:
            response = session.head(url, allow_redirects=True, timeout=30)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            return content_type.split(";")[0].strip()
    except Exception:
        _logger.warning("HEAD request failed for %s; falling back to generic type", url)
        return "application/octet-stream"


def _guess_extension(content_type: str) -> str:
    """Guess a file extension from a MIME content type."""
    mapping = {
        "text/html": ".html",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    }
    return mapping.get(content_type.lower(), "")


async def _checkout_other(
    item: str,
    checkout_dir: Path,
    checkout_prefix: str = "OTHER_",
) -> Path | None:
    """Checkout an OTHER source (local file or URL) into the checkout directory.

    Args:
        item: File path or URL to checkout.
        checkout_dir: Base checkout directory.
        checkout_prefix: Prefix for the checkout subdirectory name.

    Returns:
        Path to the checked-out file, or None on failure.
    """
    if _is_url(item):
        content_type = await _sniff_content_type(item)
        ext = _guess_extension(content_type) or ".bin"
        safe_stem = url_to_safe_stem(item, prefix=checkout_prefix)
        dest_dir = checkout_dir / "other" / safe_stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"index{ext}"

        with create_cached_session() as session:
            try:
                response = session.get(item, timeout=60)
                response.raise_for_status()
                dest_file.write_bytes(response.content)
            except Exception:
                _logger.warning("Download failed for %s", item)
                return None

        return dest_file

    # Local file path
    source = Path(item).expanduser().resolve()
    if not source.exists():
        _logger.error("Local file not found: %s", item)
        return None

    safe_stem = url_to_safe_stem(str(source), prefix=checkout_prefix)
    dest_dir = checkout_dir / "other" / safe_stem
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / source.name
    shutil.copy2(source, dest_file)
    return dest_file


async def checkout_single_item(
    *,
    item: str,
    workspace: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    path_config: PathConfig,
    checkout_prefix: str = "OTHER_",
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
        checkout_prefix: Prefix for checkout directory names when adding OTHER sources.

    Returns:
        Tuple of (member, skip_reason):
        - member: WorkspaceMember if successful, None if skipped.
        - skip_reason: Reason if skipped, None if successful.
    """
    source_path: str = item
    content_type: str = ""
    original_url: str = ""

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

        elif source_kind == SourceKind.OTHER:
            original_url = item if _is_url(item) else ""
            checkout_path = await _checkout_other(
                item,
                path_config.checkout_dir,
                checkout_prefix=checkout_prefix,
            )
            if checkout_path is None:
                return None, "OTHER source checkout failed"
            content_type = await _sniff_content_type(item) if _is_url(item) else ""
            # For OTHER sources, use the safe stem as the item ID so the
            # workspace member gets a namespaced identifier instead of the
            # raw URL (which would be uppercased by normalize_tdoc_id).
            safe_stem = url_to_safe_stem(item, prefix=checkout_prefix)
            item = safe_stem

        if checkout_path is not None:
            source_path = str(checkout_path)

    # Resolve release for spec member IDs (always resolve for specs)
    resolved_release: str | None = None
    if source_kind == SourceKind.SPEC:
        resolved_release, _ = await resolve_spec_release_from_db(item, release or "latest")

    member = make_workspace_member(item, source_path, source_kind, release=resolved_release)
    member.content_type = content_type
    member.original_url = original_url
    return member, None


__all__ = ["checkout_single_item"]
