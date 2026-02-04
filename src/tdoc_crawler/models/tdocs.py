"""TDoc-related data models and configurations."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import requests
from pydantic import BaseModel, Field, field_validator

from .base import DEFAULT_CACHE_DIR, BaseConfigModel, HttpCacheConfig, OutputFormat, PortalCredentials, SortOrder, _normalize_tdoc_ids, utc_now
from .crawl_limits import CrawlLimits, _new_crawl_limits
from .working_groups import WorkingGroup

_logger = logging.getLogger(__name__)


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

    # Optional metadata fields (from portal or determined otherwise)
    meeting_name: str | None = Field(None, description="Meeting name from portal (temporary, used for resolution)")
    is_revision_of: str | None = Field(None, description="Reference to a previous TDoc version")
    file_size: int | None = Field(None, description="File size in bytes, when available/downloaded")

    # fields for local database management
    date_created: datetime | None = Field(None, description="Original creation timestamp when provided")
    date_retrieved: datetime = Field(default_factory=utc_now, description="Timestamp of the last retrieval")
    date_updated: datetime = Field(default_factory=utc_now, description="Timestamp of the last database update")
    validated: bool = Field(False, description="Flag indicating successful portal validation")
    validation_failed: bool = Field(False, description="Flag indicating cached failed validation")

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

        try:
            # Use HEAD request to check accessibility without downloading
            response = requests.head(self.url, timeout=timeout, allow_redirects=True)

            # Check for successful response (2xx or 3xx)
            if response.status_code < 400:
                _logger.debug(f"URL accessible for {self.tdoc_id}: {self.url} (status {response.status_code})")
                return True
            else:
                _logger.warning(f"URL returned error for {self.tdoc_id}: {self.url} (status {response.status_code})")
                return False

        except requests.exceptions.Timeout:
            _logger.warning(f"URL validation timeout for {self.tdoc_id}: {self.url}")
            return False
        except requests.exceptions.ConnectionError as exc:
            _logger.warning(f"URL validation connection error for {self.tdoc_id}: {exc}")
            return False
        except requests.exceptions.RequestException as exc:
            _logger.warning(f"URL validation failed for {self.tdoc_id}: {exc}")
            return False

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        """Ensure identifiers are uppercase and trimmed."""
        return value.strip().upper()


class TDocCrawlConfig(BaseConfigModel):
    """Configuration for TDoc crawling runs."""

    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DIR, description="Cache directory path")
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
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    timeout: int = Field(30, gt=0, description="Request timeout seconds")
    verbose: bool = Field(False, description="Verbose logging")

    # New options for document list vs parallel crawling
    use_document_list: bool = Field(True, description="Use meeting document list (Excel) for metadata (no credentials required)")
    allow_parallel_fallback: bool = Field(True, description="Allow fallback to parallel directory crawling if document list fails")
    use_parallel_crawling: bool = Field(False, description="Force use of parallel directory crawling (requires credentials for validation)")

    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")
    target_ids: list[str] | None = Field(None, description="Specific TDoc identifiers to fetch")
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
        return _normalize_tdoc_ids(value)


class QueryConfig(BaseConfigModel):
    """Configuration for querying TDoc metadata."""

    cache_dir: Path = Field(default_factory=lambda: DEFAULT_CACHE_DIR, description="Cache directory path")
    output_format: OutputFormat = Field(OutputFormat.TABLE, description="Output format")
    tdoc_ids: list[str] | None = Field(None, description="TDoc IDs to query")
    working_groups: list[WorkingGroup] | None = Field(None, description="Filter by working group")
    start_date: datetime | None = Field(None, description="Start date filter")
    end_date: datetime | None = Field(None, description="End date filter")
    limit: int | None = Field(None, ge=1, description="Maximum results")
    order: SortOrder = Field(SortOrder.DESC, description="Sort order applied to date_retrieved")

    def __init__(self, **data: object) -> None:
        """Normalize identifiers and accept enum values from strings."""
        tdoc_ids = data.get("tdoc_ids")
        if tdoc_ids:
            if isinstance(tdoc_ids, str):
                data["tdoc_ids"] = _normalize_tdoc_ids([tdoc_ids])
            elif isinstance(tdoc_ids, Iterable):
                data["tdoc_ids"] = _normalize_tdoc_ids(tdoc_ids)

        output_format = data.get("output_format")
        if isinstance(output_format, str):
            data["output_format"] = OutputFormat(output_format.lower())
        super().__init__(**data)

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


# Legacy alias
CrawlConfig = TDocCrawlConfig

__all__ = [
    "CrawlConfig",
    "QueryConfig",
    "TDocCrawlConfig",
    "TDocMetadata",
]
