"""Tests for targeted fetch functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tdoc_crawler.cli import _fetch_missing_tdocs, _infer_working_groups_from_ids, _maybe_fetch_missing_tdocs
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import QueryConfig, TDocMetadata, WorkingGroup


class TestInferWorkingGroups:
    """Tests for _infer_working_groups_from_ids function."""

    def test_infer_from_ran_tdocs(self) -> None:
        """Infer RAN working group from R-prefixed IDs."""
        ids = ["R1-2301234", "R2-2301567"]
        groups = _infer_working_groups_from_ids(ids)
        assert WorkingGroup.RAN in groups
        assert len(groups) == 1

    def test_infer_from_sa_tdocs(self) -> None:
        """Infer SA working group from S-prefixed IDs."""
        ids = ["S4-2301890", "S2-2301123"]
        groups = _infer_working_groups_from_ids(ids)
        assert WorkingGroup.SA in groups
        assert len(groups) == 1

    def test_infer_from_ct_tdocs(self) -> None:
        """Infer CT working group from T or C prefixed IDs."""
        ids = ["T1-2301456", "C2-2301789"]
        groups = _infer_working_groups_from_ids(ids)
        assert WorkingGroup.CT in groups
        assert len(groups) == 1

    def test_infer_from_mixed_tdocs(self) -> None:
        """Infer multiple working groups from mixed IDs."""
        ids = ["R1-2301234", "S4-2301890", "T1-2301456"]
        groups = _infer_working_groups_from_ids(ids)
        assert len(groups) == 3
        assert WorkingGroup.RAN in groups
        assert WorkingGroup.SA in groups
        assert WorkingGroup.CT in groups

    def test_infer_deduplicates_groups(self) -> None:
        """Ensure duplicate working groups are removed."""
        ids = ["R1-2301234", "R2-2301567", "R3-2301890"]
        groups = _infer_working_groups_from_ids(ids)
        assert len(groups) == 1
        assert WorkingGroup.RAN in groups

    def test_infer_empty_list(self) -> None:
        """Return all working groups for empty input."""
        ids: list[str] = []
        groups = _infer_working_groups_from_ids(ids)
        assert len(groups) == 3


class TestFetchMissingTdocs:
    """Tests for _fetch_missing_tdocs function."""

    @patch("tdoc_crawler.cli.fetch_tdoc_metadata")
    def test_fetch_missing_creates_config(
        self,
        mock_fetch_portal: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Ensure targeted fetch creates proper config."""
        from tdoc_crawler.models import PortalCredentials

        # Mock portal response
        mock_fetch_portal.return_value = {
            "meeting": "RAN1#98",
            "title": "Test TDoc",
            "contact": "Test Contact",
            "tdoc_type": "Discussion",
            "for_purpose": "Discussion",
            "agenda_item": "7.1",
            "status": "Approved",
        }

        credentials = PortalCredentials(username="test", password="test")

        with TDocDatabase(test_db_path) as database:
            result = _fetch_missing_tdocs(
                database,
                test_db_path.parent,
                ["R1-2301234"],
                credentials=credentials,
            )

        assert result.processed == 1
        assert result.inserted == 1
        assert not result.errors
        mock_fetch_portal.assert_called_once()

    @patch("tdoc_crawler.cli.fetch_tdoc_metadata")
    def test_fetch_missing_infers_working_groups(
        self,
        mock_fetch_portal: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Verify working groups are inferred from target IDs."""
        from tdoc_crawler.models import PortalCredentials

        # Mock portal responses
        mock_fetch_portal.side_effect = [
            {
                "meeting": "RAN1#98",
                "title": "Test TDoc 1",
                "contact": "Test Contact",
                "tdoc_type": "Discussion",
                "for_purpose": "Discussion",
                "agenda_item": "7.1",
                "status": "Approved",
            },
            {
                "meeting": "SA4#134",
                "title": "Test TDoc 2",
                "contact": "Test Contact",
                "tdoc_type": "Discussion",
                "for_purpose": "Discussion",
                "agenda_item": "8.2",
                "status": "Approved",
            },
        ]

        credentials = PortalCredentials(username="test", password="test")  # noqa: S106

        with TDocDatabase(test_db_path) as database:
            result = _fetch_missing_tdocs(
                database,
                test_db_path.parent,
                ["R1-2301234", "S4-2301890"],
                credentials=credentials,
            )

        # Verify both TDocs were processed
        assert result.processed == 2
        assert result.inserted == 2
        assert not result.errors


class TestMaybeFetchMissingTdocs:
    """Tests for _maybe_fetch_missing_tdocs function."""

    @patch("tdoc_crawler.cli._fetch_missing_tdocs")
    def test_no_fetch_when_all_present(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Skip fetch when all requested TDocs are present."""
        with TDocDatabase(test_db_path) as database:
            for tdoc in sample_tdocs:
                database.upsert_tdoc(tdoc)

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["R1-2301234"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            refreshed = _maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        assert len(refreshed) == 1
        mock_fetch.assert_not_called()

    @patch("tdoc_crawler.cli._fetch_missing_tdocs")
    def test_fetch_triggered_when_missing(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Trigger fetch when requested TDocs are missing."""
        mock_fetch.return_value = MagicMock(
            processed=1,
            inserted=1,
            updated=0,
            errors=[],
        )

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["R1-9999999"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            _maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        missing_ids = call_args[0][2]
        assert "R1-9999999" in missing_ids

    @patch("tdoc_crawler.cli._fetch_missing_tdocs")
    def test_no_fetch_without_tdoc_ids(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Skip fetch when query has no specific TDoc IDs."""
        config = QueryConfig(
            cache_dir=test_db_path.parent,
            working_groups=[WorkingGroup.RAN],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            refreshed = _maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        assert refreshed == results
        mock_fetch.assert_not_called()

    @patch("tdoc_crawler.cli._fetch_missing_tdocs")
    def test_partial_fetch_only_missing(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Fetch only the missing TDocs when some are present."""
        mock_fetch.return_value = MagicMock(
            processed=1,
            inserted=1,
            updated=0,
            errors=[],
        )

        with TDocDatabase(test_db_path) as database:
            database.upsert_tdoc(sample_tdocs[0])

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["R1-2301234", "R1-9999999"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            _maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        missing_ids = call_args[0][2]
        assert "R1-9999999" in missing_ids
        assert "R1-2301234" not in missing_ids
