"""Workspace utility functions."""

from __future__ import annotations

from pathlib import Path


def check_pdf_status(source_path: str, output_dir: str | None = None) -> str:
    """Check if PDF is available for a document.

    Checks whether the original file is a PDF, or if a converted PDF exists
    in the output directory. Returns 'yes', 'no', or 'error'.

    Args:
        source_path: Absolute path to the source document.
        output_dir: Directory where converted artifacts are stored (workspace sources dir).
            If None, only checks if the source itself is a PDF.

    Returns:
        'yes' if PDF available, 'no' if not yet converted, 'error' if conversion failed.
    """
    try:
        doc_path = Path(source_path)

        if doc_path.suffix.lower() == ".pdf":
            return "yes"

        if output_dir:
            out = Path(output_dir)
            pdf_file = out / f"{doc_path.stem}.pdf"
            if pdf_file.exists():
                return "yes"

            error_marker = out / ".conversion_failed"
            if error_marker.exists():
                return "error"

        return "no"
    except OSError, ValueError:
        return "error"


__all__ = ["check_pdf_status"]
