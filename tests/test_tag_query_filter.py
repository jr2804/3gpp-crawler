"""Regression test: tag filter must apply before the result limit.

Issue #3: `tdoc query --tag <name>` returned zero results because the
`limit` was applied inside `query_tdocs` *before* the tag filter ran in the
CLI layer. With 31k TDocs and `--limit 300`, the tagged rows (which sorted
beyond the first 300) were never seen by the tag filter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.database.tags import add_tags
from tdoc_crawler.models.base import TagKind
from tdoc_crawler.tdocs.models import TDocQueryConfig


@pytest.mark.asyncio
async def test_tag_filter_applies_before_limit(tmp_path: Path) -> None:
    """A tagged TDoc beyond the first `limit` rows must still be returned."""
    db_file = tmp_path / "tags.db"
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
        # 5 TDocs; the tagged one sorts last (S4-5).
        for i in range(1, 6):
            await db.upsert_tdoc(_make_tdoc(f"S4-{i}", meeting_id=1))
        await add_tags(TagKind.TDOC, "S4-5", ["atias"])

        config = TDocQueryConfig(tag=["atias"], limit=2)
        results = await db.query_tdocs(config)

    assert [r.tdoc_id for r in results] == ["S4-5"]


@pytest.mark.asyncio
async def test_tag_filter_no_match_returns_empty(tmp_path: Path) -> None:
    db_file = tmp_path / "tags.db"
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
        await db.upsert_tdoc(_make_tdoc("S4-1", meeting_id=1))
        await add_tags(TagKind.TDOC, "S4-1", ["codec"])

        config = TDocQueryConfig(tag=["atias"], limit=10)
        results = await db.query_tdocs(config)

    assert results == []


def _make_tdoc(tdoc_id: str, meeting_id: int) -> TDocMetadata:
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
    )
