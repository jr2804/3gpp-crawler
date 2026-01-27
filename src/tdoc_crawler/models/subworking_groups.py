"""Subworking group reference metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .working_groups import WorkingGroup


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


SUBWORKING_GROUP_RECORDS: tuple[SubWorkingGroupRecord, ...] = (
    # SA working groups
    SubWorkingGroupRecord(subtb=375, tbid=WorkingGroup.SA.tbid, code="SP", name="SA Plenary"),
    SubWorkingGroupRecord(subtb=384, tbid=WorkingGroup.SA.tbid, code="S1", name="SA1"),
    SubWorkingGroupRecord(subtb=385, tbid=WorkingGroup.SA.tbid, code="S2", name="SA2"),
    SubWorkingGroupRecord(subtb=386, tbid=WorkingGroup.SA.tbid, code="S3", name="SA3"),
    SubWorkingGroupRecord(subtb=387, tbid=WorkingGroup.SA.tbid, code="S4", name="SA4"),
    SubWorkingGroupRecord(subtb=388, tbid=WorkingGroup.SA.tbid, code="S5", name="SA5"),
    SubWorkingGroupRecord(subtb=825, tbid=WorkingGroup.SA.tbid, code="S6", name="SA6"),
    # CT working groups
    SubWorkingGroupRecord(subtb=649, tbid=WorkingGroup.CT.tbid, code="CP", name="CT Plenary"),
    SubWorkingGroupRecord(subtb=651, tbid=WorkingGroup.CT.tbid, code="C1", name="CT1"),
    SubWorkingGroupRecord(subtb=652, tbid=WorkingGroup.CT.tbid, code="C2", name="CT2"),
    SubWorkingGroupRecord(subtb=653, tbid=WorkingGroup.CT.tbid, code="C3", name="CT3"),
    SubWorkingGroupRecord(subtb=654, tbid=WorkingGroup.CT.tbid, code="C4", name="CT4"),
    SubWorkingGroupRecord(subtb=655, tbid=WorkingGroup.CT.tbid, code="C5", name="CT5"),
    SubWorkingGroupRecord(subtb=656, tbid=WorkingGroup.CT.tbid, code="C6", name="CT6"),
    # RAN working groups
    SubWorkingGroupRecord(subtb=373, tbid=WorkingGroup.RAN.tbid, code="RP", name="RAN Plenary"),
    SubWorkingGroupRecord(subtb=379, tbid=WorkingGroup.RAN.tbid, code="R1", name="RAN1"),
    SubWorkingGroupRecord(subtb=380, tbid=WorkingGroup.RAN.tbid, code="R2", name="RAN2"),
    SubWorkingGroupRecord(subtb=381, tbid=WorkingGroup.RAN.tbid, code="R3", name="RAN3"),
    SubWorkingGroupRecord(subtb=382, tbid=WorkingGroup.RAN.tbid, code="R4", name="RAN4"),
    SubWorkingGroupRecord(subtb=657, tbid=WorkingGroup.RAN.tbid, code="R5", name="RAN5"),
    SubWorkingGroupRecord(subtb=843, tbid=WorkingGroup.RAN.tbid, code="R6", name="RAN6"),
)


SUBTB_INDEX: dict[int, SubWorkingGroupRecord] = {record.subtb: record for record in SUBWORKING_GROUP_RECORDS}
CODE_INDEX: dict[str, SubWorkingGroupRecord] = {record.code.upper(): record for record in SUBWORKING_GROUP_RECORDS}


__all__ = [
    "CODE_INDEX",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "SubWorkingGroupRecord",
]
