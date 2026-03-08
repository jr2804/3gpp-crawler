"""Working group enumeration and reference records."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class WorkingGroup(StrEnum):
    """Enumeration of supported 3GPP working groups."""

    RAN = "RAN"
    SA = "SA"
    CT = "CT"

    @property
    def tbid(self) -> int:
        """Return the technical body ID for this working group."""
        mapping: dict[WorkingGroup, int] = {
            WorkingGroup.RAN: 373,
            WorkingGroup.SA: 375,
            WorkingGroup.CT: 649,
        }
        return mapping[self]

    @classmethod
    def from_literal(cls, literal: str) -> WorkingGroup:
        """Parse a working group from first character of a user-provided literal string."""
        lit = literal.strip().upper()[0]
        for wg in list(WorkingGroup):
            if wg.name.startswith(lit):
                return wg

        raise ValueError(f"Unknown working group literal: {literal}")


class WorkingGroupRecord(BaseModel):
    """Persistent representation of a working group reference entry."""

    tbid: int = Field(..., description="Technical body identifier")
    code: str = Field(..., description="Canonical short code (e.g., 'RAN')")
    name: str = Field(..., description="Display name for the working group")


WORKING_GROUP_RECORDS: tuple[WorkingGroupRecord, ...] = tuple(WorkingGroupRecord(tbid=wg.tbid, code=wg.value, name=wg.value) for wg in list(WorkingGroup))

__all__ = ["WORKING_GROUP_RECORDS", "WorkingGroup", "WorkingGroupRecord"]
