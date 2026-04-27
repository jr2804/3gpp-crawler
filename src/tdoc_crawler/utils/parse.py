from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from packaging.version import Version

from tdoc_crawler.meetings.utils import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import expand_spec_ranges_batch

type AgendaItemNumber = str
type SpecificationVersionNumber = str


def parse_agenda_item_nbr(value: str | int | None) -> AgendaItemNumber:
    """Parse agenda item number as canonical string."""
    return str(parse_agenda_item_version(value))


def parse_agenda_item_version(value: str | int | None) -> Version:
    """Parse agenda item number as Version."""
    if value is None:
        return Version("0")
    return Version(str(value).strip())


def parse_spec_version_nbr(value: str | int | None) -> SpecificationVersionNumber:
    """Parse specification version as canonical three-part string."""
    return str(parse_spec_version(value))


def parse_spec_version(value: str | int | None) -> Version:
    """Parse specification version as Version, normalized to major.minor.patch."""
    if value is None:
        return Version("0.0.0")

    parsed = Version(str(value).strip())
    release_parts = list(parsed.release)

    if len(release_parts) >= 3:
        return Version(".".join(str(part) for part in release_parts[:3]))

    padded_parts = release_parts + [0] * (3 - len(release_parts))
    return Version(".".join(str(part) for part in padded_parts))


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


def infer_working_groups_from_ids(ids: Iterable[str]) -> list[WorkingGroup]:
    """Infer working groups from TDoc IDs based on first character."""
    mapping = {
        "R": WorkingGroup.RAN,
        "S": WorkingGroup.SA,
        "T": WorkingGroup.CT,
        "C": WorkingGroup.CT,
    }
    resolved: list[WorkingGroup] = []
    for value in ids:
        if not value:
            continue
        group = mapping.get(value[0].upper())
        if group and group not in resolved:
            resolved.append(group)
    return resolved
