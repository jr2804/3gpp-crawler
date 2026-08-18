"""Tests for tag operations (database/tags.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.tags import (
    add_tags,
    item_ids_for_tag_groups,
    list_tags,
    normalize_tags,
    parse_tag_groups,
    remove_tags,
)
from tdoc_crawler.models.base import TagKind


class TestNormalizeTags:
    def test_strips_and_dedupes(self) -> None:
        assert normalize_tags([" A ", "a", "b", "", "  "]) == ["a", "b"]

    def test_lowercases(self) -> None:
        assert normalize_tags(["Codec", "CODEC"]) == ["codec"]


class TestParseTagGroups:
    def test_comma_split_and_repeat(self) -> None:
        groups = parse_tag_groups(["codec,codec2", "rel-18"])
        assert groups == [["codec", "codec2"], ["rel-18"]]

    def test_empty(self) -> None:
        assert parse_tag_groups([]) == []
        assert parse_tag_groups(["", "  "]) == []


@pytest.fixture(name="tag_db")
def fixture_tag_db(tmp_path: Path) -> Path:
    return tmp_path / "tags.db"


@pytest.mark.asyncio
async def test_add_remove_list_roundtrip(tag_db: Path) -> None:
    async with TDocDatabase(tag_db):
        added = await add_tags(TagKind.TDOC, "S4-250638", ["codec", "rel-18", "codec"])
        assert added == 2  # duplicate skipped

        # idempotent second add
        assert await add_tags(TagKind.TDOC, "S4-250638", ["codec"]) == 0

        rows = await list_tags(kind=TagKind.TDOC, item_id="S4-250638")
        assert [r.tag for r in rows] == ["codec", "rel-18"]

        # same tag on a spec — kinds are independent
        await add_tags(TagKind.SPEC, "26.444", ["codec"])
        assert len(await list_tags(tag="codec")) == 2
        assert len(await list_tags(kind=TagKind.SPEC, tag="codec")) == 1


@pytest.mark.asyncio
async def test_remove_tags(tag_db: Path) -> None:
    async with TDocDatabase(tag_db):
        await add_tags(TagKind.TDOC, "S4-1", ["a", "b", "c"])
        assert await remove_tags(TagKind.TDOC, "S4-1", ["a", "z"]) == 1
        assert [r.tag for r in await list_tags(item_id="S4-1")] == ["b", "c"]
        assert await remove_tags(TagKind.TDOC, "S4-1") == 2  # all
        assert await list_tags(item_id="S4-1") == []


@pytest.mark.asyncio
async def test_item_ids_and_of_or(tag_db: Path) -> None:
    async with TDocDatabase(tag_db):
        await add_tags(TagKind.TDOC, "S4-1", ["codec", "rel-18"])
        await add_tags(TagKind.TDOC, "S4-2", ["codec"])
        await add_tags(TagKind.TDOC, "S4-3", ["codec2", "rel-18"])

        # OR within group
        assert await item_ids_for_tag_groups([["codec", "codec2"]], TagKind.TDOC) == {"S4-1", "S4-2", "S4-3"}
        # AND across groups
        assert await item_ids_for_tag_groups([["codec", "codec2"], ["rel-18"]], TagKind.TDOC) == {"S4-1", "S4-3"}
        # no match
        assert await item_ids_for_tag_groups([["missing"]], TagKind.TDOC) == set()
        # empty expression
        assert await item_ids_for_tag_groups([], TagKind.TDOC) == set()
        # kind isolation: spec tags don't leak into tdoc queries
        await add_tags(TagKind.SPEC, "26.444", ["codec"])
        assert "26.444" not in await item_ids_for_tag_groups([["codec"]], TagKind.TDOC)
