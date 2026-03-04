"""Tests for workspace operations."""

from __future__ import annotations

from tdoc_crawler.ai.models import DocumentChunk, PipelineStage, ProcessingStatus, SourceKind
from tdoc_crawler.ai.operations import workspaces
from tdoc_crawler.ai.storage import AiStorage


def test_workspace_member_isolation_across_workspaces() -> None:
    """US1: same source item can exist in different workspaces without collision."""
    member_a = workspaces.make_workspace_member(
        workspace="radio-core",
        source_item_id="SP-123456",
        source_path="checkout/radio-core/SP-123456",
        source_kind=SourceKind.TDOC,
    )
    member_b = workspaces.make_workspace_member(
        workspace="edge-ai",
        source_item_id="SP-123456",
        source_path="checkout/edge-ai/SP-123456",
        source_kind=SourceKind.TDOC,
    )

    workspaces.add_workspace_members("radio-core", [member_a])
    workspaces.add_workspace_members("edge-ai", [member_b])

    radio_members = workspaces.list_workspace_members("radio-core")
    edge_members = workspaces.list_workspace_members("edge-ai")

    assert len(radio_members) == 1
    assert len(edge_members) == 1
    # Verify member IDs match what was added
    assert radio_members[0].source_item_id == "SP-123456"
    assert edge_members[0].source_item_id == "SP-123456"


def test_remove_workspace_member_operation_expected() -> None:
    """US1 red: explicit remove operation should exist on storage API."""
    member = workspaces.make_workspace_member(
        workspace="radio-core",
        source_item_id="SP-123456",
        source_path="checkout/radio-core/SP-123456",
        source_kind=SourceKind.TDOC,
    )
    workspaces.add_workspace_members("radio-core", [member])

    removed = workspaces.remove_workspace_member("radio-core", "SP-123456")
    assert removed


def test_storage_artifact_isolation_by_workspace(ai_storage: AiStorage) -> None:
    """US3: artifacts (status, chunks) are isolated by workspace."""
    # Save status for workspace A
    status_a = ProcessingStatus(document_id="DOC-1", current_stage=PipelineStage.COMPLETED)
    ai_storage.save_status(status_a, workspace="ws_a")

    # Save chunks for workspace A
    # Vector dimension must match storage's embedding_dimension (usually 384 for all-MiniLM-L6-v2)
    chunk_a = DocumentChunk(
        document_id="DOC-1",
        chunk_id="C1",
        chunk_index=0,
        text="text a",
        metadata={"test": "a"},
        char_offset_start=0,
        char_offset_end=6,
        vector=[0.1] * 384,  # 384-dimensional vector
        embedding_model="test",
    )
    ai_storage.save_chunks([chunk_a], workspace="ws_a")

    # Should not exist in workspace B
    assert ai_storage.get_status("DOC-1", workspace="ws_b") is None
    assert len(ai_storage.get_chunks("DOC-1", workspace="ws_b")) == 0

    # Should exist in workspace A
    assert ai_storage.get_status("DOC-1", workspace="ws_a") is not None
    assert len(ai_storage.get_chunks("DOC-1", workspace="ws_a")) == 1
