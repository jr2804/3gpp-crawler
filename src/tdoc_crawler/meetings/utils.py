"""Utility functions for meeting data normalization.

Note: normalize_portal_meeting_name is now centralized in tdoc_crawler.utils.normalization.
This module re-exports it for backward compatibility.
"""

from __future__ import annotations

import re

from tdoc_crawler.models.subworking_groups import SubWorkingGroup
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import normalize_portal_meeting_name


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
        if cleaned.startswith(working_group.value) or cleaned.startswith(working_group.name):
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

    raise ValueError(f"Unknown working group: {alias}")


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
        raise ValueError(f"Cannot parse/normalize subgroup format: {alias}")
    elif len(match.groups()) != 1:
        raise ValueError(f"Multiple/ambiguous matches found when parsing subgroup: {alias}")

    return SubWorkingGroup.from_wg_and_nbr(wg, match.group(1))  # e.g., S4, R1, C3


__all__ = [
    "normalize_portal_meeting_name",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
