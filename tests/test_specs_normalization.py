"""Tests for spec normalization utilities."""

import pytest

from tdoc_crawler.specs.normalization import normalize_spec_number


def test_normalize_dotted_spec_number() -> None:
    assert normalize_spec_number("26.132") == "26.132"


def test_normalize_undotted_spec_number() -> None:
    assert normalize_spec_number("26132") == "26.132"


def test_normalize_prefixed_spec_number() -> None:
    assert normalize_spec_number("TS23.501") == "23.501"


def test_normalize_invalid_spec_number() -> None:
    with pytest.raises(ValueError):
        normalize_spec_number("ABC")
