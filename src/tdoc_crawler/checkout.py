"""TDoc checkout functionality for downloading and extracting documents.

This module provides functionality to download TDocs from the 3GPP server
and extract them to a local checkout folder while maintaining the same
directory structure as the server.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from tdoc_crawler.models import TDocMetadata

logger = logging.getLogger(__name__)


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
    """
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

    # Build the checkout path: checkout_dir / path / tdoc_id
    checkout_path = checkout_dir.joinpath(*relative_parts) / metadata.tdoc_id if relative_parts else checkout_dir / metadata.tdoc_id

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

    # Download the file
    temp_zip_path = checkout_path / f"{metadata.tdoc_id}.zip"

    try:
        _download_file(metadata.url, temp_zip_path)

        # Extract the zip file
        with zipfile.ZipFile(temp_zip_path) as archive:
            archive.extractall(checkout_path)

        logger.info(f"Checked out {metadata.tdoc_id} to {checkout_path}")

    finally:
        # Clean up the zip file
        if temp_zip_path.exists():
            temp_zip_path.unlink()

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
    from urllib.request import urlopen

    destination.parent.mkdir(parents=True, exist_ok=True)

    # Validate URL scheme
    allowed_schemes = ("ftp://", "http://", "https://")
    lowered = url.lower()
    if not lowered.startswith(allowed_schemes):
        raise ValueError(f"unsupported-url-scheme: {url}")

    try:
        with urlopen(url, timeout=300) as response, destination.open("wb") as target:  # noqa: S310
            shutil.copyfileobj(response, target)
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
