"""Tests for work item operations: scoping, enrichment and the global list audit."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Never

import pytest

from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.utils.parse import parse_working_groups
from tdoc_crawler.workitems import WorkItem
from tdoc_crawler.workitems import operations as wi_operations
from tdoc_crawler.workitems.operations import (
    compare_work_item_list,
    enrich_work_items,
    expand_area_codes,
    normalize_wg_codes,
)
from tdoc_crawler.workitems.sources.dynareport import WorkItemSourceError


class TestWgCodeScoping:
    def test_normalizes_known_and_historical_codes(self) -> None:
        assert normalize_wg_codes(["sa4", "S4"]) == ["S4"]
        assert normalize_wg_codes(["GP", "t1", "smg"]) == ["GP", "T1", "SMG"]
        assert normalize_wg_codes(None) == []

    def test_expands_areas_to_lead_bodies(self) -> None:
        assert expand_area_codes(parse_working_groups(["SA"])) == ["SP", "S1", "S2", "S3", "S4", "S5", "S6"]
        assert expand_area_codes(parse_working_groups(["RAN"])) == ["RP", "R1", "R2", "R3", "R4", "R5", "R6"]
        assert expand_area_codes(parse_working_groups(["CT"])) == ["CP", "C1", "C2", "C3", "C4", "C5", "C6"]
        assert expand_area_codes(None) == []


class TestEnrichWorkItems:
    def test_enriches_selected_work_items(self, test_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await db.store_work_items(
                    [
                        WorkItem(wi_id="ULBC-MED", uid=1120096, lead_body="S4", release="Rel-20"),
                        WorkItem(wi_id="5GSAT_PH4", uid=1080054, lead_body="SP", release="Rel-20"),
                    ]
                )

        asyncio.run(seed())

        monkeypatch.setattr(wi_operations, "work_item_session", lambda **kwargs: contextlib.nullcontext(None))
        monkeypatch.setattr(
            wi_operations,
            "fetch_work_item_details",
            lambda uid, **kwargs: wi_operations.WorkItemDetails(uid=uid, wi_id="ULBC-MED", status="PCG approved"),
        )
        monkeypatch.setattr(wi_operations, "fetch_work_item_specs", lambda uid, **kwargs: ["26.114"])
        monkeypatch.setattr(wi_operations, "fetch_work_item_crs", lambda uid, **kwargs: [])

        summary = enrich_work_items(test_db_path, ["ULBC-MED"])

        assert summary.enriched == 1
        assert summary.specs_found == 1
        assert summary.failed == 0

        async def load() -> dict[str, str | None]:
            async with TDocDatabase(test_db_path) as db:
                records = await db.list_work_items()
                return {record.wi_id: record.status for record in records}

        statuses = asyncio.run(load())
        assert statuses["ULBC-MED"] == "PCG approved"
        assert statuses["5GSAT_PH4"] is None

    def test_reports_source_errors_per_work_item(self, test_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await db.store_work_items([WorkItem(wi_id="ULBC-MED", uid=1120096)])

        asyncio.run(seed())

        def raising_fetch(uid: int, **kwargs: object) -> Never:
            raise WorkItemSourceError(f"details for uid={uid} failed")

        monkeypatch.setattr(wi_operations, "work_item_session", lambda **kwargs: contextlib.nullcontext(None))
        monkeypatch.setattr(wi_operations, "fetch_work_item_details", raising_fetch)

        summary = enrich_work_items(test_db_path, ["ULBC-MED"])

        assert summary.enriched == 0
        assert summary.failed == 1
        assert "ULBC-MED" in summary.errors[0]


class TestCompareWorkItemList:
    def test_compares_catalogue_against_global_list(self, test_db_path: Path) -> None:
        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await db.store_work_items(
                    [
                        WorkItem(wi_id="ULBC-MED", uid=1120096, lead_body="S4"),
                        WorkItem(wi_id="CATALOGUE-ONLY", uid=1120100, lead_body="S4"),
                    ]
                )

        asyncio.run(seed())

        comparison = compare_work_item_list(
            test_db_path,
            fetch_entries=lambda **kwargs: [(1120096, "ULBC-MED", "S4"), (1080054, "5GSAT_PH4", "SP")],
        )

        assert comparison.list_entries == 2
        assert comparison.matched == 1
        assert comparison.missing_from_db == 1
        assert comparison.missing_from_list == 1
        s4_row = next(row for row in comparison.rows if row["lead_body"] == "S4")
        assert s4_row["list"] == 1
        assert s4_row["in_catalogue"] == 1
        assert s4_row["missing"] == 0
        sp_row = next(row for row in comparison.rows if row["lead_body"] == "SP")
        assert sp_row["missing"] == 1
