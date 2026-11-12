"""Test the meeting document list feature (Excel-based TDoc metadata source)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import niquests as requests
import pandas as pd
import pytest

from tdoc_crawler.tdocs.sources.doclist import (
    DocumentListError,
    _construct_tdoc_url,
    fetch_meeting_document_list,
    parse_excel_document_list,
    parse_excel_work_items,
    parse_work_item_ids,
)
from tdoc_crawler.utils.version_types import AgendaItem


class TestConstructTdocUrl:
    """Issue #6: files_url already ends with /Docs/ and must not be doubled."""

    def test_files_url_ending_in_docs_not_doubled(self) -> None:
        """Portal MtgDocURL already points at the Docs dir; URL must keep a single /Docs/."""
        url = _construct_tdoc_url(
            "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/",
            "S4-261564",
        )
        assert url == "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261564.zip"
        assert "/Docs/Docs/" not in url

    def test_files_url_ending_in_docs_no_trailing_slash(self) -> None:
        url = _construct_tdoc_url(
            "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs",
            "S4-261564",
        )
        assert url == "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261564.zip"

    def test_files_url_without_docs_segment_appends_it(self) -> None:
        """files_url pointing above the Docs dir still gets a single /Docs/ appended."""
        url = _construct_tdoc_url(
            "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e",
            "S4-261564",
        )
        assert url == "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261564.zip"

    def test_upper_tdoc_id(self) -> None:
        url = _construct_tdoc_url(
            "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs",
            "s4-261564",
        )
        assert url == "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261564.zip"

    def test_none_files_url_returns_none(self) -> None:
        assert _construct_tdoc_url(None, "S4-261564") is None


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
        assert result[0].agenda_item_nbr == AgendaItem("7.1")
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

    def test_parse_excel_captures_reservation_and_upload_dates(self) -> None:
        """Issue #5: Reservation date / Uploaded Excel columns must be captured."""
        test_data = {
            "TDoc": ["S4-261564", "S4-261592"],
            "Title": ["Doc A", "Doc B"],
            "Type": ["CR", "CR"],
            "For": ["Agreement", "Agreement"],
            "Source": ["Orange", "Orange, Deutsche"],
            "Contact": ["John", "Jane"],
            "Agenda Item": ["9.6", "9.7"],
            # Exact formats from issue #5
            "Reservation date": ["8/18/2026 3:37:04 PM", "8/18/2026 5:46:06 PM"],
            "Uploaded": ["2026-08-18 21:57:14.217000", "2026-08-18 18:05:40"],
        }

        df = pd.DataFrame(test_data)
        excel_content = _create_test_excel_bytes(df)

        result = parse_excel_document_list(excel_content, meeting_id=12345)

        assert len(result) == 2
        by_id = {r.tdoc_id: r for r in result}

        a = by_id["S4-261564"]
        assert a.reservation_date is not None
        assert a.reservation_date.year == 2026
        assert a.reservation_date.month == 8
        assert a.reservation_date.hour == 15  # 3:37:04 PM -> 15:37:04
        assert a.uploaded_at is not None
        assert a.uploaded_at.hour == 21
        assert a.uploaded_at.microsecond == 217000

        b = by_id["S4-261592"]
        # S4-261592 was uploaded BEFORE S4-261564 despite higher TDoc number
        assert b.uploaded_at < a.uploaded_at

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


class TestWorkItemParsing:
    """Work items come from the document list 'Related WIs' column."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ULBC-MED", ["ULBC-MED"]),
            ("FS_ULBC, ULBC-MED", ["FS_ULBC", "ULBC-MED"]),
            ("fs_ulbc;ULBC-MED", ["FS_ULBC", "ULBC-MED"]),
            ("ULBC-MED, ULBC-MED", ["ULBC-MED"]),
            ("  ULBC-MED  ", ["ULBC-MED"]),
            ("", []),
            (None, []),
            ("nan", []),
            ("N/A", []),
            ("-", []),
        ],
    )
    def test_parse_work_item_ids(self, raw: str | None, expected: list[str]) -> None:
        assert parse_work_item_ids(raw) == expected

    def test_parse_excel_work_items(self) -> None:
        df = pd.DataFrame(
            {
                "TDoc": ["S4AA260090", "S4AA260091", "S4AA260092"],
                "Title": ["a", "b", "c"],
                "Related WIs": ["ULBC-MED", "FS_ULBC, ULBC-MED", None],
            }
        )

        result = parse_excel_work_items(_create_test_excel_bytes(df), meeting_id=85916)

        assert result == {"S4AA260090": ["ULBC-MED"], "S4AA260091": ["FS_ULBC", "ULBC-MED"]}


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
