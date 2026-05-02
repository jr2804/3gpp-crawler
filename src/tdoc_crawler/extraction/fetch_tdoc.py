"""Fetch TDoc documents from 3GPP FTP or checkout."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.extraction.conversion import OFFICE_FORMATS
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.workspaces import TDocNotFoundError
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, get_checkout_path
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.workspaces.utils import resolve_tdoc_checkout_path

logger = get_logger(__name__)


@dataclass
class TDocFiles:
    """Paths to available TDoc file types."""

    checkout_dir: Path
    docx_path: Path | None = None
    doc_path: Path | None = None
    office_path: Path | None = None
    pdf_path: Path | None = None

    @property
    def primary_path(self) -> Path | None:
        """Return the primary document path, preferring PDF > DOCX > DOC > other office formats."""
        return self.pdf_path or self.docx_path or self.doc_path or self.office_path


def fetch_tdoc_files(document_id: str, force_download: bool = False) -> TDocFiles:
    """Fetch TDoc files from checkout or download from 3GPP FTP.

    Pipeline:
    1. Check if TDoc already exists in local checkout (filesystem scan)
    2. Look up TDoc in local database (populated by crawl command)
    3. Resolve via WhatTheSpec API and download if needed

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force_download: Force re-download even if exists

    Returns:
        TDocFiles with paths to available documents

    Raises:
        TDocNotFoundError: If TDoc cannot be found or downloaded
    """
    checkout_dir = PathConfig().checkout_dir
    normalized_id = document_id.upper()

    # Step 1: Check local checkout first (covers previously crawled TDocs)
    if not force_download:
        existing_path = resolve_tdoc_checkout_path(normalized_id, checkout_dir)
        if existing_path is not None:
            files = _scan_checkout_dir(existing_path)
            if files.primary_path is not None:
                return files

    # Step 2: Look up in local database (populated by crawl command)
    metadata = asyncio.run(_lookup_tdoc_in_db(normalized_id))

    # Step 3: Fall back to WhatTheSpec API if database has no record
    if metadata is None:
        metadata = resolve_via_whatthespec(document_id)

    if metadata is None:
        raise TDocNotFoundError(f"TDoc {document_id} not found in local database or WhatTheSpec")

    checkout_path = get_checkout_path(metadata, checkout_dir)

    if not checkout_path.exists() or force_download:
        with create_cached_session() as session:
            checkout_tdoc(metadata, checkout_dir, force=force_download, session=session)

    return _scan_checkout_dir(checkout_path)


async def _lookup_tdoc_in_db(tdoc_id: str) -> TDocMetadata | None:
    """Look up TDoc metadata in the local database.

    The database is populated by the crawl command and contains TDoc metadata
    including the FTP download URL, which is sufficient for checkout.

    Args:
        tdoc_id: Normalized TDoc identifier (uppercase)

    Returns:
        TDocMetadata if found with a valid URL, None otherwise
    """
    db_file = PathConfig().db_file
    async with TDocDatabase(db_file) as db:
        record = await db._get_tdoc(tdoc_id)
    if record is None or not record.url:
        return None
    return TDocMetadata(
        tdoc_id=record.tdoc_id,
        meeting_id=record.meeting_id,
        title=record.title,
        url=record.url,
        source=record.source,
        contact=record.contact,
        tdoc_type=record.tdoc_type,
        for_purpose=record.for_purpose,
        agenda_item_nbr=record.agenda_item_nbr,
        agenda_item_text=record.agenda_item_text,
        status=record.status,
        is_revision_of=record.is_revision_of,
        file_size=record.file_size,
        date_created=record.date_created,
        validated=record.validated,
        validation_failed=record.validation_failed,
    )


def _scan_checkout_dir(checkout_path: Path) -> TDocFiles:
    """Scan a checkout directory for available document files."""
    files = TDocFiles(checkout_dir=checkout_path)

    if checkout_path.is_dir():
        for file_path in sorted(checkout_path.rglob("*")):
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


__all__ = ["TDocFiles", "fetch_tdoc_files"]
