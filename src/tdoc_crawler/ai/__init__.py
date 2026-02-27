"""AI document processing domain package."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
from tdoc_crawler.ai.operations.convert import convert_tdoc
from tdoc_crawler.ai.operations.embeddings import query_embeddings as _query_embeddings
from tdoc_crawler.ai.operations.graph import query_graph as _query_graph
from tdoc_crawler.ai.operations.pipeline import get_status as _pipeline_get_status_impl
from tdoc_crawler.ai.operations.pipeline import process_all as _pipeline_process_all_impl
from tdoc_crawler.ai.operations.pipeline import process_tdoc as _pipeline_process_tdoc_impl
from tdoc_crawler.ai.operations.summarize import SummarizeResult, summarize_tdoc
from tdoc_crawler.ai.operations.workspaces import (
    DEFAULT_WORKSPACE,
    add_workspace_members,
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    create_workspace,
    delete_workspace,
    ensure_ai_subfolder,
    ensure_default_workspace,
    get_workspace,
    is_default_workspace,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    resolve_tdoc_checkout_path,
    resolve_workspace,
)
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.config import CacheManager


def _pipeline_get_status(tdoc_id: str, workspace: str) -> ProcessingStatus | None:
    """Get processing status for a TDoc."""
    return _pipeline_get_status_impl(tdoc_id, workspace=workspace)


def get_status(tdoc_id: str, workspace: str | None = None) -> ProcessingStatus | None:
    """Get processing status for a TDoc."""
    return _pipeline_get_status_impl(tdoc_id, workspace=workspace)


def process_tdoc(
    tdoc_id: str,
    checkout_path: Path,
    force_rerun: bool = False,
    workspace: str | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline."""
    return _pipeline_process_tdoc_impl(
        tdoc_id,
        checkout_path,
        force_rerun=force_rerun,
        workspace=workspace,
    )


def process_all(
    tdoc_ids: list[str],
    checkout_base: Path,
    new_only: bool = False,
    force_rerun: bool = False,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
    workspace: str | None = None,
) -> dict[str, ProcessingStatus]:
    """Process multiple TDocs through the AI pipeline."""
    return _pipeline_process_all_impl(
        tdoc_ids,
        checkout_base,
        new_only=new_only,
        force_rerun=force_rerun,
        progress_callback=progress_callback,
        workspace=workspace,
    )


def query_embeddings(
    query: str,
    workspace: str,
    top_k: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Query embeddings for semantic search."""
    return _query_embeddings(query, workspace, top_k)


def query_graph(
    query: str,
    workspace: str,
    top_k: int = 5,
) -> list[dict]:
    """Query knowledge graph."""
    return _query_graph(query, workspace, top_k)


__all__ = [
    "DEFAULT_WORKSPACE",
    "AiConfig",
    "AiStorage",
    "CacheManager",
    "DocumentChunk",
    "DocumentClassification",
    "DocumentSummary",
    "GraphEdge",
    "GraphNode",
    "PipelineStage",
    "ProcessingStatus",
    "SummarizeResult",
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "convert_tdoc",
    "create_workspace",
    "delete_workspace",
    "ensure_ai_subfolder",
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
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "summarize_tdoc",
]
