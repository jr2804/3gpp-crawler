"""Workspace helper operations for AI pipeline scoping.

This module has been refactored into submodules:
- crud: Workspace CRUD operations
- members: Member operations
- utils: Utility functions (including checkout operations)

This file re-exports all functions for backward compatibility.
"""

from __future__ import annotations

from threegpp_ai.operations.workspaces import (
    add_workspace_members,
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    create_workspace,
    deactivate_workspace_member,
    delete_ai_folder,
    delete_workspace,
    ensure_ai_subfolder,
    ensure_default_workspace,
    get_active_workspace,
    get_workspace,
    get_workspace_member_counts,
    list_workspace_members,
    list_workspaces,
    make_workspace_member,
    remove_invalid_members,
    remove_workspace_member,
    resolve_spec_release_from_db,
    resolve_tdoc_checkout_path,
    set_active_workspace,
)

__all__ = [
    "add_workspace_members",
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "create_workspace",
    "deactivate_workspace_member",
    "delete_ai_folder",
    "delete_workspace",
    "ensure_ai_subfolder",
    "ensure_default_workspace",
    "get_active_workspace",
    "get_workspace",
    "get_workspace_member_counts",
    "list_workspace_members",
    "list_workspaces",
    "make_workspace_member",
    "remove_invalid_members",
    "remove_workspace_member",
    "resolve_spec_release_from_db",
    "resolve_tdoc_checkout_path",
    "set_active_workspace",
]
