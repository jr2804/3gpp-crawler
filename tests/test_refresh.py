"""Tests for the complete-metadata refresh command."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tdoc_crawler.cli import tdoc_app
from tdoc_crawler.config.settings import CrawlConfig
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.tdocs.models import TDocCrawlConfig
from tdoc_crawler.tdocs.operations.crawl import TDocCrawler, TDocCrawlResult
from tdoc_crawler.tdocs.operations.refresh import diff_tdoc, refresh_tdocs
from tdoc_crawler.utils.version_types import AgendaItem

from .conftest import MeetingRow, insert_sample_meetings_async

TODAY = date(2026, 11, 17)
RECENT_FILES_URL = "https://www.3gpp.org/ftp/tsg_sa/WG4_Core/SA4_138/Docs/"
OLD_FILES_URL = "https://www.3gpp.org/ftp/tsg_sa/WG4_Core/SA4_100/Docs/"


def _meeting(meeting_id: int, short_name: str, start: date, end: date, files_url: str) -> MeetingRow:
    return {
        "meeting_id": meeting_id,
        "tbid": 375,
        "subtb": 387,
        "short_name": short_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "location": None,
        "files_url": files_url,
    }


def _tdoc(tdoc_id: str, title: str, meeting_id: int, files_url: str = RECENT_FILES_URL) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=tdoc_id,
        tbid=375,
        url=f"{files_url}{tdoc_id}.zip",
        meeting_id=meeting_id,
        title=title,
        source="Test Source",
        contact="Test Contact",
        tdoc_type="Discussion",
        for_purpose="Discussion",
        agenda_item_nbr="6.1",
        agenda_item_text="Original agenda item",
        status="approved",
        is_revision_of="",
        date_created=datetime(2026, 11, 1, tzinfo=UTC),
        date_retrieved=datetime(2026, 11, 1, tzinfo=UTC),
    )


async def _insert_meetings(test_db_path: Path, meetings: list[MeetingRow]) -> None:
    async with MeetingDatabase(test_db_path) as database:
        await insert_sample_meetings_async(database, meetings)


def _setup_recent_db(test_db_path: Path) -> None:
    """Three SA meetings: one concluded recently, one ongoing, one too old."""
    meetings = [
        _meeting(1001, "SA4#138", TODAY - timedelta(days=5), TODAY - timedelta(days=1), RECENT_FILES_URL),
        _meeting(1002, "SA4#139", TODAY - timedelta(days=2), TODAY + timedelta(days=3), RECENT_FILES_URL),
        _meeting(1003, "SA4#100", TODAY - timedelta(days=40), TODAY - timedelta(days=35), OLD_FILES_URL),
    ]
    asyncio.run(_insert_meetings(test_db_path, meetings))
    asyncio.run(
        _insert_tdocs(
            test_db_path,
            [
                _tdoc("S4-250001", "Original title", 1001),
                _tdoc("S4-250002", "Unchanged title", 1001),
            ],
        )
    )


async def _insert_tdocs(test_db_path: Path, tdocs: list[TDocMetadata]) -> None:
    async with TDocDatabase(test_db_path) as database:
        for tdoc in tdocs:
            await database.upsert_tdoc(tdoc)


class TestDiffTdoc:
    """Field-level change detection."""

    def test_detects_meaningful_field_changes(self) -> None:
        before = _tdoc("S4-250001", "Old title", 1001)
        after = _tdoc("S4-250001", "New title", 1001)
        after.agenda_item_nbr = AgendaItem("7.2")

        changes = diff_tdoc(before, after)

        assert {change.field for change in changes} == {"title", "agenda_item_nbr"}
        title_change = next(change for change in changes if change.field == "title")
        assert title_change.old == "Old title"
        assert title_change.new == "New title"

    def test_ignores_local_bookkeeping_fields(self) -> None:
        before = _tdoc("S4-250001", "Title", 1001)
        after = _tdoc("S4-250001", "Title", 1001)
        after.date_updated = datetime(2026, 11, 17, tzinfo=UTC)
        after.file_size = 1234
        after.validated = True

        assert diff_tdoc(before, after) == ()


class TestLookbackWindow:
    """Meeting selection by start date."""

    def test_includes_concluded_meetings_but_not_old_ones(self, test_db_path: Path) -> None:
        _setup_recent_db(test_db_path)

        async def query() -> list:
            async with TDocDatabase(test_db_path) as database:
                return await TDocCrawler(database).get_meetings_to_crawl(
                    TDocCrawlConfig(working_groups=[WorkingGroup.SA], start_date=TODAY - timedelta(days=14))
                )

        meetings = asyncio.run(query())
        names = {meeting.short_name for meeting in meetings}

        assert names == {"SA4#138", "SA4#139"}
        assert "SA4#100" not in names

    def test_database_meeting_query_end_date_filters_end_date(self, test_db_path: Path) -> None:
        """Guard the documented quirk: local end_date filters START date."""
        _setup_recent_db(test_db_path)

        async def query() -> list:
            async with MeetingDatabase(test_db_path) as database:
                return await database.query_meetings(MeetingQueryConfig(working_groups=[WorkingGroup.SA], end_date=TODAY, order=SortOrder.ASC))

        # Both concluded meetings ended before today; the ongoing one ends after.
        assert {m.short_name for m in asyncio.run(query())} == {"SA4#138", "SA4#100"}


class TestRefreshTdocs:
    """End-to-end refresh with the network crawl stubbed out."""

    def test_reports_per_meeting_changes(self, test_db_path: Path) -> None:
        _setup_recent_db(test_db_path)

        async def fake_crawl(
            self: TDocCrawler,
            config: TDocCrawlConfig,
            progress_callback: Callable[[float, float], None] | None = None,
        ) -> TDocCrawlResult:
            async with TDocDatabase(test_db_path) as database:
                changed = _tdoc("S4-250001", "Updated title", 1001)
                changed.agenda_item_nbr = AgendaItem("7.1")
                await database.upsert_tdoc(changed)
                await database.upsert_tdoc(_tdoc("S4-250003", "Brand new", 1001))
            return TDocCrawlResult(processed=3, inserted=1, updated=1, errors=[])

        with patch.object(TDocCrawler, "crawl", new=fake_crawl):
            result = asyncio.run(
                refresh_tdocs(
                    TDocDatabase(test_db_path),
                    lookback_days=14,
                    working_groups=[WorkingGroup.SA],
                    today=TODAY,
                    repair_urls=False,
                    workers=1,
                )
            )

        assert result.lookback_days == 14
        assert result.start_date == TODAY - timedelta(days=14)
        assert result.meetings_scanned == 2
        assert result.tdocs_added == 1
        assert result.tdocs_changed == 1
        assert result.tdocs_unchanged == 1
        assert result.has_changes

        meeting = next(m for m in result.meetings if m.short_name == "SA4#138")
        assert meeting.tdocs_before == 2
        assert meeting.tdocs_after == 3
        assert "S4-250003" in meeting.added
        assert {change.tdoc_id for change in meeting.changed} == {"S4-250001"}
        assert {c.field for c in meeting.changed[0].field_changes} == {"title", "agenda_item_nbr"}
        assert meeting.unchanged == 1

        other = next(m for m in result.meetings if m.short_name == "SA4#139")
        assert not other.has_changes

    def test_repairs_and_persists_corrected_url(self, test_db_path: Path) -> None:
        _setup_recent_db(test_db_path)

        async def fake_crawl(
            self: TDocCrawler,
            config: TDocCrawlConfig,
            progress_callback: Callable[[float, float], None] | None = None,
        ) -> TDocCrawlResult:
            return TDocCrawlResult(processed=2, inserted=0, updated=0, errors=[])

        corrected = f"{RECENT_FILES_URL}S4-250001 %20.zip"

        def resolve(metadata: TDocMetadata) -> str | None:
            return corrected if metadata.tdoc_id == "S4-250001" else None

        with patch.object(TDocCrawler, "crawl", new=fake_crawl):
            result = asyncio.run(
                refresh_tdocs(
                    TDocDatabase(test_db_path),
                    lookback_days=14,
                    working_groups=[WorkingGroup.SA],
                    today=TODAY,
                    repair_urls=True,
                    resolve_url=resolve,
                    workers=2,
                )
            )

        assert result.urls_repaired == 1

        async def read_url() -> str | None:
            async with TDocDatabase(test_db_path) as database:
                record = await database._get_tdoc("S4-250001")
                assert record is not None
                return record.url

        assert asyncio.run(read_url()) == corrected

    def test_invalid_lookback_is_rejected(self, test_db_path: Path) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            asyncio.run(refresh_tdocs(TDocDatabase(test_db_path), lookback_days=0))


class TestRefreshConfig:
    """Configurable lookback default and override."""

    def test_default_is_14_days(self) -> None:
        assert CrawlConfig().refresh_lookback_days == 14

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TDC_REFRESH_LOOKBACK_DAYS", "30")
        assert CrawlConfig().refresh_lookback_days == 30


class TestRefreshCli:
    """CLI smoke tests."""

    def test_help(self) -> None:
        result = CliRunner().invoke(tdoc_app, ["refresh", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output
        assert "--no-repair-urls" in result.output
        assert "--output" in result.output

    def test_invalid_days_fails(self) -> None:
        result = CliRunner().invoke(tdoc_app, ["refresh", "--days", "0"])
        assert result.exit_code == 2
        assert "greater than or equal to 1" in result.output
