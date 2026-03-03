"""AI document processing domain package."""

from __future__ import annotations

import litellm

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
from tdoc_crawler.ai.operations.convert import convert_tdoc as convert_document
from tdoc_crawler.ai.operations.embeddings import query_embeddings
from tdoc_crawler.ai.operations.graph import query_graph
from tdoc_crawler.ai.operations.pipeline import get_status, process_all, process_tdoc
from tdoc_crawler.ai.operations.pipeline import process_tdoc as process_document
from tdoc_crawler.ai.operations.summarize import SummarizeResult
from tdoc_crawler.ai.operations.summarize import summarize_tdoc as summarize_document
from tdoc_crawler.ai.operations.workspace_registry import (
    DEFAULT_WORKSPACE,
    WorkspaceDisplayInfo,
    WorkspaceRegistry,
    get_active_workspace,
    set_active_workspace,
)
from tdoc_crawler.ai.operations.workspaces import (
    add_workspace_members,
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    create_workspace,
    delete_workspace,
    ensure_ai_subfolder,
    ensure_default_workspace,
    get_workspace,
    get_workspace_member_counts,
    is_default_workspace,
    list_workspace_members,
    list_workspaces,
    make_workspace_member,
    normalize_workspace_name,
    remove_invalid_members,
    resolve_tdoc_checkout_path,
    resolve_workspace,
)
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.ai.container import AiServiceContainer
from tdoc_crawler.config import CacheManager

litellm.suppress_debug_info = True  # Suppress provider/model info logs from litellm

# Backward-compatible internal aliases used by some tests and monkeypatching.
_pipeline_get_status_impl = get_status
_pipeline_process_tdoc_impl = process_tdoc
_pipeline_process_all_impl = process_all
_query_embeddings = query_embeddings
_query_graph = query_graph


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
    "WorkspaceDisplayInfo",
    "WorkspaceRegistry",
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "convert_document",
    "create_workspace",
    "delete_workspace",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_status",
    "get_workspace",
    "get_workspace_member_counts",
    "is_default_workspace",
    "list_workspace_members",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "process_all",
    "process_document",
    "query_embeddings",
    "query_graph",
    "remove_invalid_members",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "set_active_workspace",
    "summarize_document",
]
