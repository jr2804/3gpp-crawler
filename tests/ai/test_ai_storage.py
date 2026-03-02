"""US1 red tests for workspace membership storage isolation."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.ai.models import DocumentChunk, PipelineStage, ProcessingStatus
from tdoc_crawler.ai.operations import workspaces
from tdoc_crawler.ai.storage import AiStorage


def test_workspace_member_isolation_across_workspaces(tmp_path: Path) -> None:
    """US1: the same source item can exist in different workspaces without collision."""
    storage = AiStorage(tmp_path / "lancedb")

    member_a = workspaces.make_workspace_member(
        workspace="radio-core",
        source_item_id="SP-123456",
        source_path="checkout/radio-core/SP-123456",
        source_kind="tdoc",
    )
    member_b = workspaces.make_workspace_member(
        workspace="edge-ai",
        source_item_id="SP-123456",
        source_path="checkout/edge-ai/SP-123456",
        source_kind="tdoc",
    )

    workspaces.add_workspace_members(storage, "radio-core", [member_a])
    workspaces.add_workspace_members(storage, "edge-ai", [member_b])

    radio_members = storage.list_workspace_members("radio-core")
    edge_members = storage.list_workspace_members("edge-ai")

    assert len(radio_members) == 1
    assert len(edge_members) == 1
    assert radio_members[0].workspace_name == "radio-core"
    assert edge_members[0].workspace_name == "edge-ai"


def test_remove_workspace_member_operation_expected(tmp_path: Path) -> None:
    """US1 red: explicit remove operation should exist on storage API."""
    storage = AiStorage(tmp_path / "lancedb")
    member = workspaces.make_workspace_member(
        workspace="radio-core",
        source_item_id="SP-123456",
        source_path="checkout/radio-core/SP-123456",
        source_kind="tdoc",
    )
    workspaces.add_workspace_members(storage, "radio-core", [member])

    removed = storage.remove_workspace_member("radio-core", "SP-123456")
    assert removed


def test_storage_artifact_isolation_by_workspace(tmp_path: Path) -> None:
    """US3: artifacts (status, chunks) are isolated by workspace."""
    storage = AiStorage(tmp_path / "lancedb", embedding_dimension=3)

    # Save status for workspace A
    status_a = ProcessingStatus(document_id="DOC-1", current_stage=PipelineStage.COMPLETED)
    storage.save_status(status_a, workspace="ws_a")

    # Save chunks for workspace A
    chunk_a = DocumentChunk(
        document_id="DOC-1",
        chunk_id="C1",
        chunk_index=0,
        text="text a",
        metadata={"test": "a"},
        char_offset_start=0,
        char_offset_end=6,
        vector=[0.1, 0.2, 0.3],
        embedding_model="test",
    )
    storage.save_chunks([chunk_a], workspace="ws_a")

    # Should not exist in workspace B
    assert storage.get_status("DOC-1", workspace="ws_b") is None
    assert len(storage.get_chunks("DOC-1", workspace="ws_b")) == 0

    # Should exist in workspace A
    assert storage.get_status("DOC-1", workspace="ws_a") is not None
    assert len(storage.get_chunks("DOC-1", workspace="ws_a")) == 1
