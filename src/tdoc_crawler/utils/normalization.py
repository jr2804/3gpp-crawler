"""Normalization helpers for spec identifiers."""

import re
from collections.abc import Generator, Iterable

_DOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})\s*\.\s*(?P<increment>\d{1,3})$")
_UNDOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})(?P<increment>\d{1,3})$")
_OFFSET_PATTERN = re.compile(r"^(?P<left>.+?)\s*\+\s*(?P<offset>-?\d+)\s*$")
_RANGE_SPLIT_PATTERN = re.compile(r"\s*([-:])\s*")
_RELEASE_PREFIX_PATTERN = re.compile(r"^(?:v|rel|rel[-])", re.IGNORECASE)


class NormalizationError(ValueError):
    """Raised when spec identifier normalization or expansion fails."""


# TODO is already defined in src/tdoc_crawler/tdocs/utils.py - should exist only at a single location!
def normalize_tdoc_ids(ids: Iterable[str]) -> list[str]:
    """Uppercase and strip whitespace from TDoc identifiers."""
    return [str(value).strip().upper() for value in ids]


# TODO is already defined in src/tdoc_crawler/meetings/models.py - should exist only at a single location!
def normalize_portal_meeting_name(portal_meeting: str | None) -> str:
    """Normalize portal meeting name to database format.

    The portal uses format like "SA4#133-e" while the database uses "S4-133-e".
    This function converts portal format to database format.

    Args:
        portal_meeting: Meeting name from portal (e.g., "SA4#133-e")

    Returns:
        Normalized meeting name (e.g., "S4-133-e")
    """
    if not portal_meeting:
        return ""

    # Replace "SA4#" with "S4-", "RAN1#" with "R1-", etc.
    normalized = portal_meeting.replace("#", "-")

    # Handle full working group names (SA, RAN, CT)
    for full_name, short_prefix in [("SA", "S"), ("RAN", "R"), ("CT", "C")]:
        # Match patterns like "SA4-" and replace with "S4-"
        if normalized.startswith(f"{full_name}"):
            # Extract subgroup number if present
            for i, char in enumerate(normalized[len(full_name) :]):
                if not char.isdigit():
                    subgroup_num = normalized[len(full_name) : len(full_name) + i] if i > 0 else ""
                    rest = normalized[len(full_name) + i :]
                    if subgroup_num:
                        normalized = f"{short_prefix}{subgroup_num}{rest}"
                    break
            break

    return normalized


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
        raise NormalizationError("Spec number is required")

    if "." in body:
        body_no_space = re.sub(r"\s+", "", body)
        match = _DOTTED_BODY_PATTERN.match(body_no_space)
        if not match:
            raise NormalizationError(f"Unsupported spec number format: {value}")
        series = match.group("series")
        increment_raw = match.group("increment")
        increment = increment_raw.zfill(3)
        return series, increment, "dotted", len(increment_raw)

    digits_only = re.sub(r"\s+", "", body)
    match = _UNDOTTED_BODY_PATTERN.match(digits_only)
    if not match:
        raise NormalizationError(f"Unsupported spec number format: {value}")
    series = match.group("series")
    increment_raw = match.group("increment")
    increment = increment_raw.zfill(3)
    return series, increment, "undotted", len(increment_raw)


def _validate_range(start_num: int, end_num: int, spec_input: str) -> None:
    if start_num > end_num:
        raise NormalizationError(f"Invalid range: start {start_num} > end {end_num}")
    if end_num - start_num > 1329:
        raise NormalizationError(f"Range too large: {end_num - start_num + 1} specs")


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
        NormalizationError: If the range syntax is invalid or series numbers don't match.
    """
    cleaned = spec_input.strip()
    if not cleaned:
        raise NormalizationError("Spec number is required")

    if "+" in cleaned:
        offset_match = _OFFSET_PATTERN.match(cleaned)
        if not offset_match:
            raise NormalizationError("Invalid offset format")
        left = offset_match.group("left")
        offset = int(offset_match.group("offset"))
        if offset < 0:
            raise NormalizationError("Offset must be non-negative")
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
            raise NormalizationError("Missing end value in range")
        series1, num1, format1, digits1 = _parse_spec_number(left)
        series2, num2, format2, digits2 = _parse_spec_number(right)
        if series1 != series2:
            raise NormalizationError(f"Series numbers don't match: {series1} vs {series2}")
        if format1 != format2 and (digits1 == 1 or digits2 == 1):
            raise NormalizationError("Both range endpoints must use the same format")
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
        except NormalizationError:
            # Skip invalid spec inputs silently
            continue
    return expanded


def normalize_release(release: str) -> tuple[str, str | None, int | None]:
    """Normalize a release selector string.

    Supports formats:
    - 'latest' - Returns ('latest', None, None)
    - 'all' - Returns ('all', None, None)
    - '18.0.0' - Full version (returns ('exact', '18.0.0', 3))
    - '18.1' - Partial major.minor (returns ('prefix', '18.1', 2))
    - '18' - Partial major only (returns ('prefix', '18', 1))
    - 'v18', 'V18', 'Rel-18', 'rel18', 'REL18' - Prefix variants (normalized to '18')

    Args:
        release: Release selector string in various formats.

    Returns:
        Tuple of (type, normalized_value, specificity):
        - type: 'latest', 'all', 'exact', or 'prefix'
        - normalized_value: Cleaned release string without prefixes
        - specificity: Number of version components (1=major, 2=major.minor, 3=major.minor.patch)

    Raises:
        ValueError: If the release format is invalid.
    """
    cleaned = release.strip()

    # Handle special values (case-insensitive)
    upper_cleaned = cleaned.upper()
    if upper_cleaned == "LATEST":
        return ("latest", None, None)
    if upper_cleaned == "ALL":
        return ("all", None, None)

    # Strip prefixes: v, rel, rel- (case-insensitive)
    normalized = _RELEASE_PREFIX_PATTERN.sub("", cleaned)

    # Validate that we have a valid version number after stripping
    if not normalized:
        raise ValueError(f"Invalid release format: '{release}'. Expected 'latest', 'all', or a version number like '18', '18.1', '18.1.0'.")

    # Split into components and validate
    parts = normalized.split(".")
    if len(parts) > 3:
        raise ValueError(f"Invalid release format: '{release}'. Version has too many components (max 3: major.minor.patch).")

    # Validate each part is a number
    try:
        [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"Invalid release format: '{release}'. Version components must be numbers.") from exc

    specificity = len(parts)

    # Check for exact match (all 3 components)
    if specificity == 3:
        return ("exact", normalized, 3)

    # Partial match (1 or 2 components)
    return ("prefix", normalized, specificity)


def resolve_release_to_full_version(release: str, available_versions: list[str]) -> str:
    """Resolve a release selector to a full 3-digit version string.

    Args:
        release: Release selector (e.g., "latest", "17", "17.0", "17.0.0").
        available_versions: List of available version strings (e.g., ["17.0.0", "17.1.0"]).

    Returns:
        Full 3-digit version string (e.g., "17.0.0").

    Raises:
        ValueError: If no matching version found or release format invalid.
    """
    release_type, release_value, specificity = normalize_release(release)

    # Parse and sort versions (highest first)
    def parse_version(version: str) -> tuple[int, ...]:
        try:
            return tuple(map(int, version.split(".")))
        except ValueError:
            return (0, 0, 0)

    sorted_versions = sorted(available_versions, key=parse_version, reverse=True)

    if release_type == "latest":
        # Return highest version
        if not sorted_versions:
            raise ValueError("No versions available")
        return sorted_versions[0]

    if release_type == "all":
        # Return highest version as default
        if not sorted_versions:
            raise ValueError("No versions available")
        return sorted_versions[0]

    if release_type == "exact":
        # Exact match required
        if release_value in sorted_versions:
            return release_value
        raise ValueError(f"Version {release_value} not found")

    if release_type == "prefix":
        # Match by prefix (major or major.minor)
        prefix_parts = release_value.split(".")
        for version in sorted_versions:
            version_parts = version.split(".")
            if len(version_parts) >= specificity and all(version_parts[i] == prefix_parts[i] for i in range(specificity)):
                return version
        raise ValueError(f"No version matches prefix {release_value}")

    raise ValueError(f"Invalid release type: {release_type}")
