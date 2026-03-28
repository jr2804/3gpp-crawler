"""Workspace utility functions."""

from __future__ import annotations

from pathlib import Path


def check_pdf_status(source_path: str) -> str:
    """Check if PDF is available for a document.

    Checks whether the original file is a PDF, or if a PDF was created
    in the .ai conversion folder. Returns 'yes', 'no', or 'error'.

    Args:
        source_path: Absolute path to the source document.

    Returns:
        'yes' if PDF available, 'no' if not yet converted, 'error' if conversion failed.
    """
    try:
        doc_path = Path(source_path)

        if doc_path.suffix.lower() == ".pdf":
            return "yes"

        ai_folder = doc_path.parent / ".ai" / doc_path.stem
        pdf_file = ai_folder / f"{doc_path.stem}.pdf"
        if pdf_file.exists():
            return "yes"

        error_marker = ai_folder / ".conversion_failed"
        if error_marker.exists():
            return "error"

        return "no"
    except OSError, ValueError:
        return "error"
