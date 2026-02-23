"""Tests for targeted fetch functionality."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from tdoc_crawler.config import CacheManager
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import PortalCredentials, WorkingGroup
from tdoc_crawler.tdocs.models import TDocMetadata, TDocQueryConfig
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.tdocs.operations.fetch import fetch_missing_tdocs, fetch_missing_tdocs_batch
from tdoc_crawler.utils.parse import infer_working_groups_from_ids

from .conftest import insert_sample_meetings


class TestInferWorkingGroups:
    """Tests for infer_working_groups_from_ids function."""

    def test_infer_from_ran_tdocs(self) -> None:
        """Infer RAN working group from R-prefixed IDs."""
        ids = ["R1-2301234", "R2-2301567"]
        groups = infer_working_groups_from_ids(ids)
        assert WorkingGroup.RAN in groups
        assert len(groups) == 1

    def test_infer_from_sa_tdocs(self) -> None:
        """Infer SA working group from S-prefixed IDs."""
        ids = ["S4-2301890", "S2-2301123"]
        groups = infer_working_groups_from_ids(ids)
        assert WorkingGroup.SA in groups
        assert len(groups) == 1

    def test_infer_from_ct_tdocs(self) -> None:
        """Infer CT working group from T or C prefixed IDs."""
        ids = ["T1-2301456", "C2-2301789"]
        groups = infer_working_groups_from_ids(ids)
        assert WorkingGroup.CT in groups
        assert len(groups) == 1

    def test_infer_from_mixed_tdocs(self) -> None:
        """Infer multiple working groups from mixed IDs."""
        ids = ["R1-2301234", "S4-2301890", "T1-2301456"]
        groups = infer_working_groups_from_ids(ids)
        assert len(groups) == 3
        assert WorkingGroup.RAN in groups
        assert WorkingGroup.SA in groups
        assert WorkingGroup.CT in groups

    def test_infer_deduplicates_groups(self) -> None:
        """Ensure duplicate working groups are removed."""
        ids = ["R1-2301234", "R2-2301567", "R3-2301890"]
        groups = infer_working_groups_from_ids(ids)
        assert len(groups) == 1
        assert WorkingGroup.RAN in groups

    def test_infer_empty_list(self) -> None:
        """Return all working groups for empty input."""
        ids: list[str] = []
        groups = infer_working_groups_from_ids(ids)
        assert len(groups) == 3


class TestFetchMissingTdocsBatch:
    """Tests for fetch_missing_tdocs_batch function."""

    @patch("tdoc_crawler.tdocs.operations.fetch.PortalSource")
    def test_fetch_missing_creates_config(
        self,
        mock_portal_source_class: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Ensure targeted fetch creates proper config."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        # Setup the mock to return a PortalSource instance with fetch_by_id mocked
        mock_source_instance = MagicMock()
        mock_source_instance.fetch_by_id.return_value = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=0,
            title="Test TDoc",
            url="https://example.com/R1-2301234.zip",
            contact="Test Contact",
            source="Test Source",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("7.1"),
            agenda_item_text="Test agenda",
            status="Approved",
            validated=True,
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validation_failed=False,
        )
        mock_portal_source_class.return_value = mock_source_instance

        _ = PortalCredentials(username="test", password="test")

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            result = fetch_missing_tdocs_batch(
                database,
                ["R1-2301234"],
            )

        assert result.processed == 1
        assert result.inserted == 1
        assert not result.errors
        mock_source_instance.fetch_by_id.assert_called_once_with("R1-2301234", timeout=30)

    @patch("tdoc_crawler.tdocs.operations.fetch.PortalSource")
    def test_fetch_missing_infers_working_groups(
        self,
        mock_portal_source_class: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify working groups are inferred from target IDs."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        # Setup the mock to return a PortalSource instance with fetch_by_id mocked
        mock_source_instance = MagicMock()
        mock_source_instance.fetch_by_id.side_effect = [
            TDocMetadata(
                tdoc_id="R1-2301234",
                meeting_id=0,
                title="Test TDoc 1",
                url="https://example.com/R1-2301234.zip",
                contact="Test Contact",
                source="Test Source",
                tdoc_type="Discussion",
                for_purpose="Discussion",
                agenda_item_nbr=Decimal("7.1"),
                agenda_item_text="Test agenda",
                status="Approved",
                validated=True,
                is_revision_of=None,
                file_size=None,
                date_created=None,
                validation_failed=False,
            ),
            TDocMetadata(
                tdoc_id="S4-2301890",
                meeting_id=0,
                title="Test TDoc 2",
                url="https://example.com/S4-2301890.zip",
                contact="Test Contact",
                source="Test Source",
                tdoc_type="Discussion",
                for_purpose="Discussion",
                agenda_item_nbr=Decimal("8.2"),
                agenda_item_text="Test agenda",
                status="Approved",
                validated=True,
                is_revision_of=None,
                file_size=None,
                date_created=None,
                validation_failed=False,
            ),
        ]
        mock_portal_source_class.return_value = mock_source_instance

        _ = PortalCredentials(username="test", password="test")  # noqa: S106

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            result = fetch_missing_tdocs_batch(
                database,
                ["R1-2301234", "S4-2301890"],
            )

        assert result.processed == 2
        assert result.inserted == 2
        assert not result.errors


class TestFetchMissingTdocs:
    """Tests for fetch_missing_tdocs orchestration function."""

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    def test_no_fetch_when_all_present(
        self,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Skip fetch when all requested TDocs are present."""
        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            for tdoc in sample_tdocs:
                database.upsert_tdoc(tdoc)

        config = TDocQueryConfig(
            tdoc_ids=["R1-2301234"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            result = fetch_missing_tdocs(
                database,
                config,
                results,
            )

        assert len(result.refreshed) == 1
        mock_fetch_batch.assert_not_called()

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    def test_fetch_triggered_when_missing(
        self,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Trigger fetch when requested TDocs are missing."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        mock_fetch_batch.return_value = TDocCrawlResult(
            processed=1,
            inserted=1,
            updated=0,
            errors=[],
        )

        config = TDocQueryConfig(
            tdoc_ids=["R1-9999999"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            fetch_missing_tdocs(
                database,
                config,
                results,
            )

        mock_fetch_batch.assert_called_once()
        call_kwargs = mock_fetch_batch.call_args.kwargs
        assert call_kwargs["database"] == database
        assert call_kwargs["missing_ids"] == ["R1-9999999"]

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    def test_no_fetch_without_tdoc_ids(
        self,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
    ) -> None:
        """Skip fetch when query has no specific TDoc IDs."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        config = TDocQueryConfig(
            working_groups=[WorkingGroup.RAN],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            result = fetch_missing_tdocs(
                database,
                config,
                results,
            )

        assert result.refreshed == results
        mock_fetch_batch.assert_not_called()

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    def test_partial_fetch_only_missing(
        self,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Fetch only the missing TDocs when some are present."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        mock_fetch_batch.return_value = TDocCrawlResult(
            processed=1,
            inserted=1,
            updated=0,
            errors=[],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            database.upsert_tdoc(sample_tdocs[0])

        config = TDocQueryConfig(
            tdoc_ids=["R1-2301234", "R1-9999999"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            fetch_missing_tdocs(
                database,
                config,
                results,
            )

        mock_fetch_batch.assert_called_once()
        call_kwargs = mock_fetch_batch.call_args.kwargs
        assert call_kwargs["database"] == database
        assert call_kwargs["missing_ids"] == ["R1-9999999"]
        assert "R1-9999999" in call_kwargs["missing_ids"]
        assert "R1-2301234" not in call_kwargs["missing_ids"]


class TestWhatTheSpecFallback:
    """Integration tests for whatthespec fallback in fetch_missing_tdocs."""

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_via_whatthespec_batch")
    def test_maybe_fetch_uses_whatthespec_when_no_credentials(
        self,
        mock_whatthespec_batch: MagicMock,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify whatthespec fallback is used when credentials unavailable."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        config = TDocQueryConfig(
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []

            mock_fetch_batch.return_value = TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["Portal credentials required for targeted fetch. Set TDC_EOL_USERNAME and TDC_EOL_PASSWORD."],
            )

            metadata = TDocMetadata(
                tdoc_id="S4-260001",
                meeting_id=0,
                title="SA4#135 meeting agenda",
                url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
                source="SA WG4 Chair",
                contact="Test Contact",
                tdoc_type="agenda",
                for_purpose="Approval",
                agenda_item_nbr=Decimal("2"),
                agenda_item_text="Unknown",
                status="available",
                validated=False,
                is_revision_of=None,
                file_size=None,
                date_created=None,
                validation_failed=False,
            )

            def insert_via_whatthespec(
                database: TDocDatabase,
                missing_ids: list[str],
                session: requests.Session | None = None,
                cache_manager_name: str | None = None,
            ) -> TDocCrawlResult:
                _ = database.upsert_tdoc(metadata)
                return TDocCrawlResult(
                    processed=len(missing_ids),
                    inserted=len(missing_ids),
                    updated=0,
                    errors=[],
                )

            mock_whatthespec_batch.side_effect = insert_via_whatthespec

            result = fetch_missing_tdocs(
                database,
                config,
                results,
            )

        # Verify whatthespec was called
        assert mock_whatthespec_batch.called
        # Verify TDoc was fetched and inserted
        assert len(result.refreshed) == 1
        assert result.refreshed[0].tdoc_id == "S4-260001"

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_via_whatthespec_batch")
    def test_whatthespec_fallback_multiple_tdocs(
        self,
        mock_whatthespec_batch: MagicMock,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify whatthespec fetches multiple TDocs."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        config = TDocQueryConfig(
            tdoc_ids=["S4-260001", "S4-260002"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []

            mock_fetch_batch.return_value = TDocCrawlResult(
                processed=2,
                inserted=0,
                updated=0,
                errors=["Portal credentials required"],
            )

            def insert_multiple_via_whatthespec(
                database: TDocDatabase,
                missing_ids: list[str],
                session: requests.Session | None = None,
                cache_manager_name: str | None = None,
            ) -> TDocCrawlResult:
                inserted = 0
                for tdoc_id in missing_ids:
                    if tdoc_id == "S4-260001":
                        metadata = TDocMetadata(
                            tdoc_id="S4-260001",
                            meeting_id=0,
                            title="SA4#135 meeting agenda",
                            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
                            source="SA WG4 Chair",
                            contact="Test Contact",
                            tdoc_type="agenda",
                            for_purpose="Approval",
                            agenda_item_nbr=Decimal("2"),
                            agenda_item_text="Unknown",
                            status="available",
                            validated=False,
                            is_revision_of=None,
                            file_size=None,
                            date_created=None,
                            validation_failed=False,
                        )
                    elif tdoc_id == "S4-260002":
                        metadata = TDocMetadata(
                            tdoc_id="S4-260002",
                            meeting_id=0,
                            title="SA4#135 another document",
                            url="https://www.3gpp.org/tsg_sa/WG4/s4-260002.zip",
                            source="SA WG4 Chair",
                            contact="Test Contact",
                            tdoc_type="discussion",
                            for_purpose="Discussion",
                            agenda_item_nbr=Decimal("3"),
                            agenda_item_text="Unknown",
                            status="available",
                            validated=False,
                            is_revision_of=None,
                            file_size=None,
                            date_created=None,
                            validation_failed=False,
                        )
                    else:
                        continue
                    _ = database.upsert_tdoc(metadata)
                    inserted += 1
                return TDocCrawlResult(
                    processed=len(missing_ids),
                    inserted=inserted,
                    updated=0,
                    errors=[],
                )

            mock_whatthespec_batch.side_effect = insert_multiple_via_whatthespec

            result = fetch_missing_tdocs(
                database,
                config,
                results,
            )

        # Verify whatthespec was called
        assert mock_whatthespec_batch.called
        assert len(result.refreshed) >= 2
        fetched_ids = {tdoc.tdoc_id for tdoc in result.refreshed}
        assert "S4-260001" in fetched_ids
        assert "S4-260002" in fetched_ids

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_via_whatthespec_batch")
    def test_whatthespec_fallback_graceful_failure(
        self,
        mock_whatthespec_batch: MagicMock,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify whatthespec failure is handled gracefully."""
        config = TDocQueryConfig(
            tdoc_ids=["S4-999999"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []

            mock_fetch_batch.return_value = TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["Portal credentials required"],
            )

            # No-op for fallback (simulates failure)
            mock_whatthespec_batch.return_value = TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["WhatTheSpec resolution failed"],
            )

            result = fetch_missing_tdocs(
                database,
                config,
                results,
            )

        # Verify whatthespec was called
        assert mock_whatthespec_batch.called
        # TDoc should still be missing (fallback failed)
        assert len(result.refreshed) == 0

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_via_whatthespec_batch")
    def test_no_whatthespec_when_credentials_available(
        self,
        mock_whatthespec_batch: MagicMock,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify whatthespec is NOT used when credentials available."""
        config = TDocQueryConfig(
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []
            _ = PortalCredentials(username="test", password="test")

            mock_fetch_batch.return_value = TDocCrawlResult(
                processed=1,
                inserted=1,
                updated=0,
                errors=[],
            )

            fetch_missing_tdocs(
                database,
                config,
                results,
            )

        # Verify whatthespec was NOT called (credentials took precedence)
        mock_whatthespec_batch.assert_not_called()

    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_missing_tdocs_batch")
    @patch("tdoc_crawler.tdocs.operations.fetch.fetch_via_whatthespec_batch")
    def test_whatthespec_inserts_to_database(
        self,
        mock_whatthespec_batch: MagicMock,
        mock_fetch_batch: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Verify whatthespec-resolved TDoc is inserted into database."""
        manager = CacheManager(root_path=test_db_path.parent, ensure_paths=True)
        _ = manager.register()

        metadata = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=0,
            title="SA4#135 meeting agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Gilles Teniou",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            agenda_item_text="Unknown",
            status="available",
            validated=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validation_failed=False,
        )

        config = TDocQueryConfig(
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []

            mock_fetch_batch.return_value = TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["Portal credentials required"],
            )

            def insert_metadata(
                database: TDocDatabase,
                missing_ids: list[str],
                session: requests.Session | None = None,
                cache_manager_name: str | None = None,
            ) -> TDocCrawlResult:
                _ = database.upsert_tdoc(metadata)
                return TDocCrawlResult(
                    processed=len(missing_ids),
                    inserted=len(missing_ids),
                    updated=0,
                    errors=[],
                )

            mock_whatthespec_batch.side_effect = insert_metadata

            fetch_missing_tdocs(
                database,
                config,
                results,
            )

        # Query database to verify TDoc was inserted
        with TDocDatabase(test_db_path) as database:
            query_config = TDocQueryConfig(tdoc_ids=["S4-260001"])
            results = database.query_tdocs(query_config)
            assert len(results) >= 1
            assert results[0].tdoc_id == "S4-260001"
            assert results[0].title == "SA4#135 meeting agenda"
            assert results[0].source == "SA WG4 Chair"
            assert results[0].contact == "Gilles Teniou"
