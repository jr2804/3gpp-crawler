"""Tests for spec normalization utilities."""

import os
import tempfile
from pathlib import Path

import pytest

from tdoc_crawler.utils.normalization import (
    NormalizationError,
    expand_spec_ranges,
    expand_spec_ranges_batch,
    normalize_spec_number,
)
from tdoc_crawler.utils.parse import collect_spec_numbers


def test_normalize_dotted_spec_number() -> None:
    assert normalize_spec_number("26.132") == "26.132"


def test_normalize_undotted_spec_number() -> None:
    assert normalize_spec_number("26132") == "26.132"


def test_normalize_prefixed_spec_number() -> None:
    assert normalize_spec_number("TS23.501") == "23.501"


def test_normalize_prefix_spacing_variants() -> None:
    assert normalize_spec_number("3GPPTS26132") == "26.132"
    assert normalize_spec_number("3GPP     TS    26 132") == "26.132"
    assert normalize_spec_number("TR 26.071") == "26.071"
    assert normalize_spec_number("TS 2671") == "26.071"


def test_normalize_tab_separator_variants() -> None:
    """Test tab characters as separators between components."""
    # Tab between 3GPP and TS/TR
    assert normalize_spec_number("3GPP\tTS\t26.123") == "26.123"
    assert normalize_spec_number("3GPP\tTR\t26.123") == "26.123"

    # Tab between TS/TR and number
    assert normalize_spec_number("TS\t26.123") == "26.123"
    assert normalize_spec_number("TR\t26123") == "26.123"

    # Tab within undotted number
    assert normalize_spec_number("26\t123") == "26.123"
    assert normalize_spec_number("26\t12") == "26.012"

    # Mixed tabs and spaces
    assert normalize_spec_number("3GPP  \t  TS  \t  26  \t  123") == "26.123"
    assert normalize_spec_number("3GPP\t TS \t 26.123") == "26.123"


def test_normalize_no_whitespace_between_prefixes() -> None:
    """Test no whitespace between 3GPP and TS/TR prefixes."""
    # No space between 3GPP and TS
    assert normalize_spec_number("3GPPTS26123") == "26.123"
    assert normalize_spec_number("3GPPTR26123") == "26.123"

    # No space between TS/TR and number
    assert normalize_spec_number("TS26123") == "26.123"
    assert normalize_spec_number("TR26123") == "26.123"

    # Combination: 3GPPTS + no space before number
    assert normalize_spec_number("3GPPTS26123") == "26.123"
    assert normalize_spec_number("3GPPTR26123") == "26.123"


def test_normalize_invalid_spec_number() -> None:
    with pytest.raises(NormalizationError, match="Unsupported spec number format"):
        normalize_spec_number("ABC")


def test_expand_range_hyphen() -> None:
    """Test range expansion with hyphen separator."""
    result = list(expand_spec_ranges("26.260-26.266"))
    expected = ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]
    assert result == expected


def test_expand_range_colon() -> None:
    """Test range expansion with colon separator."""
    result = list(expand_spec_ranges("26.260:26.266"))
    expected = ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]
    assert result == expected


def test_expand_offset_plus() -> None:
    """Test range expansion with offset plus syntax."""
    result = list(expand_spec_ranges("26.260+6"))
    expected = ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]
    assert result == expected


def test_expand_range_with_prefix() -> None:
    """Test range expansion with various prefixes."""
    result = list(expand_spec_ranges("TS 26.260-26.266"))
    expected = ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]
    assert result == expected

    result = list(expand_spec_ranges("3GPP TR 26.260 - TS 26266"))
    assert result == expected


def test_expand_single_spec() -> None:
    """Test that single specs without range are passed through."""
    result = list(expand_spec_ranges("26.260"))
    assert result == ["26.260"]

    result = list(expand_spec_ranges("TS 26.260"))
    assert result == ["26.260"]


def test_expand_range_mixed_formats() -> None:
    """Test range expansion with mixed formats."""
    result = list(expand_spec_ranges("TR 26260-26.266"))
    expected = ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]
    assert result == expected

    result = list(expand_spec_ranges("3GPP TS 26.260+6"))
    assert result == expected

    result = list(expand_spec_ranges("TR 23.501+2"))
    assert result == ["23.501", "23.502", "23.503"]


def test_expand_range_invalid() -> None:
    """Test invalid range syntax."""
    with pytest.raises(NormalizationError, match="Series numbers don't match"):
        list(expand_spec_ranges("26.260-25.266"))  # Different series

    with pytest.raises(NormalizationError, match="Missing end value in range"):
        list(expand_spec_ranges("26.260-"))  # Missing end

    with pytest.raises(NormalizationError, match="Invalid offset format"):
        list(expand_spec_ranges("26.260+"))  # Missing offset value


def test_expand_range_reverse() -> None:
    """Test that reverse ranges are rejected."""
    with pytest.raises(NormalizationError, match="Invalid range: start"):
        list(expand_spec_ranges("26.266-26.260"))  # Start > end


def test_expand_range_batch() -> None:
    """Test batch expansion of multiple spec inputs."""
    inputs = ["26.260-26.262", "TS 38.331", "TR 23.501+2"]
    result = expand_spec_ranges_batch(inputs)
    expected = ["26.260", "26.261", "26.262", "38.331", "23.501", "23.502", "23.503"]
    assert result == expected


def test_expand_range_batch_invalid() -> None:
    """Test batch expansion with invalid input - invalid specs are silently skipped."""
    result = expand_spec_ranges_batch(["26.260-26.262", "invalid", "38.331"])
    expected = ["26.260", "26.261", "26.262", "38.331"]
    assert result == expected


def test_expand_range_with_tab_separators() -> None:
    """Test range expansion with tab characters as separators."""
    # Tab in range separator
    result = list(expand_spec_ranges("26.260-\t26.266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Tabs around hyphen
    result = list(expand_spec_ranges("26.260\t-\t26.266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Tab within spec numbers (undotted)
    result = list(expand_spec_ranges("26\t260-26\t266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Tab between prefix and number
    result = list(expand_spec_ranges("3GPP\tTS\t26.260-26.266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Tab in offset
    result = list(expand_spec_ranges("26.260+\t6"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]


def test_expand_range_with_no_whitespace() -> None:
    """Test range expansion with no whitespace between prefixes."""
    # No space between 3GPP and TS in range
    result = list(expand_spec_ranges("3GPPTS26260-26.266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # No space between TS and number in range
    result = list(expand_spec_ranges("TS26260-TS26266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Mixed: prefixed start, bare end
    result = list(expand_spec_ranges("3GPPTS26260-26266"))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]


def test_expand_all_range_variants() -> None:
    """Test all range syntax variants mentioned in requirements."""
    # Test hyphen range with full 5-digit format
    result = list(expand_spec_ranges_batch(["26.260-26.266"]))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test colon range (alias for hyphen)
    result2 = list(expand_spec_ranges_batch(["26.260:26.266"]))
    assert result2 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test offset mode
    result3 = list(expand_spec_ranges_batch(["26.260+6"]))
    assert result3 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test mixed prefixes with whitespace
    result4 = list(expand_spec_ranges_batch(["3GPP TS 26.260-26.266"]))
    assert result4 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test mixed prefixes without dot in second part
    result5 = list(expand_spec_ranges_batch(["TR 26260-26.266"]))
    assert result5 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test complex mixed prefixes with whitespace
    result6 = list(expand_spec_ranges_batch(["3GPP TR 26.260 - TS 26266"]))
    assert result6 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test with prefix on both sides but different
    result7 = list(expand_spec_ranges_batch(["TS 26.260:TR 26.266"]))
    assert result7 == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # 26.260-266: right side "266" parses as spec 26.006, same series,
    # so it expands via short-suffix fallback to 260..266
    result = list(expand_spec_ranges_batch(["26.260-266"]))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Test dotted with one-digit suffix is allowed and normalized
    result8 = list(expand_spec_ranges_batch(["26.2-26.4"]))
    assert result8 == ["26.002", "26.003", "26.004"]


def test_expand_edge_cases() -> None:
    """Test edge cases for range expansion."""
    # Single spec (no range)
    result = list(expand_spec_ranges_batch(["26.260"]))
    assert result == ["26.260"]

    # Range of 1 (start == end)
    result = list(expand_spec_ranges_batch(["26.260-26.260"]))
    assert result == ["26.260"]

    # Reverse range (silently skipped in batch mode)
    result = list(expand_spec_ranges_batch(["26.266-26.260"]))
    assert result == []

    # Offset 0
    result = list(expand_spec_ranges_batch(["26.260+0"]))
    assert result == ["26.260"]

    # Offset 1
    result = list(expand_spec_ranges_batch(["26.260+1"]))
    assert result == ["26.260", "26.261"]

    # Large range
    result = list(expand_spec_ranges_batch(["38.331-38.335"]))
    assert result == ["38.331", "38.332", "38.333", "38.334", "38.335"]

    # Cross hundred boundary
    result = list(expand_spec_ranges_batch(["23.498-23.502"]))
    assert result == ["23.498", "23.499", "23.500", "23.501", "23.502"]

    # Short-format suffix: dotted left, numeric-only right
    result = list(expand_spec_ranges_batch(["26.131-132"]))
    assert result == ["26.131", "26.132"]

    # Short-format suffix: undotted left, short right (colon)
    result = list(expand_spec_ranges_batch(["26250:258"]))
    assert result == ["26.250", "26.251", "26.252", "26.253", "26.254", "26.255", "26.256", "26.257", "26.258"]

    # Full dotted left, short right (dash)
    result = list(expand_spec_ranges_batch(["26.260-265"]))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265"]


def test_expand_invalid_ranges() -> None:
    """Test invalid range syntax - invalid specs are silently skipped in batch mode."""
    # Invalid: missing second part after hyphen - skipped
    result = list(expand_spec_ranges_batch(["26.260-"]))
    assert result == []

    # Invalid: missing offset number - skipped
    result = list(expand_spec_ranges_batch(["26.260+"]))
    assert result == []

    # Invalid: negative offset - skipped
    result = list(expand_spec_ranges_batch(["26.260+-1"]))
    assert result == []

    # Invalid: non-numeric offset - skipped
    result = list(expand_spec_ranges_batch(["26.260+abc"]))
    assert result == []

    # Mixed dotted/undotted formats with full increment digits is allowed
    result = list(expand_spec_ranges_batch(["26.260-26266"]))
    assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    # Invalid: completely wrong format - skipped
    result = list(expand_spec_ranges_batch(["abc"]))
    assert result == []

    # Test that valid specs are still processed alongside invalid ones
    result = list(expand_spec_ranges_batch(["abc", "26.260", "invalid", "26.261"]))
    assert result == ["26.260", "26.261"]


def test_expand_with_collect_spec_numbers() -> None:
    """Test that range expansion works with CLI helper."""
    # Test with positional arguments using ranges
    result = collect_spec_numbers(["26.260-26.262", "38.331+1"], None)
    assert result == ["26.260", "26.261", "26.262", "38.331", "38.332"]

    # Test with file containing ranges
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("26.260-26.262\n")
        f.write("TR 38.331+1\n")
        f.write("3GPP TS a23.501\n")  # Should be ignored/skipped
        f.flush()
        temp_path = Path(f.name)
    try:
        result = collect_spec_numbers(specs=None, spec_file=temp_path)
        assert result == ["26.260", "26.261", "26.262", "38.331", "38.332"]
    finally:
        os.unlink(temp_path)
