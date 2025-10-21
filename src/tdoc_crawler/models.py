"""Core data models and configuration primitives used across the CLI."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import field
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic.dataclasses import dataclass

DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"


def utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""

    return datetime.now(UTC)


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


class SubworkingGroup(BaseModel):
    """Metadata for a 3GPP subworking group."""

    subtb: int = Field(..., description="Sub-technical body ID (primary key)")
    tbid: int = Field(..., description="Parent technical body ID")
    working_group: WorkingGroup = Field(..., description="Parent working group")
    code: str = Field(..., description="Short code (e.g., 'S4', 'RP', 'C1')")
    name: str = Field(..., description="Full name (e.g., 'SA4', 'RAN Plenary', 'CT1')")


class OutputFormat(StrEnum):
    """Supported output formats for CLI responses."""

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class SortOrder(StrEnum):
    """Sort orders accepted by query operations."""

    ASC = "asc"
    DESC = "desc"


def _normalize_tdoc_ids(ids: Iterable[str]) -> list[str]:
    """Uppercase and strip whitespace from TDoc identifiers."""

    return [str(value).strip().upper() for value in ids]


class BaseConfigModel(BaseModel):
    """Shared configuration base enabling attribute parsing and whitespace handling."""

    model_config = {"str_strip_whitespace": True, "use_enum_values": False}


class PortalCredentials(BaseModel):
    """Credentials required for ETSI Online Account (EOL) protected resources."""

    username: str
    password: str


class TDocMetadata(BaseModel):
    """Metadata envelope for a single TDoc file."""

    tdoc_id: str = Field(..., description="Unique TDoc identifier (case-normalized)")
    url: str = Field(..., description="Full URL to TDoc file")
    working_group: WorkingGroup = Field(..., description="Working group")
    subgroup: str | None = Field(None, description="Subgroup identifier")
    meeting: str | None = Field(None, description="Meeting identifier")
    meeting_id: int | None = Field(None, description="Numeric meeting identifier")
    file_size: int | None = Field(None, description="File size in bytes")

    # Portal metadata fields
    title: str | None = Field(None, description="Document title from portal")
    contact: str | None = Field(None, description="Contact person/organization from portal")
    tdoc_type: str | None = Field(None, description="TDoc type classification from portal")
    for_purpose: str | None = Field(None, description="Purpose (agreement, discussion, information, etc.) from portal")
    agenda_item: str | None = Field(None, description="Associated agenda item from portal")
    status: str | None = Field(None, description="Document status from portal")
    is_revision_of: str | None = Field(None, description="Reference to previous TDoc version from portal")

    # Legacy fields
    document_type: str | None = Field(None, description="Document type")
    checksum: str | None = Field(None, description="Checksum of downloaded file")
    source_path: str | None = Field(None, description="Relative FTP path of the document")
    date_created: datetime | None = Field(None, description="Document creation date")
    date_retrieved: datetime = Field(default_factory=utc_now, description="When metadata was last retrieved")
    validated: bool = Field(False, description="Whether TDoc was validated via portal")
    validation_failed: bool = Field(False, description="Whether portal validation failed (cached negative result)")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        """Ensure identifiers are uppercase and trimmed."""

        return value.strip().upper()

    @field_validator("source_path")
    @classmethod
    def _normalize_source_path(cls, value: str | None) -> str | None:
        """Ensure FTP paths use forward slashes and no trailing slash."""

        if value is None:
            return None
        normalized = value.replace("\\", "/").strip()
        return normalized.rstrip("/") if normalized else None


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
    portal_url: str | None = Field(None, description="3GPP portal URL for the meeting")


@dataclass(frozen=True, slots=True)
class TDocRecord:
    """SQLite row representation for a TDoc entry."""

    tdoc_id: str
    url: str
    working_group: WorkingGroup
    subgroup: str | None = None
    meeting: str | None = None
    meeting_id: int | None = None
    file_size: int | None = None
    title: str | None = None
    contact: str | None = None
    tdoc_type: str | None = None
    for_purpose: str | None = None
    agenda_item: str | None = None
    status: str | None = None
    is_revision_of: str | None = None
    document_type: str | None = None
    checksum: str | None = None
    source_path: str | None = None
    date_created: datetime | None = None
    date_retrieved: datetime = field(default_factory=utc_now)
    date_updated: datetime = field(default_factory=utc_now)
    validated: bool = False
    validation_failed: bool = False

    @classmethod
    def from_metadata(cls, metadata: TDocMetadata) -> TDocRecord:
        """Convert a validated metadata model into a database record."""

        return cls(
            tdoc_id=metadata.tdoc_id,
            url=metadata.url,
            working_group=metadata.working_group,
            subgroup=metadata.subgroup,
            meeting=metadata.meeting,
            meeting_id=metadata.meeting_id,
            file_size=metadata.file_size,
            title=metadata.title,
            contact=metadata.contact,
            tdoc_type=metadata.tdoc_type,
            for_purpose=metadata.for_purpose,
            agenda_item=metadata.agenda_item,
            status=metadata.status,
            is_revision_of=metadata.is_revision_of,
            document_type=metadata.document_type,
            checksum=metadata.checksum,
            source_path=metadata.source_path,
            date_created=metadata.date_created,
            date_retrieved=metadata.date_retrieved,
            date_updated=utc_now(),
            validated=metadata.validated,
            validation_failed=metadata.validation_failed,
        )


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


class CrawlLimits(BaseConfigModel):
    """Limitations applied during crawl operations."""

    limit_tdocs: int | None = Field(
        None,
        description="Maximum number of TDocs to crawl overall (negative for newest N)",
    )
    limit_meetings: int | None = Field(
        None,
        description="Maximum meetings to crawl overall (negative for newest N)",
    )
    limit_meetings_per_wg: int | None = Field(
        None,
        description="Per working group meeting limit",
    )
    limit_wgs: int | None = Field(None, description="Maximum number of working groups to process")


def _new_crawl_limits() -> CrawlLimits:
    """Return an empty crawl limits instance for Field default factories."""

    return CrawlLimits(
        limit_tdocs=None,
        limit_meetings=None,
        limit_meetings_per_wg=None,
        limit_wgs=None,
    )


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
    workers: int = Field(4, ge=1, le=16, description="Number of parallel workers")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    timeout: int = Field(30, gt=0, description="Request timeout seconds")
    verbose: bool = Field(False, description="Verbose logging")
    limits: CrawlLimits = Field(default_factory=_new_crawl_limits, description="Crawl limit parameters")
    target_ids: list[str] | None = Field(None, description="Specific TDoc identifiers to fetch")
    credentials: PortalCredentials | None = Field(None, description="Optional portal credentials")

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


CrawlConfig = TDocCrawlConfig


__all__ = [
    "DEFAULT_CACHE_DIR",
    "CrawlConfig",
    "CrawlLimits",
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
    "MeetingRecord",
    "OutputFormat",
    "PortalCredentials",
    "QueryConfig",
    "SortOrder",
    "TDocCrawlConfig",
    "TDocMetadata",
    "TDocRecord",
    "WorkingGroup",
]


if __name__ == "__main__":
    pass
# end of file
