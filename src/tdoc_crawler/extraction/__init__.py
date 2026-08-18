"""Extraction pipeline for 3GPP documents.

PDF conversion (LibreOffice with remote fallback) and file fetch
operations.  All AI/analysis capabilities were removed; this package is
PDF-only.
"""

from tdoc_crawler.extraction.convert import (
    OFFICE_FORMATS,
    ConversionError,
    ConverterBackend,
    ConverterConfig,
    convert_dir_to_pdf,
    convert_to_pdf,
    ensure_pdf,
    is_office_format,
)
from tdoc_crawler.extraction.fetch_spec import SpecFiles, fetch_spec_files
from tdoc_crawler.extraction.fetch_tdoc import TDocFiles, fetch_tdoc_files

__all__ = [
    "OFFICE_FORMATS",
    "ConversionError",
    "ConverterBackend",
    "ConverterConfig",
    "SpecFiles",
    "TDocFiles",
    "convert_dir_to_pdf",
    "convert_to_pdf",
    "ensure_pdf",
    "fetch_spec_files",
    "fetch_tdoc_files",
    "is_office_format",
]
