"""Subworking group reference metadata."""

from __future__ import annotations

from enum import StrEnum
from functools import cache

from pydantic import BaseModel, Field

from tdoc_crawler.models.working_groups import WorkingGroup


class SubWorkingGroup(StrEnum):
    """Enumeration of canonical subgroup codes."""

    # SA working groups
    SP = "SA Plenary"
    S1 = "SA1"
    S2 = "SA2"
    S3 = "SA3"
    S4 = "SA4"
    S5 = "SA5"
    S6 = "SA6"

    # CT working groups
    CP = "CT Plenary"
    C1 = "CT1"
    C2 = "CT2"
    C3 = "CT3"
    C4 = "CT4"
    C5 = "CT5"
    C6 = "CT6"

    # RAN working groups
    RP = "RAN Plenary"
    R1 = "RAN1"
    R2 = "RAN2"
    R3 = "RAN3"
    R4 = "RAN4"
    R5 = "RAN5"
    R6 = "RAN6"

    @property
    def subtb(self) -> int:
        """Return the sub-technical body ID for this subgroup."""
        mapping: dict[SubWorkingGroup, int] = {
            SubWorkingGroup.SP: 375,
            SubWorkingGroup.S1: 384,
            SubWorkingGroup.S2: 385,
            SubWorkingGroup.S3: 386,
            SubWorkingGroup.S4: 387,
            SubWorkingGroup.S5: 388,
            SubWorkingGroup.S6: 825,
            SubWorkingGroup.CP: 649,
            SubWorkingGroup.C1: 651,
            SubWorkingGroup.C2: 652,
            SubWorkingGroup.C3: 653,
            SubWorkingGroup.C4: 654,
            SubWorkingGroup.C5: 655,
            SubWorkingGroup.C6: 656,
            SubWorkingGroup.RP: 373,
            SubWorkingGroup.R1: 379,
            SubWorkingGroup.R2: 380,
            SubWorkingGroup.R3: 381,
            SubWorkingGroup.R4: 382,
            SubWorkingGroup.R5: 657,
            SubWorkingGroup.R6: 843,
        }
        return mapping[self]

    @classmethod
    def from_wg_and_nbr(cls, wg: WorkingGroup, nbr: str | int) -> SubWorkingGroup:
        """Construct a SubWorkingGroup from a parent working group and subgroup number (or "P")."""
        code = f"{wg.value[0]}{str(nbr).upper()[0]}"
        try:
            return cls[code]
        except KeyError:
            raise ValueError(f"Unknown subgroup code: {code}") from None


class SubWorkingGroupRecord(BaseModel):
    """Persistent representation of a subworking group."""

    subtb: int = Field(..., description="Sub-technical body identifier")
    tbid: int = Field(..., description="Parent technical body identifier")
    code: str = Field(..., description="Canonical subgroup code (e.g., 'S4', 'RP')")
    name: str = Field(..., description="Display name of the subgroup")

    @property
    def working_group(self) -> WorkingGroup:
        """Return the parent working group enum for the record."""
        for working_group in WorkingGroup:
            if working_group.tbid == self.tbid:
                return working_group
        raise ValueError


@cache
def _generate_swb_group_records() -> tuple[SubWorkingGroupRecord, ...]:
    """Generate SubWorkingGroupRecord entries for all defined SubWorkingGroup enums."""
    records: list[SubWorkingGroupRecord] = []
    for subgroup in SubWorkingGroup:
        subtb = subgroup.subtb
        wg = subgroup.name[0]  # First character indicates parent WG (R, S, C)
        tbid = WorkingGroup.from_literal(wg).tbid
        record = SubWorkingGroupRecord(subtb=subtb, tbid=tbid, code=subgroup.name, name=subgroup.value)
        records.append(record)
    return tuple(records)


SUBWORKING_GROUP_RECORDS: tuple[SubWorkingGroupRecord, ...] = _generate_swb_group_records()

SUBTB_INDEX: dict[int, SubWorkingGroupRecord] = {record.subtb: record for record in SUBWORKING_GROUP_RECORDS}
CODE_INDEX: dict[str, SubWorkingGroupRecord] = {record.code.upper(): record for record in SUBWORKING_GROUP_RECORDS}


__all__ = [
    "CODE_INDEX",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "SubWorkingGroup",
    "SubWorkingGroupRecord",
]
