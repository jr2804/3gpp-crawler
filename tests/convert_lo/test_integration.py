"""Integration tests for convert-lo - actual LibreOffice conversion."""

from __future__ import annotations

from pathlib import Path

import pytest
from convert_lo.converter import Converter
from convert_lo.exceptions import SofficeNotFoundError
from convert_lo.formats import LibreOfficeFormat
from convert_lo.locator import find_soffice


def _is_libreoffice_available() -> bool:
    """Check if LibreOffice is available."""
    try:
        find_soffice()
        return True
    except SofficeNotFoundError:
        return False


requires_libreoffice = pytest.mark.skipif(
    not _is_libreoffice_available(),
    reason="LibreOffice not installed or not found",
)


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
def test_convert_docx_to_pdf(
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert modern .docx to PDF."""
    converter = Converter()

    result = converter.convert(
        example_docx_path,
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".pdf"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_docx_to_markdown(
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert modern .docx to Markdown."""
    converter = Converter()

    result = converter.convert(
        example_docx_path,
        LibreOfficeFormat.MD,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".md"
    # Markdown files should have some content
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
def test_convert_docx_to_odt(
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert modern .docx to ODT."""
    converter = Converter()

    result = converter.convert(
        example_docx_path,
        LibreOfficeFormat.ODT,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".odt"
    assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_batch_to_pdf(
    example_doc_path: Path,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert multiple files to PDF in batch."""
    converter = Converter()

    results = converter.convert_batch(
        [example_doc_path, example_docx_path],
        LibreOfficeFormat.PDF,
        output_dir,
    )

    assert len(results) == 2
    for result in results:
        assert result.output_path.exists()
        assert result.output_path.suffix.lower() == ".pdf"
        assert result.output_path.stat().st_size > 0


@requires_libreoffice
def test_convert_docx_to_html(
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert modern .docx to HTML."""
    converter = Converter()

    result = converter.convert(
        example_docx_path,
        LibreOfficeFormat.HTML,
        output_dir,
    )

    assert result.output_path.exists()
    assert result.output_path.suffix.lower() == ".html"
    content = result.output_path.read_text(encoding="utf-8")
    assert len(content) > 0
    # HTML should contain basic HTML tags
    assert "<html" in content.lower() or "<body" in content.lower()
