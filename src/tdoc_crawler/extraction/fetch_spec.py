"""Fetch spec documents from checkout or 3GPP sources.

Analogous to fetch_tdoc.py but for specification documents.
Resolves spec files by number (e.g. "26.131") to their checked-out files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.normalization import normalize_spec_number

logger = get_logger(__name__)


@dataclass
class SpecFiles:
    """Paths to available spec file types."""

    checkout_dir: Path
    docx_path: Path | None = None
    doc_path: Path | None = None
    pdf_path: Path | None = None

    @property
    def primary_path(self) -> Path | None:
        """Return the primary document path, preferring PDF > DOCX > DOC."""
        return self.pdf_path or self.docx_path or self.doc_path


def fetch_spec_files(spec_number: str, force_download: bool = False) -> SpecFiles:
    """Fetch spec files from local checkout directory.

    Specs are checked out during the ``workspace add`` checkout phase.
    This function locates the checked-out files for a given spec number.

    Args:
        spec_number: Spec number (e.g., "26.131").
        force_download: Ignored for specs — files are looked up from checkout.

    Returns:
        SpecFiles with paths to available documents.

    Raises:
        FileNotFoundError: If spec directory or files cannot be found.
    """
    checkout_dir = PathConfig().checkout_dir
    normalized = normalize_spec_number(spec_number)
    series = f"{normalized.split('.', maxsplit=1)[0]}_series"

    # Spec checkout path: checkout_dir/Specs/archive/{series}/{spec_number}/
    spec_dir = checkout_dir / "Specs" / "archive" / series / normalized

    if not spec_dir.exists():
        raise FileNotFoundError(f"Spec {normalized} not found at {spec_dir}")

    return _scan_spec_dir(spec_dir)


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

    return files


__all__ = ["SpecFiles", "fetch_spec_files"]
