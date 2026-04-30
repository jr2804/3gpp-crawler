"""Extraction pipeline for 3GPP documents.

This package provides document conversion, PDF processing, and
extraction operations using OpenDataLoader and LibreOffice.
"""

from tdoc_crawler.extraction.conversion import (
    OFFICE_FORMATS,
    ConverterBackend,
    ConverterConfig,
    convert_to_pdf,
    is_office_format,
)
from tdoc_crawler.extraction.convert import (
    OpendataloaderConfig,
    convert_document_to_markdown,
    convert_tdoc_metadata,
    convert_tdoc_to_markdown,
    extract_document_structured_from_tdoc,
)
from tdoc_crawler.extraction.fetch_tdoc import TDocFiles, fetch_tdoc_files
from tdoc_crawler.extraction.hybrid_server import (
    DEFAULT_URL,
    HybridServerConfig,
    HybridServerManager,
    HybridServerStatus,
    ensure_hybrid_server,
    get_manager,
)
from tdoc_crawler.extraction.metrics import (
    DocumentMetric,
    MetricsTracker,
    MetricType,
    TimedOperationResult,
    get_metrics_tracker,
    timed_operation,
)
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.extraction.workspace_utils import check_pdf_status

__all__ = [
    "DEFAULT_EXTRACTION_PROFILE",
    "DEFAULT_URL",
    "OFFICE_FORMATS",
    "ConverterBackend",
    "ConverterConfig",
    "DocumentMetric",
    "ExtractionProfile",
    "HybridServerConfig",
    "HybridServerManager",
    "HybridServerStatus",
    "MetricType",
    "MetricsTracker",
    "OpendataloaderConfig",
    "TDocFiles",
    "TimedOperationResult",
    "check_pdf_status",
    "convert_document_to_markdown",
    "convert_tdoc_metadata",
    "convert_tdoc_to_markdown",
    "convert_to_pdf",
    "ensure_hybrid_server",
    "extract_document_structured_from_tdoc",
    "fetch_tdoc_files",
    "get_manager",
    "get_metrics_tracker",
    "is_office_format",
    "timed_operation",
]
