"""Fetch TDoc documents from 3GPP FTP or checkout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models.workspaces import TDocNotFoundError
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, get_checkout_path
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec


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
    1. Resolve TDoc ID to metadata via WhatTheSpec
    2. Calculate checkout path
    3. If not in checkout, download via checkout_tdoc
    4. Find available file types in checkout directory

    Args:
        document_id: TDoc identifier (e.g., "S4-260001")
        force_download: Force re-download even if exists

    Returns:
        TDocFiles with paths to available documents

    Raises:
        TDocNotFoundError: If TDoc cannot be found or downloaded
    """
    metadata = resolve_via_whatthespec(document_id)
    if metadata is None:
        raise TDocNotFoundError(f"TDoc {document_id} not found via WhatTheSpec")

    checkout_dir = PathConfig().checkout_dir
    checkout_path = get_checkout_path(metadata, checkout_dir)

    if not checkout_path.exists() or force_download:
        with create_cached_session() as session:
            checkout_tdoc(metadata, checkout_dir, force=force_download, session=session)

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

    return files


__all__ = ["TDocFiles", "fetch_tdoc_files"]
