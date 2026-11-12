"""Tests for agenda item hierarchy handling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.sources import agenda as agenda_source
from tdoc_crawler.utils.agenda import (
    ancestor_agenda_numbers,
    is_agenda_number,
    merge_agenda_items,
    normalize_agenda_number,
    parse_agenda_csv,
)

# --- Pure helpers ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", "4"),
        ("4.0", "4"),
        ("4.5", "4.5"),
        (" 4.5 ", "4.5"),
        ("4.5.0", "4.5"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_agenda_number(value: str | None, expected: str) -> None:
    assert normalize_agenda_number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", True),
        ("4.5", True),
        ("4.5.1", True),
        ("Agenda", False),
        ("4a", False),
    ],
)
def test_is_agenda_number(value: str, expected: bool) -> None:
    assert is_agenda_number(value) is expected


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("4.5", ["4"]),
        ("4.5.1", ["4.5", "4"]),
        ("4", []),
        ("", []),
    ],
)
def test_ancestor_agenda_numbers(number: str, expected: list[str]) -> None:
    assert ancestor_agenda_numbers(number) == expected


def test_parse_agenda_csv() -> None:
    content = (
        b"4,FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO),,\n"
        b"4.5,SA4_3GPP_AUDIO related topics for 6G,,\n"
        b"6,Close of the meeting,,\n"
        b"Agenda item,Description,,\n"
    )

    items = parse_agenda_csv(content)

    assert items["4"] == "FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO)"
    assert items["4.5"] == "SA4_3GPP_AUDIO related topics for 6G"
    assert "Agenda item" not in items


def test_parse_agenda_csv_handles_bom_and_crlf() -> None:
    content = "4,FS_ULBC-MED\r\n4.5,Related topics\r\n".encode("utf-8-sig")

    items = parse_agenda_csv(content)

    assert items == {"4": "FS_ULBC-MED", "4.5": "Related topics"}


def test_merge_agenda_items_prefers_first_map() -> None:
    merged = merge_agenda_items({"4": "FS_ULBC-MED"}, {"4": "Other", "6": "Close"})

    assert merged == {"4": "FS_ULBC-MED", "6": "Close"}


# --- Agenda source ---


def test_agenda_csv_url() -> None:
    url = agenda_source.agenda_csv_url("https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/SA4_Audio/Docs/")

    assert url == "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/SA4_Audio/Agenda/agenda.csv"


@pytest.mark.parametrize("files_url", [None, "", "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/SA4_Audio/"])
def test_agenda_csv_url_without_docs_folder(files_url: str | None) -> None:
    assert agenda_source.agenda_csv_url(files_url) is None


def test_resolve_agenda_hierarchy_fetches_missing_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    def fake_fetch(
        files_url: str | None,
        timeout: int = 30,
        http_config: object = None,
        http_cache_file: object = None,
    ) -> dict[str, str]:
        calls.append(files_url)
        return {"4": "FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO)"}

    monkeypatch.setattr(agenda_source, "fetch_meeting_agenda", fake_fetch)

    documents = [_make_tdoc("S4aA260001", 85916, "4.5", "Qualification/Selection rules")]

    resolved = agenda_source.resolve_agenda_hierarchy(documents, files_url="https://example.org/Docs/")

    assert resolved == {"4": "FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO)"}
    assert calls == ["https://example.org/Docs/"]


def test_resolve_agenda_hierarchy_skips_fetch_when_parent_known(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(*args: object, **kwargs: object) -> dict[str, str]:
        raise AssertionError("agenda file must not be fetched when the parent is known")

    monkeypatch.setattr(agenda_source, "fetch_meeting_agenda", fake_fetch)

    documents = [
        _make_tdoc("S4aA250246", 82376, "4.0", "FS_ULBC"),
        _make_tdoc("S4aA250247", 82376, "4.1", "Reports/Liaisons"),
    ]

    resolved = agenda_source.resolve_agenda_hierarchy(documents, files_url="https://example.org/Docs/")

    assert resolved == {"4": "FS_ULBC"}


# --- Database ---


def _populate(db: TDocDatabase, documents: list[TDocMetadata], agenda: dict[int, dict[str, str]]) -> None:
    async def _run() -> None:
        for document in documents:
            _ = await db.upsert_tdoc(document)
        await db.store_meeting_agenda_items(agenda)

    asyncio.run(_run())


def test_query_matches_parent_agenda_item(test_db_path: Path) -> None:
    documents = [
        _make_tdoc("S4aA260001", 85916, "4.5", "Qualification/Selection rules"),
        _make_tdoc("S4aA260002", 85916, "4.6", "Deliverables"),
        _make_tdoc("S4aA250246", 82376, "4.0", "FS_ULBC"),
    ]
    agenda = {85916: {"4": "FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO)"}}

    async def _run() -> list[str]:
        async with TDocDatabase(test_db_path) as db:
            await db.store_meeting_agenda_items(agenda)
            for document in documents:
                _ = await db.upsert_tdoc(document)
            results = await db.query_tdocs(TDocQueryConfig(agenda_pattern=["ULBC"]))
            return sorted(result.tdoc_id for result in results)

    assert asyncio.run(_run()) == ["S4aA250246", "S4aA260001", "S4aA260002"]


def test_query_without_parent_agenda_item_does_not_match(test_db_path: Path) -> None:
    documents = [_make_tdoc("S4aA260001", 85916, "4.5", "Qualification/Selection rules")]

    async def _run() -> list[str]:
        async with TDocDatabase(test_db_path) as db:
            for document in documents:
                _ = await db.upsert_tdoc(document)
            results = await db.query_tdocs(TDocQueryConfig(agenda_pattern=["ULBC"]))
            return [result.tdoc_id for result in results]

    assert asyncio.run(_run()) == []


def test_query_excludes_parent_agenda_item(test_db_path: Path) -> None:
    documents = [
        _make_tdoc("S4aA260001", 85916, "4.5", "Qualification/Selection rules"),
        _make_tdoc("S4aA260002", 85916, "7.1", "IPR, assistants and rapporteurs"),
    ]
    agenda = {85916: {"4": "FS_ULBC-MED (Study on 3GPP usage of SA4_3GPP_AUDIO)"}}

    async def _run() -> list[str]:
        async with TDocDatabase(test_db_path) as db:
            await db.store_meeting_agenda_items(agenda)
            for document in documents:
                _ = await db.upsert_tdoc(document)
            results = await db.query_tdocs(TDocQueryConfig(agenda_pattern_exclude=["ULBC"]))
            return [result.tdoc_id for result in results]

    assert asyncio.run(_run()) == ["S4aA260002"]


def test_store_meeting_agenda_items_replaces_previous(test_db_path: Path) -> None:
    async def _run() -> list[str]:
        async with TDocDatabase(test_db_path) as db:
            await db.store_meeting_agenda_items({85916: {"4": "FS_ULBC-MED"}})
            await db.store_meeting_agenda_items({85916: {"4": "Other topic"}})
            document = _make_tdoc("S4aA260001", 85916, "4.5", "Qualification/Selection rules")
            _ = await db.upsert_tdoc(document)
            results = await db.query_tdocs(TDocQueryConfig(agenda_pattern=["FS_ULBC-MED"]))
            return [result.tdoc_id for result in results]

    assert asyncio.run(_run()) == []


def _make_tdoc(tdoc_id: str, meeting_id: int, agenda_nbr: str, agenda_text: str) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=tdoc_id,
        tbid=375,
        url=f"https://www.3gpp.org/ftp/tsg_sa/WG4_Core/{tdoc_id}.zip",
        meeting_id=meeting_id,
        file_size=1024,
        title=f"Document {tdoc_id}",
        source="Test Source",
        contact="Test Contact",
        tdoc_type="Discussion",
        for_purpose="Discussion",
        agenda_item_nbr=agenda_nbr,
        agenda_item_text=agenda_text,
        status="approved",
        is_revision_of="",
        date_created=datetime(2026, 9, 28, tzinfo=UTC),
        date_retrieved=datetime(2026, 9, 28, tzinfo=UTC),
        validated=False,
        validation_failed=False,
    )
