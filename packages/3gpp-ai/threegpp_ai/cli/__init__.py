"""CLI package for 3gpp-ai.

Provides a modular command tree with convert/summarize/workspace operations
for extraction-first document workflows.
"""

from __future__ import annotations

from threegpp_ai.config_app import config_app

from ._commands import app as main_app
from ._hybrid_commands import app as hybrid_app
from ._workspace_commands import app as workspace_app

app = main_app
app.add_typer(workspace_app, name="workspace")
app.add_typer(hybrid_app, name="hybrid-server")
app.add_typer(config_app, name="config")

__all__ = ["app"]
