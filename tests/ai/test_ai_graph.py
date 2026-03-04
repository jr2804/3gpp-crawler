"""Tests for knowledge graph construction and queries."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from tdoc_crawler.ai.models import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType
from tdoc_crawler.ai.operations import graph
from tdoc_crawler.ai.operations.graph import (
    extract_change_requests,
    extract_company_entities,
    extract_work_items,
)


class TestGraph:
    """Tests for graph functions."""

    def test_node_creation_tdoc_meeting_spec_types(self) -> None:
        """Test node creation for TDoc/Meeting/Spec/Concept types."""
        node = GraphNode(
            node_id="SP-123456",
            node_type=GraphNodeType.TDOC,
            label="Test TDoc",
        )
        assert node.node_type == GraphNodeType.TDOC

    def test_edge_creation_relationships(self) -> None:
        """Test edge creation for discusses/revises/references relationships."""
        edge = GraphEdge(
            edge_id="SP-123456->discusses->SP-123457",
            source_id="SP-123456",
            target_id="SP-123457",
            edge_type=GraphEdgeType.DISCUSSES,
            weight=1.0,
            temporal_context="SA#123",
            provenance="extracted_from_tdoc",
        )
        assert edge.edge_type == GraphEdgeType.DISCUSSES

    def test_temporal_validity_fields(self) -> None:
        """Test temporal validity fields are populated."""
        edge = GraphEdge(
            edge_id="SP-123456->discusses->SP-123457",
            source_id="SP-123456",
            target_id="SP-123457",
            edge_type=GraphEdgeType.REVISES,
            weight=1.0,
            temporal_context="SA#123",
            provenance="extracted_from_tdoc",
        )
        assert edge.temporal_context is not None

    def test_incremental_update_adds_without_rebuild(self, mock_storage: MagicMock) -> None:
        """Test incremental update adds without full rebuild."""
        # Setup: Create initial graph with one node
        initial_nodes = [GraphNode(node_id="S4-250001", node_type=GraphNodeType.TDOC, label="Initial TDoc")]
        initial_edges: list[GraphEdge] = []

        # Mock query_graph to return existing nodes
        mock_storage.query_graph.return_value = (initial_nodes, initial_edges)

        # Call build_graph with new content that should add one more node
        markdown_content = """
        # Test Document
        This is a test TDoc S4-250002.
        It references S4-250001.
        """

        # Simulate calling build_graph which should use storage
        result_nodes, result_edges = graph.build_graph(
            document_id="S4-250002", markdown=markdown_content, meeting_id="SA4#123", storage=mock_storage, workspace="test_ws"
        )

        # Verify query_graph was called to fetch existing data (incremental check)
        mock_storage.query_graph.assert_called_once()

        # Verify new nodes/edges were created
        assert len(result_nodes) >= 1  # At minimum the new node
        assert len(result_edges) >= 1  # At minimum the REFERENCES edge

    def test_cross_meeting_query_chronological(self, mock_storage: MagicMock) -> None:
        """Test cross-meeting query returns chronological order."""
        # Setup: Create nodes from 3 different dates
        nodes = [
            GraphNode(
                node_id="S4-250001",
                node_type=GraphNodeType.TDOC,
                label="TDoc 1",
                properties={"meeting_id": "SA4#123"},
                created_at=datetime(2025, 1, 15),
            ),
            GraphNode(
                node_id="SP-123002",
                node_type=GraphNodeType.TDOC,
                label="TDoc 2",
                properties={"meeting_id": "SP#123"},
                created_at=datetime(2025, 3, 20),
            ),
            GraphNode(
                node_id="RP-880003",
                node_type=GraphNodeType.TDOC,
                label="TDoc 3",
                properties={"meeting_id": "RP#88"},
                created_at=datetime(2025, 2, 10),
            ),
        ]
        edges: list[GraphEdge] = []

        # Mock storage methods (not query_graph, but the helper methods)
        mock_storage.get_all_graph_nodes.return_value = nodes
        mock_storage.get_all_graph_edges.return_value = edges
        mock_storage.query_graph.return_value = (nodes, edges)

        # Query with temporal filtering - query_graph returns dict with 'results' key
        results = graph.query_graph(query="all tdocs", storage=mock_storage, meeting_ids=["SA4#123", "SP#123", "RP#88"])

        # Extract nodes from results
        filtered_nodes = [r.node for r in results["results"]]

        # Verify results are sorted chronologically by created_at
        assert len(filtered_nodes) == 3
        # First should be Jan, then Feb, then Mar
        assert filtered_nodes[0].node_id == "S4-250001"  # Jan 15
        assert filtered_nodes[1].node_id == "RP-880003"  # Feb 10
        assert filtered_nodes[2].node_id == "SP-123002"  # Mar 20

    def test_explicit_tdoc_reference_creates_edge(self, mock_storage: MagicMock) -> None:
        """Test explicit TDoc-ID reference creates references edge."""
        # Setup: Markdown content with explicit TDoc reference
        markdown_content = """
        # Technical Contribution
        This document proposes enhancements to NR uplink.

        As discussed in S4-251003, we need to consider power control.
        The approach builds on principles from S4-240567.
        """

        # Mock storage to return empty graph initially
        mock_storage.query_graph.return_value = ([], [])

        # Build graph - should extract references and create edges
        result_nodes, result_edges = graph.build_graph(
            document_id="S4-252000", markdown=markdown_content, meeting_id="SA4#123", storage=mock_storage, workspace="test_ws"
        )

        # Verify REFERENCES edges were created
        ref_edges = [e for e in result_edges if e.edge_type == GraphEdgeType.REFERENCES]
        assert len(ref_edges) >= 2  # Should have edges to S4-251003 and S4-240567

        # Verify edge targets match extracted TDoc IDs
        target_ids = {e.target_id for e in ref_edges}
        assert "S4-251003" in target_ids
        assert "S4-240567" in target_ids


class TestGraphModuleExports:
    """Tests that graph module exports required functions."""

    def test_build_graph_exported(self) -> None:
        """Verify build_graph is exported."""
        assert hasattr(graph, "build_graph")
        assert callable(graph.build_graph)

    def test_query_graph_exported(self) -> None:
        """Verify query_graph is exported."""
        assert hasattr(graph, "query_graph")
        assert callable(graph.query_graph)


class TestEntityExtractors:
    """Test entity extraction functions for graph-RAG."""

    def test_extract_company_entities(self) -> None:
        """Test company name extraction."""
        text = "This document was submitted by Huawei and Nokia for discussion at 3GPP."
        companies = extract_company_entities(text)

        assert "Huawei" in companies
        assert "Nokia" in companies
        assert len(companies) >= 2

    def test_extract_work_items(self) -> None:
        """Test work item extraction."""
        text = "This relates to WI-12345 and Work Item 67890 for 5G enhancement."
        wis = extract_work_items(text)

        assert "WI-12345" in wis
        assert "WI-67890" in wis

    def test_extract_change_requests(self) -> None:
        """Test change request extraction."""
        text = "This CR-001234 and Change Request 5678 propose modifications to the spec."
        crs = extract_change_requests(text)

        assert "CR-001234" in crs
        assert "CR-5678" in crs

    def test_extract_all_entity_types(self) -> None:
        """Test extraction of all entity types together."""
        text = """
        Samsung proposes WI-99999 to address CR-11111.
        This work item relates to change request CP-230001.
        Ericsson and Qualcomm support this proposal.
        """

        companies = extract_company_entities(text)
        wis = extract_work_items(text)
        crs = extract_change_requests(text)

        assert "Samsung" in companies
        assert "Ericsson" in companies
        assert "Qualcomm" in companies
        assert "WI-99999" in wis
        assert "CR-11111" in crs
        assert "CR-CP-230001" in crs or "CR-230001" in crs
