"""Fetch spec documents from checkout or 3GPP sources.

Analogous to fetch_tdoc.py but for specification documents.
Resolves spec files by number (e.g. "26.131") to their checked-out files.
If files are not present locally and a release is provided, downloads from 3GPP FTP.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.extraction.conversion import OFFICE_FORMATS
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.utils.normalization import normalize_spec_number

logger = get_logger(__name__)


@dataclass
class SpecFiles:
    """Paths to available spec file types."""

    checkout_dir: Path
    docx_path: Path | None = None
    doc_path: Path | None = None
    office_path: Path | None = None
    pdf_path: Path | None = None

    @property
    def primary_path(self) -> Path | None:
        """Return the primary document path, preferring PDF > DOCX > DOC > other office formats."""
        return self.pdf_path or self.docx_path or self.doc_path or self.office_path


def fetch_spec_files(spec_number: str, release: str | None = None, force_download: bool = False) -> SpecFiles:
    """Fetch spec files from local checkout directory, downloading if needed.

    Pipeline:
    1. Check if spec already exists in local checkout (filesystem scan)
    2. If found, return immediately — no network call needed
    3. Otherwise download from 3GPP FTP via SpecDownloads if a release is provided

    Args:
        spec_number: Spec number (e.g., "26.131").
        release: Release identifier (e.g., "19.0.0", "latest"). When ``None``
            and files are not found locally, no download is attempted.
        force_download: Force re-download even if exists locally.

    Returns:
        SpecFiles with paths to available documents.

    Raises:
        FileNotFoundError: If spec directory or files cannot be found and no
            download is possible.
    """
    checkout_dir = PathConfig().checkout_dir
    normalized = normalize_spec_number(spec_number)
    series = f"{normalized.split('.', maxsplit=1)[0]}_series"

    # Spec checkout path: checkout_dir/Specs/archive/{series}/{spec_number}/
    spec_dir = checkout_dir / "Specs" / "archive" / series / normalized

    # For "latest"/"all"/None, local-first scan is safe: any file matches.
    # For a concrete release (e.g. "18.0.0"), we must NOT return files from
    # a different release that happens to live in the same base directory.
    is_generic_release = release is None or release.strip().lower() in ("latest", "all")

    # Step 1: Check local checkout (only for generic release selectors)
    if is_generic_release and spec_dir.exists() and not force_download:
        files = _scan_spec_dir(spec_dir)
        if files.primary_path is not None:
            return files

    # Step 2: Download from 3GPP FTP
    if release is not None or force_download:
        effective_release = release or "latest"
        extracted_dir = _download_spec(normalized, effective_release, checkout_dir)

        if extracted_dir is not None and extracted_dir.exists():
            # Scan ONLY the version-specific extracted directory
            files = _scan_spec_dir(extracted_dir)
            if files.primary_path is not None:
                return SpecFiles(
                    checkout_dir=spec_dir,
                    docx_path=files.docx_path,
                    doc_path=files.doc_path,
                    office_path=files.office_path,
                    pdf_path=files.pdf_path,
                )

        # Fallback: scan the entire spec directory (covers legacy layouts)
        if spec_dir.exists():
            files = _scan_spec_dir(spec_dir)
            if files.primary_path is not None:
                return files

    raise FileNotFoundError(f"Spec {normalized} not found at {spec_dir}")


def _download_spec(spec_number: str, release: str, checkout_dir: Path) -> Path | None:
    """Download a spec, returning the version-specific extracted directory.

    Returns:
        Path to the extracted directory (e.g. ``.../26261-g00/``) or ``None``
        on failure.
    """
    db_file = PathConfig().db_file

    async def _do_download() -> list[Path]:
        async with SpecDatabase(db_file) as db:
            downloader = SpecDownloads(db)
            return await downloader.checkout_specs_async(
                specs=[spec_number],
                doc_only=False,
                checkout_dir=checkout_dir,
                release=release,
            )

    try:
        results = asyncio.run(_do_download())
        return results[0] if results else None
    except Exception as exc:
        logger.warning("Failed to download spec %s (release=%s): %s", spec_number, release, exc)
        return None


def _scan_spec_dir(spec_dir: Path) -> SpecFiles:
    """Scan a spec checkout directory for available document files.

    Searches the directory tree for document files, excluding hidden files.
    """
    files = SpecFiles(checkout_dir=spec_dir)

    if spec_dir.is_dir():
        for file_path in sorted(spec_dir.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                suffix = file_path.suffix.lower()
                if suffix == ".pdf":
                    files.pdf_path = file_path
                elif suffix == ".docx":
                    files.docx_path = file_path
                elif suffix == ".doc":
                    files.doc_path = file_path
                elif suffix in OFFICE_FORMATS:
                    files.office_path = file_path

    return files


__all__ = ["SpecFiles", "fetch_spec_files"]
