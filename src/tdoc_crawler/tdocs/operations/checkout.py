"""TDoc checkout operations for downloading and extracting documents.

This module provides functionality to download TDocs from the 3GPP server
and extract them to a local checkout folder while maintaining the same
directory structure as the server.
"""

from __future__ import annotations

import posixpath
import shutil
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from tdoc_crawler.http_client import download_to_file
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.doclist import DocumentListError, fetch_meeting_document_list

logger = get_logger(__name__)


@dataclass
class CheckoutResult:
    """Result of a checkout operation."""

    success_count: int
    error_count: int
    errors: list[str]


def get_checkout_path(metadata: TDocMetadata, checkout_dir: Path) -> Path:
    """Calculate the checkout path for a TDoc based on its URL.

    The checkout path mirrors the 3GPP server directory structure.

    Args:
        metadata: TDoc metadata containing the URL
        checkout_dir: Base checkout directory

    Returns:
        Path to the checkout directory for this TDoc
    """
    url_path_str: str = str(urlparse(metadata.url).path)
    url_path_str = url_path_str.lstrip("/")
    path_parts: list[str] = url_path_str.split("/")

    try:
        ftp_index = path_parts.index("ftp")
        relative_parts: list[str] = path_parts[ftp_index + 1 :]
    except ValueError:
        relative_parts = path_parts

    if relative_parts:
        relative_parts = relative_parts[:-1]

    checkout_path = checkout_dir.joinpath(*relative_parts) / metadata.tdoc_id if relative_parts else checkout_dir / metadata.tdoc_id
    return checkout_path


def checkout_tdoc(
    metadata: TDocMetadata,
    checkout_dir: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
) -> Path:
    """Download and extract a TDoc to the checkout folder.

    Args:
        metadata: TDoc metadata containing URL and ID
        checkout_dir: Base checkout directory
        force: If True, re-download even if already exists
        session: Optional requests.Session to reuse for downloads

    Returns:
        Path to the extracted TDoc directory

    Raises:
        FileNotFoundError: If download fails or zip is empty
    """
    checkout_path = get_checkout_path(metadata, checkout_dir)

    if checkout_path.exists() and not force:
        logger.debug(f"TDoc {metadata.tdoc_id} already checked out at {checkout_path}")
        return checkout_path

    checkout_path.mkdir(parents=True, exist_ok=True)
    temp_zip_path = checkout_path / f"{metadata.tdoc_id}.zip"

    if metadata.url is None:
        raise ValueError(f"TDoc {metadata.tdoc_id} has no URL")

    try:
        download_to_file(metadata.url, temp_zip_path, session=session)
        with zipfile.ZipFile(temp_zip_path) as archive:
            archive.extractall(checkout_path)
        logger.info(f"Checked out {metadata.tdoc_id} to {checkout_path}")
    finally:
        if temp_zip_path.exists():
            temp_zip_path.unlink()

    return checkout_path


def prepare_tdoc_file(metadata: TDocMetadata, cache_dir: Path, return_dir: bool = False, session: requests.Session | None = None) -> Path:
    """Prepare TDoc file for opening (download and extract if needed).

    Args:
        metadata: TDoc metadata with download URL.
        cache_dir: Cache directory for downloads and extracted files.
        return_dir: When True and TDoc is a zip, return the extract directory.
        session: Optional requests.Session to reuse for downloads.

    Returns:
        Path to the downloaded file, or the extract directory when return_dir is True.
    """
    # Handle the case where metadata.url is None
    if metadata.url is None:
        raise ValueError(f"Cannot prepare TDoc file for {metadata.tdoc_id}: URL is None")

    downloads_dir = cache_dir / "checkout"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    path = urlparse(metadata.url).path
    filename = str(posixpath.basename(path))
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip":
        extract_dir = downloads_dir / metadata.tdoc_id
        if extract_dir.exists():
            files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
            if files:
                return extract_dir if return_dir else files[0]
            shutil.rmtree(extract_dir)
        zip_path = downloads_dir / f"{metadata.tdoc_id}.zip"
        download_to_file(metadata.url, zip_path, session=session)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_dir)
        finally:
            with suppress(FileNotFoundError):
                zip_path.unlink()
        files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
        if not files:
            raise FileNotFoundError("no-files-in-archive")
        return extract_dir if return_dir else files[0]

    # For non-zip files, download directly
    target_suffix = suffix or ""
    target_name = filename if filename else f"{metadata.tdoc_id}{target_suffix or '.bin'}"
    target_path = downloads_dir / target_name
    if not target_path.exists():
        try:
            download_to_file(metadata.url, target_path, session=session)
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise FileNotFoundError(f"failed-to-download ({status_code}): {metadata.url}") from exc
    return target_path


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


def clear_checkout_tdocs(checkout_dir: Path) -> int:
    """Clear TDoc checkout entries from the checkout directory.

    Args:
        checkout_dir: Base checkout directory

    Returns:
        Number of entries removed
    """
    if not checkout_dir.exists():
        return 0
    removed = 0
    for entry in checkout_dir.iterdir():
        if entry.name == "Specs":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        removed += 1
    return removed


def checkout_tdocs(
    results: list[TDocMetadata],
    checkout_dir: Path,
    force: bool = False,
    session: requests.Session | None = None,
    cache_manager_name: str | None = None,
) -> CheckoutResult:
    """Checkout multiple TDoc files to the checkout directory.

    Args:
        results: List of TDocMetadata to checkout
        checkout_dir: Base checkout directory
        force: If True, re-download even if already exists
        session: Optional requests.Session to reuse for downloads
        cache_manager_name: Optional cache manager name for HTTP caching

    Returns:
        CheckoutResult with success/error counts
    """
    if not results:
        return CheckoutResult(success_count=0, error_count=0, errors=[])

    success_count = 0
    error_count = 0
    errors: list[str] = []

    for metadata in results:
        try:
            if not metadata.url:
                raise ValueError("missing URL")
            checkout_tdoc(metadata, checkout_dir, force=force, session=session)
            success_count += 1
        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(f"{metadata.tdoc_id}: {exc}")
            error_count += 1

    return CheckoutResult(success_count=success_count, error_count=error_count, errors=errors)


def checkout_meeting_tdocs(
    meetings: list[MeetingMetadata],
    checkout_dir: Path,
    http_cache_file: Path,
    session: requests.Session | None = None,
    cache_manager_name: str | None = None,
) -> CheckoutResult:
    """Checkout TDoc files from a list of meetings.

    Args:
        meetings: List of MeetingMetadata to checkout TDocs from
        checkout_dir: Base checkout directory
        http_cache_file: Path to HTTP cache database
        session: Optional requests.Session to reuse for downloads
        cache_manager_name: Optional cache manager name for HTTP caching

    Returns:
        CheckoutResult with success/error counts
    """
    if not meetings:
        return CheckoutResult(success_count=0, error_count=0, errors=[])

    unique: dict[str, TDocMetadata] = {}
    errors: list[str] = []

    for meeting in meetings:
        if not meeting.files_url:
            errors.append(f"{meeting.short_name}: no files URL")
            continue
        try:
            tdocs = fetch_meeting_document_list(meeting.meeting_id, http_cache_file)
        except DocumentListError as exc:
            errors.append(f"{meeting.short_name}: {exc}")
            continue
        for metadata in tdocs:
            if metadata.tdoc_id not in unique:
                unique[metadata.tdoc_id] = metadata

    return checkout_tdocs(list(unique.values()), checkout_dir, force=False, session=session, cache_manager_name=cache_manager_name)


__all__ = [
    "CheckoutResult",
    "checkout_meeting_tdocs",
    "checkout_tdoc",
    "checkout_tdocs",
    "clear_checkout_tdocs",
    "get_checked_out_tdocs",
    "get_checkout_path",
    "prepare_tdoc_file",
]
