"""Workspace management package for the main application."""

from tdoc_crawler.models.workspaces import DEFAULT_WORKSPACE, is_default_workspace, normalize_workspace_name
from tdoc_crawler.workspaces.crud import (
    create_workspace,
    delete_workspace,
    ensure_default_workspace,
    get_active_workspace,
    get_workspace,
    list_workspaces,
    set_active_workspace,
)
from tdoc_crawler.workspaces.members import (
    add_workspace_members,
    deactivate_workspace_member,
    get_workspace_member_counts,
    list_workspace_members,
    make_workspace_member,
    remove_invalid_members,
    remove_workspace_member,
)
from tdoc_crawler.workspaces.utils import delete_artifact_folder, resolve_tdoc_checkout_path

__all__ = [
    "DEFAULT_WORKSPACE",
    "add_workspace_members",
    "create_workspace",
    "deactivate_workspace_member",
    "delete_artifact_folder",
    "delete_workspace",
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
    "remove_workspace_member",
    "resolve_tdoc_checkout_path",
    "set_active_workspace",
]
