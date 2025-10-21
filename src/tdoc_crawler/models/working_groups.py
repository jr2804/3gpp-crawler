"""Working group enumeration and properties."""

from __future__ import annotations

from enum import StrEnum


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


__all__ = ["WorkingGroup"]
