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
from urllib.parse import urljoin, urlparse

import niquests as requests
from bs4 import BeautifulSoup

from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.http_client import download_to_file
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocStatus
from tdoc_crawler.tdocs.sources.doclist import DocumentListError, fetch_meeting_document_list
from tdoc_crawler.utils.security import safe_extract_zip

logger = get_logger(__name__)


@dataclass
class CheckoutResult:
    """Result of a checkout operation."""

    success_count: int
    error_count: int
    errors: list[str]


def resolve_tdoc_file_sizes(results: list[TDocMetadata], checkout_dir: Path) -> None:
    """Resolve file sizes for TDocs from on-disk checkout directories.

    For each TDoc with ``file_size`` unset and a valid URL, computes the
    checkout path and sums the sizes of all files in that directory.
    Updates ``record.file_size`` in-place.
    """
    for record in results:
        if record.file_size or not record.url:
            continue
        tdoc_dir = get_checkout_path(record, checkout_dir)
        if not tdoc_dir.exists():
            continue
        total = sum(f.stat().st_size for f in tdoc_dir.iterdir() if f.is_file())
        if total:
            record.file_size = total


def prepare_tdoc_file(metadata: TDocMetadata, checkout_dir: Path, return_dir: bool = False, session: requests.Session | None = None) -> Path:
    """Prepare TDoc file for opening (download and extract if needed).

    Args:
        metadata: TDoc metadata with download URL.
        checkout_dir: Checkout directory for downloads and extracted files.
        return_dir: When True and TDoc is a zip, return the extract directory.
        session: Optional requests.Session to reuse for downloads.

    Returns:
        Path to the downloaded file, or the extract directory when return_dir is True.

    Raises:
        FileNotFoundError: If download fails for non-withdrawn TDocs
    """
    # Handle the case where metadata.url is None
    if metadata.url is None:
        msg = f"Cannot prepare TDoc file for {metadata.tdoc_id}: URL is None"
        raise ValueError(msg)

    # Check if TDoc is withdrawn - if so, skip download and log debug message
    if metadata.status == TDocStatus.WITHDRAWN:
        logger.debug(f"Skipping download for withdrawn TDoc {metadata.tdoc_id}")
        msg = "withdrawn"
        raise FileNotFoundError(msg)

    downloads_dir = Path(checkout_dir)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    url_path = urlparse(metadata.url).path
    filename = str(posixpath.basename(url_path))
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip":
        extract_dir = downloads_dir / metadata.tdoc_id
        if extract_dir.exists():
            files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
            if files:
                return extract_dir if return_dir else files[0]
            shutil.rmtree(extract_dir)
        zip_file = downloads_dir / f"{metadata.tdoc_id}.zip"
        download_to_file(metadata.url, zip_file, session=session)
        try:
            safe_extract_zip(zip_file, extract_dir)
        finally:
            with suppress(FileNotFoundError):
                zip_file.unlink()
        files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
        if not files:
            msg = "no-files-in-archive"
            raise FileNotFoundError(msg)
        return extract_dir if return_dir else files[0]

    # For non-zip files, download directly
    target_suffix = suffix or ""
    target_name = filename or f"{metadata.tdoc_id}{target_suffix or '.bin'}"
    target_file = downloads_dir / target_name
    if not target_file.exists():
        try:
            download_to_file(metadata.url, target_file, session=session)
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            msg = f"failed-to-download ({status_code}): {metadata.url}"
            raise FileNotFoundError(msg) from exc
    return target_file


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
            meeting_folder = get_meeting_checkout_folder(meeting, checkout_dir)
            doclist_path = meeting_folder / f"meeting_{meeting.meeting_id}_doclist.xlsx"
            tdocs = fetch_meeting_document_list(meeting.meeting_id, http_cache_file, save_doclist_to=doclist_path)
        except DocumentListError as exc:
            errors.append(f"{meeting.short_name}: {exc}")
            continue
        for metadata in tdocs:
            if metadata.tdoc_id not in unique:
                unique[metadata.tdoc_id] = metadata

    return checkout_tdocs(list(unique.values()), checkout_dir, force=False, session=session, cache_manager_name=cache_manager_name)


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
                msg = "missing URL"
                raise ValueError(msg)
            checkout_tdoc(metadata, checkout_dir, force=force, session=session)
            success_count += 1
        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            error_message = str(exc)
            # For withdrawn TDocs, log debug instead of adding to errors
            if error_message == "withdrawn":  # This matches the FileNotFoundError message
                logger.debug(f"Skipped withdrawn TDoc {metadata.tdoc_id}")
            else:
                errors.append(f"{metadata.tdoc_id}: {exc}")
                error_count += 1

    return CheckoutResult(success_count=success_count, error_count=error_count, errors=errors)


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
    # Check if TDoc is withdrawn - if so, skip download and log debug message
    if metadata.status == TDocStatus.WITHDRAWN:
        logger.debug(f"Skipping checkout for withdrawn TDoc {metadata.tdoc_id}")
        msg = "withdrawn"
        raise FileNotFoundError(msg)

    checkout_path = get_checkout_path(metadata, checkout_dir)

    if checkout_path.exists() and not force:
        has_files = any(f.is_file() for f in checkout_path.rglob("*") if not f.name.startswith("."))
        if has_files:
            logger.debug(f"TDoc {metadata.tdoc_id} already checked out at {checkout_path}")
            return checkout_path
        logger.debug(f"TDoc {metadata.tdoc_id} checkout dir exists but is empty, re-downloading")

    checkout_path.mkdir(parents=True, exist_ok=True)
    temp_zip_file = checkout_path / f"{metadata.tdoc_id}.zip"

    if metadata.url is None:
        msg = f"TDoc {metadata.tdoc_id} has no URL"
        raise ValueError(msg)

    try:
        try:
            download_to_file(metadata.url, temp_zip_file, session=session)
        except requests.HTTPError:
            corrected_url = _resolve_corrected_url(metadata)
            if corrected_url and corrected_url != metadata.url:
                logger.info("Retrying %s with corrected URL: %s", metadata.tdoc_id, corrected_url)
                with requests.Session(disable_http3=True) as plain_session:
                    download_to_file(corrected_url, temp_zip_file, session=plain_session)
            else:
                raise
        try:
            with zipfile.ZipFile(temp_zip_file) as _zf:
                pass
        except zipfile.BadZipFile:
            corrected_url = _resolve_corrected_url(metadata)
            if corrected_url and corrected_url != metadata.url:
                logger.info("Retrying %s with corrected URL: %s", metadata.tdoc_id, corrected_url)
                with requests.Session(disable_http3=True) as plain_session:
                    download_to_file(corrected_url, temp_zip_file, session=plain_session)
            else:
                raise
        safe_extract_zip(temp_zip_file, checkout_path)
        logger.info("Checked out %s to %s", metadata.tdoc_id, checkout_path)
    finally:
        if temp_zip_file.exists():
            temp_zip_file.unlink()

    return checkout_path


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

    return checkout_dir.joinpath(*relative_parts) / metadata.tdoc_id if relative_parts else checkout_dir / metadata.tdoc_id


def _resolve_corrected_url(metadata: TDocMetadata, session: requests.Session | None = None) -> str | None:
    """Fetch directory listing and find the correct URL for the TDoc zip.

    Tries the direct parent directory first. If that fails (e.g. the
    directory does not exist due to path duplication like ``Docs/Docs/``),
    progressively tries ancestor directories until a match is found.

    Handles case-mismatched filenames and duplicated path segments.
    """
    if not metadata.url:
        return None

    expected_filename = posixpath.basename(metadata.url)
    expected_lower = expected_filename.lower()

    # Build candidate directory URLs: direct parent, then grandparents
    url_parts = metadata.url.rsplit("/", 1)
    directory_url = url_parts[0] + "/"
    candidate_dirs = [directory_url]

    # Walk up the path to handle duplicated segments (e.g. Docs/Docs/)
    parsed = urlparse(directory_url)
    path_segments = [s for s in parsed.path.split("/") if s]
    # Remove the last segment and try again (up to 3 levels)
    for i in range(1, min(4, len(path_segments))):
        shorter = "/" + "/".join(path_segments[:-i]) + "/"
        candidate = f"{parsed.scheme}://{parsed.netloc}{shorter}"
        candidate_dirs.append(candidate)

    with requests.Session(disable_http3=True) as plain_session:
        for dir_url in candidate_dirs:
            try:
                response = plain_session.get(dir_url, timeout=60)
                response.raise_for_status()
            except (requests.RequestException, OSError):
                logger.debug("Directory listing failed for %s", dir_url)
                continue

            soup = BeautifulSoup(response.content or b"", "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                if not isinstance(href, str):
                    continue
                full_url = urljoin(dir_url, href)
                actual_filename = posixpath.basename(full_url)
                if actual_filename.lower() == expected_lower:
                    return full_url

    return None


def get_meeting_checkout_folder(meeting: MeetingMetadata, checkout_dir: Path) -> Path:
    """Calculate the checkout folder for a meeting based on its files_url.

    The folder mirrors the 3GPP server directory structure.

    Args:
        meeting: MeetingMetadata containing the files_url
        checkout_dir: Base checkout directory

    Returns:
        Path to the meeting checkout folder
    """
    if meeting.files_url is None:
        msg = f"Meeting {meeting.short_name} has no files_url"
        raise ValueError(msg)

    url_path_str: str = str(urlparse(meeting.files_url).path)
    url_path_str = url_path_str.lstrip("/")
    path_parts: list[str] = url_path_str.split("/")

    try:
        ftp_index = path_parts.index("ftp")
        relative_parts: list[str] = path_parts[ftp_index + 1 :]
    except ValueError:
        relative_parts = path_parts

    return checkout_dir.joinpath(*relative_parts) if relative_parts else checkout_dir


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
    for docs_dir in checkout_base.rglob("Docs"):
        tdoc_path = docs_dir / tdoc_id
        if tdoc_path.exists() and tdoc_path.is_dir():
            return tdoc_path
    return None


__all__ = [
    "CheckoutResult",
    "checkout_meeting_tdocs",
    "checkout_tdoc",
    "checkout_tdocs",
    "clear_checkout_tdocs",
    "get_checked_out_tdocs",
    "get_checkout_path",
    "get_meeting_checkout_folder",
    "prepare_tdoc_file",
]
