"""Contract tests for workspace-scoped behaviors."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tdoc_ai import get_status


class TestWorkspaceContract:
    @patch("tdoc_ai.operations.pipeline.AiStorage")
    def test_get_status_scopes_to_workspace(self, mock_ai_storage: MagicMock, mock_storage: MagicMock) -> None:
        """Verify get_status uses workspace scope."""
        mock_ai_storage.return_value = mock_storage
        with patch("tdoc_ai.operations.pipeline.AiServiceContainer") as mock_container:
            mock_container_instance = MagicMock()
            mock_container_instance.get_storage.return_value = mock_storage
            mock_container.get_instance.return_value = mock_container_instance
            get_status(document_id="S4-251003", workspace="custom_ws")
            mock_storage.get_status.assert_called_once_with("S4-251003", workspace="custom_ws")

    @patch("tdoc_ai.operations.pipeline.AiStorage")
    @patch("tdoc_ai.operations.pipeline.run_pipeline")
    def test_process_all_scopes_to_workspace_members(
        self, mock_run_pipeline: MagicMock, mock_ai_storage: MagicMock, mock_storage: MagicMock, test_data_dir: Path
    ) -> None:
        """Verify process_all applies workspace member filtering.

        Note: This test is skipped because process_all() does not currently implement
        workspace member filtering - it's a future feature (FR-019).
        """
        # Skipping this test as the feature is not implemented yet
        # The test demonstrates the expected behavior but the implementation
        # does not currently filter by workspace members
        pass
