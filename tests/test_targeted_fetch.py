"""Tests for targeted fetch functionality."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import insert_sample_meetings

from tdoc_crawler.cli.fetching import fetch_missing_tdocs, maybe_fetch_missing_tdocs
from tdoc_crawler.cli.helpers import infer_working_groups_from_ids
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import PortalCredentials, QueryConfig, TDocMetadata, WorkingGroup


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


class TestFetchMissingTdocs:
    """Tests for fetch_missing_tdocs function."""

    @patch("tdoc_crawler.cli.fetching.fetch_tdoc_metadata")
    def test_fetch_missing_creates_config(
        self,
        mock_fetch_portal: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Ensure targeted fetch creates proper config."""
        # Mock portal response (now returns TDocMetadata)
        mock_fetch_portal.return_value = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=0,
            meeting_name="RAN1#98",
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
        )

        credentials = PortalCredentials(username="test", password="test")

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            result = fetch_missing_tdocs(
                database,
                test_db_path.parent,
                ["R1-2301234"],
                credentials=credentials,
            )

        assert result.processed == 1
        assert result.inserted == 1
        assert not result.errors
        mock_fetch_portal.assert_called_once()

    @patch("tdoc_crawler.cli.fetching.fetch_tdoc_metadata")
    def test_fetch_missing_infers_working_groups(
        self,
        mock_fetch_portal: MagicMock,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify working groups are inferred from target IDs."""
        # Mock portal responses (now return TDocMetadata instances)
        mock_fetch_portal.side_effect = [
            TDocMetadata(
                tdoc_id="R1-2301234",
                meeting_id=0,
                meeting_name="RAN1#98",
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
            ),
            TDocMetadata(
                tdoc_id="S4-2301890",
                meeting_id=0,
                meeting_name="SA4#134",
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
            ),
        ]

        credentials = PortalCredentials(username="test", password="test")  # noqa: S106

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            result = fetch_missing_tdocs(
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
    """Tests for maybe_fetch_missing_tdocs function."""

    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    def test_no_fetch_when_all_present(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict],
    ) -> None:
        """Skip fetch when all requested TDocs are present."""
        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            for tdoc in sample_tdocs:
                database.upsert_tdoc(tdoc)

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["R1-2301234"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            refreshed = maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        assert len(refreshed) == 1
        mock_fetch.assert_not_called()

    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
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
            maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        missing_ids = call_args[0][2]
        assert "R1-9999999" in missing_ids

    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
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
            refreshed = maybe_fetch_missing_tdocs(
                database,
                test_db_path.parent,
                config,
                results,
            )

        assert refreshed == results
        mock_fetch.assert_not_called()

    @patch("tdoc_crawler.cli.fetching.fetch_missing_tdocs")
    def test_partial_fetch_only_missing(
        self,
        mock_fetch: MagicMock,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict],
    ) -> None:
        """Fetch only the missing TDocs when some are present."""
        mock_fetch.return_value = MagicMock(
            processed=1,
            inserted=1,
            updated=0,
            errors=[],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            database.upsert_tdoc(sample_tdocs[0])

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["R1-2301234", "R1-9999999"],
        )

        with TDocDatabase(test_db_path) as database:
            results = database.query_tdocs(config)
            maybe_fetch_missing_tdocs(
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


class TestWhatTheSpecFallback:
    """Integration tests for whatthespec fallback in maybe_fetch_missing_tdocs."""

    def test_maybe_fetch_uses_whatthespec_when_no_credentials(
        self,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify whatthespec fallback is used when credentials unavailable.

        This test simulates:
        1. Database lookup fails to find TDoc
        2. No portal credentials available (credentials=None)
        3. Portal fetch returns credentials error
        4. whatthespec fallback is triggered
        5. whatthespec returns TDocMetadata
        6. TDoc is inserted into database
        """
        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            # Start with empty results (TDoc not in database)
            results: list[TDocMetadata] = []
            # Call maybe_fetch_missing_tdocs with NO credentials
            # Mock fetch_missing_tdocs to return credentials error
            with patch(
                "tdoc_crawler.cli.fetching.fetch_missing_tdocs",
                return_value=MagicMock(
                    processed=1,
                    inserted=0,
                    updated=0,
                    errors=["Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD."],
                ),
            ):
                # Mock the _fetch_via_whatthespec to actually do something useful
                with patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec") as mock_whatthespec_fetch:

                    def insert_via_whatthespec(database, cache_dir, missing_ids) -> None:
                        """Helper to insert TDoc via mocked whatthespec."""
                        metadata = TDocMetadata(
                            tdoc_id="S4-260001",
                            meeting_id=0,
                            meeting_name="S4-135",
                            title="SA4#135 meeting agenda",
                            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
                            source="SA WG4 Chair",
                            contact="Test Contact",
                            tdoc_type="agenda",
                            for_purpose="Approval",
                            agenda_item_nbr=Decimal("2"),
                            status="available",
                            validated=False,
                        )
                        database.upsert_tdoc(metadata)

                    mock_whatthespec_fetch.side_effect = insert_via_whatthespec
                    refreshed = maybe_fetch_missing_tdocs(
                        database,
                        test_db_path.parent,
                        config,
                        results,
                        credentials=None,
                    )

            # Verify whatthespec was called
            assert mock_whatthespec_fetch.called
            # Verify TDoc was fetched and inserted
            assert len(refreshed) == 1
            assert refreshed[0].tdoc_id == "S4-260001"

    def test_whatthespec_fallback_multiple_tdocs(
        self,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify whatthespec fetches multiple TDocs.

        This test verifies:
        1. Multiple TDocs missing from database
        2. No credentials available
        3. whatthespec resolves all TDocs
        4. All TDocs inserted into database
        """
        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["S4-260001", "S4-260002"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []
            with (
                patch(
                    "tdoc_crawler.cli.fetching.fetch_missing_tdocs",
                    return_value=MagicMock(
                        processed=2,
                        inserted=0,
                        updated=0,
                        errors=["Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD."],
                    ),
                ),
                patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec") as mock_whatthespec_fetch,
            ):

                def insert_multiple_via_whatthespec(database, cache_dir, missing_ids) -> None:
                    """Helper to insert multiple TDocs via mocked whatthespec."""
                    for tdoc_id in missing_ids:
                        if tdoc_id == "S4-260001":
                            metadata = TDocMetadata(
                                tdoc_id="S4-260001",
                                meeting_id=0,
                                meeting_name="S4-135",
                                title="SA4#135 meeting agenda",
                                url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
                                source="SA WG4 Chair",
                                contact="Test Contact",
                                tdoc_type="agenda",
                                for_purpose="Approval",
                                agenda_item_nbr=Decimal("2"),
                                status="available",
                                validated=False,
                            )
                        elif tdoc_id == "S4-260002":
                            metadata = TDocMetadata(
                                tdoc_id="S4-260002",
                                meeting_id=0,
                                meeting_name="S4-135",
                                title="SA4#135 another document",
                                url="https://www.3gpp.org/tsg_sa/WG4/s4-260002.zip",
                                source="SA WG4 Chair",
                                contact="Test Contact",
                                tdoc_type="discussion",
                                for_purpose="Discussion",
                                agenda_item_nbr=Decimal("3"),
                                status="available",
                                validated=False,
                            )
                        else:
                            continue
                        database.upsert_tdoc(metadata)

                mock_whatthespec_fetch.side_effect = insert_multiple_via_whatthespec
                refreshed = maybe_fetch_missing_tdocs(
                    database,
                    test_db_path.parent,
                    config,
                    results,
                    credentials=None,
                )

            # Verify whatthespec was called
            assert mock_whatthespec_fetch.called
            assert len(refreshed) >= 2
            fetched_ids = {tdoc.tdoc_id for tdoc in refreshed}
            assert "S4-260001" in fetched_ids
            assert "S4-260002" in fetched_ids

    def test_whatthespec_fallback_graceful_failure(
        self,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify whatthespec failure is handled gracefully.

        This test verifies:
        1. whatthespec raises error or returns no data
        2. Error is caught and logged (not crashing CLI)
        3. Function continues processing
        4. Results reflect TDoc still missing
        """
        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["S4-999999"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []
            # This should not raise, but handle gracefully
            with (
                patch(
                    "tdoc_crawler.cli.fetching.fetch_missing_tdocs",
                    return_value=MagicMock(
                        processed=1,
                        inserted=0,
                        updated=0,
                        errors=["Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD."],
                    ),
                ),
                patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec") as mock_whatthespec_fetch,
            ):
                # No-op for fallback (simulates failure)
                mock_whatthespec_fetch.side_effect = lambda *args, **kwargs: None
                refreshed = maybe_fetch_missing_tdocs(
                    database,
                    test_db_path.parent,
                    config,
                    results,
                    credentials=None,
                )

        # Verify whatthespec was called
        assert mock_whatthespec_fetch.called
        # TDoc should still be missing (fallback failed)
        assert len(refreshed) == 0

    def test_no_whatthespec_when_credentials_available(
        self,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify whatthespec is NOT used when credentials available.

        This test verifies:
        1. Portal credentials are provided
        2. Portal fetch returns no error
        3. whatthespec fallback is NOT triggered
        """
        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []
            credentials = PortalCredentials(username="test", password="test")
            # Mock fetch_missing_tdocs to succeed (no error)
            with (
                patch(
                    "tdoc_crawler.cli.fetching.fetch_missing_tdocs",
                    return_value=MagicMock(
                        processed=1,
                        inserted=1,
                        updated=0,
                        errors=[],
                    ),
                ),
                patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec") as mock_whatthespec_fetch,
            ):
                maybe_fetch_missing_tdocs(
                    database,
                    test_db_path.parent,
                    config,
                    results,
                    credentials=credentials,
                )

        # Verify whatthespec was NOT called (credentials took precedence)
        mock_whatthespec_fetch.assert_not_called()

    def test_whatthespec_inserts_to_database(
        self,
        test_db_path: Path,
        sample_meetings: list[dict],
    ) -> None:
        """Verify whatthespec-resolved TDoc is inserted into database.

        This test verifies:
        1. whatthespec returns TDocMetadata
        2. TDoc is successfully inserted into database
        3. Subsequent query finds the TDoc
        """
        metadata = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=0,
            meeting_name="S4-135",
            title="SA4#135 meeting agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Gilles Teniou",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr=Decimal("2"),
            status="available",
            validated=False,
        )

        config = QueryConfig(
            cache_dir=test_db_path.parent,
            tdoc_ids=["S4-260001"],
        )

        with TDocDatabase(test_db_path) as database:
            insert_sample_meetings(database, sample_meetings)
            results: list[TDocMetadata] = []
            with (
                patch(
                    "tdoc_crawler.cli.fetching.fetch_missing_tdocs",
                    return_value=MagicMock(
                        processed=1,
                        inserted=0,
                        updated=0,
                        errors=["Portal credentials required for targeted fetch. Set EOL_USERNAME and EOL_PASSWORD."],
                    ),
                ),
                patch("tdoc_crawler.cli.fetching._fetch_via_whatthespec") as mock_whatthespec_fetch,
            ):

                def insert_metadata(database, cache_dir, missing_ids) -> None:
                    database.upsert_tdoc(metadata)

                mock_whatthespec_fetch.side_effect = insert_metadata
                maybe_fetch_missing_tdocs(
                    database,
                    test_db_path.parent,
                    config,
                    results,
                    credentials=None,
                )

        # Query database to verify TDoc was inserted
        with TDocDatabase(test_db_path) as database:
            query_config = QueryConfig(cache_dir=test_db_path.parent, tdoc_ids=["S4-260001"])
            results = database.query_tdocs(query_config)
            assert len(results) >= 1
            assert results[0].tdoc_id == "S4-260001"
            assert results[0].title == "SA4#135 meeting agenda"
            assert results[0].source == "SA WG4 Chair"
            assert results[0].contact == "Gilles Teniou"
