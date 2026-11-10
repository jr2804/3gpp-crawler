"""Tests for archive member tracking (utils/archive.py, database/archives.py)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.archives import clear_archive_members, list_archive_members, replace_archive_members
from tdoc_crawler.models.archives import ArchiveKind, ArchiveMemberInfo, ArchiveRecord
from tdoc_crawler.utils.archive import list_zip_members


@pytest.fixture(name="archive_db")
def fixture_archive_db(tmp_path: Path) -> Path:
    return tmp_path / "archives.db"


def test_list_zip_members_skips_directories(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path / "x.zip", {"main.docx": b"abc", "notes/readme.txt": b"hello"})

    members = list_zip_members(zip_path)

    assert [m.member_path for m in members] == ["main.docx", "notes/readme.txt"]
    assert [m.file_size for m in members] == [3, 5]


def _make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("folder/", b"")
        for name, data in members.items():
            zf.writestr(name, data)
    return path


@pytest.mark.asyncio
async def test_replace_list_and_clear_roundtrip(archive_db: Path) -> None:
    record = ArchiveRecord(
        kind=ArchiveKind.TDOC,
        item_id="S4-240001",
        archive_name="S4-240001.zip",
        members=[
            ArchiveMemberInfo(member_path="b.docx", file_size=10),
            ArchiveMemberInfo(member_path="a.docx", file_size=20),
            ArchiveMemberInfo(member_path="__MACOSX/._a.docx", file_size=1),
        ],
    )

    async with TDocDatabase(archive_db):
        await replace_archive_members(record)
        rows = await list_archive_members(ArchiveKind.TDOC, "S4-240001")

        assert [row.member_path for row in rows] == ["__MACOSX/._a.docx", "a.docx", "b.docx"]
        clutter = {row.member_path: row.is_clutter for row in rows}
        assert clutter["__MACOSX/._a.docx"] is True
        assert clutter["a.docx"] is False

        replacement = ArchiveRecord(
            kind=ArchiveKind.TDOC,
            item_id="S4-240001",
            archive_name="S4-240001.zip",
            members=[ArchiveMemberInfo(member_path="only.docx", file_size=7)],
        )
        await replace_archive_members(replacement)
        rows = await list_archive_members(ArchiveKind.TDOC, "S4-240001")
        assert [row.member_path for row in rows] == ["only.docx"]

        removed = await clear_archive_members(ArchiveKind.TDOC)
        assert removed == 1
        assert await list_archive_members(ArchiveKind.TDOC, "S4-240001") == []


@pytest.mark.asyncio
async def test_clear_is_scoped_to_kind(archive_db: Path) -> None:
    async with TDocDatabase(archive_db):
        await replace_archive_members(ArchiveRecord(kind=ArchiveKind.TDOC, item_id="S4-240001", archive_name="a.zip", members=[ArchiveMemberInfo("a.docx", 1)]))
        await replace_archive_members(
            ArchiveRecord(kind=ArchiveKind.SPEC, item_id="26131", archive_name="26131.zip", members=[ArchiveMemberInfo("26131.docx", 2)])
        )

        assert await clear_archive_members(ArchiveKind.SPEC) == 1
        assert len(await list_archive_members(ArchiveKind.TDOC, "S4-240001")) == 1
