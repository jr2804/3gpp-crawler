"""Config management CLI commands for 3gpp-ai."""

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
from tdoc_crawler.config.settings import ThreeGPPConfig

from threegpp_ai.config import AiConfig

from .config_exporter import ConfigExporter

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
ConfigShowSecretsOption = Annotated[
    bool,
    typer.Option("--show-secrets", help="Show actual API keys instead of ${VAR} placeholders (WARNING: not secure)"),
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
    typer.Option("--section", "-s", help="Show specific section (path, http, credentials, crawl, llm, extraction, runtime)"),
]

config_app = typer.Typer(help="Manage configuration")


@config_app.command("init")
def config_init(
    output: ConfigInitOutputOption,
    format: ConfigInitFormatOption = "toml",
    force: ConfigInitForceOption = False,
) -> None:
    """Generate default configuration file.

    Creates a configuration file with all crawler and AI settings.
    Sensitive values (API keys) use ${ENV_VAR} syntax for security.

    Example:
        3gpp-ai config init -o 3gpp-ai.toml
        3gpp-ai config init -o config.yaml --format yaml
    """
    exporter = ConfigExporter()

    try:
        exporter.save(output, format=format, force=force)
        rprint(f"[green]Configuration written to:[/green] {output}")
        rprint("[dim]Note: Sensitive values use ${ENV_VAR} syntax. Set environment variables or edit the file.[/dim]")
    except FileExistsError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("show")
def config_show(
    format: ConfigShowFormatOption = "toml",
    show_secrets: ConfigShowSecretsOption = False,
) -> None:
    """Display current configuration (stdout).

    Shows merged configuration from:
    1. Config files (3gpp-ai.toml, etc.)
    2. Environment variables (TDC_*)
    3. Hard-coded defaults

    Use --show-secrets to display actual API key values (WARNING: not secure).
    """
    if show_secrets:
        rprint("[yellow]WARNING: Showing sensitive values in plain text![/yellow]\n")

    exporter = ConfigExporter(show_secrets=show_secrets)
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


def _validate_model_format(model: str, field_name: str) -> list[tuple[str, str]]:
    """Validate model format: <provider>/<model> or <provider>/<model>:<tag>."""
    issues: list[tuple[str, str]] = []

    if not model or "/" not in model:
        issues.append(("error", f"{field_name} must be in format <provider>/<model>, got: {model}"))
        return issues

    parts = model.split("/")
    if len(parts) != 2:
        issues.append(("error", f"{field_name} must have exactly one '/', got: {model}"))

    return issues


def _validate_config_values(
    crawler_config: ThreeGPPConfig,
    ai_config: AiConfig,
) -> list[tuple[str, str]]:
    """Validate config values and return list of (severity, message) tuples.

    Validates both crawler and AI configuration settings.
    """
    issues: list[tuple[str, str]] = []

    # ========== Crawler Validation ==========

    # Check cache_dir
    cache_dir = crawler_config.path.cache_dir
    exists, detail = _check_path_exists(cache_dir)
    if not exists:
        issues.append(("error", f"cache_dir does not exist and cannot be created: {cache_dir}{detail}"))
    elif detail:
        issues.append(("warning", f"cache_dir will be created: {cache_dir}"))

    # Check timeout range
    if crawler_config.http.timeout < 1:
        issues.append(("error", f"http.timeout must be >= 1, got {crawler_config.http.timeout}"))

    # Check max_retries range
    if crawler_config.http.max_retries < 0:
        issues.append(("error", f"http.max_retries must be >= 0, got {crawler_config.http.max_retries}"))

    # Check cache_ttl range
    if crawler_config.http.cache_ttl < 0:
        issues.append(("error", f"http.cache_ttl must be >= 0, got {crawler_config.http.cache_ttl}"))

    # Check workers range
    if crawler_config.crawl.workers < 1 or crawler_config.crawl.workers > 32:
        issues.append(("error", f"crawl.workers must be 1-32, got {crawler_config.crawl.workers}"))

    # Check limit range
    if crawler_config.crawl.limit < 1:
        issues.append(("error", f"crawl.limit must be >= 1, got {crawler_config.crawl.limit}"))

    # Warnings for missing optional credentials
    if not crawler_config.credentials.has_credentials:
        issues.append(("warning", "credentials not set (username/password); some features may require authentication"))

    # Warnings for missing optional filters
    if crawler_config.crawl.working_group is None:
        issues.append(("warning", "crawl.working_group not set (no filter applied)"))

    # ========== AI Validation ==========

    # Validate LLM model format
    llm_model = ai_config.llm.model
    issues.extend(_validate_model_format(llm_model, "llm.model"))

    # Warnings for API keys
    if ai_config.llm.api_key is None and "/" in llm_model:
        provider = llm_model.split("/")[0]
        if provider not in ("ollama", "localhost"):
            issues.append(("warning", f"llm.api_key not set for cloud provider '{provider}'"))

    return issues


def _validate_from_file(file: Path) -> tuple[ThreeGPPConfig, AiConfig]:
    """Load configs from a specific file with validation.

    Note: Currently only validates syntax. Full validation happens in config_validate.
    """
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

    # Return default configs (will be validated with env vars applied)
    combined = ThreeGPPConfig.from_settings(config_file=file)
    return combined, combined.ai


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


@config_app.command("validate")
def config_validate(
    file: ConfigValidateFileOption = None,
    strict: ConfigValidateStrictOption = False,
) -> None:
    """Validate configuration files.

    Validates both crawler and AI settings:
    - Crawler: paths, HTTP settings, credentials, crawl limits
    - AI: LLM model format and runtime extraction controls

    Exit codes:
    - 0: All valid
    - 1: Syntax error
    - 2: Validation error (bad values)
    - 3: Warnings only (ok to proceed, or --strict treats warnings as errors)
    """
    if file:
        crawler_config, ai_config = _validate_from_file(file)
    else:
        try:
            combined = ThreeGPPConfig.from_settings()
            crawler_config = combined
            ai_config = combined.ai
        except ValidationError as e:
            rprint("[red]Validation error in discovered config:[/red]")
            for error in e.errors():
                rprint(f"  {error['loc']}: {error['msg']}")
            raise typer.Exit(2)
        except Exception as e:
            rprint(f"[red]Error loading config:[/red] {e}")
            raise typer.Exit(1)

    issues = _validate_config_values(crawler_config, ai_config)
    _display_validation_results(issues, strict)


@config_app.command("docs")
def config_docs(
    section: ConfigDocsSectionOption = None,
) -> None:
    """Show configuration documentation.

    Shows all sections or a specific section if --section is provided.
    Each section shows field names, types, defaults, and descriptions.

    Sections:
    - path: File system paths
    - http: HTTP client and caching
    - credentials: Portal authentication
    - crawl: Crawling filters and limits
    - llm: LLM model and API settings
    - extraction: Document extraction toggles
    - runtime: Processing behavior and limits
    """
    # Build documentation data
    sections: dict[str, list[dict]] = {
        "path": [],
        "http": [],
        "credentials": [],
        "crawl": [],
        "llm": [],
        "extraction": [],
        "runtime": [],
    }

    # Introspect crawler config
    crawler_config = ThreeGPPConfig()
    crawler_data = crawler_config.model_dump()

    for section_name, section_model in [
        ("path", crawler_config.path),
        ("http", crawler_config.http),
        ("credentials", crawler_config.credentials),
        ("crawl", crawler_config.crawl),
    ]:
        model_cls = type(section_model)
        fields = model_cls.model_fields

        for field_name, field_info in fields.items():
            description = field_info.description or ""
            default = field_info.default
            if callable(default):
                default = None

            value = crawler_data.get(section_name, {}).get(field_name)

            sections[section_name].append(
                {
                    "field": field_name,
                    "type": field_info.annotation.__name__ if hasattr(field_info.annotation, "__name__") else str(field_info.annotation),
                    "default": default,
                    "value": value,
                    "description": description,
                }
            )

    # Introspect AI config
    ai_config = AiConfig()
    ai_data = ai_config.model_dump()

    # LLM
    for field_name in ("llm_model", "llm_api_base", "llm_api_key"):
        field_info = type(ai_config).model_fields[field_name]
        description = field_info.description or ""
        default = field_info.default
        value = ai_data.get(field_name)

        sections["llm"].append(
            {
                "field": field_name,
                "type": field_info.annotation.__name__ if hasattr(field_info.annotation, "__name__") else str(field_info.annotation),
                "default": default,
                "value": value,
                "description": description,
            }
        )

    # Extraction toggles
    for field_name in ("extract_tables", "extract_figures", "extract_equations", "figure_description_enabled"):
        field_info = type(ai_config).model_fields[field_name]
        description = field_info.description or ""
        default = field_info.default
        value = ai_data.get(field_name)

        sections["extraction"].append(
            {
                "field": field_name,
                "type": field_info.annotation.__name__ if hasattr(field_info.annotation, "__name__") else str(field_info.annotation),
                "default": default,
                "value": value,
                "description": description,
            }
        )

    # Runtime behavior
    for field_name in (
        "convert_pdf",
        "convert_md",
        "vlm",
        "device",
        "num_threads",
        "batch_size",
        "parallelism",
        "max_chunk_size",
        "chunk_overlap",
        "abstract_min_words",
        "abstract_max_words",
    ):
        field_info = type(ai_config).model_fields[field_name]
        description = field_info.description or ""
        default = field_info.default
        value = ai_data.get(field_name)

        sections["runtime"].append(
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

        _print_section_docs(section_lower, sections[section_lower], _get_section_description(section_lower))
    else:
        # Show all sections
        for section_name, fields_list in sections.items():
            _print_section_docs(section_name, fields_list, _get_section_description(section_name))
            if section_name != "runtime":
                rprint()


def _get_section_description(section: str) -> str:
    """Get description for a configuration section."""
    descriptions = {
        "path": "File system paths for cache, database, and documents",
        "http": "HTTP client and caching configuration",
        "credentials": "ETSI Online (EOL) portal authentication credentials",
        "crawl": "Crawling behavior, filters, and limits",
        "llm": "LLM model and API configuration",
        "extraction": "Document element extraction toggles (tables, figures, equations)",
        "runtime": "Runtime conversion, VLM, threading, and chunking behavior",
    }
    return descriptions.get(section, "")


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
