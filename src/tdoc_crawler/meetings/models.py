"""Meeting-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, Field, field_validator

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.meetings.utils import normalize_subgroup_alias
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import normalize_working_group_list


class MeetingCrawlConfig(BaseModel):
    """Configuration for meeting crawling operations."""

    model_config = {"str_strip_whitespace": True}

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
    http_config: HttpConfig | None = Field(None, description="HTTP client configuration")
    limit_meetings: int | None = Field(None, description="Maximum meetings to crawl overall (negative = newest N)")
    limit_meetings_per_subwg: int | None = Field(None, description="Per sub-working group meeting limit")
    limit_subwgs: int | None = Field(None, description="Maximum number of sub-working groups to process")
    start_date: date | None = Field(None, description="Only crawl meetings starting from this date")
    end_date: date | None = Field(None, description="Only crawl meetings ending before this date")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup]) -> list[WorkingGroup]:
        """Ensure the working groups list only contains valid enum members."""
        return normalize_working_group_list(value)

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names (uppercase and strip whitespace)."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).name for item in value]


class MeetingQueryConfig(BaseModel):
    """Configuration for querying meeting metadata."""

    model_config = {"str_strip_whitespace": True}

    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
    subgroups: list[str] | None = Field(None, description="Filter by sub-working group")
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.DESC, description="Sort order applied to start date")
    include_without_files: bool = Field(False, description="Include meetings without associated files URL")
    start_date: date | None = Field(None, description="Filter meetings starting from this date")
    end_date: date | None = Field(None, description="Filter meetings ending before this date")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup] | None) -> list[WorkingGroup] | None:
        """Ensure the working group list is comprised of enum members."""
        if value is None:
            return None
        return normalize_working_group_list(value)

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names (uppercase and strip whitespace)."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).name for item in value]


__all__ = [
    "MeetingCrawlConfig",
    "MeetingQueryConfig",
]
