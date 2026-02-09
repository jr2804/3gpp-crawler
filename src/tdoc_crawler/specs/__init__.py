"""Spec catalog and download support."""

from tdoc_crawler.models import SpecQueryFilters, SpecQueryResult
from tdoc_crawler.specs.catalog import SpecCatalog, SpecCrawlResult, SpecCrawlSourceOutcome
from tdoc_crawler.specs.downloads import SpecDownloads
from tdoc_crawler.specs.normalization import normalize_spec_number

__all__ = [
    "SpecCatalog",
    "SpecCrawlResult",
    "SpecCrawlSourceOutcome",
    "SpecDownloads",
    "SpecQueryFilters",
    "SpecQueryResult",
    "normalize_spec_number",
]
