"""Shared constants used across tdoc_crawler domains."""

OFFICE_FORMATS: frozenset[str] = frozenset(
    {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt", ".odp", ".ods"},
)

__all__ = ["OFFICE_FORMATS"]
