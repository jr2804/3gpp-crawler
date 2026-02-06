"""Spec metadata sources."""

from .threegpp import SpecNotFoundError, fetch_threegpp_metadata
from .whatthespec import fetch_whatthespec_metadata

__all__ = ["SpecNotFoundError", "fetch_threegpp_metadata", "fetch_whatthespec_metadata"]
