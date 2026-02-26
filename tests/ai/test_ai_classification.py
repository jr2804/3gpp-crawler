"""Tests for TDoc file classification."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.ai.models import DocumentClassification
from tdoc_crawler.ai.operations import classify
from tdoc_crawler.ai.operations.classify import _score_filename, classify_tdoc_files


class TestClassifyTdocFiles:
    """Tests for classify_tdoc_files function."""

    def test_single_file_gets_confidence_one(self, test_data_dir: Path) -> None:
        """Test that a single file gets confidence 1.0."""
        tdoc_folder = test_data_dir / "S4-251003"
        if tdoc_folder.exists():
            result = classify_tdoc_files("S4-251003", tdoc_folder)
            assert len(result) == 1
            assert result[0].confidence == 1.0
            assert result[0].is_main_document is True

    def test_two_files_picks_larger(self, test_data_dir: Path) -> None:
        """Test that two files picks the larger/structured one."""
        # Use a folder with 2 files
        tdoc_folder = test_data_dir / "26260-j10"
        if tdoc_folder.exists() and len(list(tdoc_folder.glob("*"))) >= 2:
            result = classify_tdoc_files("26260-J10", tdoc_folder)
            # Find the main document
            main = next((r for r in result if r.is_main_document), None)
            assert main is not None
            assert main.confidence >= 0.7

    def test_filename_heuristics_final_draft(self) -> None:
        """Test filename heuristics for final vs draft documents."""
        # Final should score higher than draft
        final_score = _score_filename("S4-251003 Final Report.docx")
        draft_score = _score_filename("S4-251003 Draft.docx")
        assert final_score > draft_score

    def test_revision_preference(self) -> None:
        """Test that revision documents are preferred."""
        rev_score = _score_filename("S4-251003 CR to 26.260 rev 3.docx")
        base_score = _score_filename("S4-251003 Meeting agenda.docx")
        # Revision files should score higher
        assert rev_score > base_score

    def test_confidence_scoring_range(self, test_data_dir: Path) -> None:
        """Test that confidence scores are in valid range 0.0-1.0."""
        # Test with various folders
        for tdoc_folder in test_data_dir.iterdir():
            if tdoc_folder.is_dir():
                result = classify_tdoc_files(tdoc_folder.name, tdoc_folder)
                for classification in result:
                    assert 0.0 <= classification.confidence <= 1.0

    def test_classification_includes_heuristic(self, test_data_dir: Path) -> None:
        """Test that classification includes the decisive heuristic."""
        tdoc_folder = test_data_dir / "S4-251003"

        if tdoc_folder.exists():
            result = classify_tdoc_files("S4-251003", tdoc_folder)
            for classification in result:
                assert classification.decisive_heuristic is not None
                assert len(classification.decisive_heuristic) > 0

    def test_non_docx_files_are_ignored(self, tmp_path: Path) -> None:
        """US2 classification should only consider DOCX candidates."""
        (tmp_path / "agenda.xlsx").write_text("xlsx placeholder", encoding="utf-8")
        (tmp_path / "slides.pptx").write_text("pptx placeholder", encoding="utf-8")

        result = classify_tdoc_files("S4-260999", tmp_path)
        assert result == []


class TestClassifyModuleExports:
    """Tests that classify module exports required functions."""

    def test_classify_tdoc_files_exported(self) -> None:
        """Verify classify_tdoc_files is exported."""
        assert hasattr(classify, "classify_tdoc_files")
        assert callable(classify.classify_tdoc_files)

    def test_document_classification_exported(self) -> None:
        """Verify DocumentClassification is exported."""
        assert DocumentClassification is not None


US2_T027_RED_CHECKPOINT = """
Command: uv run pytest tests/ai/test_ai_classification.py -q

Observed failure:
- TestClassifyTdocFiles.test_non_docx_files_are_ignored
    AssertionError: assert [DocumentClassification(...)] == []
    Cause: classify_tdoc_files currently includes non-DOCX files (e.g., .xlsx/.pptx)
    instead of filtering classification candidates to DOCX only.

Checkpoint status: RED (1 failed, 8 passed)
"""
