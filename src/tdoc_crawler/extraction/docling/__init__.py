"""Docling document converter — ML-based structured extraction (Markdown + JSON)."""

from tdoc_crawler.extraction.docling.converter import (
    DoclingConfig,
    _converter_cache,
    _export_tables_as_csv,
    _get_or_create_converter,
    _run_docling,
)
from tdoc_crawler.extraction.docling.filter import _DOCLING_PIPELINE_LOGGER, _DoclingBadAllocFilter
from tdoc_crawler.extraction.docling.pipeline import _build_pipeline_options

__all__ = [
    "_DOCLING_PIPELINE_LOGGER",
    "DoclingConfig",
    "_DoclingBadAllocFilter",
    "_build_pipeline_options",
    "_converter_cache",
    "_export_tables_as_csv",
    "_get_or_create_converter",
    "_run_docling",
]
