"""Oxyde ORM models for database persistence.

This module contains all ORM models using Oxyde for database storage.
These models replace the previous pydantic-sqlite based persistence layer.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from oxyde import Field, Model
from pydantic import field_validator

from tdoc_crawler.utils.json_types import JSONValue, coerce_json_value
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.version_types import AgendaItem, SpecVersion


class WorkingGroupRecord(Model):
    """Reference data for working groups."""

    tbid: int = Field(db_pk=True)
    code: str
    name: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class SubWorkingGroupRecord(Model):
    """Reference data for subworking groups."""

    subtb: int = Field(db_pk=True)
    tbid: int
    code: str
    name: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class CrawlLogEntry(Model):
    """Log entry for crawl operations."""

    log_id: str = Field(db_pk=True)
    crawl_type: str
    start_time: datetime
    end_time: datetime | None = None
    working_groups: list[str] = Field(default_factory=list)
    incremental: bool = Field(default=False)
    items_added: int = Field(default=0, ge=0)
    items_updated: int = Field(default=0, ge=0)
    errors_count: int = Field(default=0, ge=0)
    status: str = Field(default="RUNNING")
    created_at: datetime = Field(default_factory=utc_now)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class TagEntry(Model):
    """Tag attached to an item (polymorphic: kind + item_id is the pointer)."""

    tag_id: str = Field(db_pk=True)
    kind: str
    item_id: str
    tag: str
    created_at: datetime = Field(default_factory=utc_now)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class MeetingMetadata(Model):
    """Metadata for 3GPP meetings."""

    meeting_id: int = Field(db_pk=True)
    tbid: int
    subtb: int | None = None
    short_name: str
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    location: str | None = None
    files_url: str | None = None
    portal_url: str | None = None
    tdoc_count: int = Field(default=0, ge=0)
    last_synced: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class MeetingAgendaItem(Model):
    """One agenda item of a meeting, including parent items without documents."""

    link_id: str = Field(db_pk=True)
    meeting_id: int
    agenda_nbr: str
    agenda_text: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class TDocMetadata(Model):
    """Metadata for TDoc documents."""

    tdoc_id: str = Field(db_pk=True)
    meeting_id: int
    tbid: int | None = None
    title: str
    url: str | None = None
    source: str
    contact: str
    tdoc_type: str = Field(default="unknown")
    for_purpose: str = Field(default="unknown")
    agenda_item_nbr: AgendaItem
    agenda_item_text: str = Field(default="Unknown")
    status: str | None = None
    is_revision_of: str | None = None
    spec_number: str | None = None
    release: str | None = None
    cr_number: str | None = None
    cr_category: str | None = None
    file_size: int | None = None
    date_created: datetime | None = None
    date_retrieved: datetime = Field(default_factory=utc_now)
    date_updated: datetime = Field(default_factory=utc_now)
    reservation_date: datetime | None = None
    uploaded_at: datetime | None = None
    validated: bool = Field(default=False)
    validation_failed: bool = Field(default=False)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class WorkItemRecord(Model):
    """3GPP work item taken from DynaReport lists and TDoc document lists."""

    wi_id: str = Field(db_pk=True)
    uid: int | None = None
    title: str | None = None
    release: str | None = None
    status: str | None = None
    level: int | None = None
    parent_wi_id: str | None = None
    parent_uid: int | None = None
    lead_body: str | None = Field(None, description="Lead sub-working group(s), comma separated (e.g. 'S4')")
    tdoc_count: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=utc_now)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class WorkItemSpecRecord(Model):
    """Link between a work item and a specification it impacts."""

    link_id: str = Field(db_pk=True)
    wi_id: str
    spec_number: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class WorkItemCrRecord(Model):
    """Change request attributed to a work item (WiCr DynaReport page)."""

    link_id: str = Field(db_pk=True)
    wi_id: str
    spec_number: str
    cr_number: str
    cr_revision: str | None = None
    cr_title: str | None = None

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class TDocWorkItem(Model):
    """Link between a TDoc and a work item it relates to."""

    link_id: str = Field(db_pk=True)
    tdoc_id: str
    wi_id: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class Specification(Model):
    """Canonical specification identity and metadata."""

    spec_number: str = Field(db_pk=True)
    spec_number_compact: str
    spec_type: str
    title: str
    status: str
    working_group: str
    series: str
    latest_version: SpecVersion | None = None

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class SpecificationSourceRecord(Model):
    """Source-specific metadata snapshot for specifications."""

    record_id: str = Field(db_pk=True)
    spec_number: str
    source_name: str
    source_identifier: str | None = None
    metadata_payload: dict[str, JSONValue] = Field(default_factory=dict)
    versions: list[SpecVersion] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @field_validator("metadata_payload", mode="before")
    @classmethod
    def _parse_metadata_payload(cls, value: dict[str, JSONValue] | str) -> dict[str, JSONValue]:
        if isinstance(value, str):
            try:
                parsed = coerce_json_value(json.loads(value))
            except (json.JSONDecodeError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return value

    @field_validator("versions", mode="before")
    @classmethod
    def _parse_versions(cls, value: list[str | SpecVersion] | str) -> list[SpecVersion]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return [SpecVersion(str(item)) for item in parsed] if isinstance(parsed, list) else []
        return [SpecVersion(str(item)) for item in value]

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class SpecificationVersion(Model):
    """Version details for specifications."""

    record_id: str = Field(db_pk=True)
    spec_number: str
    version: SpecVersion
    file_name: str
    source_name: str

    class Meta:
        """Oxyde table configuration."""

        is_table = True


class ArchiveMember(Model):
    """One file inside a TDoc or spec zip (kind + item_id is the pointer, no FK)."""

    member_id: str = Field(db_pk=True)
    kind: str
    item_id: str
    archive_name: str
    member_path: str
    file_size: int | None = None
    is_clutter: bool = Field(default=False)
    classification: str | None = None
    recorded_at: datetime = Field(default_factory=utc_now)

    class Meta:
        """Oxyde table configuration."""

        is_table = True


__all__ = [
    "ArchiveMember",
    "CrawlLogEntry",
    "MeetingAgendaItem",
    "MeetingMetadata",
    "Specification",
    "SpecificationSourceRecord",
    "SpecificationVersion",
    "SubWorkingGroupRecord",
    "TDocMetadata",
    "TagEntry",
    "WorkingGroupRecord",
]
