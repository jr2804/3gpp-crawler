"""TDoc-related data models and configurations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

import requests
from pydantic import BaseModel, Field, field_serializer, field_validator

from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import (
    BaseConfigModel,
    OutputFormat,
    SortOrder,
)
from tdoc_crawler.models.crawl_limits import CrawlLimits, _new_crawl_limits
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_tdoc_ids

_logger = get_logger(__name__)


class TDocStatus(StrEnum):
    """Enumeration of valid TDoc status values.

    These status values represent the lifecycle states of TDocs as reported
    by the 3GPP portal and should be used consistently throughout the application.
    Any status not in this enum will raise a ValueError during parsing.
    """

    RESERVED = "reserved"
    AVAILABLE = "available"
    REVISED = "revised"
    AGREED = "agreed"
    CONDITIONALLY_AGREED = "conditionally agreed"
    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally approved"
    PARTIALLY_APPROVED = "partially approved"
    TREATED = "treated"
    ENDORSED = "endorsed"
    REPLIED_TO = "replied to"
    MERGED = "merged"
    NOT_PURSUED = "not pursued"
    POSTPONED = "postponed"
    NOTED = "noted"
    NOT_CONCLUDED = "not concluded"
    WITHDRAWN = "withdrawn"
    REISSUED = "reissued"
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

        # Provide helpful error message with all valid values
        valid_values = [f"'{m.value}'" for m in cls]
        raise ValueError(f"Invalid TDoc status '{value}'. Expected one of: {', '.join(valid_values)}")


class TDocMetadata(BaseModel):
    """Persistent representation for a TDoc entry."""

    # Mandatory metadata fields from portal
    tdoc_id: str = Field(..., description="Unique TDoc identifier (case-normalized)")
    meeting_id: int = Field(..., description="Foreign key reference to the meetings table")
    title: str = Field(..., description="Document title as published on the portal")
    url: str | None = Field(None, description="Full URL to the TDoc resource, None if not available")
    source: str = Field(..., description="Contact person or organization")
    contact: str = Field(..., description="Contact person or organization")

    tdoc_type: str = Field("unknown", description="TDoc classification as reported by the portal")
    for_purpose: str = Field("unknown", description="Purpose of the contribution (agreement, information, etc.)")
    agenda_item_nbr: Decimal = Field(..., max_digits=3, decimal_places=1, description="Associated agenda item (numerical identifier)")
    agenda_item_text: str = Field("Unknown", description="Associated agenda item (text identifier)")
    status: str | None = Field(None, description="Document status as reported by the portal")

    @property
    def is_valid(self) -> bool:
        """Check if TDoc metadata is valid and downloadable.

        Validates:
        - tdoc_id is not empty
        - url is present and well-formed (not containing placeholder patterns like "/.../")

        Note: This does not actually download the file, only validates URL structure.
        URLs without explicit scheme (relative paths) are considered valid for checkout purposes.
        URL scheme validation (http/https/ftp) happens during download.
        """
        if not self.tdoc_id or not self.tdoc_id.strip():
            return False
        if not self.url or not self.url.strip():
            return False
        # Check for placeholder/corrupt URL patterns
        return not ("/.../" in self.url or "..." in self.url)

    @property
    def has_valid_url(self) -> bool:
        """Check if URL is present and valid (alias for is_valid)."""
        return self.is_valid

    def validate_url_accessible(self, timeout: int = 10) -> bool:
        """Validate that the URL is accessible via HTTP.

        Makes an HTTP HEAD request to check if the URL returns a successful
        status code (2xx or 3xx). This is a lightweight check that doesn't
        download the full file.

        Args:
            timeout: Request timeout in seconds (default: 10)

        Returns:
            True if URL is accessible (2xx/3xx status), False otherwise

        Note:
            Returns False for network errors, timeouts, or 4xx/5xx responses.
            Logs warnings for failed requests.
        """
        if not self.is_valid:
            _logger.debug(f"URL validation skipped for {self.tdoc_id}: basic validation failed")
            return False
        url = self.url
        if url is None:
            return False

        is_accessible = False
        try:
            # Use HEAD request to check accessibility without downloading
            response = requests.head(url, timeout=timeout, allow_redirects=True)

            # Check for successful response (2xx or 3xx)
            if response.status_code < 400:
                _logger.debug(f"URL accessible for {self.tdoc_id}: {url} (status {response.status_code})")
                is_accessible = True
            else:
                _logger.warning(f"URL returned error for {self.tdoc_id}: {url} (status {response.status_code})")

        except requests.exceptions.Timeout:
            _logger.warning(f"URL validation timeout for {self.tdoc_id}: {url}")
        except requests.exceptions.ConnectionError as exc:
            _logger.warning(f"URL validation connection error for {self.tdoc_id}: {exc}")
        except requests.exceptions.RequestException as exc:
            _logger.warning(f"URL validation failed for {self.tdoc_id}: {exc}")

        return is_accessible

    @classmethod
    @field_serializer("status")
    def _serialize_status(cls, value: TDocStatus | str | None) -> str | None:
        """Serialize TDocStatus enum to string for database storage."""
        if value is None:
            return None
        if isinstance(value, TDocStatus):
            return value.value
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, value: str | TDocStatus | None) -> str | None:
        """Validate and normalize status value against TDocStatus enum.

        Args:
            value: Status string or enum value

        Returns:
            Normalized status string (lowercase) or None

        Raises:
            ValueError: If status value is not in TDocStatus enum
        """
        if value is None:
            return None

        if isinstance(value, TDocStatus):
            return value.value

        # Let TDocStatus._missing_ handle validation and case-insensitive lookup
        return TDocStatus(value).value

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        """Ensure identifiers are uppercase and trimmed."""
        return value.strip().upper()

    # Optional metadata fields (from portal or determined otherwise)
    is_revision_of: str | None = Field(None, description="Reference to a previous TDoc version")
    file_size: int | None = Field(None, description="File size in bytes, when available/downloaded")

    # fields for local database management

    date_created: datetime | None = Field(None, description="Original creation timestamp when provided")
    date_retrieved: datetime = Field(default_factory=utc_now, description="Timestamp of the last retrieval")
    date_updated: datetime = Field(default_factory=utc_now, description="Timestamp of the last database update")
    validated: bool = Field(False, description="Flag indicating successful portal validation")
    validation_failed: bool = Field(False, description="Flag indicating cached failed validation")


class TDocCrawlConfig(BaseConfigModel):
    """Configuration for TDoc crawling runs."""

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
    overall_timeout: int | None = Field(
        None,
        ge=1,
        description="Maximum total crawl duration in seconds (None = unlimited). When exceeded remaining futures are cancelled and crawl ends early.",
    )
    timeout: int = Field(30, gt=0, description="Request timeout seconds")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")

    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")
    target_ids: list[str] | None = Field(None, description="Specific TDoc identifiers to fetch")

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
        """Normalize subgroup names to uppercase."""
        if value is None:
            return None
        return [str(item).upper().strip() for item in value]

    @field_validator("target_ids", mode="before")
    @classmethod
    def _normalize_target_ids(cls, value: Iterable[str] | None) -> list[str] | None:
        """Ensure target identifiers are normalized."""
        if value is None:
            return None
        return normalize_tdoc_ids(value)


class TDocQueryConfig(BaseConfigModel):
    """Configuration for querying TDoc metadata."""

    output_format: OutputFormat = Field(OutputFormat.TABLE, description="Output format")
    tdoc_ids: list[str] | None = Field(None, description="TDoc IDs to query")
    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
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
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.DESC, description="Sort order applied to date_retrieved")

    # TODO: normalization of tdoc name(s) is most likely done already several times in the project? Consider re-using existing utils function?
    @field_validator("tdoc_ids", mode="before")
    @classmethod
    def _normalize_tdoc_ids(cls, value: Iterable[str] | None) -> list[str] | None:
        """Normalize TDoc IDs to uppercase."""
        if value is None:
            return None
        return [str(item).upper() for item in value]

    @classmethod
    def _normalize_working_groups(cls, value: Iterable[str | WorkingGroup] | None) -> list[WorkingGroup] | None:
        """Ensure the working group list is comprised of enum members."""
        if value is None:
            return None
        normalized: list[WorkingGroup] = []
        for item in value:
            normalized.append(WorkingGroup(item) if not isinstance(item, WorkingGroup) else item)
        return normalized


__all__ = [
    "TDocCrawlConfig",
    "TDocMetadata",
    "TDocQueryConfig",
    "TDocStatus",
]
