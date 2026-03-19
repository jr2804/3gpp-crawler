"""Integration tests for convert-lo - actual LibreOffice conversion."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from convert_lo.converter import Converter
from convert_lo.exceptions import SofficeNotFoundError
from convert_lo.formats import LibreOfficeFormat
from convert_lo.locator import find_soffice


def _is_libreoffice_available() -> bool:
    """Check if LibreOffice is available and can actually convert.

    This goes beyond just finding the executable - it verifies that
    LibreOffice can perform a basic conversion.
    """
    try:
        soffice_path = find_soffice()
    except SofficeNotFoundError:
        return False

    # Try a quick test to see if LibreOffice can run
    # This catches cases where soffice exists but can't run properly
    try:
        result = subprocess.run(
            [str(soffice_path), "--headless", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # If --help works, LibreOffice is functional
        return result.returncode == 0 or "LibreOffice" in result.stdout
    except subprocess.TimeoutExpired, FileNotFoundError, OSError:
        return False


requires_libreoffice = pytest.mark.skipif(
    not _is_libreoffice_available(),
    reason="LibreOffice not installed or not functional",
)


# Fast tests with small files
@requires_libreoffice
def test_convert_small_docx_to_pdf(
    example_small_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert small .docx to PDF (fast test)."""
    converter = Converter()

    result = converter.convert(
        example_small_docx_path,
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".pdf"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_small_docx_to_markdown(
    example_small_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert small .docx to Markdown (fast test)."""
    converter = Converter()

    result = converter.convert(
        example_small_docx_path,
        LibreOfficeFormat.MD,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".md"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0


@requires_libreoffice
def test_convert_small_docx_to_html(
    example_small_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert small .docx to HTML (fast test)."""
    converter = Converter()

    result = converter.convert(
        example_small_docx_path,
        LibreOfficeFormat.HTML,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".html"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0
    # HTML should contain basic HTML tags
    assert "<html" in content.lower() or "<body" in content.lower()


@requires_libreoffice
def test_convert_small_docx_to_odt(
    example_small_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert small .docx to ODT (fast test)."""
    converter = Converter()

    result = converter.convert(
        example_small_docx_path,
        LibreOfficeFormat.ODT,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".odt"
    assert result.output_path.stat().st_size > 0


# Tests with medium files (may take longer on some systems)
@requires_libreoffice
def test_convert_doc_to_pdf(
    example_doc_path: Path,
    output_dir: Path,
) -> None:
    """Convert legacy .doc to PDF."""
    converter = Converter()

    result = converter.convert(
        example_doc_path,
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".pdf"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_medium_docx_to_pdf(
    example_medium_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert medium .docx to PDF."""
    converter = Converter()

    result = converter.convert(
        example_medium_docx_path,
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".pdf"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_medium_docx_to_markdown(
    example_medium_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert medium .docx to Markdown."""
    converter = Converter()

    result = converter.convert(
        example_medium_docx_path,
        LibreOfficeFormat.MD,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".md"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0


@requires_libreoffice
def test_convert_doc_to_markdown(
    example_doc_path: Path,
    output_dir: Path,
) -> None:
    """Convert legacy .doc to Markdown."""
    converter = Converter()

    result = converter.convert(
        example_doc_path,
        LibreOfficeFormat.MD,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".md"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0


@requires_libreoffice
def test_convert_doc_to_odt(
    example_doc_path: Path,
    output_dir: Path,
) -> None:
    """Convert legacy .doc to ODT."""
    converter = Converter()

    result = converter.convert(
        example_doc_path,
        LibreOfficeFormat.ODT,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".odt"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_medium_docx_to_odt(
    example_medium_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert medium .docx to ODT."""
    converter = Converter()

    result = converter.convert(
        example_medium_docx_path,
        LibreOfficeFormat.ODT,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".odt"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_batch_to_pdf(
    example_doc_path: Path,
    example_medium_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert multiple files to PDF in batch."""
    converter = Converter()

    results = converter.convert_batch(
        [example_doc_path, example_medium_docx_path],
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert len(results) == 2
    for result in results:
        assert result.output_path.exists()
        assert result.output_path.suffix.lower() == ".pdf"
        assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_medium_docx_to_html(
    example_medium_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert medium .docx to HTML."""
    converter = Converter()

    result = converter.convert(
        example_medium_docx_path,
        LibreOfficeFormat.HTML,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".html"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0
    # HTML should contain basic HTML tags
    assert "<html" in content.lower() or "<body" in content.lower()
