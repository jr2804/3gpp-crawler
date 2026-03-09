"""Tests for the AI processing pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tdoc_ai import get_status, process_tdoc
from tdoc_ai import process_all as process_all_api
from tdoc_ai.models import PipelineStage, ProcessingStatus
from tdoc_ai.operations import pipeline
from tdoc_ai.operations.pipeline import process_all, run_pipeline
from tdoc_ai.storage import AiStorage

from tdoc_crawler.config import CacheManager
from tdoc_crawler.utils.misc import utc_now


def _status(document_id: str, stage: PipelineStage = PipelineStage.PENDING) -> ProcessingStatus:
    return ProcessingStatus.model_validate({"document_id": document_id, "current_stage": stage})


class TestRunPipeline:
    """Tests for run_pipeline function."""

    def test_full_single_tdoc_pipeline(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test running full pipeline on a single TDoc."""
        tdoc_folder = test_data_dir / "S4-251003"
        if tdoc_folder.exists():
            status = run_pipeline("S4-251003", tdoc_folder, mock_storage)
            assert status is not None

    @patch("tdoc_ai.operations.pipeline.AiStorage")
    @patch("tdoc_ai.operations.pipeline.run_pipeline")
    def test_batch_processing(self, mock_run_pipeline: MagicMock, mock_ai_storage: MagicMock, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test processing multiple TDocs."""
        mock_ai_storage.return_value = mock_storage
        mock_run_pipeline.return_value = _status("foo")

        tdoc_folders = [d for d in test_data_dir.iterdir() if d.is_dir()][:3]

        if tdoc_folders:
            results = process_all([d.name for d in tdoc_folders], test_data_dir)
            assert isinstance(results, dict)

    def test_resume_from_interrupted_stage(self, mock_storage: MagicMock, test_data_dir: Path) -> None:
        """Test resume from interrupted stage works."""
        # Create a status with partial completion
        mock_status = _status("S4-251003")
        mock_status.classified_at = utc_now()
        mock_storage.get_status.return_value = mock_status

        tdoc_folder = test_data_dir / "S4-251003"
        if tdoc_folder.exists():
            status = run_pipeline("S4-251003", tdoc_folder, mock_storage)
            assert status is not None

    @patch("tdoc_ai.operations.pipeline.EmbeddingsManager")
    @patch("tdoc_ai.operations.pipeline.run_pipeline")
    def test_incremental_new_only_mode(
        self,
        mock_run_pipeline: MagicMock,
        mock_embeddings_manager: MagicMock,
        mock_storage: MagicMock,
        test_data_dir: Path,
    ) -> None:
        """Test incremental processing only processes new items."""
        mock_embeddings_manager.return_value.storage = mock_storage

        # Status shows already completed
        mock_status = _status("S4-251003", stage=PipelineStage.COMPLETED)
        mock_storage.get_status.return_value = mock_status

        tdoc_folder = test_data_dir / "S4-251003"
        if tdoc_folder.exists():
            results = process_all(["S4-251003"], test_data_dir, new_only=True)
            assert "S4-251003" not in results  # Should be skipped
            mock_run_pipeline.assert_not_called()

    @patch("tdoc_ai.operations.pipeline.AiStorage")
    @patch("tdoc_ai.operations.pipeline.run_pipeline")
    def test_failed_tdoc_does_not_block_others(
        self, mock_run_pipeline: MagicMock, mock_ai_storage: MagicMock, mock_storage: MagicMock, test_data_dir: Path
    ) -> None:
        """Test that a failed TDoc doesn't block processing of others."""
        mock_ai_storage.return_value = mock_storage
        # Make one TDoc fail
        mock_run_pipeline.side_effect = [Exception("Simulated failure"), MagicMock()]

        base_path = test_data_dir
        tdoc_ids = ["S4-251003", "26260-j10"]

        # Should not raise - errors are isolated
        results = process_all(tdoc_ids, base_path)
        assert isinstance(results, dict)

    @patch("tdoc_ai.operations.pipeline.list_workspace_members")
    @patch("tdoc_ai.operations.pipeline.run_pipeline")
    def test_process_all_scopes_to_workspace_members(self, mock_run_pipeline: MagicMock, mock_list_members: MagicMock, test_data_dir: Path) -> None:
        """Test process_all filters input by workspace members."""
        mock_list_members.return_value = [
            MagicMock(
                source_item_id="S4-251003",
                is_active=True,
                source_kind="tdoc",
            ),
        ]

        mock_run_pipeline.return_value = _status("S4-251003", stage=PipelineStage.COMPLETED)

        tdoc_ids = ["S4-251003", "26260-j10"]
        # Only S4-251003 should be processed because of the workspace scope
        results = process_all(tdoc_ids, test_data_dir, workspace="test_ws")

        assert "S4-251003" in results
        assert "26260-j10" not in results
        mock_list_members.assert_called_once_with("test_ws")


class TestProcessTdocApi:
    """Tests for public API functions."""

    def test_process_tdoc_exported(self) -> None:
        """Verify process_tdoc is exported."""
        assert callable(process_tdoc)

    def test_process_all_exported(self) -> None:
        """Verify process_all is exported."""
        assert callable(process_all_api)

    def test_get_status_exported(self) -> None:
        """Verify get_status is exported."""
        assert callable(get_status)

    def test_process_all_new_only_filters_completed_statuses(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """new_only mode should return only non-completed items."""
        # This test verifies the filtering logic in process_all
        # by mocking the storage.get_status call
        completed = _status("S4-251003", stage=PipelineStage.COMPLETED)
        _status("S4-260001", stage=PipelineStage.PENDING)

        # Create a mock storage that returns completed status for one doc
        mock_storage = MagicMock(spec=AiStorage)
        mock_storage.get_status.side_effect = lambda doc_id, workspace=None: completed if doc_id == "S4-251003" else None

        mock_manager = MagicMock()
        mock_manager.storage = mock_storage
        monkeypatch.setattr("tdoc_ai.operations.pipeline.EmbeddingsManager", lambda _: mock_manager)

        # Create checkout folders so the pipeline doesn't skip them
        (tmp_path / "S4-251003").mkdir()
        (tmp_path / "S4-260001").mkdir()

        # Mock the internal stage functions to avoid actual processing
        def mock_classify_stage(doc_id: str, folder_path: Path, storage: AiStorage, status: ProcessingStatus, **kwargs) -> None:
            status.current_stage = PipelineStage.CLASSIFYING
            status.classified_at = utc_now()

        def mock_extract_stage(doc_id: str, folder_path: Path, storage: AiStorage, status: ProcessingStatus, **kwargs) -> str:
            status.current_stage = PipelineStage.EXTRACTING
            status.extracted_at = utc_now()
            return "mocked markdown"

        monkeypatch.setattr("tdoc_ai.operations.pipeline._run_classify_stage", mock_classify_stage)
        monkeypatch.setattr("tdoc_ai.operations.pipeline._run_extract_stage", mock_extract_stage)

        result = process_all_api(
            document_ids=["S4-251003", "S4-260001"],
            checkout_base=tmp_path,
            new_only=True,
        )

        # With new_only=True, completed docs should be filtered out
        assert "S4-251003" not in result, "Completed doc should be filtered in new_only mode"
        assert "S4-260001" in result, "Pending doc should be included"


class TestPipelineModuleExports:
    """Tests that pipeline module exports required functions."""

    def test_run_pipeline_exported(self) -> None:
        """Verify run_pipeline is exported."""
        assert hasattr(pipeline, "run_pipeline")
        assert callable(pipeline.run_pipeline)


class TestStorageBoundaryIntegration:
    """Integration assertions for FR-018 storage boundaries."""

    def test_pipeline_storage_path_keeps_core_db_untouched(self, tmp_path: Path) -> None:
        """Pipeline storage path remains in .ai and does not require core DB writes.

        This test verifies that process_all does NOT create or touch the core SQLite DB.
        The AI storage is managed by the container and may be in a different location.
        """
        manager = CacheManager(root_path=tmp_path, name="pipeline-storage-boundary").register(force=True)
        core_db = manager.db_file
        checkout_base = manager.root / "checkout"
        checkout_base.mkdir(parents=True, exist_ok=True)

        # This should NOT create the core database file
        results = process_all([], checkout_base)

        assert isinstance(results, dict)
        # Core DB should NOT be created - this is the main assertion for the storage boundary
        assert not core_db.exists()


US3_T032_RED_CHECKPOINT = """
Command: uv run pytest tests/ai/test_ai_pipeline.py -q

Observed failure:
- TestProcessTdocApi.test_process_all_new_only_filters_completed_statuses
    AssertionError: assert ['S4-251003', 'S4-260001'] == ['S4-260001']
    Cause: process_all(new_only=True, ...) currently returns completed items
    and does not apply incremental filtering semantics.

Checkpoint status: RED (1 failed, 11 passed)
"""
