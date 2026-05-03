"""Workspace CLI commands — split from monolithic _workspace_commands.py."""

from __future__ import annotations

import typer

from tdoc_crawler.cli.workspace.create import workspace_create
from tdoc_crawler.cli.workspace.lifecycle import (
    workspace_activate,
    workspace_deactivate,
    workspace_delete,
    workspace_list,
)
from tdoc_crawler.cli.workspace.members import (
    workspace_add,
    workspace_clear_invalid,
    workspace_members,
)
from tdoc_crawler.cli.workspace.process import workspace_process

app = typer.Typer(help="Manage extraction workspaces")

app.command("create")(workspace_create)
app.command("list")(workspace_list)
app.command("activate")(workspace_activate)
app.command("deactivate")(workspace_deactivate)
app.command("delete")(workspace_delete)
app.command("members")(workspace_members)
app.command("add")(workspace_add)
app.command("clear-invalid")(workspace_clear_invalid)
app.command("process")(workspace_process)

__all__ = ["app"]
