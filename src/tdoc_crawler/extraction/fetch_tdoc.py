"""Fetch TDoc documents from 3GPP FTP or checkout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, get_checkout_path
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_tdoc_id


class TDocNotFoundError(Exception):
    """Raised when a TDoc cannot be found or checked out."""


@dataclass
class TDocFiles:
    """Paths to available TDoc file types."""

    checkout_dir: Path
    docx_path: Path | None = None
    doc_path: Path | None = None
    pdf_path: Path | None = None

    @property
    def primary_path(self) -> Path | None:
        """Return the primary document path, preferring PDF > DOCX > DOC."""
        return self.pdf_path or self.docx_path or self.doc_path


def fetch_tdoc_files(document_id: str, force_download: bool = False) -> TDocFiles:
    """Fetch TDoc files from checkout or download from 3GPP FTP.

    Pipeline:
    1. Check local database for metadata
    2. If not found, resolve TDoc ID to metadata via WhatTheSpec and save to DB
    3. Calculate checkout path
    4. If not in checkout, download via checkout_tdoc
    5. Find available file types in checkout directory

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force_download: Force re-download even if exists

    Returns:
        TDocFiles with paths to available documents

    Raises:
        TDocNotFoundError: If TDoc cannot be found or downloaded
    """
    normalized_id = normalize_tdoc_id(document_id)

    async def _resolve_metadata() -> TDocMetadata | None:
        manager = resolve_cache_manager()
        async with TDocDatabase(manager.db_file) as db:
            # 1. Check database
            record = await db._get_tdoc(normalized_id)
            if record:
                return record

            # 2. Resolve via WhatTheSpec
            metadata = resolve_via_whatthespec(normalized_id)
            if metadata:
                # 3. Put into database
                await db.upsert_tdoc(metadata)
                return metadata
        return None

    metadata = run_async(_resolve_metadata())
    if metadata is None:
        msg = f"TDoc {document_id} not found"
        raise TDocNotFoundError(msg)

    checkout_dir = PathConfig().checkout_dir
    checkout_path = get_checkout_path(metadata, checkout_dir)

    needs_download = force_download or not _checkout_has_files(checkout_path)
    if needs_download:
        with create_cached_session() as session:
            checkout_tdoc(metadata, checkout_dir, force=force_download, session=session)

    return _find_files_in_checkout(checkout_path)


def fetch_spec_files(checkout_path: Path) -> TDocFiles:
    """Find available spec files in a checkout directory.

    Args:
        checkout_path: Path to the checked out spec directory.

    Returns:
        TDocFiles with paths to available documents.
    """
    return _find_files_in_checkout(checkout_path)


def _checkout_has_files(checkout_path: Path) -> bool:
    """Check if a checkout directory exists and contains actual files."""
    if not checkout_path.is_dir():
        return False
    return any(f.is_file() for f in checkout_path.rglob("*") if not f.name.startswith("."))


def _find_files_in_checkout(checkout_path: Path) -> TDocFiles:
    """Find available file types in checkout directory."""
    files = TDocFiles(checkout_dir=checkout_path)

    if checkout_path.is_dir():
        # Prefer PDF > DOCX > DOC
        for file_path in sorted(checkout_path.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                suffix = file_path.suffix.lower()
                if suffix == ".pdf":
                    files.pdf_path = file_path
                elif suffix == ".docx":
                    files.docx_path = file_path
                elif suffix == ".doc":
                    files.doc_path = file_path

    return files


__all__ = ["TDocFiles", "fetch_spec_files", "fetch_tdoc_files"]
