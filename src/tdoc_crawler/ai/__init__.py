"""AI document processing domain package."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import (
    DocumentChunk,
    DocumentClassification,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    PipelineStage,
    ProcessingStatus,
)
from tdoc_crawler.ai.operations.embeddings import query_embeddings as _query_embeddings
from tdoc_crawler.ai.operations.graph import query_graph as _query_graph
from tdoc_crawler.ai.operations.pipeline import get_status as _pipeline_get_status_impl
from tdoc_crawler.ai.operations.pipeline import process_all as _pipeline_process_all_impl
from tdoc_crawler.ai.operations.pipeline import process_tdoc as _pipeline_process_tdoc_impl
from tdoc_crawler.ai.operations.workspaces import (
    DEFAULT_WORKSPACE,
    add_workspace_members,
    create_workspace,
    delete_workspace,
    ensure_default_workspace,
    get_workspace,
    is_default_workspace,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    resolve_workspace,
)
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.config import CacheManager


def _pipeline_get_status(tdoc_id: str, workspace: str) -> ProcessingStatus | None:
    return _pipeline_get_status_impl(tdoc_id, workspace=workspace)


def _pipeline_process_all(
    tdoc_ids: list[str],
    checkout_base: Path,
    new_only: bool,
    force_rerun: bool,
    progress_callback: Callable[[PipelineStage, str], None] | None,
    workspace: str,
) -> dict[str, ProcessingStatus]:
    return _pipeline_process_all_impl(
        tdoc_ids,
        checkout_base,
        new_only=new_only,
        force_rerun=force_rerun,
        progress_callback=progress_callback,
        workspace=workspace,
    )


def _pipeline_process_tdoc(
    tdoc_id: str,
    checkout_path: Path,
    force_rerun: bool,
    workspace: str,
) -> ProcessingStatus:
    return _pipeline_process_tdoc_impl(
        tdoc_id,
        checkout_path,
        force_rerun=force_rerun,
        workspace=workspace,
    )


def process_tdoc(
    tdoc_id: str,
    config: AiConfig | str | Path | None = None,
    stages: list[PipelineStage] | None = None,
    checkout_path: str | Path | None = None,
    force_rerun: bool = False,
    workspace: str | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline.

    Args:
        tdoc_id: TDoc identifier (e.g., "SP-123456").
        config: Optional AI configuration.
        stages: Optional subset of pipeline stages.
        checkout_path: Optional path to TDoc checkout folder.
        force_rerun: If True, skip resume logic.
        workspace: Optional workspace name. Omitted/blank resolves to default.

    Returns:
        Updated ProcessingStatus after pipeline execution.
    """
    _ = stages
    normalized_workspace = normalize_workspace_name(workspace)

    if checkout_path is None and isinstance(config, (str, Path)):
        checkout_path = config
        config = None
    _ = config

    if checkout_path is not None:
        return _pipeline_process_tdoc(
            tdoc_id,
            Path(checkout_path),
            force_rerun=force_rerun,
            workspace=normalized_workspace,
        )

    status = _pipeline_get_status(tdoc_id, workspace=normalized_workspace)
    if status is None:
        msg = f"No status found for {tdoc_id}. Provide checkout_path to process the TDoc."
        raise ValueError(msg)
    return status


def process_all(
    config: AiConfig | None = None,
    new_only: bool = False,
    stages: list[PipelineStage] | None = None,
    progress_callback: Callable[[str, PipelineStage], None] | None = None,
    tdoc_ids: list[str] | None = None,
    checkout_base: str | Path | None = None,
    force_rerun: bool = False,
    workspace: str | None = None,
) -> list[ProcessingStatus]:
    """Batch process TDocs through the AI pipeline.

    Args:
        config: Optional AI configuration.
        new_only: Process new-only mode flag.
        stages: Optional subset of pipeline stages.
        progress_callback: Optional progress callback.
        tdoc_ids: Optional list of TDoc identifiers (backward-compatible mode).
        checkout_base: Optional base path containing TDoc folders.
        force_rerun: If True, skip resume logic.
        workspace: Optional workspace name. Omitted/blank resolves to default.

    Returns:
        List of ProcessingStatus values.
    """
    _ = config
    _ = stages
    normalized_workspace = normalize_workspace_name(workspace)

    if tdoc_ids is None or checkout_base is None:
        return []

    mapped_progress_callback = (lambda stage, current_tdoc_id: progress_callback(current_tdoc_id, stage)) if progress_callback else None
    try:
        results = _pipeline_process_all(
            tdoc_ids,
            Path(checkout_base),
            new_only=new_only,
            force_rerun=force_rerun,
            progress_callback=mapped_progress_callback,
            workspace=normalized_workspace,
        )
    except TypeError:
        results = _pipeline_process_all(
            tdoc_ids,
            Path(checkout_base),
            new_only=False,
            force_rerun=force_rerun,
            progress_callback=None,
            workspace=normalized_workspace,
        )
    statuses = list(results.values())
    if new_only:
        return [status for status in statuses if status.current_stage != PipelineStage.COMPLETED]
    return statuses


def get_status(
    tdoc_id: str | None = None,
    workspace: str | None = None,
) -> ProcessingStatus | list[ProcessingStatus] | None:
    """Get processing status for a TDoc.

    Args:
        tdoc_id: Optional TDoc identifier. If omitted, returns all statuses.
        workspace: Optional workspace name. Omitted/blank resolves to default.

    Returns:
        ProcessingStatus, list of statuses, or None if not found.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    if tdoc_id is None:
        manager = CacheManager().register()
        storage = AiStorage(manager.root / ".ai" / "lancedb")
        ensure_default_workspace(storage)
        return storage.list_statuses(workspace=normalized_workspace)
    return _pipeline_get_status(tdoc_id, workspace=normalized_workspace)


def query_embeddings(
    query: str,
    top_k: int = 5,
    workspace: str | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Semantic search over embedded document chunks.

    Args:
        query: Natural language query text.
        top_k: Number of top results to return.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        List of (chunk, similarity_score) tuples.
    """
    return _query_embeddings(query, top_k, workspace=workspace)


def query_graph(
    query: str,
    temporal_range: tuple[datetime, datetime] | None = None,
    node_types: list[str] | None = None,
) -> dict[str, Any]:
    """Query the temporal knowledge graph.

    Args:
        query: Natural language query about relationships/evolution.
        temporal_range: Optional (start, end) datetime filter.
        node_types: Optional filter for node types.

    Returns:
        Dict with keys "nodes", "edges", and "answer".
    """
    results = _query_graph(query, top_k=10)

    # Convert to dict format
    return {
        "nodes": [r.node.model_dump() for r in results],
        "edges": [e.model_dump() for r in results for e in r.connected_edges],
        "answer": f"Found {len(results)} related documents",
    }


__all__ = [
    "DEFAULT_WORKSPACE",
    "AiConfig",
    "DocumentChunk",
    "DocumentClassification",
    "DocumentSummary",
    "GraphEdge",
    "GraphNode",
    "PipelineStage",
    "ProcessingStatus",
    "add_workspace_members",
    "create_workspace",
    "delete_workspace",
    "ensure_default_workspace",
    "get_status",
    "get_workspace",
    "is_default_workspace",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "process_all",
    "process_tdoc",
    "query_embeddings",
    "query_graph",
    "resolve_workspace",
]
