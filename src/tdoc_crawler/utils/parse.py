from __future__ import annotations

import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version

from tdoc_crawler.meetings.utils import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import expand_spec_ranges_batch
from tdoc_crawler.utils.version_types import AgendaItem, SpecVersion

type AgendaItemNumber = AgendaItem
type SpecificationVersionNumber = SpecVersion


def parse_agenda_item(value: str | int | None) -> AgendaItem:
    """Parse agenda item number as AgendaItem (Version subclass)."""
    if value is None:
        return AgendaItem("0")
    try:
        return AgendaItem(str(value).strip())
    except InvalidVersion:
        return AgendaItem("0")


# Backward-compatible aliases
parse_agenda_item_nbr = parse_agenda_item
parse_agenda_item_version = parse_agenda_item


def parse_spec_version(value: str | int | None) -> SpecVersion:
    """Parse specification version as SpecVersion (Version subclass).

    Normalizes to major.minor.patch.
    """
    if value is None:
        return SpecVersion("0.0.0")
    try:
        v = Version(str(value).strip())
    except InvalidVersion:
        return SpecVersion("0.0.0")
    parts = list(v.release) + [0] * (3 - len(v.release))
    return SpecVersion(".".join(str(p) for p in parts[:3]))


# Backward-compatible aliases
parse_spec_version_nbr = parse_spec_version


def infer_working_groups_from_subgroups(subgroups: list[str]) -> list[WorkingGroup]:
    """Infer working groups from subgroup codes.

    Args:
        subgroups: List of subgroup codes (e.g., ["S4", "R1"])

    Returns:
        List of inferred working groups without duplicates
    """
    working_groups: list[WorkingGroup] = []
    for subgroup in subgroups:
        if not subgroup:
            continue
        first_char = subgroup[0].upper()
        if first_char == "R":
            wg = WorkingGroup.RAN
        elif first_char == "S":
            wg = WorkingGroup.SA
        elif first_char == "C":
            wg = WorkingGroup.CT
        else:
            continue

        if wg not in working_groups:
            working_groups.append(wg)

    return working_groups


def parse_working_groups(values: list[str] | None, subgroups: list[str] | None = None) -> list[WorkingGroup]:
    """Parse and normalize working group names, expanding plenary aliases.

    Args:
        values: Explicit working group values from CLI
        subgroups: Optional subgroup list to infer working groups from

    Returns:
        List of working groups to crawl
    """
    if not values:
        if subgroups:
            return infer_working_groups_from_subgroups(subgroups)
        return [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]

    resolved: list[WorkingGroup] = []
    for item in values:
        normalized = normalize_working_group_alias(item)
        resolved.append(normalized)

    return resolved


def parse_subgroups(values: list[str] | None) -> list[str] | None:
    """Parse and normalize subgroup aliases to canonical subgroup codes."""
    if not values:
        return None

    resolved: list[str] = []
    for item in values:
        normalized = normalize_subgroup_alias(item)
        resolved.append(normalized.name)

    return resolved


def collect_spec_numbers(specs: list[str] | None, spec_file: Path | None) -> list[str]:
    """Collect spec numbers from CLI arguments or a file."""
    collected: list[str] = []

    if specs:
        for spec in specs:
            if spec == "-":
                for line in sys.stdin:
                    line_stripped = line.strip()
                    if line_stripped:
                        collected.append(line_stripped)
            else:
                collected.append(spec.strip())

    if spec_file and spec_file.exists():
        with spec_file.open("r", encoding="utf-8") as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped:
                    collected.append(line_stripped)

    if not collected:
        return []

    return expand_spec_ranges_batch(collected)
