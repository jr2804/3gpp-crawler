"""Singleton Console instance for CLI output.

This module provides a cached Console instance to avoid multiple
instantiations across the CLI module.
"""

from __future__ import annotations

from functools import cache

from rich.console import Console


@cache
def get_console() -> Console:
    """Get the singleton Console instance.

    Returns:
        Cached Console instance for consistent CLI output.
    """
    return Console()
