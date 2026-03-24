"""AI document processing domain package.

This package provides AI-powered document processing for 3GPP TDocs.
Supports both legacy LiteLLM summarization and modern LightRAG knowledge graph.
"""

from __future__ import annotations

import litellm

# Import LightRAG integration
from threegpp_ai.lightrag import (
    DatabaseConfig,
    EmbeddingConfig,
    LightRAGConfig,
    LLMConfig,
    Pg0Error,
    Pg0Manager,
    ProcessingResult,
    ProcessingResultStatus,
    QueryMode,
    RAGMetadata,
    StorageBackend,
    TDocProcessor,
    TDocRAG,
    create_metadata_from_dict,
    enrich_text,
)
from threegpp_ai.models import SourceKind, SummarizeResult
from threegpp_ai.operations.convert import convert_tdoc as convert_document
from threegpp_ai.operations.convert import convert_tdoc_to_markdown
from threegpp_ai.operations.summarize import summarize_tdoc as summarize_document
from threegpp_ai.operations.workspace_registry import (
    DEFAULT_WORKSPACE,
    WorkspaceRegistry,
    get_active_workspace,
    set_active_workspace,
)
from threegpp_ai.operations.workspaces import (
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

litellm.suppress_debug_info = True  # Suppress provider/model info logs from litellm


__all__ = [
    # Workspace management
    "DEFAULT_WORKSPACE",
    # LightRAG integration
    "DatabaseConfig",
    "EmbeddingConfig",
    "LLMConfig",
    "LightRAGConfig",
    "Pg0Error",
    "Pg0Manager",
    "ProcessingResult",
    "ProcessingResultStatus",
    "QueryMode",
    "RAGMetadata",
    "SourceKind",
    "StorageBackend",
    "SummarizeResult",
    "TDocProcessor",
    "TDocRAG",
    "WorkspaceRegistry",
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    # Document operations
    "convert_document",
    "convert_tdoc_to_markdown",
    "create_metadata_from_dict",
    "create_workspace",
    "delete_workspace",
    "enrich_text",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_workspace",
    "get_workspace_member_counts",
    "is_default_workspace",
    "list_workspace_members",
    "list_workspaces",
    "make_workspace_member",
    "normalize_workspace_name",
    "remove_invalid_members",
    "resolve_tdoc_checkout_path",
    "resolve_workspace",
    "set_active_workspace",
    "summarize_document",
]
