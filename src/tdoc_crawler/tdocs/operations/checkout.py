"""TDoc checkout operations for downloading and extracting documents.

This module provides functionality to download TDocs from the 3GPP server
and extract them to a local checkout folder while maintaining the same
directory structure as the server.
"""

from __future__ import annotations

import posixpath
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import niquests as requests
from bs4 import BeautifulSoup

from tdoc_crawler.config.settings import CheckoutConfig, ExtractConfig
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.http_client import download_to_file
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.archives import ArchiveKind, ArchiveRecord
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSource
from tdoc_crawler.tdocs.models import TDocStatus
from tdoc_crawler.tdocs.operations.main_file import (
    resolve_main_file,
    select_heuristic_main_file,
)
from tdoc_crawler.tdocs.sources.doclist import DocumentListError, fetch_meeting_document_list
from tdoc_crawler.utils.archive import list_zip_members
from tdoc_crawler.utils.security import safe_extract_zip

logger = get_logger(__name__)


@dataclass
class CheckoutResult:
    """Result of a checkout operation."""

    success_count: int
    error_count: int
    errors: list[str]
    archives: list[ArchiveRecord] = field(default_factory=list)
    skipped_count: int = 0


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


def prepare_tdoc_file(
    metadata: TDocMetadata,
    checkout_dir: Path,
    return_dir: bool = False,
    session: requests.Session | None = None,
    *,
    override_member: str | None = None,
    config: CheckoutConfig | None = None,
    extract: ExtractConfig | None = None,
) -> Path:
    """Prepare the local file for a TDoc, downloading/extracting if needed.

    Routes through :func:`checkout_tdoc` so that ``tdoc open`` and
    ``tdoc checkout`` share a single business-logic path: the on-disk
    layout mirrors the 3GPP server (under
    ``tsg_<tsg>/<wg>/<meeting>/Docs/<tdoc_id>``); archive clutter is
    filtered by the user-editable ``clutter-ignore`` patterns.

    Main-file choice is delegated to
    :func:`tdoc_crawler.tdocs.operations.main_file.resolve_main_file`:
    manual override first, then the optional decision model, then the
    offline heuristic. Call :func:`prepare_tdoc_selection` instead when
    the source of the choice matters to the caller.

    Args:
        metadata: TDoc metadata with download URL.
        checkout_dir: Checkout directory (base of the mirror tree).
        return_dir: When True, return the extract directory itself instead
            of the picked "main file" inside it.
        session: Optional requests.Session to reuse for downloads.
        override_member: Stored manual override (archive-relative path).
        config: Checkout settings; defaults to ``CheckoutConfig()``.
        extract: Extraction settings; defaults to ``ExtractConfig()``.

    Returns:
        Path to the picked main file, or the extract directory when
        ``return_dir`` is True. For non-zip URLs, returns the downloaded
        file path.

    Raises:
        FileNotFoundError: If the TDoc is withdrawn, the download fails,
            or the archive contains no usable file.
        ValueError: If ``metadata.url`` is missing.
    """
    if return_dir:
        filename, extract_dir = _resolve_archive(metadata, checkout_dir, session=session, extract=extract)
        if extract_dir is not None:
            return extract_dir
        return _download_loose_tdoc(metadata, checkout_dir, filename, session=session)

    return prepare_tdoc_selection(
        metadata,
        checkout_dir,
        override_member=override_member,
        config=config,
        session=session,
        extract=extract,
    ).path


def prepare_tdoc_selection(
    metadata: TDocMetadata,
    checkout_dir: Path,
    *,
    override_member: str | None = None,
    config: CheckoutConfig | None = None,
    session: requests.Session | None = None,
    extract: ExtractConfig | None = None,
) -> MainFileSelection:
    """Prepare a TDoc and report *which* file was chosen as its main file.

    Same download/extract path as :func:`prepare_tdoc_file`; use this
    variant when the caller must show or log the selection source
    (manual override, decision model, or heuristic).

    Args:
        metadata: TDoc metadata with download URL.
        checkout_dir: Checkout directory (base of the mirror tree).
        override_member: Stored manual override (archive-relative path).
        config: Checkout settings; defaults to ``CheckoutConfig()``.
        session: Optional requests.Session to reuse for downloads.
        extract: Extraction settings; defaults to ``ExtractConfig()``.

    Returns:
        The resolved main file plus its source.

    Raises:
        FileNotFoundError: If the TDoc is withdrawn, the download fails,
            or the archive contains no usable (or no overridden) file.
        ValueError: If ``metadata.url`` is missing.
    """
    filename, extract_dir = _resolve_archive(metadata, checkout_dir, session=session, extract=extract)
    if extract_dir is None:
        # A loose (non-zip) TDoc *is* its own main file; the heuristic
        # source is reported because no choice was made.
        downloaded = _download_loose_tdoc(metadata, checkout_dir, filename, session=session)
        return MainFileSelection(
            path=downloaded,
            relative_path=downloaded.name,
            source=MainFileSource.HEURISTIC,
        )

    return resolve_main_file(
        extract_dir,
        metadata.tdoc_id,
        title=metadata.title,
        override_member=override_member,
        config=config,
        session=session,
    )


def _resolve_archive(
    metadata: TDocMetadata,
    checkout_dir: Path,
    *,
    session: requests.Session | None,
    extract: ExtractConfig | None = None,
) -> tuple[str, Path | None]:
    """Validate the TDoc and resolve its local container.

    Returns:
        ``(filename, extract_dir)``; ``extract_dir`` is None for non-zip
        TDocs, which are downloaded as-is by :func:`_download_loose_tdoc`.

    Raises:
        ValueError: If ``metadata.url`` is missing.
        FileNotFoundError: If the TDoc is withdrawn.
    """
    if not metadata.url or not metadata.url.strip():
        msg = f"Cannot prepare TDoc file for {metadata.tdoc_id}: no download URL"
        raise ValueError(msg)

    if metadata.status == TDocStatus.WITHDRAWN:
        logger.debug(f"Skipping download for withdrawn TDoc {metadata.tdoc_id}")
        msg = "withdrawn"
        raise FileNotFoundError(msg)

    filename = str(posixpath.basename(urlparse(metadata.url).path))
    if Path(filename).suffix.lower() != ".zip":
        return filename, None
    return filename, checkout_tdoc(metadata, checkout_dir, session=session, extract=extract)


def _download_loose_tdoc(metadata: TDocMetadata, checkout_dir: Path, filename: str, *, session: requests.Session | None) -> Path:
    """Download a non-zip TDoc under the mirror path and return its path."""
    if not metadata.url or not metadata.url.strip():
        msg = f"Cannot prepare TDoc file for {metadata.tdoc_id}: no download URL"
        raise ValueError(msg)
    target_dir = get_checkout_path(metadata, checkout_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    target_name = filename or f"{metadata.tdoc_id}{suffix or '.bin'}"
    target_file = target_dir / target_name
    if not target_file.exists():
        try:
            download_to_file(metadata.url, target_file, session=session)
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            msg = f"failed-to-download ({status_code}): {metadata.url}"
            raise FileNotFoundError(msg) from exc
    return target_file


def _select_main_file(extract_dir: Path, tdoc_id: str, *, title: str | None = None) -> Path:
    """Heuristic main-file picker (backwards-compatible alias).

    The implementation and its full documentation live in
    :func:`tdoc_crawler.tdocs.operations.main_file.select_heuristic_main_file`.
    Kept here because checkout tests and older callers import it from
    this module; new code should call :func:`resolve_main_file` so the
    manual override and decision-model layers apply.
    """
    return select_heuristic_main_file(extract_dir, tdoc_id, title=title)


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


def clear_checkout_tdocs(checkout_dir: Path, *, keep_specs: bool = True) -> int:
    """Delete downloaded TDoc files from the checkout directory.

    Destructive by design and never called automatically: only the explicit
    ``--purge-checkouts`` switch on ``database clear-*`` reaches this helper.

    Args:
        checkout_dir: Base checkout directory
        keep_specs: Preserve the ``Specs`` subtree (TDoc-only clears)

    Returns:
        Number of top-level entries removed
    """
    if not checkout_dir.exists():
        return 0
    removed = 0
    for entry in checkout_dir.iterdir():
        if keep_specs and entry.name == "Specs":
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
    extract: ExtractConfig | None = None,
) -> CheckoutResult:
    """Checkout TDoc files from a list of meetings.

    Args:
        meetings: List of MeetingMetadata to checkout TDocs from
        checkout_dir: Base checkout directory
        http_cache_file: Path to HTTP cache database
        session: Optional requests.Session to reuse for downloads
        cache_manager_name: Optional cache manager name for HTTP caching
        extract: Extraction settings; defaults to ``ExtractConfig()``

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
            tdocs = fetch_meeting_document_list(
                meeting.meeting_id,
                http_cache_file=http_cache_file,
                save_doclist_to=doclist_path,
            )
        except DocumentListError as exc:
            errors.append(f"{meeting.short_name}: {exc}")
            continue
        for metadata in tdocs:
            if metadata.tdoc_id not in unique:
                unique[metadata.tdoc_id] = metadata

    return checkout_tdocs(
        list(unique.values()),
        checkout_dir,
        force=False,
        session=session,
        cache_manager_name=cache_manager_name,
        extract=extract,
    )


def checkout_tdocs(
    results: list[TDocMetadata],
    checkout_dir: Path,
    force: bool = False,
    session: requests.Session | None = None,
    cache_manager_name: str | None = None,
    keep_zip: bool = False,
    extract: ExtractConfig | None = None,
) -> CheckoutResult:
    """Checkout multiple TDoc files to the checkout directory.

    Args:
        results: List of TDocMetadata to checkout
        checkout_dir: Base checkout directory
        force: If True, re-download even if already exists
        session: Optional requests.Session to reuse for downloads
        cache_manager_name: Optional cache manager name for HTTP caching
        keep_zip: If True, keep each downloaded zip next to its extracted files
        extract: Extraction settings; defaults to ``ExtractConfig()``

    Returns:
        CheckoutResult with success/error counts and the archive listings
        recorded during this run (persist them with ``save_archive_records``)
    """
    if not results:
        return CheckoutResult(success_count=0, error_count=0, errors=[])

    success_count = 0
    error_count = 0
    skipped_count = 0
    errors: list[str] = []
    archives: list[ArchiveRecord] = []

    for metadata in results:
        try:
            if not metadata.url:
                msg = "missing URL"
                raise ValueError(msg)
            checkout_tdoc(metadata, checkout_dir, force=force, session=session, keep_zip=keep_zip, archive_sink=archives, extract=extract)
            success_count += 1
        except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as exc:
            error_message = str(exc)
            # Withdrawn TDocs are skipped, not failures: nothing to download.
            if error_message == "withdrawn":  # This matches the FileNotFoundError message
                logger.debug(f"Skipped withdrawn TDoc {metadata.tdoc_id}")
                skipped_count += 1
            else:
                errors.append(f"{metadata.tdoc_id}: {exc}")
                error_count += 1

    return CheckoutResult(success_count=success_count, error_count=error_count, errors=errors, archives=archives, skipped_count=skipped_count)


def checkout_tdoc(
    metadata: TDocMetadata,
    checkout_dir: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
    keep_zip: bool = False,
    archive_sink: list[ArchiveRecord] | None = None,
    extract: ExtractConfig | None = None,
) -> Path:
    """Download and extract a TDoc to the checkout folder.

    Args:
        metadata: TDoc metadata containing URL and ID
        checkout_dir: Base checkout directory
        force: If True, re-download even if already exists
        session: Optional requests.Session to reuse for downloads
        keep_zip: If True, keep the downloaded zip in the checkout folder
        archive_sink: If given, the zip member listing is appended to it when
            a download happens (an already checked-out TDoc records nothing)
        extract: Extraction settings (flattening, skip patterns); defaults to
            ``ExtractConfig()``

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

    # Validate the URL *before* touching the filesystem: WhatTheSpec records
    # for TDocs without a downloadable document carry an empty link, and
    # creating the directory first used to leave empty ``<checkout>/<id>``
    # folders behind (the path mirrors the URL, so an empty URL maps to the
    # root of the checkout tree).
    if not metadata.url or not metadata.url.strip():
        msg = f"TDoc {metadata.tdoc_id} has no download URL (the metadata source provided no file link)"
        raise ValueError(msg)

    checkout_path = get_checkout_path(metadata, checkout_dir)

    if checkout_path.exists() and not force:
        has_files = any(f.is_file() for f in checkout_path.rglob("*") if not f.name.startswith("."))
        if has_files:
            logger.debug(f"TDoc {metadata.tdoc_id} already checked out at {checkout_path}")
            return checkout_path
        logger.debug(f"TDoc {metadata.tdoc_id} checkout dir exists but is empty, re-downloading")

    checkout_path.mkdir(parents=True, exist_ok=True)
    temp_zip_file = checkout_path / f"{metadata.tdoc_id}.zip"

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
            archive_members = list_zip_members(temp_zip_file)
        except zipfile.BadZipFile:
            corrected_url = _resolve_corrected_url(metadata)
            if corrected_url and corrected_url != metadata.url:
                logger.info("Retrying %s with corrected URL: %s", metadata.tdoc_id, corrected_url)
                with requests.Session(disable_http3=True) as plain_session:
                    download_to_file(corrected_url, temp_zip_file, session=plain_session)
                archive_members = list_zip_members(temp_zip_file)
            else:
                raise
        extraction = extract or ExtractConfig()
        safe_extract_zip(
            temp_zip_file,
            checkout_path,
            exclude=extraction.exclude,
            flatten_single_root=extraction.flatten_single_root,
        )
        if archive_sink is not None:
            archive_sink.append(ArchiveRecord(kind=ArchiveKind.TDOC, item_id=metadata.tdoc_id, archive_name=temp_zip_file.name, members=archive_members))
        logger.info("Checked out %s to %s", metadata.tdoc_id, checkout_path)
    finally:
        if not keep_zip and temp_zip_file.exists():
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
