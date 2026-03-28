"""Tests for shared structured extraction payload behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from threegpp_ai.lightrag import processor as processor_module
from threegpp_ai.lightrag.processor import DocumentProcessor, ProcessingResultStatus
from threegpp_ai.operations.extraction_result import (
    ExtractedTableElement,
    build_structured_extraction_result,
    from_docling_result,
)


def test_build_structured_extraction_result_defaults() -> None:
    """Builder should create a payload with empty optional collections."""
    result = build_structured_extraction_result("hello")
    assert result.content == "hello"
    assert result.tables == []
    assert result.figures == []
    assert result.equations == []
    assert result.metadata == {}
    assert result.table_count == 0
    assert result.figure_count == 0
    assert result.equation_count == 0


def test_from_docling_result_maps_tables_and_figures() -> None:
    """Converter should map available tables/pictures into structured elements."""

    class FakeTableData:
        def __init__(self, cells: list[list[str]]) -> None:
            self.grid = cells
            self.page_number = 3

    class FakeTable:
        def __init__(self, cells: list[list[str]]) -> None:
            self.data = FakeTableData(cells)
            self.markdown = "|a|b|\n|-|-|\n|c|d|"

        def export_to_markdown(self, *, doc: object = None) -> str:
            return self.markdown

    class FakeDoc:
        def __init__(self) -> None:
            self.tables = [FakeTable([["a", "b"], ["c", "d"]])]
            self.pictures = []

        def export_to_markdown(self) -> str:
            return "body text\n\n$$ x = y + z $$"

    class FakeResult:
        def __init__(self) -> None:
            self.document = FakeDoc()
            self.metadata = {"source": "test"}

    mapped = from_docling_result(FakeResult())
    assert mapped.content.startswith("body text")
    assert "$$ x = y + z $$" in mapped.content
    assert mapped.table_count == 1
    assert mapped.figure_count == 0
    assert mapped.equation_count == 1
    assert "<!-- table:id=table_1" in mapped.content
    assert "<!-- equation:id=equation_1" in mapped.content

    table = mapped.tables[0]
    assert isinstance(table, ExtractedTableElement)
    assert table.element_id == "table_1"
    assert table.page_number == 3
    assert table.row_count == 2
    assert table.column_count == 2


@pytest.mark.asyncio
async def test_processor_process_file_reports_structured_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Processor result should include structured extraction counters."""

    async def fake_insert(_: str, **__: object) -> None:
        return None

    # Mock extract_document_structured in the processor module where it's imported
    # This prevents actual docling extraction
    monkeypatch.setattr(
        processor_module,
        "extract_document_structured",
        lambda *args, **kwargs: build_structured_extraction_result(
            content="x" * 120,
            tables=[
                ExtractedTableElement(
                    element_id="table_1",
                    page_number=1,
                    row_count=1,
                    column_count=1,
                    cells=[["v"]],
                )
            ],
            figures=[],
            equations=[],
        ),
    )

    processor = DocumentProcessor()
    monkeypatch.setattr(processor.rag, "insert", fake_insert)

    # Use a .md file to skip PDF conversion, testing only the processor logic
    file_path = tmp_path / "doc.md"
    file_path.write_text("placeholder content " * 10, encoding="utf-8")

    result = await processor.process_file(file_path, metadata={"document_id": "test-doc"})
    assert result.status == ProcessingResultStatus.SUCCESS
    # chars_extracted includes metadata enrichment header, so we check it's > 120
    assert result.chars_extracted > 120
    assert result.table_count == 1
    assert result.figure_count == 0
    assert result.equation_count == 0
