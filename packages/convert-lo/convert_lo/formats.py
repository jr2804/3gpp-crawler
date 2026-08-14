"""LibreOffice format definitions."""

from __future__ import annotations

from enum import StrEnum, auto

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


class LibreOfficeFormat(StrEnum):
    """Supported LibreOffice output formats."""

    ODT = auto()
    DOC = auto()
    DOCX = auto()
    RTF = auto()
    PDF = auto()
    HTML = auto()
    XHTML = auto()
    TXT = auto()
    MD = auto()
    EPUB = auto()
    FODT = auto()

    ODS = auto()
    XLS = auto()
    XLSX = auto()
    CSV = auto()
    FODS = auto()

    ODP = auto()
    PPT = auto()
    PPTX = auto()
    FODP = auto()

    ODG = auto()
    SVG = auto()
    FODG = auto()
