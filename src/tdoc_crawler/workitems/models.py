"""3GPP work item catalogue models."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field, field_validator

from tdoc_crawler.utils.normalization import normalize_spec_number


class LeadBodyCoverage(TypedDict):
    """Coverage of one lead body in the global work item list."""

    lead_body: str
    """Sub-working group code the work items belong to."""

    list: int
    """Number of work items listed for that lead body."""

    in_catalogue: int
    """Number of listed work items that exist in the local catalogue."""

    missing: int
    """Number of listed work items missing from the local catalogue."""


class WorkItem(BaseModel):
    """A work item entry from a DynaReport per-working-group list.

    ``level`` is the WI level shown in the list title prefix
    (1 = feature/study item, 2 = building block, 3 = work task).
    """

    model_config = {"str_strip_whitespace": True}

    wi_id: str
    uid: int | None = Field(None, description="Portal work item unique ID (WorkItemDetails.aspx?workitemId=...)")
    title: str | None = None
    release: str | None = None
    status: str | None = None
    level: int | None = None
    parent_wi_id: str | None = None
    parent_uid: int | None = Field(None, description="Portal UID of the parent work item, from the details page")
    lead_body: str | None = Field(None, description="Sub-working group(s) leading the work item (e.g. 'S4')")
    spec_numbers: list[str] = Field(default_factory=list, description="Specifications impacted by the work item")

    @field_validator("wi_id", mode="before")
    @classmethod
    def _normalize_wi_id(cls, value: str) -> str:
        """Normalize work item IDs to uppercase."""
        return str(value).strip().upper()

    @field_validator("parent_wi_id", mode="before")
    @classmethod
    def _normalize_parent(cls, value: str | None) -> str | None:
        """Normalize the parent work item ID to uppercase."""
        if value is None:
            return None
        cleaned = str(value).strip().upper()
        return cleaned or None

    @field_validator("spec_numbers", mode="before")
    @classmethod
    def _normalize_specs(cls, value: object) -> list[str]:
        """Normalize specification numbers to their dotted form."""
        if value is None:
            return []
        items = [value] if isinstance(value, str) else value
        normalized: list[str] = []
        if not isinstance(items, list | tuple | set | frozenset):
            return normalized
        for item in items:
            candidate = str(item).strip()
            if not candidate:
                continue
            normalized.append(normalize_spec_number(candidate))
        return normalized


class WorkItemDetails(BaseModel):
    """Details of one work item parsed from WorkItemDetails.aspx."""

    model_config = {"str_strip_whitespace": True}

    uid: int
    wi_id: str
    title: str | None = None
    status: str | None = None
    release: str | None = None
    level: int | None = None
    parent_uid: int | None = None
    parent_title: str | None = None
    child_uids: list[int] = Field(default_factory=list)
    rapporteur: str | None = None

    @field_validator("wi_id", mode="before")
    @classmethod
    def _normalize_wi_id(cls, value: str) -> str:
        """Normalize work item IDs to uppercase."""
        return str(value).strip().upper()


class WorkItemCr(BaseModel):
    """A change request attributed to a work item, from a WiCr DynaReport page."""

    model_config = {"str_strip_whitespace": True}

    spec_number: str
    cr_number: str
    cr_revision: str | None = Field(None, description="Revision of the CR, e.g. '5' from '0002 rev 5'")
    cr_title: str | None = None

    @field_validator("spec_number", mode="before")
    @classmethod
    def _normalize_spec(cls, value: str) -> str:
        """Normalize the specification number to its dotted form."""
        return normalize_spec_number(str(value))

    @field_validator("cr_number", mode="before")
    @classmethod
    def _normalize_cr_number(cls, value: str) -> str:
        """Normalize the CR number to a zero-padded 4-digit string."""
        cleaned = str(value).strip()
        return cleaned.zfill(4) if cleaned.isdigit() else cleaned.upper()


__all__ = ["LeadBodyCoverage", "WorkItem", "WorkItemCr", "WorkItemDetails"]
