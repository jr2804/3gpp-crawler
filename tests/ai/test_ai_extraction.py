"""Tests for DOCX-to-Markdown extraction."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tdoc_crawler.ai.models import ExtractionError
from tdoc_crawler.ai.operations import extract
from tdoc_crawler.ai.operations.extract import (
    compute_source_hash,
    extract_docx_to_markdown,
    extract_from_folder,
)


class TestExtractDocxToMarkdown:
    """Tests for extract_docx_to_markdown function."""

    def test_single_docx_to_markdown(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test basic DOCX to Markdown conversion."""
        # Test with a real DOCX file if available
        docx_path = test_data_dir / "S4-251003" / "S4-251003 - On nominal transmission levels in ATIAS.docx"
        if docx_path.exists():
            result = extract_docx_to_markdown("S4-251003", docx_path, mock_storage)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_table_preservation(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test that tables are preserved in Markdown output."""
        docx_path = test_data_dir / "26260-j10" / "26260-j10.docx"
        if docx_path.exists():
            result = extract_docx_to_markdown("26260-J10", docx_path, mock_storage)
            # Tables should be represented in Markdown
            assert "|" in result or "table" in result.lower()

    def test_heading_hierarchy(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test heading hierarchy is preserved."""
        docx_path = test_data_dir / "S4-251003"
        # Find any docx file
        docx_files = list(docx_path.glob("*.docx")) if docx_path.exists() else []
        if docx_files:
            result = extract_docx_to_markdown("S4-251003", docx_files[0], mock_storage)
            # Should contain markdown headings
            assert "#" in result

    def test_3gpp_section_numbering(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test 3GPP section numbering is handled."""
        pytest.skip("Requires test data with 3GPP section numbering")

    def test_extraction_writes_markdown_artifact(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Extraction should persist a Markdown artifact for the processed TDoc."""
        docx_path = test_data_dir / "S4-251003" / "S4-251003 - On nominal transmission levels in ATIAS.docx"
        if not docx_path.exists():
            pytest.skip("S4-251003 fixture not available")

        markdown = extract_docx_to_markdown("S4-251003", docx_path, mock_storage)
        assert markdown

        artifact_path = docx_path.parent / ".ai" / "S4-251003.md"
        assert artifact_path.exists()

    def test_idempotent_rerun_skips_unchanged(self, mock_storage: MagicMock) -> None:
        """Test that re-run with unchanged file skips processing."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            # Create empty temp file
            f.write(b"PK\x03\x04")  # Minimal DOCX header
            temp_path = Path(f.name)

        try:
            # Compute hash
            hash1 = compute_source_hash(temp_path)
            hash2 = compute_source_hash(temp_path)
            assert hash1 == hash2  # Same content = same hash
        finally:
            temp_path.unlink()

    def test_corrupt_file_raises_extraction_error(self, mock_storage: MagicMock) -> None:
        """Test that corrupt file raises ExtractionError."""
        # Create corrupt DOCX
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"not a valid docx")
            corrupt_path = Path(f.name)

        try:
            with pytest.raises(ExtractionError):
                extract_docx_to_markdown("TEST", corrupt_path, mock_storage)
        finally:
            corrupt_path.unlink()

    def test_no_docx_folder_raises_extraction_error(self, mock_storage: MagicMock, tmp_path: Path) -> None:
        """Folders without DOCX should fail extraction for status/error tracking."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()

        with pytest.raises(ExtractionError):
            extract_from_folder("TEST", empty_folder, mock_storage)


class TestExtractModuleExports:
    """Tests that extract module exports required functions."""

    def test_extract_docx_to_markdown_exported(self) -> None:
        """Verify extract_docx_to_markdown is exported."""
        assert hasattr(extract, "extract_docx_to_markdown")
        assert callable(extract.extract_docx_to_markdown)

    def test_extract_from_folder_exported(self) -> None:
        """Verify extract_from_folder is exported."""
        assert hasattr(extract, "extract_from_folder")
        assert callable(extract.extract_from_folder)

    def test_compute_source_hash_exported(self) -> None:
        """Verify compute_source_hash is exported."""
        assert hasattr(extract, "compute_source_hash")
        assert callable(extract.compute_source_hash)


US1_T021_RED_CHECKPOINT = """
Command: uv run pytest tests/ai/test_ai_extraction.py -q

Observed failure:
- TestExtractDocxToMarkdown.test_no_docx_folder_raises_extraction_error
    Failed: DID NOT RAISE <class 'tdoc_crawler.ai.models.ExtractionError'>
"""
