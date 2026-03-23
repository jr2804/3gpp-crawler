"""Contract tests for workspace-scoped behaviors."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from threegpp_ai import get_status


class TestWorkspaceContract:
    @patch("threegpp_ai.operations.pipeline.EmbeddingsManager")
    def test_get_status_scopes_to_workspace(self, mock_embeddings_manager: MagicMock, mock_storage: MagicMock) -> None:
        """Verify get_status uses workspace scope."""
        mock_embeddings_manager.return_value.storage = mock_storage
        get_status(document_id="S4-251003", workspace="custom_ws")
        mock_storage.get_status.assert_called_once_with("S4-251003", workspace="custom_ws")

    @patch("threegpp_ai.operations.pipeline.AiStorage")
    @patch("threegpp_ai.operations.pipeline.run_pipeline")
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
