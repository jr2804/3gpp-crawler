"""Extraction pipeline for 3GPP documents.

This package provides document conversion, PDF processing, and
extraction operations using Docling and LibreOffice.
"""

from tdoc_crawler.extraction.conversion import (
    OFFICE_FORMATS,
    ConverterBackend,
    ConverterConfig,
    convert_to_pdf,
    is_office_format,
)
from tdoc_crawler.extraction.convert import (
    ConversionError,
    DoclingConfig,
    convert_for_wiki,
)
from tdoc_crawler.extraction.fetch_spec import SpecFiles, fetch_spec_files
from tdoc_crawler.extraction.fetch_tdoc import TDocFiles, fetch_tdoc_files
from tdoc_crawler.extraction.metrics import (
    DocumentMetric,
    MetricsTracker,
    MetricType,
    TimedOperationResult,
    get_metrics_tracker,
    timed_operation,
)
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile

__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "OFFICE_FORMATS",
    "ConversionError",
    "ConverterBackend",
    "ConverterConfig",
    "DoclingConfig",
    "DocumentMetric",
    "ExtractionProfile",
    "MetricType",
    "MetricsTracker",
    "SpecFiles",
    "TDocFiles",
    "TimedOperationResult",
    "convert_for_wiki",
    "convert_to_pdf",
    "fetch_spec_files",
    "fetch_tdoc_files",
    "get_metrics_tracker",
    "is_office_format",
    "timed_operation",
]
