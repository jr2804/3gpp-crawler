"""Config management CLI commands."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from tdoc_crawler.cli.constants import HELP_PANEL_CONFIG, SECTION_DESCRIPTIONS
from tdoc_crawler.config.export import ConfigExporter
from tdoc_crawler.config.settings import ThreeGPPConfig

FormatType = Literal["toml", "yaml", "json"]

console = Console()
logger = logging.getLogger(__name__)

ConfigInitOutputOption = Annotated[
    Path,
    typer.Option("--output", "-o", help="Output file path"),
]
ConfigInitFormatOption = Annotated[
    FormatType,
    typer.Option("--format", "-f", help="Output format (toml, yaml, json)"),
]
ConfigInitForceOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite existing file"),
]
ConfigShowFormatOption = Annotated[
    FormatType,
    typer.Option("--format", "-f", help="Output format (toml, yaml, json)"),
]
ConfigValidateFileOption = Annotated[
    Path | None,
    typer.Option("--file", "-f", help="Validate specific config file instead of discovered config"),
]
ConfigValidateStrictOption = Annotated[
    bool,
    typer.Option("--strict", help="Treat warnings as errors (exit 2)"),
]
ConfigDocsSectionOption = Annotated[
    str | None,
    typer.Option("--section", "-s", help="Show specific section (path, http, credentials, crawl)"),
]

config_app = typer.Typer(help="Manage configuration")


@config_app.command("init", rich_help_panel=HELP_PANEL_CONFIG)
def config_init(
    output: ConfigInitOutputOption,
    format: ConfigInitFormatOption = "toml",
    force: ConfigInitForceOption = False,
) -> None:
    """Generate default configuration file."""
    exporter = ConfigExporter()

    try:
        exporter.save(output, format=format, force=force)
        rprint(f"[green]Configuration written to:[/green] {output}")
    except FileExistsError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("show", rich_help_panel=HELP_PANEL_CONFIG)
def config_show(
    format: ConfigShowFormatOption = "toml",
) -> None:
    """Display current configuration (stdout)."""
    exporter = ConfigExporter()
    print(exporter.export(format))


def _check_path_exists(path: Path) -> tuple[bool, str]:
    """Check if a path exists or can be created."""
    if path.exists():
        return True, ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return True, " (will be created)"
    except PermissionError:
        return False, " (permission denied)"
    except OSError as e:
        return False, f" ({e})"


def _validate_config_values(config: ThreeGPPConfig) -> list[tuple[str, str]]:
    """Validate config values and return list of (severity, message) tuples."""
    issues: list[tuple[str, str]] = []

    # Check cache_dir
    cache_dir = config.path.cache_dir
    exists, detail = _check_path_exists(cache_dir)
    if not exists:
        issues.append(("error", f"cache_dir does not exist and cannot be created: {cache_dir}{detail}"))
    elif detail:
        issues.append(("warning", f"cache_dir will be created: {cache_dir}"))

    # Check timeout range
    if config.http.timeout < 1:
        issues.append(("error", f"http.timeout must be >= 1, got {config.http.timeout}"))

    # Check max_retries range
    if config.http.max_retries < 0:
        issues.append(("error", f"http.max_retries must be >= 0, got {config.http.max_retries}"))

    # Check cache_ttl range
    if config.http.cache_ttl < 0:
        issues.append(("error", f"http.cache_ttl must be >= 0, got {config.http.cache_ttl}"))

    # Check workers range
    if config.crawl.workers < 1 or config.crawl.workers > 32:
        issues.append(("error", f"crawl.workers must be 1-32, got {config.crawl.workers}"))

    # Check limit range
    if config.crawl.limit < 1:
        issues.append(("error", f"crawl.limit must be >= 1, got {config.crawl.limit}"))

    # Warnings for missing optional credentials
    if not config.credentials.has_credentials:
        issues.append(("warning", "credentials not set (username/password); some features may require authentication"))

    # Warnings for missing optional filters
    if config.crawl.working_group is None:
        issues.append(("warning", "crawl.working_group not set (no filter applied)"))

    return issues


def _validate_from_file(file: Path) -> ThreeGPPConfig:
    """Load config from a specific file with validation."""
    if not file.exists():
        rprint(f"[red]Error: File not found:[/red] {file}")
        raise typer.Exit(1)

    # Syntax check via tomllib
    try:
        with file.open("rb") as f:
            tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        rprint(f"[red]Syntax error in {file}:[/red]")
        rprint(f"  {e}")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error reading {file}:[/red] {e}")
        raise typer.Exit(1)

    # Load and validate
    try:
        return ThreeGPPConfig.from_settings(config_file=file)
    except ValidationError as e:
        rprint(f"[red]Validation error in {file}:[/red]")
        for error in e.errors():
            rprint(f"  {error['loc']}: {error['msg']}")
        raise typer.Exit(2)


def _display_validation_results(issues: list[tuple[str, str]], strict: bool) -> None:
    """Display validation results and exit with appropriate code."""
    errors = [msg for sev, msg in issues if sev == "error"]
    warnings = [msg for sev, msg in issues if sev == "warning"]

    if errors:
        rprint("[red]Errors:[/red]")
        for error in errors:
            rprint(f"  • {error}")
        rprint()

    if warnings:
        rprint("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            rprint(f"  • {warning}")
        rprint()

    if not errors and not warnings:
        rprint("[green]✓ Configuration is valid[/green]")
        raise typer.Exit(0)

    if errors:
        raise typer.Exit(2)

    # Warnings only
    if strict:
        rprint("[red]Warnings treated as errors (--strict)[/red]")
        raise typer.Exit(2)

    rprint("[yellow]Configuration is valid (with warnings)[/yellow]")
    raise typer.Exit(3)


@config_app.command("validate", rich_help_panel=HELP_PANEL_CONFIG)
def config_validate(
    file: ConfigValidateFileOption = None,
    strict: ConfigValidateStrictOption = False,
) -> None:
    """Validate configuration files.

    Exit codes:
    - 0: All valid
    - 1: Syntax error
    - 2: Validation error (bad values)
    - 3: Warnings only (ok to proceed, or --strict treats warnings as errors)
    """
    if file:
        config = _validate_from_file(file)
    else:
        try:
            config = ThreeGPPConfig.from_settings()
        except ValidationError as e:
            rprint("[red]Validation error in discovered config:[/red]")
            for error in e.errors():
                rprint(f"  {error['loc']}: {error['msg']}")
            raise typer.Exit(2)
        except Exception as e:
            rprint(f"[red]Error loading config:[/red] {e}")
            raise typer.Exit(1)

    issues = _validate_config_values(config)
    _display_validation_results(issues, strict)


@config_app.command("docs", rich_help_panel=HELP_PANEL_CONFIG)
def config_docs(
    section: ConfigDocsSectionOption = None,
) -> None:
    """Show configuration documentation.

    Shows all sections or a specific section if --section is provided.
    Each section shows field names, types, defaults, and descriptions.
    """
    # Build documentation table
    sections: dict[str, list[dict]] = {
        "path": [],
        "http": [],
        "credentials": [],
        "crawl": [],
    }

    # Introspect ThreeGPPConfig
    config = ThreeGPPConfig()
    config_data = config.model_dump()

    for section_name, section_model in [
        ("path", config.path),
        ("http", config.http),
        ("credentials", config.credentials),
        ("crawl", config.crawl),
    ]:
        model_cls = type(section_model)
        fields = model_cls.model_fields

        for field_name, field_info in fields.items():
            description = field_info.description or ""
            default = field_info.default
            if callable(default):
                default = None

            # Get current value
            value = config_data.get(section_name, {}).get(field_name)

            sections[section_name].append(
                {
                    "field": field_name,
                    "type": field_info.annotation.__name__ if hasattr(field_info.annotation, "__name__") else str(field_info.annotation),
                    "default": default,
                    "value": value,
                    "description": description,
                }
            )

    if section:
        # Show specific section
        section_lower = section.lower()
        if section_lower not in sections:
            available = ", ".join(sections.keys())
            rprint(f"[red]Unknown section:[/red] {section}")
            rprint(f"Available sections: {available}")
            raise typer.Exit(1)

        _print_section_docs(section_lower, sections[section_lower], SECTION_DESCRIPTIONS.get(section_lower, ""))
    else:
        # Show all sections
        for section_name, fields_list in sections.items():
            _print_section_docs(section_name, fields_list, SECTION_DESCRIPTIONS.get(section_name, ""))
            if section_name != "crawl":
                rprint()


def _print_section_docs(section: str, fields: list[dict], description: str) -> None:
    """Print documentation for a single section."""
    title = section.upper() if section == "http" else section.capitalize()
    rprint(f"[bold]{title} Settings[/bold]")
    if description:
        rprint(f"[dim]{description}[/dim]")
    rprint()

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Field", style="cyan")
    table.add_column("Type")
    table.add_column("Default")
    table.add_column("Description")

    for field in fields:
        desc = field["description"]
        default_str = str(field["default"]) if field["default"] is not None else "(none)"
        table.add_row(
            field["field"],
            field["type"],
            default_str,
            desc[:60] + "..." if len(desc) > 60 else desc,
        )

    console.print(table)


__all__ = ["config_app"]
