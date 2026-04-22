"""Top-level CLI entrypoint for the 3gpp-ai package.

This module is a thin compatibility shim that re-exports the refactored
command tree from :mod:`threegpp_ai.cli`.
"""

from __future__ import annotations

from threegpp_ai.cli import app

__all__ = ["app"]
