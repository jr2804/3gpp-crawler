"""Tests for LibreOffice converter wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from convert_lo.converter import Converter
from convert_lo.exceptions import ConversionError, UnsupportedConversionError
from convert_lo.formats import LibreOfficeFormat


def test_converter_init_with_custom_path() -> None:
    """Use provided soffice path without discovery."""
    soffice_path = Path("C:/custom/soffice.exe")

    converter = Converter(soffice_path=soffice_path)

    assert converter._soffice_path == soffice_path


def test_converter_init_with_auto_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve soffice path via find_soffice when not provided."""
    expected_path = Path("C:/Program Files/LibreOffice/program/soffice.exe")
    monkeypatch.setattr("convert_lo.converter.find_soffice", lambda: expected_path)

    converter = Converter()

    assert converter._soffice_path == expected_path


def test_convert_accepts_string_format(
    monkeypatch: pytest.MonkeyPatch,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Accept string format values and convert to enum."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("convert_lo.converter.subprocess.run", return_value=mock_result):
        converter = Converter(soffice_path=Path("C:/soffice.exe"))

        # String "pdf" should be accepted and converted to LibreOfficeFormat.PDF
        result = converter.convert(example_docx_path, "pdf", output_dir)

        assert result.output_format is LibreOfficeFormat.PDF


def test_convert_rejects_invalid_format(
    monkeypatch: pytest.MonkeyPatch,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Reject invalid format values."""
    converter = Converter(soffice_path=Path("C:/soffice.exe"))

    with pytest.raises(UnsupportedConversionError):
        converter.convert(example_docx_path, "invalid_format", output_dir)


def test_convert_raises_on_unsupported_conversion(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> None:
    """Raise when conversion pair is unsupported."""
    converter = Converter(soffice_path=Path("C:/soffice.exe"))

    input_file = output_dir / "input.pdf"
    input_file.write_text("dummy", encoding="utf-8")

    with pytest.raises(UnsupportedConversionError):
        converter.convert(input_file, LibreOfficeFormat.DOCX, output_dir)


def test_convert_batch_multiple_files(
    monkeypatch: pytest.MonkeyPatch,
    example_doc_path: Path,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Convert multiple files with mocked subprocess."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("convert_lo.converter.subprocess.run", return_value=mock_result):
        converter = Converter(soffice_path=Path("C:/soffice.exe"))

        results = converter.convert_batch(
            [example_doc_path, example_docx_path],
            LibreOfficeFormat.PDF,
            output_dir,
        )

    assert len(results) == 2
    assert results[0].output_format is LibreOfficeFormat.PDF
    assert results[1].output_format is LibreOfficeFormat.PDF


def test_convert_batch_empty_list(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> None:
    """Return empty results for empty input list."""
    converter = Converter(soffice_path=Path("C:/soffice.exe"))

    results = converter.convert_batch([], LibreOfficeFormat.PDF, output_dir)

    assert results == []


def test_convert_raises_on_missing_input(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> None:
    """Raise ConversionError when input file does not exist."""
    converter = Converter(soffice_path=Path("C:/soffice.exe"))
    missing_path = output_dir / "missing.docx"

    with pytest.raises(ConversionError):
        converter.convert(missing_path, LibreOfficeFormat.PDF, output_dir)


def test_convert_raises_on_subprocess_failure(
    monkeypatch: pytest.MonkeyPatch,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Raise ConversionError when subprocess fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Conversion failed"

    with patch("convert_lo.converter.subprocess.run", return_value=mock_result):
        converter = Converter(soffice_path=Path("C:/soffice.exe"))

        with pytest.raises(ConversionError):
            converter.convert(example_docx_path, LibreOfficeFormat.PDF, output_dir)


def test_convert_uses_correct_command(
    monkeypatch: pytest.MonkeyPatch,
    example_docx_path: Path,
    output_dir: Path,
) -> None:
    """Verify subprocess.run is called with correct arguments."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    soffice_path = Path("C:/soffice.exe")

    with patch("convert_lo.converter.subprocess.run", return_value=mock_result) as mock_run:
        converter = Converter(soffice_path=soffice_path)
        converter.convert(example_docx_path, LibreOfficeFormat.PDF, output_dir)

        # Verify the command was constructed correctly
        call_args = mock_run.call_args
        cmd = call_args[0][0]  # First positional argument is the command list

        assert str(soffice_path) in cmd
        assert "--headless" in cmd
        assert "--convert-to" in cmd
        assert "pdf" in cmd
        assert "--outdir" in cmd
        assert str(output_dir) in cmd
        assert str(example_docx_path) in cmd
