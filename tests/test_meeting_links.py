"""Tests for meeting filtering and automatic meeting linkage of fetched TDocs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.parsers.portal import PortalParsingError
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.crawl import MeetingPatternError, TDocCrawlResult, filter_meetings_by_patterns
from tdoc_crawler.tdocs.operations.fetch import (
    ensure_meeting_links,
    fetch_missing_tdocs,
    fetch_via_portal_url_batch,
)
from tdoc_crawler.utils.parse import parse_agenda_item_nbr

DOCS_SA4_138 = "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_138/Docs/"
TDOC_URL = f"{DOCS_SA4_138}S4-251501.zip"


def _meeting(meeting_id: int, short_name: str, files_url: str | None, subtb: int = 379) -> MeetingMetadata:
    """Build a minimal meeting row."""
    return MeetingMetadata(
        meeting_id=meeting_id,
        tbid=373,
        subtb=subtb,
        short_name=short_name,
        title=None,
        start_date=None,
        end_date=None,
        location=None,
        files_url=files_url,
        portal_url=None,
        tdoc_count=0,
    )


def _tdoc(tdoc_id: str, *, url: str | None, meeting_id: int = 0) -> TDocMetadata:
    """Build a minimal TDoc row."""
    return TDocMetadata(
        tdoc_id=tdoc_id,
        meeting_id=meeting_id,
        title="",
        source="",
        contact="",
        agenda_item_nbr=parse_agenda_item_nbr("0"),
        url=url,
    )


MEETINGS = [
    _meeting(12345, "SA4#138", DOCS_SA4_138),
    _meeting(12346, "SA4#139", "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_139/Docs/"),
    _meeting(12347, "RAN1#98", "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/"),
]


class TestFilterMeetingsByPatterns:
    """``--meeting`` accepts portal spellings, normalized names, wildcards, ids."""

    def test_accepts_portal_short_name(self) -> None:
        matched = filter_meetings_by_patterns(MEETINGS, ["SA4#138"])
        assert [meeting.meeting_id for meeting in matched] == [12345]

    def test_accepts_normalized_name(self) -> None:
        matched = filter_meetings_by_patterns(MEETINGS, ["S4-138"])
        assert [meeting.meeting_id for meeting in matched] == [12345]

    def test_accepts_wildcard(self) -> None:
        matched = filter_meetings_by_patterns(MEETINGS, ["SA4#13*"])
        assert [meeting.meeting_id for meeting in matched] == [12345, 12346]

    def test_accepts_numeric_id(self) -> None:
        matched = filter_meetings_by_patterns(MEETINGS, ["12347"])
        assert [meeting.meeting_id for meeting in matched] == [12347]

    def test_unmatched_pattern_raises(self) -> None:
        with pytest.raises(MeetingPatternError, match=r"No meetings matched: SA4#999"):
            filter_meetings_by_patterns(MEETINGS, ["SA4#138", "SA4#999"])

    def test_none_keeps_all(self) -> None:
        assert filter_meetings_by_patterns(MEETINGS, None) == MEETINGS


@pytest.mark.asyncio
class TestMeetingUrlResolution:
    """A TDoc URL resolves to its meeting without guessing."""

    async def test_longest_prefix_wins(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_meeting(_meeting(1, "SA4#1", "https://example.com/ftp/tsg_sa/Docs/"))
            await database.upsert_meeting(_meeting(2, "SA4#138", "https://example.com/ftp/tsg_sa/WG4/Docs/"))

            meeting_id = await database.find_meeting_id_for_url("https://example.com/ftp/tsg_sa/WG4/Docs/S4-251501.zip")

        assert meeting_id == 2

    async def test_unknown_url_returns_zero(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_meeting(_meeting(1, "SA4#1", "https://example.com/ftp/tsg_sa/Docs/"))

            assert await database.find_meeting_id_for_url("https://example.com/other/S4-1.zip") == 0
            assert await database.find_meeting_id_for_url(None) == 0

    async def test_upsert_links_tdoc_to_meeting(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_meeting(_meeting(12345, "S4-138", DOCS_SA4_138))
            await database.upsert_tdoc(_tdoc("S4-251501", url=TDOC_URL))

            stored = await database._get_tdoc("S4-251501")

        assert stored is not None
        assert stored.meeting_id == 12345
        assert stored.tbid == 373

    async def test_no_link_when_meeting_unknown(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_tdoc(_tdoc("S4-251501", url="https://example.com/unknown/S4-251501.zip"))
            stored = await database._get_tdoc("S4-251501")

        assert stored is not None
        assert stored.meeting_id == 0


@pytest.mark.asyncio
class TestEnsureMeetingLinks:
    """By-ID fetches load the parent meetings once, so no orphans are created."""

    async def test_loads_missing_subgroup_meetings(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            with patch(
                "tdoc_crawler.tdocs.operations.fetch.fetch_meetings",
                return_value=MEETINGS[:2],
            ) as mock_fetch:
                loaded = await ensure_meeting_links(database, ["S4-251501"])

        assert loaded == 2
        assert mock_fetch.call_args.kwargs["subgroups"] == ["S4"]

    async def test_noop_when_subgroup_known(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_meeting(_meeting(12345, "SA4#138", DOCS_SA4_138, subtb=387))
            with patch("tdoc_crawler.tdocs.operations.fetch.fetch_meetings") as mock_fetch:
                loaded = await ensure_meeting_links(database, ["S4-251501"])

        assert loaded == 0
        mock_fetch.assert_not_called()

    async def test_ignores_unknown_prefix(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            with patch("tdoc_crawler.tdocs.operations.fetch.fetch_meetings") as mock_fetch:
                loaded = await ensure_meeting_links(database, ["XX-1"])

        assert loaded == 0
        mock_fetch.assert_not_called()


@pytest.mark.asyncio
class TestPortalUrlOnlyFetch:
    """URL-only lookup stores the download URL and links the meeting."""

    async def test_fetch_via_portal_url_batch(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            await database.upsert_meeting(_meeting(12345, "S4-138", DOCS_SA4_138))
            with patch(
                "tdoc_crawler.tdocs.operations.fetch.PortalClient.extract_tdoc_url",
                return_value=TDOC_URL,
            ):
                result = await fetch_via_portal_url_batch(database, ["S4-251501"])

            stored = await database._get_tdoc("S4-251501")

        assert result.inserted == 1
        assert not result.errors
        assert stored is not None
        assert stored.url == TDOC_URL
        assert stored.meeting_id == 12345

    async def test_failed_lookup_is_skipped(self, test_db_path: Path) -> None:
        async with TDocDatabase(test_db_path) as database:
            with patch(
                "tdoc_crawler.tdocs.operations.fetch.PortalClient.extract_tdoc_url",
                side_effect=PortalParsingError("unknown tdoc"),
            ):
                result = await fetch_via_portal_url_batch(database, ["S4-999999"])

        assert result.inserted == 0
        assert not result.errors

    async def test_url_only_first_skips_metadata_sources(self, test_db_path: Path) -> None:
        config = TDocQueryConfig(tdoc_ids=["S4-251501"])

        async def _fake_url_batch(database: TDocDatabase, missing_ids: list[str], **_kwargs: object) -> TDocCrawlResult:
            assert missing_ids == ["S4-251501"]
            await database.upsert_tdoc(_tdoc("S4-251501", url=TDOC_URL))
            return TDocCrawlResult(processed=1, inserted=1, updated=0, errors=[])

        async with TDocDatabase(test_db_path) as database:
            results = await database.query_tdocs(config)
            with (
                patch("tdoc_crawler.tdocs.operations.fetch.ensure_meeting_links", new=AsyncMock(return_value=0)),
                patch(
                    "tdoc_crawler.tdocs.operations.fetch.fetch_via_portal_url_batch",
                    side_effect=_fake_url_batch,
                ) as mock_url_batch,
                patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch") as mock_batch,
            ):
                fetch_result = await fetch_missing_tdocs(
                    database,
                    config,
                    results,
                    url_only_first=True,
                )

        mock_url_batch.assert_awaited_once()
        mock_batch.assert_not_called()
        assert [item.tdoc_id for item in fetch_result.refreshed] == ["S4-251501"]
        assert fetch_result.fetch_result is not None
        assert fetch_result.fetch_result.inserted == 1


@pytest.fixture(autouse=True)
def _no_network_meetings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep this module offline: meeting downloads must be patched explicitly."""
    monkeypatch.setattr(
        "tdoc_crawler.tdocs.operations.fetch.fetch_meetings",
        MagicMock(side_effect=AssertionError("meeting download must be patched explicitly")),
    )
