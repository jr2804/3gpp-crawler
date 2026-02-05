"""Spec catalog and download support."""

from .catalog import SpecCatalog, SpecCrawlResult, SpecCrawlSourceOutcome
from .downloads import SpecDownloads
from .normalization import normalize_spec_number
from .query import SpecQueryFilters, SpecQueryResult

__all__ = [
    "SpecCatalog",
    "SpecCrawlResult",
    "SpecCrawlSourceOutcome",
    "SpecDownloads",
    "SpecQueryFilters",
    "SpecQueryResult",
    "normalize_spec_number",
]
