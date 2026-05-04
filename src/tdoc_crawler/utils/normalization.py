"""Normalization helpers for spec identifiers."""

import re
from collections.abc import Generator

from tdoc_crawler.models.subworking_groups import SubWorkingGroup
from tdoc_crawler.models.working_groups import WorkingGroup

_DOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})\s*\.\s*(?P<increment>\d{1,3})$")
_UNDOTTED_BODY_PATTERN = re.compile(r"^(?P<series>\d{2})(?P<increment>\d{1,3})$")
_OFFSET_PATTERN = re.compile(r"^(?P<left>.+?)\s*\+\s*(?P<offset>-?\d+)\s*$")
_RANGE_SPLIT_PATTERN = re.compile(r"\s*([-:])\s*")
_RELEASE_PREFIX_PATTERN = re.compile(r"^(?:v|rel|rel[-])", re.IGNORECASE)


class NormalizationError(ValueError):
    """Raised when spec identifier normalization or expansion fails."""


def _strip_prefixes(value: str) -> str:
    """Strip optional 3GPP and TS/TR prefixes from a spec string."""
    cleaned = value.strip().upper()
    cleaned = cleaned.removeprefix("3GPP")
    cleaned = cleaned.strip()
    if cleaned.startswith(("TS", "TR")):
        cleaned = cleaned[2:]
    return cleaned.strip()


def _parse_spec_number(value: str) -> tuple[str, str, str, int]:
    """Parse a spec number and return (series, increment, format_kind, increment_digits)."""
    body = _strip_prefixes(value)
    if not body:
        msg = "Spec number is required"
        raise NormalizationError(msg)

    if "." in body:
        body_no_space = re.sub(r"\s+", "", body)
        match = _DOTTED_BODY_PATTERN.match(body_no_space)
        if not match:
            msg = f"Unsupported spec number format: {value}"
            raise NormalizationError(msg)
        series = match.group("series")
        increment_raw = match.group("increment")
        increment = increment_raw.zfill(3)
        return series, increment, "dotted", len(increment_raw)

    digits_only = re.sub(r"\s+", "", body)
    match = _UNDOTTED_BODY_PATTERN.match(digits_only)
    if not match:
        msg = f"Unsupported spec number format: {value}"
        raise NormalizationError(msg)
    series = match.group("series")
    increment_raw = match.group("increment")
    increment = increment_raw.zfill(3)
    return series, increment, "undotted", len(increment_raw)


def _validate_range(start_num: int, end_num: int, spec_input: str) -> None:
    if start_num > end_num:
        msg = f"Invalid range: start {start_num} > end {end_num}"
        raise NormalizationError(msg)
    if end_num - start_num > 1329:
        msg = f"Range too large: {end_num - start_num + 1} specs"
        raise NormalizationError(msg)


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


def normalize_spec_number_compact(value: str) -> str:
    """Normalize spec numbers to compact canonical format.

    Args:
        value: Spec number in dotted or undotted form.

    Returns:
        Normalized compact spec number (e.g., "26260").

    Raises:
        ValueError: When the spec number is not in a supported format.
    """
    return normalize_spec_number(value).replace(".", "")


def _expand_offset_range(cleaned: str) -> Generator[str]:
    """Expand offset range syntax like '26.260+6'."""
    offset_match = _OFFSET_PATTERN.match(cleaned)
    if not offset_match:
        msg = "Invalid offset format"
        raise NormalizationError(msg)
    left = offset_match.group("left")
    offset = int(offset_match.group("offset"))
    if offset < 0:
        msg = "Offset must be non-negative"
        raise NormalizationError(msg)
    series, start_str, _, _ = _parse_spec_number(left)
    start_num = int(start_str)
    end_num = start_num + offset
    _validate_range(start_num, end_num, cleaned)
    for num in range(start_num, end_num + 1):
        yield f"{series}.{num:03d}"


def _expand_dash_range(left: str, right: str, original: str) -> Generator[str]:
    """Expand dash/colon range syntax like '26.260-26.266'."""
    series1, num1, format1, digits1 = _parse_spec_number(left)
    series2, num2, format2, digits2 = _parse_spec_number(right)
    if series1 != series2:
        msg = f"Series numbers don't match: {series1} vs {series2}"
        raise NormalizationError(msg)
    if format1 != format2 and (digits1 == 1 or digits2 == 1):
        msg = "Both range endpoints must use the same format"
        raise NormalizationError(msg)
    start_num = int(num1)
    end_num = int(num2)
    _validate_range(start_num, end_num, original)
    for num in range(start_num, end_num + 1):
        yield f"{series1}.{num:03d}"


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
        msg = "Spec number is required"
        raise NormalizationError(msg)

    if "+" in cleaned:
        yield from _expand_offset_range(cleaned)
        return

    split = _RANGE_SPLIT_PATTERN.split(cleaned, maxsplit=1)
    if len(split) == 3:
        left, _sep, right = split
        if not right.strip():
            msg = "Missing end value in range"
            raise NormalizationError(msg)
        yield from _expand_dash_range(left, right, spec_input)
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
        msg = f"Invalid release format: '{release}'. Expected 'latest', 'all', or a version number like '18', '18.1', '18.1.0'."
        raise ValueError(msg)

    # Split into components and validate
    parts = normalized.split(".")
    if len(parts) > 3:
        msg = f"Invalid release format: '{release}'. Version has too many components (max 3: major.minor.patch)."
        raise ValueError(msg)

    # Validate each part is a number
    try:
        [int(p) for p in parts]
    except ValueError as exc:
        msg = f"Invalid release format: '{release}'. Version components must be numbers."
        raise ValueError(msg) from exc

    specificity = len(parts)

    # Check for exact match (all 3 components)
    if specificity == 3:
        return ("exact", normalized, 3)

    # Partial match (1 or 2 components)
    return ("prefix", normalized, specificity)


def normalize_tdoc_id(tdoc_id: str) -> str:
    """Normalize a TDoc ID to uppercase.

    Args:
        tdoc_id: TDoc identifier to normalize.

    Returns:
        Uppercase normalized TDoc ID.

    Raises:
        ValueError: If the ID is empty after stripping whitespace.
    """
    normalized = str(tdoc_id).strip().upper()
    if not normalized:
        msg = "TDoc ID cannot be empty"
        raise ValueError(msg)
    return normalized


def normalize_tdoc_ids(tdoc_ids: list[str] | None) -> list[str] | None:
    """Normalize a list of TDoc IDs to uppercase.

    Args:
        tdoc_ids: List of TDoc identifiers to normalize.

    Returns:
        List of uppercase normalized TDoc IDs, or None if input is None.
    """
    if tdoc_ids is None:
        return None
    return [normalize_tdoc_id(tdoc_id) for tdoc_id in tdoc_ids]


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


def normalize_release_version(release: str) -> str:
    """Normalize a release version to three numeric components.

    Pads partial versions with ".0" and strips "rel-" prefix.

    Examples:
        '19' -> '19.0.0'
        '19.1' -> '19.1.0'
        '19.1.2' -> '19.1.2'
        'rel-19' -> '19.0.0'

    Args:
        release: Release version string.

    Returns:
        Normalized 3-component version string, or original string if not a valid version.
    """
    cleaned = release.strip()
    if cleaned.lower().startswith("rel-"):
        cleaned = cleaned[4:]

    parts = [part for part in cleaned.split(".") if part != ""]
    if not parts:
        return release

    if any(not part.isdigit() for part in parts):
        return release

    while len(parts) < 3:
        parts.append("0")
    if len(parts) > 3:
        parts = parts[:3]

    return ".".join(parts)


def normalize_working_group_alias(alias: str) -> WorkingGroup:
    """Normalize working group aliases to canonical working group enums.

    Supports: RAN, SA, CT and their common name variants.

    Args:
        alias: Working group alias or name

    Returns:
        Canonical working group enum value (WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT)

    Raises:
        ValueError: When the alias cannot be resolved
    """
    alias_upper = alias.strip().upper()
    cleaned = re.sub(r"[#\-_\s]", "", alias_upper)

    # Easy check via list(WorkingGroup): match against name or value
    for working_group in WorkingGroup:
        if cleaned.startswith((working_group.value, working_group.name)):
            return working_group

    # If not found: match first letter
    if cleaned:
        for working_group in WorkingGroup:
            if working_group.value[0] == cleaned[0]:
                return working_group

    # If not found: any match of name/value in cleaned
    for working_group in WorkingGroup:
        if working_group.value in cleaned or working_group.name in cleaned:
            return working_group

    msg = f"Unknown working group: {alias}"
    raise ValueError(msg)


def normalize_subgroup_alias(alias: str) -> SubWorkingGroup:
    """Normalize subgroup aliases to canonical subgroup enums.

    Returns a SubWorkingGroup enum value (e.g., SubWorkingGroup.S4).
    Supports:
    - Short codes: S4, R1, C3
    - Full names: SA4, RAN1, CT3
    - Separators: SA-4, SA#4, SA 4
    - Plenary: RP, SP, CP, RAN PLENARY, etc.

    Args:
        alias: Subgroup alias or code

    Returns:
        Canonical subgroup enum value (e.g., SubWorkingGroup.S4)
    """
    input_str = alias.strip().upper()
    cleaned = re.sub(r"[#\-_\s]", "", input_str)

    # determine WorkingGroup first
    wg = normalize_working_group_alias(cleaned)

    # check if cleaned contains a _single_ number or the letter "P"
    match = re.search(r"(P|\d+)", cleaned)
    if not match:
        msg = f"Cannot parse/normalize subgroup format: {alias}"
        raise ValueError(msg)
    if len(match.groups()) != 1:
        msg = f"Multiple/ambiguous matches found when parsing subgroup: {alias}"
        raise ValueError(msg)

    return SubWorkingGroup.from_wg_and_nbr(wg, match.group(1))  # e.g., S4, R1, C3
