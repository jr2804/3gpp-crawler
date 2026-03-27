"""Tests for AI pipeline error recovery and workspace state consistency.

Verifies that document processing failures are properly reported via
ProcessingResult and do not corrupt workspace state or prevent
other documents from being processed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from threegpp_ai.lightrag.processor import (
    DocumentProcessor,
    ProcessingResultStatus,
)
from threegpp_ai.models import ConversionError, ExtractionError


@pytest.fixture
def mock_rag() -> MagicMock:
    """Create a mock TDocRAG instance."""
    rag = MagicMock()
    rag.insert = AsyncMock()
    rag.start = AsyncMock()
    rag.stop = AsyncMock()
    rag.workspace_index = None
    return rag


@pytest.fixture
def processor(mock_rag: MagicMock) -> DocumentProcessor:
    """Create a DocumentProcessor with mocked RAG."""
    proc = DocumentProcessor.__new__(DocumentProcessor)
    proc.config = MagicMock()
    proc.rag = mock_rag
    return proc


class TestExtractionFailure:
    """Test extraction failures produce correct ProcessingResult."""

    @pytest.mark.asyncio
    async def test_extraction_error_returns_error_status(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """ExtractionError from extract_document_structured yields ERROR result."""
        docx_file = tmp_path / "broken.docx"
        docx_file.write_text("not a real docx")

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            side_effect=ExtractionError("Corrupt DOCX file"),
        ):
            result = await processor.process_file(docx_file)

        assert result.status == ProcessingResultStatus.ERROR
        assert "Corrupt DOCX file" in (result.error or "")
        assert result.file_path == str(docx_file)

    @pytest.mark.asyncio
    async def test_conversion_error_returns_error_status(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """ConversionError from Office-to-PDF conversion yields ERROR result."""
        docx_file = tmp_path / "needs_conversion.docx"
        docx_file.write_bytes(b"\xd0\xcf\x11\xe0")  # OLE2 header

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            side_effect=ConversionError("LibreOffice conversion failed"),
        ):
            result = await processor.process_file(docx_file)

        assert result.status == ProcessingResultStatus.ERROR
        assert "LibreOffice conversion failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_file_extraction_error(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """Missing file triggers ExtractionError → ERROR status."""
        missing_file = tmp_path / "nonexistent.pdf"

        # extract_document_structured raises ExtractionError for missing files
        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            side_effect=ExtractionError(f"Source file does not exist: {missing_file}"),
        ):
            result = await processor.process_file(missing_file)

        assert result.status == ProcessingResultStatus.ERROR


class TestRAGInsertionFailure:
    """Test RAG insertion failures are properly caught and reported."""

    @pytest.mark.asyncio
    async def test_rag_insert_connection_error(self, processor: DocumentProcessor, mock_rag: MagicMock, tmp_path: Path) -> None:
        """Connection error during rag.insert() yields ERROR result."""
        mock_rag.insert.side_effect = ConnectionError("Connection refused")

        fake_extraction = MagicMock()
        fake_extraction.content = "A" * 100  # Above 50-char minimum

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            return_value=fake_extraction,
        ):
            result = await processor.process_file(tmp_path / "test.pdf")

        assert result.status == ProcessingResultStatus.ERROR
        assert "Connection refused" in (result.error or "")
        assert result.chars_extracted == 100

    @pytest.mark.asyncio
    async def test_rag_insert_timeout(self, processor: DocumentProcessor, mock_rag: MagicMock, tmp_path: Path) -> None:
        """Timeout during rag.insert() yields ERROR result."""
        mock_rag.insert.side_effect = TimeoutError("LLM request timed out")

        fake_extraction = MagicMock()
        fake_extraction.content = "B" * 100
        fake_extraction.table_count = 0
        fake_extraction.figure_count = 0
        fake_extraction.equation_count = 0

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            return_value=fake_extraction,
        ):
            result = await processor.process_file(tmp_path / "test.pdf")

        assert result.status == ProcessingResultStatus.ERROR
        assert "timed out" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rag_insert_runtime_error(self, processor: DocumentProcessor, mock_rag: MagicMock, tmp_path: Path) -> None:
        """RuntimeError during rag.insert() yields ERROR result."""
        mock_rag.insert.side_effect = RuntimeError("Embedding dimension mismatch")

        fake_extraction = MagicMock()
        fake_extraction.content = "C" * 100
        fake_extraction.table_count = 2
        fake_extraction.figure_count = 1
        fake_extraction.equation_count = 0

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            return_value=fake_extraction,
        ):
            result = await processor.process_file(tmp_path / "test.pdf")

        assert result.status == ProcessingResultStatus.ERROR
        assert result.chars_extracted == 100


class TestUnsupportedFormat:
    """Test unsupported file formats are skipped."""

    @pytest.mark.asyncio
    async def test_unsupported_format_skipped(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """Unsupported format (.xyz) yields SKIPPED status."""
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("content")

        result = await processor.process_file(unsupported)

        assert result.status == ProcessingResultStatus.SKIPPED
        assert "unsupported format" in (result.reason or "").lower()
        # rag.insert should NOT be called for skipped files
        processor.rag.insert.assert_not_called()


class TestInsufficientContent:
    """Test documents with too little content are skipped."""

    @pytest.mark.asyncio
    async def test_short_content_skipped(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """Document with < 50 chars yields SKIPPED status."""
        fake_extraction = MagicMock()
        fake_extraction.content = "short"
        fake_extraction.table_count = 0
        fake_extraction.figure_count = 0
        fake_extraction.equation_count = 0

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            return_value=fake_extraction,
        ):
            result = await processor.process_file(tmp_path / "short.pdf")

        assert result.status == ProcessingResultStatus.SKIPPED
        assert "insufficient content" in (result.reason or "").lower()
        assert result.chars_extracted == 5
        # rag.insert should NOT be called for skipped files
        processor.rag.insert.assert_not_called()


class TestSuccessfulProcessing:
    """Test successful processing produces correct result."""

    @pytest.mark.asyncio
    async def test_success_with_extraction_metadata(self, processor: DocumentProcessor, mock_rag: MagicMock, tmp_path: Path) -> None:
        """Successful extraction and insertion yields SUCCESS with counts."""
        fake_extraction = MagicMock()
        fake_extraction.content = "D" * 200
        fake_extraction.table_count = 3
        fake_extraction.figure_count = 2
        fake_extraction.equation_count = 1
        fake_extraction.tables = [MagicMock(element_id="t1"), MagicMock(element_id="t2"), MagicMock(element_id="t3")]
        fake_extraction.figures = [MagicMock(element_id="f1"), MagicMock(element_id="f2")]
        fake_extraction.equations = [MagicMock(element_id="e1")]

        with patch(
            "threegpp_ai.lightrag.processor.extract_document_structured",
            return_value=fake_extraction,
        ):
            result = await processor.process_file(tmp_path / "good.pdf")

        assert result.status == ProcessingResultStatus.SUCCESS
        assert result.chars_extracted == 200
        assert result.table_count == 3
        assert result.figure_count == 2
        assert result.equation_count == 1
        assert result.error is None
        processor.rag.insert.assert_called_once()


class TestWorkspaceStateConsistency:
    """Test that processing failures do not affect subsequent documents."""

    @pytest.mark.asyncio
    async def test_partial_failure_does_not_stop_processing(self, processor: DocumentProcessor, mock_rag: MagicMock, tmp_path: Path) -> None:
        """When one document fails, subsequent documents still process."""
        files = [
            tmp_path / "doc1.pdf",
            tmp_path / "doc2.pdf",
            tmp_path / "doc3.pdf",
        ]
        for f in files:
            f.write_text("content")

        call_count = 0

        def fake_extract(file_path: Path, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            fake = MagicMock()
            if call_count == 2:
                # Second document fails extraction
                raise ExtractionError("corrupt file")
            fake.content = f"Document {call_count} " * 10  # > 50 chars
            fake.table_count = 0
            fake.figure_count = 0
            fake.equation_count = 0
            return fake

        results = []
        for f in files:
            with patch(
                "threegpp_ai.lightrag.processor.extract_document_structured",
                side_effect=fake_extract,
            ):
                result = await processor.process_file(f)
                results.append(result)

        # First: success
        assert results[0].status == ProcessingResultStatus.SUCCESS

        # Second: extraction failure
        assert results[1].status == ProcessingResultStatus.ERROR
        assert "corrupt file" in (results[1].error or "")

        # Third: still succeeds despite second failure
        assert results[2].status == ProcessingResultStatus.SUCCESS
