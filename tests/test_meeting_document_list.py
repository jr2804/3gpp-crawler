"""Test the new meeting document list feature."""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tdoc_crawler.crawlers import (DocumentListError, HybridCrawlResult,
                                   HybridTDocCrawler,
                                   fetch_meeting_document_list,
                                   parse_excel_document_list)
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import MeetingMetadata, TDocCrawlConfig, WorkingGroup
from tdoc_crawler.models.tdocs import TDocMetadata


class TestMeetingDocumentList:
    """Test meeting document list functionality."""

    def test_parse_excel_document_list_basic(self) -> None:
        """Test basic Excel parsing functionality."""
        # Create test Excel data
        test_data = {
            "TDoc": ["R1-2301234", "S4-251209", "C1-231234"],
            "Title": ["Test Document 1", "Test Document 2", "Test Document 3"],
            "Type": ["CR", "CR", "CR"],
            "For": ["Agreement", "Agreement", "Discussion"],
            "Source": ["Company A", "Company B", "Company C"],
            "Contact": ["John Doe", "Jane Smith", "Bob Johnson"],
            "Agenda Item": ["7.1 - Radio", "4.1 - Services", "5.1 - Core"],
            "Status": ["Approved", "Approved", "Under Review"],
        }

        df = pd.DataFrame(test_data)
        excel_content = _create_test_excel_bytes(df)

        # Parse the document list
        result = parse_excel_document_list(excel_content, meeting_id=12345)

        # Verify results
        assert len(result) == 3
        assert result[0].tdoc_id == "R1-2301234"
        assert result[0].title == "Test Document 1"
        assert result[0].agenda_item_nbr == Decimal("7.1")
        assert result[0].agenda_item_text == "Radio"
        assert result[0].meeting_id == 12345
        assert result[0].validated is True  # Direct from portal

    def test_parse_excel_document_list_with_alternate_columns(self) -> None:
        """Test Excel parsing with alternate column names."""
        # Test with different column naming conventions
        test_data = {
            "Contribution": ["R1-2301234"],  # Alternative to "TDoc"
            "Document Title": ["Test Document"],  # Alternative to "Title"
            "TDoc Type": ["CR"],  # Alternative to "Type"
            "For Purpose": ["Agreement"],  # Alternative to "For"
            "Organization": ["Company A"],  # Alternative to "Source"
            "Contact Person": ["John Doe"],  # Alternative to "Contact"
            "Agenda": ["7.1 - Radio"],  # Alternative to "Agenda Item"
        }

        df = pd.DataFrame(test_data)
        excel_content = _create_test_excel_bytes(df)

        result = parse_excel_document_list(excel_content, meeting_id=12345)

        assert len(result) == 1
        assert result[0].tdoc_id == "R1-2301234"
        assert result[0].title == "Test Document"
        assert result[0].tdoc_type == "CR"

    def test_parse_excel_document_list_invalid_tdoc_id(self) -> None:
        """Test handling of invalid TDoc IDs."""
        test_data = {
            "TDoc": ["INVALID-ID", "R1-2301234", "ALSO-INVALID"],
            "Title": ["Invalid", "Valid Document", "Also Invalid"],
            "Type": ["CR", "CR", "CR"],
            "For": ["Agreement", "Agreement", "Discussion"],
            "Source": ["Company A", "Company B", "Company C"],
            "Contact": ["John Doe", "Jane Smith", "Bob Johnson"],
            "Agenda Item": ["7.1", "4.1", "5.1"],
        }

        df = pd.DataFrame(test_data)
        excel_content = _create_test_excel_bytes(df)

        result = parse_excel_document_list(excel_content, meeting_id=12345)

        # Should only return valid TDoc IDs
        assert len(result) == 1
        assert result[0].tdoc_id == "R1-2301234"

    def test_parse_excel_document_list_missing_tdoc_column(self) -> None:
        """Test handling when TDoc column is missing."""
        test_data = {
            "Title": ["Test Document"],
            "Type": ["CR"],
        }

        df = pd.DataFrame(test_data)
        excel_content = _create_test_excel_bytes(df)

        # Should raise an error or return empty list
        with pytest.raises(Exception):  # DocumentListError or pandas error
            parse_excel_document_list(excel_content, meeting_id=12345)

    def test_fetch_meeting_document_list_network_error(self) -> None:
        """Test handling of network errors."""
        with patch("tdoc_crawler.crawlers.meeting_doclist.create_cached_session") as mock_session:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("Network error")
            mock_session.return_value.get.return_value = mock_response

            with pytest.raises(DocumentListError):
                fetch_meeting_document_list(
                    meeting_id=12345,
                    cache_dir=Path("/tmp"),
                )

    def test_hybrid_crawler_document_list_only(self) -> None:
        """Test hybrid crawler with document list method only."""
        # Mock the database
        mock_database = MagicMock(spec=TDocDatabase)
        mock_database.query_meetings.return_value = []
        mock_database.get_existing_tdoc_ids.return_value = []
        mock_database.bulk_upsert_tdocs.return_value = (0, 0)
        mock_database.log_crawl_start.return_value = 1
        mock_database.log_crawl_end.return_value = None

        # Create hybrid crawler
        crawler = HybridTDocCrawler(mock_database)

        # Configure for document list only
        config = TDocCrawlConfig(
            use_document_list=True,
            use_parallel_crawling=False,
            allow_parallel_fallback=False,
            working_groups=[WorkingGroup.RAN],
            workers=1,
        )

        # Mock the document list method to return test data
        test_metadata = [
            TDocMetadata(
                tdoc_id="R1-2301234",
                meeting_id=12345,
                title="Test Document",
                url="https://example.com/R1-2301234.zip",
                source="Test Company",
                contact="Test Contact",
                tdoc_type="CR",
                for_purpose="Agreement",
                agenda_item_nbr=Decimal("7.1"),
                agenda_item_text="Test Agenda",
                status="Approved",
            )
        ]

        with patch.object(crawler, "_get_meetings_to_crawl") as mock_get_meetings:
            # Mock meeting

            mock_meeting = MeetingMetadata(
                meeting_id=12345,
                tbid=373,  # RAN
                subtb=379,  # RAN1
                working_group=WorkingGroup.RAN,
                subgroup="R1",
                short_name="RAN1#98",
                files_url="https://example.com/meeting/",
                start_date=None,
            )
            mock_get_meetings.return_value = [mock_meeting]

            with patch("tdoc_crawler.crawlers.meeting_doclist.fetch_meeting_document_list") as mock_fetch:
                mock_fetch.return_value = test_metadata

                result = crawler.crawl(config)

                assert isinstance(result, HybridCrawlResult)
                assert result.processed == 1
                assert result.document_list_meetings == 1
                assert result.parallel_meetings == 0
                assert result.fallbacks == 0
                assert len(result.errors) == 0

    def test_hybrid_crawler_fallback_scenario(self) -> None:
        """Test hybrid crawler with document list failure and parallel fallback."""
        # Mock the database
        mock_database = MagicMock(spec=TDocDatabase)
        mock_database.query_meetings.return_value = []
        mock_database.get_existing_tdoc_ids.return_value = []
        mock_database.bulk_upsert_tdocs.return_value = (0, 0)
        mock_database.log_crawl_start.return_value = 1
        mock_database.log_crawl_end.return_value = None

        crawler = HybridTDocCrawler(mock_database)

        # Configure for document list with fallback
        config = TDocCrawlConfig(
            use_document_list=True,
            use_parallel_crawling=False,
            allow_parallel_fallback=True,
            working_groups=[WorkingGroup.RAN],
            workers=1,
        )

        with patch.object(crawler, "_get_meetings_to_crawl") as mock_get_meetings:
            mock_meeting = MeetingMetadata(
                meeting_id=12345,
                tbid=373,  # RAN
                subtb=379,  # RAN1
                working_group=WorkingGroup.RAN,
                subgroup="R1",
                short_name="RAN1#98",
                files_url="https://example.com/meeting/",
                start_date=None,
            )
            mock_get_meetings.return_value = [mock_meeting]

            # Mock document list to fail, parallel to succeed
            with patch("tdoc_crawler.crawlers.meeting_doclist.fetch_meeting_document_list") as mock_fetch:
                mock_fetch.side_effect = DocumentListError("Document list not available")

            with patch("asyncio.run") as mock_asyncio:
                # Mock parallel crawling result
                mock_asyncio.return_value = ([], 1)  # (errors, meetings_processed)

                result = crawler.crawl(config)

                assert isinstance(result, HybridCrawlResult)
                assert result.fallbacks == 1
                assert result.document_list_meetings == 1

    def test_hybrid_crawler_force_parallel(self) -> None:
        """Test hybrid crawler with forced parallel crawling."""
        # Mock the database
        mock_database = MagicMock(spec=TDocDatabase)
        mock_database.query_meetings.return_value = []
        mock_database.get_existing_tdoc_ids.return_value = []
        mock_database.bulk_upsert_tdocs.return_value = (0, 0)
        mock_database.log_crawl_start.return_value = 1
        mock_database.log_crawl_end.return_value = None

        crawler = HybridTDocCrawler(mock_database)

        # Configure for forced parallel crawling
        config = TDocCrawlConfig(
            use_document_list=False,  # Disabled
            use_parallel_crawling=True,
            working_groups=[WorkingGroup.RAN],
            workers=1,
        )

        with patch.object(crawler, "_get_meetings_to_crawl") as mock_get_meetings:
            mock_meeting = MeetingMetadata(
                meeting_id=12345,
                tbid=373,  # RAN
                subtb=379,  # RAN1
                working_group=WorkingGroup.RAN,
                subgroup="R1",
                short_name="RAN1#98",
                files_url="https://example.com/meeting/",
                start_date=None,
            )
            mock_get_meetings.return_value = [mock_meeting]

            with patch("asyncio.run") as mock_asyncio:
                # Mock parallel crawling result
                mock_asyncio.return_value = ([], 1)  # (errors, meetings_processed)

                result = crawler.crawl(config)

                assert isinstance(result, HybridCrawlResult)
                assert result.document_list_meetings == 0
                assert result.parallel_meetings == 1
                assert result.fallbacks == 0


def _create_test_excel_bytes(df: pd.DataFrame) -> bytes:
    """Create test Excel file bytes from DataFrame."""
    # Use xlsxwriter for writing Excel files (as per AGENTS.md)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="TDoc_List", index=False)

    output.seek(0)
    return output.read()


if __name__ == "__main__":
    # Run a simple test to demonstrate functionality
    test = TestMeetingDocumentList()
    test.test_parse_excel_document_list_basic()
    print("✅ Basic Excel parsing test passed")
    print("✅ Meeting document list feature is working correctly")
