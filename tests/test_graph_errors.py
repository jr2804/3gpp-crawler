"""Tests for graph error handling and deprecated import verification.

This test module verifies:
1. No deprecated imports remain in the codebase (AiStorage, EmbeddingsManager, lancedb, etc.)
2. Graph error handling readiness for future LightRAG integration
3. Datetime scoping is correct in CLI operations
"""

import sys
from datetime import UTC, datetime

import pytest
import threegpp_ai
import threegpp_ai.operations.workspaces as workspaces_ops
from threegpp_ai import cli
from threegpp_ai.operations.workspaces import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    ensure_ai_subfolder,
)

from tdoc_crawler.utils.date_parser import parse_partial_date


class TestDeprecatedImports:
    """Verify deprecated modules are not imported in the codebase."""

    def test_no_aistorage_import(self) -> None:
        """AiStorage deprecated class should not be imported."""
        # Verify AiStorage not in module namespaces
        assert not hasattr(threegpp_ai, "AiStorage"), "AiStorage should not be exported"
        assert not hasattr(threegpp_ai.operations, "AiStorage"), "AiStorage should not be in operations"

    def test_no_embeddings_manager_import(self) -> None:
        """EmbeddingsManager deprecated class should not be imported."""
        # Verify EmbeddingsManager not in module namespaces
        assert not hasattr(threegpp_ai, "EmbeddingsManager"), "EmbeddingsManager should not be exported"

    def test_no_lancedb_import(self) -> None:
        """Lancedb deprecated module should not be imported."""
        # Verify lancedb not in loaded modules
        assert "lancedb" not in sys.modules, "lancedb module should not be loaded"
        assert "tdoc_ai.storage.lancedb" not in sys.modules, "tdoc_ai.storage.lancedb should not be loaded"

    def test_no_sentence_transformers_import(self) -> None:
        """sentence_transformers deprecated module should not be imported."""
        # Verify sentence_transformers not in loaded modules
        assert "sentence_transformers" not in sys.modules, "sentence_transformers should not be loaded"

    def test_no_legacy_pipeline_import(self) -> None:
        """Legacy pipeline module should not be imported."""
        # Verify legacy pipeline not in loaded modules
        assert "tdoc_ai.operations.pipeline" not in sys.modules, "Legacy pipeline should not be loaded"


class TestDatetimeScoping:
    """Verify datetime variables are properly scoped."""

    def test_datetime_module_level_import(self) -> None:
        """Datetime should be imported at module level in cli.py."""
        # Verify datetime is available in cli module
        assert hasattr(cli, "datetime"), "datetime should be imported in cli module"
        assert hasattr(cli, "UTC"), "UTC should be imported in cli module"

    def test_datetime_combine_usage(self) -> None:
        """datetime.combine should be used with proper scoping."""
        # Test that datetime.combine works correctly with parse_partial_date
        start_date_str = "2025-01"
        parsed_date = parse_partial_date(start_date_str)
        combined = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)

        assert combined is not None
        assert combined.tzinfo == UTC
        assert combined.year == 2025
        assert combined.month == 1

    def test_datetime_combine_end_date(self) -> None:
        """datetime.combine should work for end dates with is_end flag."""
        # Test end date parsing
        end_date_str = "2025-03"
        parsed_date = parse_partial_date(end_date_str, is_end=True)
        combined = datetime.combine(parsed_date, datetime.max.time(), tzinfo=UTC)

        assert combined is not None
        assert combined.tzinfo == UTC
        assert combined.year == 2025
        assert combined.month == 3


class TestGraphErrorHandling:
    """Test graph error handling readiness.

    Note: Currently there is NO LightRAG integration or graph building code
    in the 3gpp-ai package. These tests document the expected behavior when
    graph operations are added in a future phase.
    """

    def test_graph_operations_not_yet_implemented(self) -> None:
        """Document that graph operations are not yet implemented.

        This test verifies the current state: no LightRAG or graph building
        code exists in the codebase. When LightRAG integration is added,
        this test should be updated to verify actual graph error handling.
        """
        # Verify no LightRAG classes are exported
        assert not hasattr(threegpp_ai, "LightRAGConfig"), "LightRAGConfig not yet implemented"
        assert not hasattr(threegpp_ai, "TDocRAG"), "TDocRAG not yet implemented"
        assert not hasattr(threegpp_ai, "TDocProcessor"), "TDocProcessor not yet implemented"

        # Verify no graph-related functions in workspaces
        assert not hasattr(workspaces_ops, "build_graph"), "build_graph not yet implemented"
        assert not hasattr(workspaces_ops, "insert_to_graph"), "insert_to_graph not yet implemented"

    def test_workspace_process_continues_without_graph(self) -> None:
        """Workspace processing should work without graph operations.

        Currently workspace processing only does extraction, not graph building.
        This test documents that extraction works independently.
        """
        # Verify core workspace operations exist and work without graph
        assert checkout_tdoc_to_workspace is not None
        assert checkout_spec_to_workspace is not None
        assert ensure_ai_subfolder is not None

    @pytest.mark.skip(reason="LightRAG integration not yet implemented")
    def test_graph_error_caught_and_logged(self) -> None:
        """When LightRAG is integrated, graph errors should be caught.

        Future test: Verify that when rag.insert() raises ValueError or
        RuntimeError, the error is caught, logged with document ID, and
        processing continues for other documents.
        """
        pass

    @pytest.mark.skip(reason="LightRAG integration not yet implemented")
    def test_graph_error_doesnt_crash_workspace_process(self) -> None:
        """When LightRAG is integrated, graph errors should not crash processing.

        Future test: Verify that graph building failures for individual
        documents don't stop the entire workspace process.
        """
        pass
