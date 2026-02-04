"""TDoc checkout functionality for downloading and extracting documents.

This module provides functionality to download TDocs from the 3GPP server
and extract them to a local checkout folder while maintaining the same
directory structure as the server.
"""

from __future__ import annotations

import logging
import posixpath
import shutil
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

import requests

from tdoc_crawler.models import TDocMetadata

logger = logging.getLogger(__name__)


def _sanitize_path_component(component: str) -> str:
    """Sanitize a path component to be valid on all platforms.

    Removes or replaces characters that are invalid in file/directory names:
    - Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    - Invalid characters: < > : " | ? *
    - Special sequences like "..." which can cause issues

    Args:
        component: Path component to sanitize

    Returns:
        Sanitized path component
    """
    if not component:
        return "_"

    # Replace problematic sequences
    sanitized = component.replace("...", "_")

    # Windows reserved names (case-insensitive)
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
    if sanitized.lower() in reserved:
        sanitized = f"_{sanitized}"

    return sanitized


def get_checkout_path(metadata: TDocMetadata, checkout_dir: Path) -> Path:
    """Calculate the checkout path for a TDoc based on its URL.

    The checkout path mirrors the 3GPP server directory structure.
    For example:
    - URL: https://www.3gpp.org/ftp/tsg_sa/SA4/s4-251234.zip
    - Checkout: checkout_dir/tsg_sa/SA4/s4-251234/

    Args:
        metadata: TDoc metadata containing the URL
        checkout_dir: Base checkout directory

    Returns:
        Path to the checkout directory for this TDoc

    Raises:
        ValueError: If the URL is invalid or contains placeholder patterns
    """
    # Validate URL before processing
    if not metadata.is_valid:
        raise ValueError(f"Invalid or corrupt URL for TDoc {metadata.tdoc_id}: {metadata.url}")

    url_path = urlparse(metadata.url).path

    # Normalize the path: remove leading slash and split into components
    # Use str.split('/') to avoid Path treating it as absolute on Windows
    url_path = url_path.lstrip("/")
    path_parts = url_path.split("/")

    # Find the 'ftp' component and take everything after it
    try:
        ftp_index = path_parts.index("ftp")
        relative_parts = path_parts[ftp_index + 1 :]
    except ValueError:
        # If 'ftp' not found, use the full path
        relative_parts = path_parts

    # Remove the filename (last component) - we'll use tdoc_id as folder name
    if relative_parts:
        relative_parts = relative_parts[:-1]

    # Sanitize path components to avoid invalid directory names
    sanitized_parts = [_sanitize_path_component(part) for part in relative_parts if part]

    # Build the checkout path: checkout_dir / path / tdoc_id
    checkout_path = checkout_dir.joinpath(*sanitized_parts) / metadata.tdoc_id if sanitized_parts else checkout_dir / metadata.tdoc_id

    return checkout_path


def checkout_tdoc(
    metadata: TDocMetadata,
    checkout_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Download and extract a TDoc to the checkout folder.

    Args:
        metadata: TDoc metadata containing URL and ID
        checkout_dir: Base checkout directory
        force: If True, re-download even if already exists

    Returns:
        Path to the extracted TDoc directory

    Raises:
        FileNotFoundError: If download fails or zip is empty
        ValueError: If URL scheme is not supported
        zipfile.BadZipFile: If the downloaded file is not a valid zip
    """
    checkout_path = get_checkout_path(metadata, checkout_dir)

    # Check if already checked out
    if checkout_path.exists() and not force:
        logger.debug(f"TDoc {metadata.tdoc_id} already checked out at {checkout_path}")
        return checkout_path

    # Create checkout directory
    checkout_path.mkdir(parents=True, exist_ok=True)

    cache_dir = checkout_dir.parent if checkout_dir.name == "checkout" else checkout_dir

    if force:
        downloads_dir = cache_dir / "checkout"
        extract_dir = downloads_dir / metadata.tdoc_id
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        zip_path = downloads_dir / f"{metadata.tdoc_id}.zip"
        with suppress(FileNotFoundError):
            zip_path.unlink()
        filename = posixpath.basename(urlparse(metadata.url).path)
        if filename:
            with suppress(FileNotFoundError):
                (downloads_dir / filename).unlink()

    import importlib  # noqa: PLC0415

    from tdoc_crawler.cli.helpers import prepare_tdoc_file  # noqa: PLC0415

    cli_helpers = importlib.import_module("tdoc_crawler.cli.helpers")
    original_download = cli_helpers.download_to_path
    try:
        cli_helpers.download_to_path = _download_file
        prepared_path = prepare_tdoc_file(metadata, cache_dir, return_dir=True)
    finally:
        cli_helpers.download_to_path = original_download
    if prepared_path.is_dir():
        if prepared_path != checkout_path:
            shutil.copytree(prepared_path, checkout_path, dirs_exist_ok=True)
            shutil.rmtree(prepared_path)
    else:
        target_path = checkout_path / prepared_path.name
        shutil.copy2(prepared_path, target_path)
        if prepared_path != target_path:
            with suppress(FileNotFoundError):
                prepared_path.unlink()

    logger.info(f"Checked out {metadata.tdoc_id} to {checkout_path}")

    return checkout_path


def _download_file(url: str, destination: Path) -> None:
    """Download a file from URL to destination path.

    Args:
        url: Source URL
        destination: Destination path

    Raises:
        ValueError: If URL scheme is not supported
        FileNotFoundError: If download fails
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Validate URL scheme
    allowed_schemes = ("ftp://", "http://", "https://")
    lowered = url.lower()
    if not lowered.startswith(allowed_schemes):
        raise ValueError(f"unsupported-url-scheme: {url}")

    try:
        response = requests.get(url, timeout=300, stream=True)  # noqa: S113
        response.raise_for_status()
        with destination.open("wb") as target:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    target.write(chunk)
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        raise FileNotFoundError(f"failed-to-download ({status_code}): {url}") from exc
    except Exception as exc:
        raise FileNotFoundError(f"failed-to-download: {url}") from exc


def get_checked_out_tdocs(checkout_dir: Path) -> list[str]:
    """Get list of TDoc IDs that are already checked out.

    Args:
        checkout_dir: Base checkout directory

    Returns:
        List of TDoc IDs (directory names)
    """
    if not checkout_dir.exists():
        return []

    tdoc_ids = []
    for path in checkout_dir.rglob("*"):
        if path.is_dir():
            # Check if this is a leaf directory (contains files, not just subdirs)
            # and is not an intermediate directory
            has_files = any(f.is_file() for f in path.iterdir())
            if has_files:
                tdoc_ids.append(path.name)

    return tdoc_ids


__all__ = [
    "checkout_tdoc",
    "get_checked_out_tdocs",
    "get_checkout_path",
]
