"""TDoc-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from enum import StrEnum, auto

from pydantic import BaseModel, Field, field_validator

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.executors import ExecutorType
from tdoc_crawler.meetings.utils import normalize_subgroup_alias
from tdoc_crawler.models.base import (
    OutputFormat,
    SortKey,
    SortOrder,
)
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import normalize_tdoc_ids, normalize_working_group_list


class TDocStatus(StrEnum):
    """Enumeration of valid TDoc status values.

    These status values represent the lifecycle states of TDocs as reported
    by the 3GPP portal and should be used consistently throughout the application.
    Any status not in this enum will raise a ValueError during parsing.
    """

    RESERVED = auto()
    AVAILABLE = auto()
    REVISED = auto()
    AGREED = auto()
    CONDITIONALLY_AGREED = "conditionally agreed"
    APPROVED = auto()
    CONDITIONALLY_APPROVED = "conditionally approved"
    PARTIALLY_APPROVED = "partially approved"
    TREATED = auto()
    ENDORSED = auto()
    REPLIED_TO = "replied to"
    MERGED = auto()
    NOT_PURSUED = "not pursued"
    POSTPONED = auto()
    NOTED = auto()
    NOT_CONCLUDED = "not concluded"
    WITHDRAWN = auto()
    REISSUED = auto()
    NOT_TREATED = "not treated"

    @classmethod
    def _missing_(cls, value: object) -> TDocStatus | None:
        """Handle case-insensitive lookup and provide clear error messages.

        This method is called when a value cannot be found in the enum.
        It attempts case-insensitive matching first before raising an error.

        Args:
            value: The string value to look up

        Returns:
            The matching TDocStatus enum member

        Raises:
            ValueError: If the value doesn't match any known status (case-insensitive)
        """
        if isinstance(value, str):
            # Try case-insensitive match
            for member in cls:
                if member.value == value.lower():
                    return member

        # Return None for unknown statuses instead of raising
        return None


# TDocMetadata is defined in tdoc_crawler.database.oxyde_models.
# Import it from there directly:
#   from tdoc_crawler.database.oxyde_models import TDocMetadata


class TDocCrawlConfig(BaseModel):
    """Configuration for TDoc crawling runs."""

    model_config = {"str_strip_whitespace": True}

    working_groups: list[WorkingGroup] = Field(
        default_factory=lambda: [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT],
        description="Working groups to crawl",
    )
    subgroups: list[str] | None = Field(None, description="Filter by sub-working groups")
    meeting_ids: list[int] | None = Field(None, description="Filter by specific meeting IDs")
    start_date: date | None = Field(None, description="Filter meetings from this date")
    end_date: date | None = Field(None, description="Filter meetings until this date")
    incremental: bool = Field(True, description="Incremental crawl (only new items)")
    force_revalidate: bool = Field(False, description="Re-validate existing TDocs via portal")
    workers: int = Field(
        4,
        ge=1,
        le=16,
        description=(
            "Number of parallel workers. ProcessPoolExecutor (Python <3.14) "
            "has higher memory overhead than subinterpreters; "
            "consider lower worker counts on constrained systems."
        ),
    )
    executor: ExecutorType | None = Field(
        None,
        description=(
            "Executor type override: serial, threading, multiprocessing, or subinterpreter. "
            "None = auto (serial when workers=1, else the fastest available: threading without GIL, "
            "subinterpreter on 3.14+, otherwise multiprocessing). "
            "Use 'threading'/'subinterpreter' when child-process spawn is unsafe (e.g. stdio MCP server)."
        ),
    )
    overall_timeout: int | None = Field(
        None,
        ge=1,
        description="Maximum total crawl duration in seconds (None = unlimited). When exceeded remaining futures are cancelled and crawl ends early.",
    )
    timeout: int = Field(30, gt=0, description="Request timeout seconds")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    http_config: HttpConfig | None = Field(None, description="HTTP client configuration")

    limit_tdocs: int | None = Field(None, description="Maximum number of TDocs to crawl overall (negative = newest N)")
    limit_meetings: int | None = Field(None, description="Maximum meetings to crawl (negative = newest N)")
    limit_meetings_per_subwg: int | None = Field(None, description="Per sub-WG meeting limit")
    limit_subwgs: int | None = Field(None, description="Maximum sub-working groups to process")
    target_ids: list[str] | None = Field(None, description="Specific TDoc identifiers to fetch")

    @field_validator("working_groups", mode="before")
    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup]) -> list[WorkingGroup]:
        """Ensure the working groups list only contains valid enum members."""
        return normalize_working_group_list(value)

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup names to uppercase."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).value for item in value]

    @field_validator("target_ids", mode="before")
    @classmethod
    def _normalize_target_ids(cls, value: Iterable[str] | None) -> list[str] | None:
        """Ensure target identifiers are normalized."""
        if value is None:
            return None
        return normalize_tdoc_ids(value)


class TDocQueryConfig(BaseModel):
    """Configuration for querying TDoc metadata."""

    model_config = {"str_strip_whitespace": True}

    output_format: OutputFormat = Field(OutputFormat.TABLE, description="Output format")
    tdoc_ids: list[str] | None = Field(None, description="TDoc IDs to query")
    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
    subgroups: list[str] | None = Field(None, description="Filter by sub-working-group codes (e.g. 'S4', 'R1')")
    start_date: datetime | None = Field(None, description="Start date filter")
    end_date: datetime | None = Field(None, description="End date filter")
    # Meeting date filters (filter by associated meeting's dates)
    meeting_start_date: date | None = Field(None, description="Filter by meeting start date")
    meeting_end_date: date | None = Field(None, description="Filter by meeting end date")
    # Glob-style metadata filters (case-insensitive fnmatch)
    source_pattern: list[str] | None = Field(None, description="Glob pattern(s) for source field; multiple values are OR'd")
    source_pattern_exclude: list[str] | None = Field(None, description="Glob pattern(s) to exclude source field; multiple values are OR'd")
    title_pattern: list[str] | None = Field(None, description="Glob pattern(s) for title field; multiple values are OR'd")
    title_pattern_exclude: list[str] | None = Field(None, description="Glob pattern(s) to exclude title field; multiple values are OR'd")
    agenda_pattern: list[str] | None = Field(None, description="Glob pattern(s) for agenda_item_text field; multiple values are OR'd")
    agenda_pattern_exclude: list[str] | None = Field(None, description="Glob pattern(s) to exclude agenda_item_text field; multiple values are OR'd")
    tag: list[str] | None = Field(None, description="Tag filter: comma-separated values are OR-combined; repeated values are AND-combined")
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.ASC, description="Sort order (asc|desc)")
    sort_key: SortKey = Field(SortKey.MEETING_DATE, description="Sort key: meeting_date, reservation_date, uploaded_at, tdoc_id")

    @field_validator("tdoc_ids", mode="before")
    @classmethod
    def _normalize_tdoc_ids(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize TDoc IDs to uppercase."""
        if value is None:
            return None
        return normalize_tdoc_ids(value)

    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup] | None) -> list[WorkingGroup] | None:
        """Ensure the working group list is comprised of enum members."""
        if value is None:
            return None
        return normalize_working_group_list(value)

    @field_validator("subgroups", mode="before")
    @classmethod
    def _normalize_subgroups(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize subgroup aliases to canonical codes (``S4``, ``R1``)."""
        if value is None:
            return None
        return [normalize_subgroup_alias(str(item)).name for item in value]


__all__ = [
    "TDocCrawlConfig",
    "TDocQueryConfig",
    "TDocStatus",
]
