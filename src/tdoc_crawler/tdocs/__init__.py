"""TDoc domain package."""

from __future__ import annotations

from tdoc_crawler.tdocs.models import TDocStatus

# Note: Operations are available via explicit submodule imports
# Importing them here would create circular dependencies
# Use: from tdoc_crawler.tdocs.operations import TDocCrawler

__all__ = ["TDocStatus"]
