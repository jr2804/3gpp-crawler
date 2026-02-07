"""Spec catalog and download support."""

from tdoc_crawler.models import SpecQueryFilters, SpecQueryResult

from .catalog import SpecCatalog, SpecCrawlResult, SpecCrawlSourceOutcome
from .downloads import SpecDownloads
from .normalization import normalize_spec_number

__all__ = [
    "SpecCatalog",
    "SpecCrawlResult",
    "SpecCrawlSourceOutcome",
    "SpecDownloads",
    "SpecQueryFilters",
    "SpecQueryResult",
    "normalize_spec_number",
]
