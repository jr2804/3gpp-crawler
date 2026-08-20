"""Test TDoc query sort keys (reservation_date, uploaded_at, tdoc_id).

Issue #5: callers need to sort by true submission order, not tdoc_id number
order, because uploads/revisions happen out of number order over following days.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.models.base import SortKey
from tdoc_crawler.tdocs.models import TDocQueryConfig


@pytest.mark.asyncio
async def test_sort_by_uploaded_at(tmp_path: Path) -> None:
    """Higher TDoc number uploaded earlier must sort before lower number when sorted by uploaded_at."""
    db_file = tmp_path / "sort.db"
    async with TDocDatabase(db_file) as db:
        await db.upsert_meeting(
            MeetingMetadata(
                meeting_id=1,
                tbid=375,
                subtb=None,
                short_name="SA4#1",
                title=None,
                start_date=None,
                end_date=None,
                location=None,
                files_url=None,
                portal_url=None,
                tdoc_count=0,
            )
        )
        # reservation order: S4-261564 then S4-261592
        await db.upsert_tdoc(_make_tdoc("S4-261564", datetime(2026, 8, 18, 15, 37, tzinfo=UTC), datetime(2026, 8, 18, 21, 57, tzinfo=UTC)))
        # uploaded EARLIER than S4-261564 despite higher number
        await db.upsert_tdoc(_make_tdoc("S4-261592", datetime(2026, 8, 18, 17, 46, tzinfo=UTC), datetime(2026, 8, 18, 18, 5, tzinfo=UTC)))

        config = TDocQueryConfig(sort_key=SortKey.UPLOADED_AT)
        records = await db.query_tdocs(config)

        assert [r.tdoc_id for r in records] == ["S4-261592", "S4-261564"]


@pytest.mark.asyncio
async def test_sort_by_reservation_date_desc(tmp_path: Path) -> None:
    db_file = tmp_path / "sort2.db"
    async with TDocDatabase(db_file) as db:
        await db.upsert_meeting(
            MeetingMetadata(
                meeting_id=1,
                tbid=375,
                subtb=None,
                short_name="SA4#1",
                title=None,
                start_date=None,
                end_date=None,
                location=None,
                files_url=None,
                portal_url=None,
                tdoc_count=0,
            )
        )
        await db.upsert_tdoc(_make_tdoc("S4-261564", datetime(2026, 8, 18, 15, 37, tzinfo=UTC), datetime(2026, 8, 18, 21, 57, tzinfo=UTC)))
        await db.upsert_tdoc(_make_tdoc("S4-261592", datetime(2026, 8, 18, 17, 46, tzinfo=UTC), datetime(2026, 8, 18, 18, 5, tzinfo=UTC)))

        config = TDocQueryConfig(sort_key=SortKey.RESERVATION_DATE, order="desc")
        records = await db.query_tdocs(config)

        assert [r.tdoc_id for r in records] == ["S4-261592", "S4-261564"]


@pytest.mark.asyncio
async def test_sort_by_tdoc_id_ignores_dates(tmp_path: Path) -> None:
    db_file = tmp_path / "sort3.db"
    async with TDocDatabase(db_file) as db:
        await db.upsert_meeting(
            MeetingMetadata(
                meeting_id=1,
                tbid=375,
                subtb=None,
                short_name="SA4#1",
                title=None,
                start_date=None,
                end_date=None,
                location=None,
                files_url=None,
                portal_url=None,
                tdoc_count=0,
            )
        )
        await db.upsert_tdoc(_make_tdoc("S4-261564", datetime(2026, 8, 18, 15, 37, tzinfo=UTC), datetime(2026, 8, 18, 21, 57, tzinfo=UTC)))
        await db.upsert_tdoc(_make_tdoc("S4-261592", datetime(2026, 8, 18, 17, 46, tzinfo=UTC), datetime(2026, 8, 18, 18, 5, tzinfo=UTC)))

        config = TDocQueryConfig(sort_key=SortKey.TDOC_ID)
        records = await db.query_tdocs(config)

        assert [r.tdoc_id for r in records] == ["S4-261564", "S4-261592"]


def _make_tdoc(
    tdoc_id: str,
    reservation_date: datetime,
    uploaded_at: datetime,
    meeting_id: int = 1,
) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=tdoc_id,
        meeting_id=meeting_id,
        tbid=375,
        title=f"Title {tdoc_id}",
        source="Test",
        contact="Test",
        agenda_item_nbr="9.1",
        agenda_item_text="Test agenda",
        date_retrieved=datetime(2023, 1, 1, tzinfo=UTC),
        reservation_date=reservation_date,
        uploaded_at=uploaded_at,
    )
