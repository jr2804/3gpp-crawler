"""Tests for shared structured extraction payload behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from threegpp_ai.lightrag import processor as processor_module
from threegpp_ai.lightrag.processor import DocumentProcessor, ProcessingResultStatus
from threegpp_ai.operations.extraction_result import (
    ExtractedTableElement,
    build_structured_extraction_result,
    from_kreuzberg_result,
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


def test_from_kreuzberg_result_maps_tables_and_figures() -> None:
    """Converter should map available tables/images into structured elements."""
    fake_result = SimpleNamespace(
        content="body\n\n$$ x = y + z $$",
        tables=[
            SimpleNamespace(
                cells=[["a", "b"], ["c", "d"]],
                markdown="|a|b|",
                page_number=3,
            )
        ],
        images=[
            SimpleNamespace(
                format="png",
                page_number=4,
                metadata={"width": 10, "height": 20},
            )
        ],
        metadata={"source": "test"},
    )

    mapped = from_kreuzberg_result(fake_result)
    assert mapped.content.startswith("body")
    assert "$$ x = y + z $$" in mapped.content
    assert mapped.table_count == 1
    assert mapped.figure_count == 1
    assert mapped.equation_count == 1
    assert "<!-- table:id=table_1" in mapped.content
    assert "<!-- figure:id=figure_1" in mapped.content
    assert "<!-- equation:id=equation_1" in mapped.content

    table = mapped.tables[0]
    assert isinstance(table, ExtractedTableElement)
    assert table.element_id == "table_1"
    assert table.page_number == 3
    assert table.row_count == 2
    assert table.column_count == 2

    figure = mapped.figures[0]
    assert figure.element_id == "figure_1"
    assert figure.page_number == 4
    assert figure.image_format == "png"
    assert figure.metadata == {"width": 10, "height": 20}


@pytest.mark.asyncio
async def test_processor_process_file_reports_structured_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Processor result should include structured extraction counters."""

    async def fake_insert(_: str, **__: object) -> None:
        return None

    # Mock extract_document_structured in the processor module where it's imported
    # This prevents actual kreuzberg extraction
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
