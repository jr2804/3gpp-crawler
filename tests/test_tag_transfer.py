"""Tests for tag export/import and backup (database/tag_transfer.py)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.tag_transfer import (
    TagRecord,
    export_tags,
    import_tags,
    normalize_item_id,
    read_tag_file,
    read_tags_from_database_file,
    tag_records_from_payload,
    tag_records_to_payload,
    write_tag_backup,
)
from tdoc_crawler.models.base import TagKind


class TestNormalizeItemId:
    def test_tdoc_and_spec_are_canonical(self) -> None:
        assert normalize_item_id(TagKind.TDOC, " s4-250638 ") == "S4-250638"
        assert normalize_item_id(TagKind.SPEC, "26444") == "26.444"

    def test_other_is_stripped(self) -> None:
        assert normalize_item_id(TagKind.OTHER, "  free text ") == "free text"


class TestPayload:
    def test_roundtrip(self) -> None:
        records = [TagRecord(TagKind.TDOC, "S4-250638", "codec"), TagRecord(TagKind.SPEC, "26.444", "rel-18")]
        assert tag_records_from_payload(tag_records_to_payload(records)) == records

    def test_invalid_kind(self) -> None:
        with pytest.raises(ValueError, match="invalid tag kind 'bogus'"):
            tag_records_from_payload([{"kind": "bogus", "item_id": "x", "tag": "y"}])

    def test_missing_key(self) -> None:
        with pytest.raises(ValueError, match="invalid tag entry"):
            tag_records_from_payload([{"kind": "tdoc", "item_id": "S4-250638"}])

    def test_not_a_list(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            tag_records_from_payload({"kind": "tdoc"})


class TestFiles:
    def test_json_backup_roundtrip(self, tmp_path: Path) -> None:
        records = [TagRecord(TagKind.TDOC, "S4-250638", "codec")]
        path = tmp_path / "tags-backup.json"
        write_tag_backup(records, path)
        assert json.loads(path.read_text(encoding="utf-8")) == [{"kind": "tdoc", "item_id": "S4-250638", "tag": "codec"}]
        assert read_tag_file(path) == records

    def test_yaml_dump(self, tmp_path: Path) -> None:
        path = tmp_path / "tags.yaml"
        path.write_text("- kind: spec\n  item_id: '26.444'\n  tag: rel-18\n", encoding="utf-8")
        assert read_tag_file(path) == [TagRecord(TagKind.SPEC, "26.444", "rel-18")]

    def test_unsupported_suffix(self, tmp_path: Path) -> None:
        path = tmp_path / "tags.csv"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported tag dump format"):
            read_tag_file(path)

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "tags.yaml"
        path.write_text("- [unclosed", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid YAML"):
            read_tag_file(path)


class TestRawRead:
    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert read_tags_from_database_file(tmp_path / "absent.db") == []

    def test_reads_tags_without_model_schema(self, tmp_path: Path) -> None:
        db_file = tmp_path / "old.db"
        with sqlite3.connect(db_file) as connection:
            connection.execute("CREATE TABLE tagentry (tag_id TEXT, kind TEXT, item_id TEXT, tag TEXT, created_at TEXT)")
            connection.execute("INSERT INTO tagentry VALUES ('x', 'tdoc', 'S4-250638', 'codec', '2026-01-01')")
        assert read_tags_from_database_file(db_file) == [TagRecord(TagKind.TDOC, "S4-250638", "codec")]

    def test_unreadable_file_raises(self, tmp_path: Path) -> None:
        db_file = tmp_path / "broken.db"
        db_file.write_text("not a sqlite file", encoding="utf-8")
        with pytest.raises(sqlite3.Error):
            read_tags_from_database_file(db_file)


@pytest.fixture(name="tag_db")
def fixture_tag_db(tmp_path: Path) -> Path:
    return tmp_path / "tags.db"


@pytest.mark.asyncio
async def test_export_import_roundtrip(tag_db: Path, tmp_path: Path) -> None:
    async with TDocDatabase(tag_db):
        records = [
            TagRecord(TagKind.TDOC, "S4-250638", "codec"),
            TagRecord(TagKind.TDOC, "S4-250638", "rel-18"),
            TagRecord(TagKind.SPEC, "26.444", "codec"),
        ]
        assert await import_tags(records) == 3
        exported = await export_tags()
        assert sorted(exported, key=lambda r: (r.kind, r.item_id, r.tag)) == sorted(records, key=lambda r: (r.kind, r.item_id, r.tag))

    other_db = tmp_path / "other.db"
    async with TDocDatabase(other_db):
        assert await import_tags(exported) == 3
        assert await import_tags(exported) == 0  # re-import skips existing rows
        assert len(await export_tags(TagKind.SPEC)) == 1
