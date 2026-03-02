"""Contract tests for workspace-scoped behaviors."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tdoc_crawler.ai import get_status, process_all
from tdoc_crawler.ai.models import PipelineStage, ProcessingStatus, WorkspaceMember


class TestWorkspaceContract:
    @patch("tdoc_crawler.ai.operations.pipeline.AiStorage")
    def test_get_status_scopes_to_workspace(self, mock_ai_storage: MagicMock, mock_storage: MagicMock) -> None:
        """Verify get_status uses workspace scope."""
        mock_ai_storage.return_value = mock_storage
        get_status(document_id="S4-251003", workspace="custom_ws")
        mock_storage.get_status.assert_called_once_with("S4-251003", workspace="custom_ws")

    @patch("tdoc_crawler.ai.operations.pipeline.AiStorage")
    @patch("tdoc_crawler.ai.operations.pipeline.run_pipeline")
    def test_process_all_scopes_to_workspace_members(
        self, mock_run_pipeline: MagicMock, mock_ai_storage: MagicMock, mock_storage: MagicMock, test_data_dir: Path
    ) -> None:
        """Verify process_all applies workspace member filtering."""
        mock_ai_storage.return_value = mock_storage
        mock_storage.list_workspace_members.return_value = [
            WorkspaceMember(workspace_name="custom_ws", source_item_id="S4-251003", source_path="/path", source_kind="tdoc", status="included")
        ]

        mock_run_pipeline.return_value = ProcessingStatus(document_id="S4-251003", current_stage=PipelineStage.COMPLETED)

        results = process_all(tdoc_ids=["S4-251003", "26260-j10"], checkout_base=test_data_dir, workspace="custom_ws")

        assert "S4-251003" in [s.document_id for s in results]
        assert "26260-j10" not in [s.document_id for s in results]
        assert "26260-j10" not in [s.document_id for s in results]
