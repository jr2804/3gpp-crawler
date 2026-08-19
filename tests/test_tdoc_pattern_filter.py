"""Tests for TDocDatabase glob pattern filter normalization."""

from __future__ import annotations

from tdoc_crawler.database.tdocs import TDocDatabase


def test_normalize_glob_bare_pattern_wraps_in_stars() -> None:
    """Bare patterns without glob metacharacters get substring-match treatment."""
    assert TDocDatabase._normalize_glob("ATIAS") == "*ATIAS*"
    assert TDocDatabase._normalize_glob("atias") == "*atias*"
    assert TDocDatabase._normalize_glob("foo bar") == "*foo bar*"


def test_normalize_glob_passes_through_explicit_globs() -> None:
    """Patterns with glob metacharacters are unchanged."""
    assert TDocDatabase._normalize_glob("*ATIAS*") == "*ATIAS*"
    assert TDocDatabase._normalize_glob("ATIAS*") == "ATIAS*"
    assert TDocDatabase._normalize_glob("*ATIAS") == "*ATIAS"
    assert TDocDatabase._normalize_glob("ATIAS?") == "ATIAS?"
    assert TDocDatabase._normalize_glob("[abc]") == "[abc]"


def test_normalize_glob_empty_pattern() -> None:
    """Empty pattern wraps to '**' which fnmatch treats as 'match all'."""
    assert TDocDatabase._normalize_glob("") == "**"
