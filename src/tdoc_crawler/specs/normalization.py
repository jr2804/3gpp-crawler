"""Normalization helpers for spec identifiers."""

import re
from collections.abc import Generator

_DOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})\s*\.\s*(?P<increment>\d{1,3})$")
_UNDOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})(?P<increment>\d{1,3})$")
_OFFSET_PATTERN = re.compile(r"^(?P<left>.+?)\s*\+\s*(?P<offset>-?\d+)\s*$")
_RANGE_SPLIT_PATTERN = re.compile(r"\s*([-:])\s*")


def _strip_prefixes(value: str) -> str:
    """Strip optional 3GPP and TS/TR prefixes from a spec string."""
    cleaned = value.strip().upper()
    if cleaned.startswith("3GPP"):
        cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    if cleaned.startswith("TS") or cleaned.startswith("TR"):
        cleaned = cleaned[2:]
    return cleaned.strip()


def _parse_spec_number(value: str) -> tuple[str, str, str, int]:
    """Parse a spec number and return (series, increment, format_kind, increment_digits)."""
    body = _strip_prefixes(value)
    if not body:
        raise ValueError("Spec number is required")

    if "." in body:
        body_no_space = re.sub(r"\s+", "", body)
        match = _DOTTED_BODY_PATTERN.match(body_no_space)
        if not match:
            raise ValueError(f"Unsupported spec number format: {value}")
        series = match.group("series")
        increment_raw = match.group("increment")
        increment = increment_raw.zfill(3)
        return series, increment, "dotted", len(increment_raw)

    digits_only = re.sub(r"\s+", "", body)
    match = _UNDOTTED_BODY_PATTERN.match(digits_only)
    if not match:
        raise ValueError(f"Unsupported spec number format: {value}")
    series = match.group("series")
    increment_raw = match.group("increment")
    increment = increment_raw.zfill(3)
    return series, increment, "undotted", len(increment_raw)


def _validate_range(start_num: int, end_num: int, spec_input: str) -> None:
    if start_num > end_num:
        raise ValueError(f"Invalid range: start {start_num} > end {end_num}")
    if end_num - start_num > 1329:
        raise ValueError(f"Range too large: {end_num - start_num + 1} specs")


def normalize_spec_number(value: str) -> str:
    """Normalize spec numbers to dotted canonical format.

    Args:
        value: Spec number in dotted or undotted form.

    Returns:
        Normalized dotted spec number (e.g., "26.132").

    Raises:
        ValueError: When the spec number is not in a supported format.
    """
    series, increment, _, _ = _parse_spec_number(value)
    return f"{series}.{increment}"


def expand_spec_ranges(spec_input: str) -> Generator[str]:
    """Expand spec range syntax into individual spec numbers.

    Supports formats:
    - 26.260-26.266  (260,261,262,263,264,265,266)
    - 26.260:26.266  (same as above, alias)
    - 26.260+6       (260,261,262,263,264,265,266)
    - Flexible prefixes: "3GPP TS 26.260-26.266", "TR 26260-26.266", etc.

    Args:
        spec_input: Input string that may contain range syntax.

    Yields:
        Individual normalized spec numbers (e.g., "26.260", "26.261", ...)

    Raises:
        ValueError: If the range syntax is invalid or series numbers don't match.
    """
    cleaned = spec_input.strip()
    if not cleaned:
        raise ValueError("Spec number is required")

    if "+" in cleaned:
        offset_match = _OFFSET_PATTERN.match(cleaned)
        if not offset_match:
            raise ValueError("Invalid offset format")
        left = offset_match.group("left")
        offset = int(offset_match.group("offset"))
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        series, start_str, _, _ = _parse_spec_number(left)
        start_num = int(start_str)
        end_num = start_num + offset
        _validate_range(start_num, end_num, spec_input)
        for num in range(start_num, end_num + 1):
            yield f"{series}.{num:03d}"
        return

    split = _RANGE_SPLIT_PATTERN.split(cleaned, maxsplit=1)
    if len(split) == 3:
        left, _sep, right = split
        if not right.strip():
            raise ValueError("Missing end value in range")
        series1, num1, format1, digits1 = _parse_spec_number(left)
        series2, num2, format2, digits2 = _parse_spec_number(right)
        if series1 != series2:
            raise ValueError(f"Series numbers don't match: {series1} vs {series2}")
        if format1 != format2 and (digits1 == 1 or digits2 == 1):
            raise ValueError("Both range endpoints must use the same format")
        start_num = int(num1)
        end_num = int(num2)
        _validate_range(start_num, end_num, spec_input)
        for num in range(start_num, end_num + 1):
            yield f"{series1}.{num:03d}"
        return

    yield normalize_spec_number(cleaned)


def expand_spec_ranges_batch(spec_inputs: list[str]) -> list[str]:
    """Expand all spec range inputs in a batch.

    Args:
        spec_inputs: List of spec inputs that may contain range syntax.

    Returns:
        List of expanded and normalized individual spec numbers.
        Invalid spec inputs are silently skipped.
    """
    expanded: list[str] = []
    for spec_input in spec_inputs:
        try:
            expanded.extend(expand_spec_ranges(spec_input))
        except ValueError:
            # Skip invalid spec inputs silently
            continue
    return expanded
