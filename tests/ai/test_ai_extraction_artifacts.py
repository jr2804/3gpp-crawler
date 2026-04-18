"""Integration tests for extraction artifact storage.

Tests the folder-based storage pattern for tables, figures, and equations
extracted from TDoc documents.
"""

import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from threegpp_ai.models import (
    ExtractedEquationElement,
    ExtractedFigureElement,
    ExtractedTableElement,
)
from threegpp_ai.operations.extraction_result import (
    build_canonical_output,
    build_structured_extraction_result,
    evaluate_quality_gates,
    from_docling_result,
    has_cached_artifacts,
    persist_canonical_output,
    persist_equations_from_extraction,
    persist_figures_from_extraction,
    persist_output_contracts,
    persist_output_manifest,
    persist_tables_from_extraction,
    read_cached_artifacts,
)


class TestArtifactStorage:
    """Test artifact storage utilities."""

    @pytest.fixture
    def temp_ai_dir(self) -> Path:
        """Create temporary .ai directory."""
        tmpdir = Path(tempfile.mkdtemp())
        ai_dir = tmpdir / ".ai"
        ai_dir.mkdir()
        yield ai_dir
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def sample_tables(self) -> list[ExtractedTableElement]:
        """Create sample table elements."""
        return [
            ExtractedTableElement(
                element_id="table_1",
                page_number=1,
                row_count=2,
                column_count=3,
                cells=[["A1", "B1", "C1"], ["A2", "B2", "C2"]],
                cell_metadata=[
                    [{"row": 1, "column": 1}, {"row": 1, "column": 2}, {"row": 1, "column": 3}],
                    [{"row": 2, "column": 1}, {"row": 2, "column": 2}, {"row": 2, "column": 3}],
                ],
                markdown="| A1 | B1 | C1 |\n| A2 | B2 | C2 |",
                caption="Test table caption",
                source_anchor_id="tbl-1",
            ),
            ExtractedTableElement(
                element_id="table_2",
                page_number=3,
                row_count=4,
                column_count=2,
                cells=[["X1", "Y1"], ["X2", "Y2"], ["X3", "Y3"], ["X4", "Y4"]],
                markdown="| X1 | Y1 |\n| X2 | Y2 |\n| X3 | Y3 |\n| X4 | Y4 |",
                source_anchor_id="tbl-2",
            ),
        ]

    @pytest.fixture
    def sample_equations(self) -> list[ExtractedEquationElement]:
        """Create sample equation elements."""
        return [
            ExtractedEquationElement(
                element_id="equation_1",
                page_number=2,
                latex=r"E = mc^2",
                raw_text="E = mc^2",
                source_anchor_id="eq-1",
                normalized_text="E = mc^2",
                equation_type="latex",
                display_mode="display",
            ),
            ExtractedEquationElement(
                element_id="equation_2",
                page_number=5,
                latex=r"\int_0^\infty e^{-x} dx = 1",
                raw_text="integral from 0 to infinity",
                source_anchor_id="eq-2",
                normalized_text="integral from 0 to infinity",
                equation_type="latex",
                display_mode="display",
            ),
        ]

    @pytest.fixture
    def sample_figures(self) -> list[ExtractedFigureElement]:
        """Create sample figure elements with image bytes in metadata."""
        return [
            ExtractedFigureElement(
                element_id="figure_1",
                page_number=1,
                image_path="/path/to/figure_1.png",
                image_format="png",
                caption="Test figure caption",
                source_anchor_id="fig-1",
                is_partial=False,
                partial_reason_codes=[],
                metadata={"image_bytes": b"\x89PNG\r\n\x1a\n" + b"\x00" * 100},
            ),
            ExtractedFigureElement(
                element_id="figure_2",
                page_number=4,
                image_path="/path/to/figure_2.jpg",
                image_format="jpeg",
                source_anchor_id="fig-2",
                is_partial=False,
                partial_reason_codes=[],
                metadata={"image_bytes": b"\xff\xd8\xff" + b"\x00" * 100},
            ),
        ]

    def test_persist_tables_creates_folder_structure(self, temp_ai_dir: Path, sample_tables: list[ExtractedTableElement]) -> None:
        """Tables are persisted in individual JSON files under tables/ subfolder."""
        doc_stem = "S4-250638"
        tables_dir = temp_ai_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)

        paths = persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)

        assert len(paths) == 2
        assert (temp_ai_dir / "tables" / "S4-250638_table_1_1.json").exists()
        assert (temp_ai_dir / "tables" / "S4-250638_table_3_2.json").exists()

    def test_persist_equations_creates_folder_structure(self, temp_ai_dir: Path, sample_equations: list[ExtractedEquationElement]) -> None:
        """Equations are persisted in individual JSON files under equations/ subfolder."""
        doc_stem = "S4-250638"
        equations_dir = temp_ai_dir / "equations"
        equations_dir.mkdir(parents=True, exist_ok=True)

        paths = persist_equations_from_extraction(sample_equations, temp_ai_dir, doc_stem)

        assert len(paths) == 2
        assert (temp_ai_dir / "equations" / "S4-250638_equation_2_1.json").exists()
        assert (temp_ai_dir / "equations" / "S4-250638_equation_5_2.json").exists()

    def test_persist_figures_creates_folder_structure(self, temp_ai_dir: Path, sample_figures: list[ExtractedFigureElement]) -> None:
        """Figures are persisted with metadata under figures/ subfolder."""
        doc_stem = "S4-250638"
        figures_dir = temp_ai_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        paths = persist_figures_from_extraction(sample_figures, figures_dir, doc_stem)

        assert len(paths) == 2
        assert "figure_1" in paths
        assert "figure_2" in paths

    def test_read_cached_artifacts_reconstructs_result(
        self,
        temp_ai_dir: Path,
        sample_tables: list[ExtractedTableElement],
        sample_equations: list[ExtractedEquationElement],
        sample_figures: list[ExtractedFigureElement],
    ) -> None:
        """read_cached_artifacts reconstructs StructuredExtractionResult from folder storage."""
        doc_stem = "S4-250638"

        # Persist all artifacts
        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)
        persist_equations_from_extraction(sample_equations, temp_ai_dir, doc_stem)
        figures_dir = temp_ai_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        persist_figures_from_extraction(sample_figures, figures_dir, doc_stem)

        # Read back
        cached = read_cached_artifacts(temp_ai_dir, doc_stem)

        assert cached is not None
        assert len(cached.tables) == 2
        assert len(cached.equations) == 2
        assert len(cached.figures) == 2

        # Verify table data integrity
        assert cached.tables[0].element_id == "table_1"
        assert cached.tables[0].page_number == 1
        assert cached.tables[0].cells == [["A1", "B1", "C1"], ["A2", "B2", "C2"]]

        # Verify equation data integrity
        assert cached.equations[0].element_id == "equation_1"
        assert cached.equations[0].latex == r"E = mc^2"

    def test_has_cached_artifacts_checks_existence(self, temp_ai_dir: Path, sample_tables: list[ExtractedTableElement]) -> None:
        """has_cached_artifacts correctly reports which artifact types exist."""
        doc_stem = "S4-250638"

        # Initially nothing cached
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables"}) is False
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables", "equations"}) is False

        # Persist tables
        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)

        # Now tables exist
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables"}) is True
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables", "equations"}) is False

    def test_has_cached_artifacts_partial_types(self, temp_ai_dir: Path, sample_tables: list[ExtractedTableElement]) -> None:
        """has_cached_artifacts returns True only if ALL requested types exist."""
        doc_stem = "S4-250638"

        # Persist tables only
        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)

        # tables=True, figures=False, equations=False
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables"}) is True
        assert has_cached_artifacts(temp_ai_dir, doc_stem, {"tables", "figures"}) is False

    def test_read_cached_artifacts_returns_none_when_empty(self, temp_ai_dir: Path) -> None:
        """read_cached_artifacts returns None if no artifacts exist."""
        doc_stem = "S4-250638"
        cached = read_cached_artifacts(temp_ai_dir, doc_stem)
        assert cached is None

    def test_build_structured_extraction_with_artifacts(
        self,
        temp_ai_dir: Path,
        sample_tables: list[ExtractedTableElement],
        sample_equations: list[ExtractedEquationElement],
        sample_figures: list[ExtractedFigureElement],
    ) -> None:
        """build_structured_extraction_result creates proper result with artifacts."""
        doc_stem = "S4-250638"
        content = "# Test Document\n\nSome content here."

        # Persist artifacts
        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)
        persist_equations_from_extraction(sample_equations, temp_ai_dir, doc_stem)
        figures_dir = temp_ai_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        persist_figures_from_extraction(sample_figures, figures_dir, doc_stem)

        # Read and build
        cached = read_cached_artifacts(temp_ai_dir, doc_stem)
        result = build_structured_extraction_result(
            content,
            tables=cached.tables if cached else [],
            figures=cached.figures if cached else [],
            equations=cached.equations if cached else [],
        )

        assert result.content == content
        assert result.table_count == 2
        assert result.figure_count == 2
        assert result.equation_count == 2

    def test_artifact_filename_includes_page_and_index(self, temp_ai_dir: Path, sample_tables: list[ExtractedTableElement]) -> None:
        """Artifact filenames encode page number and index for traceability."""
        doc_stem = "S4-250999"

        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)

        # First table: page=1, index=1 -> S4-250999_table_1_1.json
        assert (temp_ai_dir / "tables" / "S4-250999_table_1_1.json").exists()

        # Second table: page=3, index=2 -> S4-250999_table_3_2.json
        assert (temp_ai_dir / "tables" / "S4-250999_table_3_2.json").exists()

    def test_empty_artifacts_list_handled_gracefully(self, temp_ai_dir: Path) -> None:
        """Empty artifact lists are handled without creating files."""
        doc_stem = "S4-250638"
        empty_tables: list[ExtractedTableElement] = []

        paths = persist_tables_from_extraction(empty_tables, temp_ai_dir, doc_stem)

        assert len(paths) == 0
        tables_dir = temp_ai_dir / "tables"
        # Directory should not be created for empty list
        assert not tables_dir.exists() or not any(tables_dir.iterdir())

    def test_build_structured_result_populates_canonical_page_metadata(
        self,
        sample_tables: list[ExtractedTableElement],
        sample_equations: list[ExtractedEquationElement],
        sample_figures: list[ExtractedFigureElement],
    ) -> None:
        """Structured result auto-populates deterministic page metadata contracts."""
        result = build_structured_extraction_result(
            "content",
            tables=sample_tables,
            figures=sample_figures,
            equations=sample_equations,
            metadata={"document_id": "S4-250638", "extraction_profile": "balanced"},
        )

        assert result.document_metadata is not None
        assert result.document_metadata.document_id == "S4-250638"
        assert result.document_metadata.extraction_profile == "balanced"
        assert [page.page_number for page in result.pages] == [1, 2, 3, 4, 5]

    def test_build_canonical_output_is_deterministic(
        self,
        sample_tables: list[ExtractedTableElement],
        sample_equations: list[ExtractedEquationElement],
        sample_figures: list[ExtractedFigureElement],
    ) -> None:
        """Canonical JSON payload ordering is stable for identical input."""
        result = build_structured_extraction_result(
            "content",
            tables=sample_tables,
            figures=sample_figures,
            equations=sample_equations,
            metadata={"document_id": "S4-250638", "extraction_profile": "default"},
        )

        payload_a = build_canonical_output(result)
        payload_b = build_canonical_output(result)

        assert payload_a == payload_b
        assert payload_a["document"]["document_id"] == "S4-250638"
        assert payload_a["elements"]["tables"][0]["element_id"] == "table_1"

    def test_manifest_includes_inventory_and_status(
        self,
        temp_ai_dir: Path,
        sample_tables: list[ExtractedTableElement],
    ) -> None:
        """Manifest inventories generated artifacts with extraction status and config hash."""
        doc_stem = "S4-250638"
        markdown_path = temp_ai_dir / f"{doc_stem}.md"
        markdown_path.write_text("# markdown", encoding="utf-8")
        persist_tables_from_extraction(sample_tables, temp_ai_dir, doc_stem)

        extraction = build_structured_extraction_result(
            "content",
            tables=sample_tables,
            metadata={
                "document_id": "S4-250638",
                "extraction_status": "ok",
                "extraction_profile": "default",
                "effective_extraction_settings": {"tables": True},
            },
        )
        canonical_path = persist_canonical_output(temp_ai_dir, doc_stem, extraction)
        manifest_path = persist_output_manifest(temp_ai_dir, doc_stem, extraction, canonical_path)

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact_types = {entry["type"] for entry in payload["artifacts"]}

        assert payload["extraction_status"] == "ok"
        assert payload["config_hash"]
        assert {"markdown", "canonical_json", "table", "manifest"}.issubset(artifact_types)

    def test_quality_gate_status_is_deterministic_for_identical_input(
        self,
        sample_tables: list[ExtractedTableElement],
    ) -> None:
        """Deterministic gate logic produces stable status and reason codes."""
        extraction = build_structured_extraction_result(
            "content",
            tables=sample_tables,
            metadata={
                "document_id": "S4-250638",
                "source_path": "x.pdf",
                "file_extension": ".pdf",
            },
        )

        report_a = evaluate_quality_gates(extraction)
        report_b = evaluate_quality_gates(extraction)

        assert report_a.status.value == "ok"
        assert report_a.model_dump(mode="json") == report_b.model_dump(mode="json")

    def test_persist_output_contracts_writes_quality_report_and_reason_codes(self, temp_ai_dir: Path) -> None:
        """Output contracts include persisted quality report path and reason codes."""
        doc_stem = "S4-250638"
        extraction = build_structured_extraction_result(
            "",
            metadata={
                "document_id": "S4-250638",
                "source_path": "x.pdf",
                "file_extension": ".pdf",
            },
        )

        persisted = persist_output_contracts(temp_ai_dir, doc_stem, extraction)
        quality_path = Path(persisted.metadata["quality_report_path"])
        quality_payload = json.loads(quality_path.read_text(encoding="utf-8"))

        assert persisted.metadata["extraction_status"] == "failed"
        assert "missing_artifact" in persisted.metadata["quality_reason_codes"]
        assert quality_payload["status"] == "failed"
        assert quality_payload["reason_codes"]
        assert quality_payload["gate_metrics_summary"]["checks_total"] >= 1

    def test_from_docling_result_populates_additive_fidelity_fields(self) -> None:
        """Docling mapping populates source anchors, partial flags, and equation normalization fields."""

        class _DummyCell:
            def __init__(self, text: str, row: int, column: int) -> None:
                self.text = text
                self.row = row
                self.column = column

        class _DummyTableData:
            def __init__(self) -> None:
                self.page_number = 2
                self.source_anchor_id = "table anchor#2"
                self.grid = [[_DummyCell("A", 1, 1), _DummyCell("B", 1, 2)]]

        class _DummyTable:
            def __init__(self) -> None:
                self.data = _DummyTableData()

            def export_to_markdown(self, doc: object | None = None) -> str:
                _ = doc
                return "| A | B |"

        class _DummyPicture:
            def __init__(self) -> None:
                self.page_number = 3
                self.source_anchor = "figure source/3"
                self.image = SimpleNamespace(type="image/png")

            def caption_text(self, doc: object) -> str:
                _ = doc
                return ""

        class _DummyDocument:
            def __init__(self) -> None:
                self.tables = [_DummyTable()]
                self.pictures = [_DummyPicture()]

            def export_to_markdown(self) -> str:
                return "Equation: $$ a + b = c $$"

        result = SimpleNamespace(document=_DummyDocument(), metadata={"document_id": "S4-250638"})
        extraction = from_docling_result(result, figure_paths={}, figure_descriptions={})

        assert extraction.tables[0].source_anchor_id == "table-anchor-2"
        assert extraction.tables[0].cell_metadata[0][0] == {"row": 1, "column": 1}

        assert extraction.figures[0].source_anchor_id == "figure-source-3"
        assert extraction.figures[0].is_partial is True
        assert "missing_image_path" in extraction.figures[0].partial_reason_codes

        assert extraction.equations[0].normalized_text == "a + b = c"
        assert extraction.equations[0].equation_type == "latex"
        assert extraction.equations[0].display_mode == "display"
