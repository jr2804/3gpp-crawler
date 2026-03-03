"""CLI dependency injection integration.

Provides container state management and service resolution helpers for CLI commands.
Commands can use get_container() to obtain services from the DI container when
``--di-mode`` is enabled, or create services directly for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.di.container import ServiceContainer

# Module-level container state, set by the app callback when --di-mode is active
_active_container: ServiceContainer | None = None


def set_container(container: ServiceContainer | None) -> None:
    """Set the active container for this CLI session.

    Called by the app callback when ``--di-mode`` is enabled.

    Args:
        container: Container to activate, or None to clear.
    """
    global _active_container  # noqa: PLW0603
    _active_container = container


def get_container() -> ServiceContainer | None:
    """Return the active container if DI mode is enabled.

    Returns:
        The active ServiceContainer, or None if DI mode is not enabled.
    """
    return _active_container


def is_di_mode() -> bool:
    """Check whether DI mode is currently active.

    Returns:
        True if a container is active, False otherwise.
    """
    return _active_container is not None


def resolve_cache_dir(cache_dir: Path | None = None) -> Path | None:
    """Resolve effective cache directory, preferring the active container.

    When DI mode is active and the container already has a cache manager, its
    root path is returned so callers do not need to re-read ``--cache-dir``.
    Falls back to the supplied ``cache_dir`` argument when DI mode is off.

    Args:
        cache_dir: Explicit cache directory passed via CLI option.

    Returns:
        Resolved cache directory path, or None to use the default.
    """
    if _active_container is not None and _active_container._cache_manager is not None:
        return _active_container._cache_manager.root
    return cache_dir


__all__ = [
    "get_container",
    "is_di_mode",
    "resolve_cache_dir",
    "set_container",
]
