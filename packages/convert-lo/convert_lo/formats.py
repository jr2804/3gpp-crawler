"""LibreOffice format definitions."""

from __future__ import annotations

from enum import StrEnum


class LibreOfficeFormat(StrEnum):
    """Supported LibreOffice output formats."""

    ODT = "odt"
    DOC = "doc"
    DOCX = "docx"
    RTF = "rtf"
    PDF = "pdf"
    HTML = "html"
    XHTML = "xhtml"
    TXT = "txt"
    MD = "md"
    EPUB = "epub"
    FODT = "fodt"

    ODS = "ods"
    XLS = "xls"
    XLSX = "xlsx"
    CSV = "csv"
    FODS = "fods"

    ODP = "odp"
    PPT = "ppt"
    PPTX = "pptx"
    FODP = "fodp"

    ODG = "odg"
    SVG = "svg"
    FODG = "fodg"


UNSUPPORTED_CONVERSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("pdf", "doc"),
        ("pdf", "docx"),
        ("pdf", "odt"),
        ("pdf", "rtf"),
        ("pdf", "txt"),
        ("pdf", "md"),
        ("pdf", "epub"),
        ("pdf", "ods"),
        ("pdf", "xls"),
        ("pdf", "xlsx"),
        ("pdf", "csv"),
        ("pdf", "odp"),
        ("pdf", "ppt"),
        ("pdf", "pptx"),
        ("pdf", "odg"),
        ("pdf", "svg"),
    }
)
