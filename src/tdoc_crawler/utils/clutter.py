"""Gitignore-style clutter filtering for archive extraction and file picking.

Patterns come from a data file, not hardcoded rules: a default set ships
inside the package (``tdoc_crawler/utils/clutter-ignore``) and is copied to
``<cache-dir>/clutter-ignore`` (e.g. ``~/.3gpp-crawler/clutter-ignore``) on
first use. Users edit that copy to extend or narrow the filter; ``!``
negation lines re-include. Deleting the file restores the defaults.

Applied at two places: :func:`tdoc_crawler.utils.security.safe_extract_zip`
(OS metadata never lands on disk) and ``_select_main_file`` in
``tdocs/operations/checkout.py`` (files matching the patterns are never
picked as a TDoc's main document, even in pre-existing checkouts).
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path

from pathspec import GitIgnoreSpec

from tdoc_crawler.config.cache_manager import CacheManagerNotRegisteredError, resolve_cache_manager
from tdoc_crawler.logging import get_logger

#: Name of the user-editable pattern file inside the cache directory.
USER_IGNORE_FILENAME = "clutter-ignore"

logger = get_logger(__name__)


def is_clutter(relpath: str) -> bool:
    """Return True when *relpath* (POSIX-style, relative to the archive/checkout root) matches the clutter patterns."""
    return get_clutter_spec().match_file(relpath)


@lru_cache(maxsize=1)
def get_clutter_spec() -> GitIgnoreSpec:
    """Load the active pattern set.

    Prefers the user-editable file in the cache directory; falls back to the
    packaged defaults when no CacheManager is registered (library use, tests).
    """
    try:
        cache_dir = resolve_cache_manager().root
    except CacheManagerNotRegisteredError:
        return packaged_default_spec()
    return GitIgnoreSpec.from_lines(user_ignore_file(cache_dir).read_text(encoding="utf-8").splitlines())


def packaged_default_spec() -> GitIgnoreSpec:
    """Compile the pattern set shipped with the package."""
    text = (resources.files("tdoc_crawler.utils") / USER_IGNORE_FILENAME).read_text(encoding="utf-8")
    return GitIgnoreSpec.from_lines(text.splitlines())


def user_ignore_file(cache_dir: Path) -> Path:
    """Materialize ``<cache_dir>/clutter-ignore`` from the packaged default if missing."""
    target = cache_dir / USER_IGNORE_FILENAME
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (resources.files("tdoc_crawler.utils") / USER_IGNORE_FILENAME).read_text(encoding="utf-8")
        target.write_text(text, encoding="utf-8")
        logger.debug("Created clutter-ignore file at %s", target)
    return target


__all__ = ["USER_IGNORE_FILENAME", "get_clutter_spec", "is_clutter", "packaged_default_spec", "user_ignore_file"]
