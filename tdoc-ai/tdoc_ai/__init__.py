"""AI document processing domain package."""

from __future__ import annotations

import litellm

from tdoc_ai.config import AiConfig
from tdoc_ai.container import AiServiceContainer
from tdoc_ai.models import (
    DocumentChunk,
    DocumentClassification,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    PipelineStage,
    ProcessingStatus,
)
from tdoc_ai.operations.convert import convert_tdoc as convert_document
from tdoc_ai.operations.graph import query_graph
from tdoc_ai.operations.pipeline import get_status, process_all
from tdoc_ai.operations.pipeline import process_tdoc as process_document
from tdoc_ai.operations.summarize import SummarizeResult
from tdoc_ai.operations.summarize import summarize_tdoc as summarize_document
from tdoc_ai.operations.workspace_registry import (
    DEFAULT_WORKSPACE,
    WorkspaceDisplayInfo,
    WorkspaceRegistry,
    get_active_workspace,
    set_active_workspace,
)
from tdoc_ai.operations.workspaces import (
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
from tdoc_ai.storage import AiStorage
from tdoc_crawler.config import CacheManager

litellm.suppress_debug_info = True  # Suppress provider/model info logs from litellm

process_tdoc = process_document


__all__ = [
    "DEFAULT_WORKSPACE",
    "AiConfig",
    "AiServiceContainer",
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
    "process_tdoc",
    "process_document",
    "query_graph",
    "remove_invalid_members",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "set_active_workspace",
    "summarize_document",
]
