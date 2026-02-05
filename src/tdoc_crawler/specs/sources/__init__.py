"""Spec metadata sources."""

from .threegpp import fetch_threegpp_metadata
from .whatthespec import fetch_whatthespec_metadata

__all__ = ["fetch_threegpp_metadata", "fetch_whatthespec_metadata"]
