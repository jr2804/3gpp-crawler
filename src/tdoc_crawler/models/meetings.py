"""Meeting-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import field
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic.dataclasses import dataclass

from .base import DEFAULT_CACHE_DIR, BaseConfigModel, PortalCredentials, SortOrder, utc_now
from .crawl_limits import CrawlLimits, _new_crawl_limits
from .working_groups import WorkingGroup


class MeetingMetadata(BaseModel):
    """Structured metadata for a single 3GPP meeting."""

    meeting_id: int = Field(..., description="Unique meeting identifier from 3GPP portal")
    tbid: int = Field(..., description="Technical body ID (working group)")
    subtb: int | None = Field(None, description="Sub-technical body ID (subworking group)")
    working_group: WorkingGroup = Field(..., description="Working group owning the meeting")
    subgroup: str | None = Field(None, description="Sub group name (for display)")
    short_name: str = Field(..., description="Short name of the meeting (e.g., SA4#134)")
    title: str | None = Field(None, description="Descriptive title of the meeting")
    start_date: date | None = Field(None, description="Meeting start date")
    end_date: date | None = Field(None, description="Meeting end date")
    location: str | None = Field(None, description="Meeting location")
    files_url: str | None = Field(None, description="Direct link to meeting files on FTP")
    portal_url: str | None = Field(None, description="3GPP portal URL for the meeting")


@dataclass(frozen=True, slots=True)
class MeetingRecord:
    """SQLite row representation for a meeting entry."""

    meeting_id: int
    tbid: int
    subtb: int | None
    working_group: WorkingGroup
    subgroup: str | None
    short_name: str
    title: str | None
    start_date: date | None
    end_date: date | None
    location: str | None
    files_url: str | None
    portal_url: str | None
    last_synced: datetime = field(default_factory=utc_now)

    @classmethod
    def from_metadata(cls, metadata: MeetingMetadata) -> MeetingRecord:
        """Convert a meeting metadata model into a database row representation."""

        return cls(
            meeting_id=metadata.meeting_id,
            tbid=metadata.tbid,
            subtb=metadata.subtb,
            working_group=metadata.working_group,
            subgroup=metadata.subgroup,
            short_name=metadata.short_name,
            title=metadata.title,
            start_date=metadata.start_date,
            end_date=metadata.end_date,
            location=metadata.location,
            files_url=metadata.files_url,
            portal_url=metadata.portal_url,
        )


class MeetingCrawlConfig(BaseConfigModel):
    """Configuration for meeting crawling operations."""

    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DIR, description="Cache directory path")
    working_groups: list[WorkingGroup] = Field(
        default_factory=lambda: [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT],
        description="Working groups to crawl",
    )
    incremental: bool = Field(True, description="Only fetch updated meetings")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    timeout: int = Field(30, gt=0, description="HTTP timeout in seconds")
    verbose: bool = Field(False, description="Verbose logging")
    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")
    credentials: PortalCredentials | None = Field(None, description="Optional portal credentials")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup]) -> list[WorkingGroup]:
        """Ensure the working groups list only contains valid enum members."""

        normalized: list[WorkingGroup] = []
        for item in value:
            normalized.append(WorkingGroup(item) if not isinstance(item, WorkingGroup) else item)
        return normalized


class MeetingQueryConfig(BaseConfigModel):
    """Configuration for querying meeting metadata."""

    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DIR, description="Cache directory path")
    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
    subgroups: list[str] | None = Field(None, description="Filter by sub-working group")
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.DESC, description="Sort order applied to start date")
    include_without_files: bool = Field(False, description="Include meetings without associated files URL")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup] | None) -> list[WorkingGroup] | None:
        """Ensure the working group list is comprised of enum members."""

        if value is None:
            return None
        normalized: list[WorkingGroup] = []
        for item in value:
            normalized.append(WorkingGroup(item) if not isinstance(item, WorkingGroup) else item)
        return normalized

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names (uppercase and strip whitespace)."""

        if value is None:
            return None
        return [str(item).strip().upper() for item in value]


__all__ = [
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
    "MeetingRecord",
]
