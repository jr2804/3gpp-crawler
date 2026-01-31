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

    @property
    def ftp_root(self) -> str:
        """Return the FTP root path segment for the working group."""
        return f"/tsg_{self.value.lower()}"

    @property
    def portal_meetings_code(self) -> str:
        """Return the meetings code (two characters) used for the dynareport endpoint."""
        mapping: dict[WorkingGroup, str] = {
            WorkingGroup.RAN: "R",
            WorkingGroup.SA: "S",
            WorkingGroup.CT: "C",
        }
        return mapping[self]


class WorkingGroupRecord(BaseModel):
    """Persistent representation of a working group reference entry."""

    tbid: int = Field(..., description="Technical body identifier")
    code: str = Field(..., description="Canonical short code (e.g., 'RAN')")
    name: str = Field(..., description="Display name for the working group")
    ftp_identifier: str = Field(..., description="FTP root path segment")


WORKING_GROUP_RECORDS: tuple[WorkingGroupRecord, ...] = (
    WorkingGroupRecord(tbid=WorkingGroup.RAN.tbid, code="RAN", name="RAN", ftp_identifier=WorkingGroup.RAN.ftp_root),
    WorkingGroupRecord(tbid=WorkingGroup.SA.tbid, code="SA", name="SA", ftp_identifier=WorkingGroup.SA.ftp_root),
    WorkingGroupRecord(tbid=WorkingGroup.CT.tbid, code="CT", name="CT", ftp_identifier=WorkingGroup.CT.ftp_root),
)


__all__ = ["WORKING_GROUP_RECORDS", "WorkingGroup", "WorkingGroupRecord"]
