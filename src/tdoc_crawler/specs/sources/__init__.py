"""Spec metadata sources."""

from tdoc_crawler.specs.sources.threegpp import SpecNotFoundError, fetch_threegpp_metadata
from tdoc_crawler.specs.sources.whatthespec import fetch_whatthespec_metadata

__all__ = ["SpecNotFoundError", "fetch_threegpp_metadata", "fetch_whatthespec_metadata"]
