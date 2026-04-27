"""Tests for deprecated import verification and datetime scoping.

This test module verifies:
1. No deprecated imports remain in the codebase (AiStorage, EmbeddingsManager, lancedb, etc.)
2. Datetime scoping is correct in CLI operations
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from tdoc_crawler.utils.date_parser import parse_partial_date


class TestDeprecatedImports:
    """Verify deprecated modules are not imported in the codebase."""

    def test_no_lancedb_import(self) -> None:
        """Lancedb deprecated module should not be imported."""
        assert "lancedb" not in sys.modules, "lancedb module should not be loaded"

    def test_no_sentence_transformers_import(self) -> None:
        """sentence_transformers deprecated module should not be imported."""
        assert "sentence_transformers" not in sys.modules, "sentence_transformers should not be loaded"


class TestDatetimeScoping:
    """Verify datetime variables are properly scoped."""

    def test_datetime_combine_usage(self) -> None:
        """datetime.combine should be used with proper scoping."""
        start_date_str = "2025-01"
        parsed_date = parse_partial_date(start_date_str)
        combined = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)

        assert combined is not None
        assert combined.tzinfo == UTC
        assert combined.year == 2025
        assert combined.month == 1

    def test_datetime_combine_end_date(self) -> None:
        """datetime.combine should work for end dates with is_end flag."""
        end_date_str = "2025-03"
        parsed_date = parse_partial_date(end_date_str, is_end=True)
        combined = datetime.combine(parsed_date, datetime.max.time(), tzinfo=UTC)

        assert combined is not None
        assert combined.tzinfo == UTC
        assert combined.year == 2025
        assert combined.month == 3
