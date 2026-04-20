"""AI document processing domain package.

This package provides AI-powered document processing for 3GPP TDocs.
Supports extraction, conversion, workspace operations, and summarization flows.
"""

from __future__ import annotations

import litellm

from threegpp_ai.models import SourceKind, SummarizeResult, WorkspaceNotFoundError
from threegpp_ai.operations.convert import convert_tdoc_metadata as convert_document
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
    delete_ai_folder,
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
    resolve_spec_release_from_db,
    resolve_tdoc_checkout_path,
)

litellm.suppress_debug_info = True  # Suppress provider/model info logs from litellm


__all__ = [
    # Workspace management
    "DEFAULT_WORKSPACE",
    "SourceKind",
    "SummarizeResult",
    "WorkspaceNotFoundError",
    "WorkspaceRegistry",
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    # Document operations
    "convert_document",
    "convert_tdoc_to_markdown",
    "create_workspace",
    "delete_ai_folder",
    "delete_workspace",
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
    "resolve_spec_release_from_db",
    "resolve_tdoc_checkout_path",
    "set_active_workspace",
    "summarize_document",
]
