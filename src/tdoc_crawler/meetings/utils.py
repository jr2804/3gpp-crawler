"""Utility functions for meeting data normalization."""

from __future__ import annotations

from tdoc_crawler.constants.registry import MEETING_CODE_REGISTRY


def normalize_working_group_alias(alias: str) -> str:
    """Normalize working group aliases to canonical names.

    Supports: RP→RAN, SP→SA, CP→CT, and their reverse mappings.

    Args:
        alias: Working group alias or name

    Returns:
        Normalized working group name (RAN, SA, or CT)
    """
    alias_upper = alias.strip().upper()
    # Plenary aliases
    if alias_upper in ("RP", "RAN PLENARY"):
        return "RAN"
    if alias_upper in ("SP", "SA PLENARY"):
        return "SA"
    if alias_upper in ("CP", "CT PLENARY"):
        return "CT"
    # Standard working groups
    if alias_upper in ("RAN", "SA", "CT"):
        return alias_upper
    # If not recognized, return as-is (will be validated later)
    return alias_upper


def normalize_subgroup_alias(alias: str) -> list[str]:
    """Normalize subgroup aliases to canonical names.

    Returns a list of possible matching subgroup names.
    Supports:
    - Short codes: S4, R1, C3
    - Full names: SA4, RAN1, CT3
    - Plenary codes: RP, SP, CP
    - Full plenary names: RAN PLENARY, SA PLENARY, CT PLENARY

    Args:
        alias: Subgroup alias or code

    Returns:
        List of possible matching canonical subgroup names
    """
    alias_upper = alias.strip().upper()
    matches: list[str] = []

    # Try to normalize long form to short form (SA4 → S4, RAN1 → R1, CT3 → C3)
    normalized_alias = alias_upper
    if alias_upper.startswith("SA") and len(alias_upper) > 2:
        # SA4 → S4, SA1 → S1, etc.
        normalized_alias = "S" + alias_upper[2:]
    elif alias_upper.startswith("RAN") and len(alias_upper) > 3:
        # RAN1 → R1, RAN2 → R2, etc.
        normalized_alias = "R" + alias_upper[3:]
    elif alias_upper.startswith("CT") and len(alias_upper) > 2:
        # CT1 → C1, CT2 → C2, etc.
        normalized_alias = "C" + alias_upper[2:]

    # Check all registries for matches
    for _working_group, codes in MEETING_CODE_REGISTRY.items():
        for code, subgroup in codes:
            # Check if normalized alias matches the code
            if code.upper() == normalized_alias or code.upper() == alias_upper:
                if subgroup:
                    matches.append(subgroup)
            # Check if subgroup name matches
            elif subgroup and subgroup.upper() == alias_upper:
                matches.append(subgroup)

    # If no matches found, return the original alias (might be exact name)
    if not matches:
        matches.append(alias_upper)

    return matches


__all__ = [
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
