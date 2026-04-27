"""Test the meeting document list feature (Excel-based TDoc metadata source)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import niquests as requests
import pandas as pd
import pytest

from tdoc_crawler.tdocs.sources.doclist import DocumentListError, fetch_meeting_document_list, parse_excel_document_list


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
        assert result[0].agenda_item_nbr == "7.1"
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
        with pytest.raises(DocumentListError, match="No recognizable TDoc ID columns found"):
            parse_excel_document_list(excel_content, meeting_id=12345)

    def test_fetch_meeting_document_list_network_error(self) -> None:
        """Test handling of network errors."""
        with patch("tdoc_crawler.tdocs.sources.doclist.create_cached_session") as mock_session:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.RequestException("Network error")
            mock_session.return_value.get.return_value = mock_response

            with pytest.raises(DocumentListError):
                fetch_meeting_document_list(
                    meeting_id=12345,
                )


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
