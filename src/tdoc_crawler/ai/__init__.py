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


def query_embeddings(query: str, workspace: str, top_k: int = 10) -> list:
    """Query embeddings for a given query string."""
    return _query_embeddings(query, workspace=workspace, top_k=top_k)


def query_graph(query: str, workspace: str, top_k: int = 10) -> list:
    """Query the knowledge graph for a given query string."""
    return _query_graph(query, workspace=workspace, top_k=top_k)


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
    "checkout_tdoc_to_workspace",
    "convert_tdoc",
    "create_workspace",
    "delete_workspace",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_workspace",
    "is_default_workspace",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "query_embeddings",
    "query_graph",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "summarize_tdoc",
]
