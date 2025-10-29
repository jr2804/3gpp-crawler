"""Meeting-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import DEFAULT_CACHE_DIR, BaseConfigModel, HttpCacheConfig, PortalCredentials, SortOrder, utc_now
from .crawl_limits import CrawlLimits, _new_crawl_limits
from .subworking_groups import CODE_INDEX, SUBTB_INDEX
from .working_groups import WorkingGroup


class MeetingMetadata(BaseModel):
    """Persistent representation for a 3GPP meeting."""

    # parsed from the portal
    meeting_id: int = Field(..., description="Unique meeting identifier from the 3GPP portal")
    tbid: int = Field(..., description="Technical body identifier of the parent working group")
    subtb: int | None = Field(..., description="Sub-technical body identifier of the subworking group")
    working_group: str | None = Field(None, description="Working group (as string, e.g., 'SA')")
    subgroup: str | None = Field(None, description="Canonical subgroup code (e.g., 'R1')")
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

    @field_validator("working_group", mode="before")
    @classmethod
    def _validate_working_group(cls, value):
        if value is None:
            return None
        # Accept enum or str, store as str
        if isinstance(value, WorkingGroup):
            return value.value
        if value not in {wg.value for wg in WorkingGroup}:
            raise ValueError(f"Invalid working_group: {value}")
        return value

    @field_validator("subgroup", mode="before")
    @classmethod
    def _normalize_subgroup(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def _sync_relationships(self) -> MeetingMetadata:
        # working_group is now a string, so match tbid if not set
        if self.working_group is None:
            for working_group in WorkingGroup:
                if working_group.tbid == self.tbid:
                    self.working_group = working_group.value
                    break
        else:
            # Validate tbid matches working_group
            try:
                wg = WorkingGroup(self.working_group)
            except Exception:
                raise ValueError(f"Invalid working_group: {self.working_group}")
            if wg.tbid != self.tbid:
                msg = "tbid does not match provided working_group"
                raise ValueError(msg)

        if self.subtb is None and self.subgroup:
            record = CODE_INDEX.get(self.subgroup)
            if record is not None:
                self.subtb = record.subtb

        if self.subgroup is None and self.subtb is not None:
            record = SUBTB_INDEX.get(self.subtb)
            if record is not None:
                self.subgroup = record.code

        return self


class MeetingCrawlConfig(BaseConfigModel):
    """Configuration for meeting crawling operations."""

    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DIR, description="Cache directory path")
    working_groups: list[WorkingGroup] = Field(
        default_factory=lambda: [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT],
        description="Working groups to crawl",
    )
    subgroups: list[str] | None = Field(None, description="Filter by sub-working groups (e.g., 'R1', 'SA4')")
    incremental: bool = Field(True, description="Only fetch updated meetings")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    timeout: int = Field(30, gt=0, description="HTTP timeout in seconds")
    verbose: bool = Field(False, description="Verbose logging")
    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")
    credentials: PortalCredentials | None = Field(None, description="Optional portal credentials")
    http_cache: HttpCacheConfig = Field(default_factory=HttpCacheConfig, description="HTTP cache configuration")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup]) -> list[WorkingGroup]:
        """Ensure the working groups list only contains valid enum members."""

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
]
