"""Meeting-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from tdoc_crawler.meetings.utils import normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.models.base import BaseConfigModel, SortOrder
from tdoc_crawler.models.crawl_limits import CrawlLimits, _new_crawl_limits
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.misc import utc_now


class MeetingMetadata(BaseModel):
    """Persistent representation for a 3GPP meeting."""

    # parsed from the portal
    meeting_id: int = Field(..., description="Unique meeting identifier from the 3GPP portal")
    tbid: int = Field(
        ...,
        description="Technical body identifier of the parent working group (FK to working_groups.tbid)",
    )
    subtb: int | None = Field(
        ...,
        description="Sub-technical body identifier (FK to subworking_groups.subtb)",
    )
    short_name: str = Field(..., description="Short meeting name (e.g., SA4#134)")
    title: str | None = Field(None, description="Descriptive meeting title")
    start_date: date | None = Field(None, description="Meeting start date")
    end_date: date | None = Field(None, description="Meeting end date")
    location: str | None = Field(None, description="Meeting location")
    files_url: str | None = Field(None, description="HTTP directory containing meeting documents")
    portal_url: str | None = Field(None, description="Link to the portal meeting overview")

    # Crawling statistics
    tdoc_count: int = Field(0, ge=0, description="Number of TDocs associated with this meeting")

    # Database management fields
    last_synced: datetime = Field(default_factory=utc_now, description="Timestamp when the meeting was last refreshed")
    created_at: datetime = Field(default_factory=utc_now, description="Timestamp when the record was first stored")
    updated_at: datetime = Field(default_factory=utc_now, description="Timestamp when the record was last updated")

    @model_validator(mode="after")
    def _sync_relationships(self) -> MeetingMetadata:
        if self.subtb is None:
            return self
        record = SUBTB_INDEX.get(self.subtb)
        if record is None:
            return self
        if record.tbid != self.tbid:
            msg = "tbid does not match subworking group"
            raise ValueError(msg)
        return self


class MeetingCrawlConfig(BaseConfigModel):
    """Configuration for meeting crawling operations."""

    working_groups: list[WorkingGroup] = Field(
        default_factory=lambda: [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT],
        description="Working groups to crawl",
    )
    subgroups: list[str] | None = Field(None, description="Filter by sub-working groups (e.g., 'R1', 'SA4')")
    incremental: bool = Field(
        True,
        description=("When true, skip meetings already stored in the database (fetch only new meetings)."),
    )
    include_without_files: bool = Field(
        False,
        description="Include meetings without associated files URL (e.g., future meetings)",
    )
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    timeout: int = Field(30, gt=0, description="HTTP timeout in seconds")
    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup]) -> list[WorkingGroup]:
        """Ensure the working groups list only contains valid enum members."""
        return [normalize_working_group_alias(str(item)) if not isinstance(item, WorkingGroup) else item for item in value]

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names (uppercase and strip whitespace)."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).value for item in value]


class MeetingQueryConfig(BaseConfigModel):
    """Configuration for querying meeting metadata."""

    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
    subgroups: list[str] | None = Field(None, description="Filter by sub-working group")
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.DESC, description="Sort order applied to start date")
    include_without_files: bool = Field(False, description="Include meetings without associated files URL")
    # Date range filters
    start_date: date | None = Field(None, description="Filter meetings starting from this date")
    end_date: date | None = Field(None, description="Filter meetings ending before this date")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup] | None) -> list[WorkingGroup] | None:
        """Ensure the working group list is comprised of enum members."""
        if value is None:
            return None
        return [normalize_working_group_alias(str(item)) if not isinstance(item, WorkingGroup) else item for item in value]

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names (uppercase and strip whitespace)."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).value for item in value]


__all__ = [
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
]
