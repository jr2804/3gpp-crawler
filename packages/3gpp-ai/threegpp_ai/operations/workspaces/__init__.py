"""Workspace operations - refactored into submodules.

This module provides workspace management functionality for AI pipeline scoping.
It has been refactored into three submodules:

- crud: Workspace CRUD operations (create, delete, list, active workspace)
- members: Member operations (add, remove, deactivate, list members)
- utils: Utility functions (delete_ai_folder, resolve paths, metadata lookup, checkout)
"""

from __future__ import annotations

# Re-export all public functions for backward compatibility
from threegpp_ai.operations.workspaces.crud import (
    create_workspace,
    delete_workspace,
    ensure_default_workspace,
    get_active_workspace,
    get_workspace,
    list_workspaces,
    set_active_workspace,
)
from threegpp_ai.operations.workspaces.members import (
    add_workspace_members,
    deactivate_workspace_member,
    get_workspace_member_counts,
    list_workspace_members,
    make_workspace_member,
    remove_invalid_members,
    remove_workspace_member,
)
from threegpp_ai.operations.workspaces.utils import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    delete_ai_folder,
    ensure_ai_subfolder,
    resolve_spec_release_from_db,
    resolve_tdoc_checkout_path,
)

__all__ = [
    # Member operations
    "add_workspace_members",
    # Checkout operations
    "checkout_spec_to_workspace",
    "checkout_tdoc_to_workspace",
    "create_workspace",
    "deactivate_workspace_member",
    # Utilities
    "delete_ai_folder",
    "delete_workspace",
    "ensure_ai_subfolder",
    # CRUD operations
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
