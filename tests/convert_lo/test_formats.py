"""Tests for LibreOffice format definitions."""

from __future__ import annotations

import pytest
from convert_lo.formats import UNSUPPORTED_CONVERSIONS, LibreOfficeFormat


def test_libreoffice_format_values() -> None:
    """Ensure LibreOfficeFormat values match expected strings."""
    assert LibreOfficeFormat.ODT.value == "odt"
    assert LibreOfficeFormat.DOC.value == "doc"
    assert LibreOfficeFormat.DOCX.value == "docx"
    assert LibreOfficeFormat.PDF.value == "pdf"


def test_unsupported_conversions_contains_expected_pairs() -> None:
    """Validate known unsupported conversions."""
    assert ("pdf", "doc") in UNSUPPORTED_CONVERSIONS
    assert ("pdf", "docx") in UNSUPPORTED_CONVERSIONS
    assert ("pdf", "odt") in UNSUPPORTED_CONVERSIONS


@pytest.mark.parametrize("format_value", list(LibreOfficeFormat))
def test_all_formats_are_strenum(format_value: LibreOfficeFormat) -> None:
    """Ensure all format entries are StrEnum instances with string values."""
    assert isinstance(format_value.value, str)
