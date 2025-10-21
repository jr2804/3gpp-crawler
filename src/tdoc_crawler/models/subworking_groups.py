"""Subworking group metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .working_groups import WorkingGroup


class SubworkingGroup(BaseModel):
    """Metadata for a 3GPP subworking group."""

    subtb: int = Field(..., description="Sub-technical body ID (primary key)")
    tbid: int = Field(..., description="Parent technical body ID")
    working_group: WorkingGroup = Field(..., description="Parent working group")
    code: str = Field(..., description="Short code (e.g., 'S4', 'RP', 'C1')")
    name: str = Field(..., description="Full name (e.g., 'SA4', 'RAN Plenary', 'CT1')")


__all__ = ["SubworkingGroup"]
