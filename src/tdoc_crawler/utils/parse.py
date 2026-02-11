from __future__ import annotations

import sys
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import click
import typer

from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.utils import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import expand_spec_ranges_batch

_logger = get_logger(__name__)


def parse_agenda_item_nbr(value: Any) -> Decimal:
    """Parse agenda item number as Decimal with fallback to zero."""
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        _logger.warning(f"Invalid agenda item number '{value}': {exc}")
        return Decimal(0)


def infer_working_groups_from_subgroups(subgroups: list[str]) -> list[WorkingGroup]:
    """Infer working groups from subgroup codes.

    Args:
        subgroups: List of subgroup codes (e.g., ["S4", "R1"])

    Returns:
        List of inferred working groups without duplicates
    """
    working_groups: list[WorkingGroup] = []
    for subgroup in subgroups:
        # Extract first character to determine working group
        if subgroup and len(subgroup) >= 1:
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

    return working_groups if working_groups else [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]


def parse_working_groups(values: list[str] | None, subgroups: list[str] | None = None) -> list[WorkingGroup]:
    """Parse and normalize working group names, expanding plenary aliases.

    Args:
        values: Explicit working group values from CLI
        subgroups: Optional subgroup list to infer working groups from

    Returns:
        List of working groups to crawl
    """
    if not values:
        # If subgroups are specified but no explicit working groups, infer from subgroups
        if subgroups:
            return infer_working_groups_from_subgroups(subgroups)
        # Otherwise default to all working groups
        return [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]
    resolved: list[WorkingGroup] = []
    for item in values:
        # Try alias normalization first (RP->RAN, SP->SA, CP->CT)
        normalized = normalize_working_group_alias(item)
        try:
            resolved.append(WorkingGroup(normalized.upper()))
        except ValueError as exc:
            _logger.warning(f"Unknown working group: {item}")
            raise typer.Exit(code=2) from exc
    if not resolved:
        _logger.warning("No valid working groups specified")
        raise typer.Exit(code=2)
    return resolved


def parse_subgroups(values: list[str] | None) -> list[str] | None:
    """Parse and normalize subgroup aliases to canonical names."""
    if not values:
        return None

    resolved: list[str] = []
    for item in values:
        normalized = normalize_subgroup_alias(item)
        if not normalized:
            _logger.warning(f"Unknown subgroup: {item}")
            raise typer.Exit(code=2)
        resolved.extend(normalized)

    return resolved


def collect_spec_numbers(specs: list[str] | None, spec_file: Path | None) -> list[str]:
    """Collect spec numbers from CLI arguments or a file."""
    collected: list[str] = []

    if specs:
        for spec in specs:
            if spec == "-":
                # Read from stdin
                for line in sys.stdin:
                    line_stripped = line.strip()
                    if line_stripped:
                        collected.append(line_stripped)
            else:
                collected.append(spec.strip())

    if spec_file and spec_file.exists():
        try:
            with spec_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line_stripped = line.strip()
                    if line_stripped:
                        collected.append(line_stripped)
        except OSError as exc:
            raise click.FileError(str(spec_file), hint=f"Cannot read spec file: {exc}")

    if not collected:
        return []

    try:
        expanded = expand_spec_ranges_batch(collected)
    except ValueError as e:
        raise click.UsageError(str(e))

    return expanded


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
    return resolved or [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]
