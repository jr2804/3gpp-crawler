"""Workspace process command and helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer

from tdoc_crawler.cli._shared import console, create_progress_bar
from tdoc_crawler.cli.args import (
    DeviceOption,
    DocxDirectOption,
    FiguresModeOption,
    MdYamlFrontmatterOption,
    ProcessLimitOption,
    ProfileOption,
    SkipExistingOption,
    TablesModeOption,
    VerbosityOption,
    WorkspaceProcessForceOption,
)
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.config.workspace_registry import WorkspaceMember
from tdoc_crawler.extraction.convert import ConversionError, DoclingConfig, convert_for_wiki
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, ExtractionProfile
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import get_logger, set_verbosity
from tdoc_crawler.workspaces import (
    get_active_workspace,
    get_workspace,
    list_workspace_members,
    normalize_workspace_name,
)

logger = get_logger(__name__)

_PROFILE_LEVELS = {
    ExtractionProfile.PDF_ONLY: 0,
    ExtractionProfile.MARKDOWN_ONLY: 1,
    ExtractionProfile.DEFAULT: 2,
    ExtractionProfile.ADVANCED: 3,
}


def _read_json_profile(json_path: Path) -> str:
    """Read extraction_profile from a JSON file, empty string on failure."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data.get("extraction_profile", "")
    except (json.JSONDecodeError, OSError):
        return ""


def _coerce_profile(value: str) -> ExtractionProfile | None:
    """Try to parse a string as ExtractionProfile, return None on failure."""
    try:
        return ExtractionProfile(value)
    except ValueError:
        return None


def _should_skip_member(
    source_id: str,
    wiki_base: Path,
    profile: ExtractionProfile,
    force: bool,
    skip_existing: bool,
) -> bool:
    """Check if a workspace member should be skipped due to existing artifacts."""
    if force or not skip_existing:
        return False

    member_dir = wiki_base / source_id

    if profile == ExtractionProfile.PDF_ONLY:
        check_glob, label = "*.pdf", "PDF"
    elif profile == ExtractionProfile.MARKDOWN_ONLY:
        check_glob, label = "*.md", "Markdown"
    else:
        check_glob, label = None, None

    if check_glob is not None:
        if list(member_dir.glob(check_glob)):
            logger.debug("Skipping %s — %s exists", source_id, label)
            return True
        return False

    md_files = list(member_dir.glob("*.md"))
    json_files = list(member_dir.glob("*.json"))
    if not md_files or not json_files:
        return False

    saved_profile = _read_json_profile(json_files[0])
    saved_level = _PROFILE_LEVELS.get(saved_profile, -1)
    if saved_level < 0:
        saved_level = _PROFILE_LEVELS.get(_coerce_profile(saved_profile), -1)

    required_level = _PROFILE_LEVELS[profile]
    if saved_level >= required_level:
        label = saved_profile if saved_level >= 0 else "unknown"
        logger.debug("Skipping %s — %s output exists", source_id, label)
        return True

    return False


def _read_page_count(json_dir: Path) -> int:
    """Read page count from Docling JSON output.

    Returns 0 if the JSON file is not found or cannot be read.
    """
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        return 0
    try:
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        # DoclingDocument stores pages as a list
        pages = data.get("pages", [])
        return len(pages) if isinstance(pages, list) else 0
    except (json.JSONDecodeError, OSError, ValueError):
        return 0


def _process_member(
    member: WorkspaceMember,
    wiki_source_dir_base: Path,
    extraction_profile: ExtractionProfile,
    force: bool,
    md_yaml_frontmatter: bool,
    docling_config: DoclingConfig,
    docx_direct: bool = False,
) -> tuple[str, bool, bool, int]:
    """Process a single workspace member.

    Returns:
        Tuple of ``(source_id, succeeded, failed, page_count)``.
    """
    source_id = member.source_item_id
    wiki_source_dir = wiki_source_dir_base / source_id
    wiki_source_dir.mkdir(parents=True, exist_ok=True)

    try:
        result_path = convert_for_wiki(
            document_id=source_id,
            wiki_source_dir=wiki_source_dir,
            source_kind=member.source_kind,
            profile=extraction_profile,
            force=force,
            docling_config=docling_config,
            docx_direct=docx_direct,
            md_yaml_frontmatter=md_yaml_frontmatter,
        )
        suffix = result_path.suffix.lstrip(".")
        logger.debug("%s [%s] → %s", source_id, extraction_profile.value, suffix)
        return source_id, True, False, _read_page_count(wiki_source_dir)
    except (ConversionError, FileNotFoundError) as e:
        console.print(f"[red]  Failed {source_id}: {e}[/red]")
        logger.error("Failed to process %s: %s", source_id, e)
        return source_id, False, True, 0
    except Exception as e:
        console.print(f"[red]  Failed {source_id}: {e}[/red]")
        logger.error("Failed to process %s: %s", source_id, e)
        return source_id, False, True, 0


def workspace_process(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    force: WorkspaceProcessForceOption = False,
    limit: ProcessLimitOption = None,
    skip_existing: SkipExistingOption = False,
    profile: ProfileOption = DEFAULT_EXTRACTION_PROFILE.value,
    figures: FiguresModeOption = "embed",
    tables: TablesModeOption = "embed",
    device: DeviceOption = "auto",
    docx_direct: DocxDirectOption = False,
    md_yaml_frontmatter: MdYamlFrontmatterOption = True,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Extract structured data from all workspace members."""
    set_verbosity(verbosity)

    if workspace_name is None:
        workspace_name = get_active_workspace()

    normalized = normalize_workspace_name(workspace_name)

    try:
        extraction_profile = ExtractionProfile(profile)
    except ValueError:
        console.print(f"[red]Invalid profile '{profile}'. Use: pdf-only, markdown-only, default, advanced[/red]")
        raise typer.Exit(1)

    # Validate figure/table mode options
    if figures not in ("embed", "reference"):
        console.print(f"[red]Invalid figures mode '{figures}'. Use: embed, reference[/red]")
        raise typer.Exit(1)
    if tables not in ("embed", "csv"):
        console.print(f"[red]Invalid tables mode '{tables}'. Use: embed, csv[/red]")
        raise typer.Exit(1)
    if device not in ("auto", "cpu", "cuda", "mps"):
        console.print(f"[red]Invalid device '{device}'. Use: auto, cpu, cuda, mps[/red]")
        raise typer.Exit(1)

    docling_config = DoclingConfig(figures_mode=figures, tables_mode=tables, device=device)

    console.print(f"[yellow]Processing workspace '{normalized}' with profile '{extraction_profile.value}' (figures={figures}, tables={tables})...[/yellow]")

    try:
        members = list_workspace_members(normalized, include_inactive=False)
    except Exception as e:
        console.print(f"[red]Error listing members: {e}[/red]")
        raise typer.Exit(1)

    if not members:
        console.print(f"[dim]No active members in workspace '{normalized}'.[/dim]")
        return

    if limit is not None:
        members = members[:limit]

    cache_manager = resolve_cache_manager()
    metadata = get_workspace(normalized)
    if metadata is not None:
        wiki_source_dir_base = metadata.resolve_sources_directory(cache_manager.llm_wiki_dir)
    else:
        wiki_source_dir_base = cache_manager.llm_wiki_dir / normalized / "sources"

    processed = 0
    failed = 0
    skipped = 0
    total_pages = 0
    start_time = time.monotonic()

    progress, task = create_progress_bar(
        f"Processing [{extraction_profile.value}]",
        total=len(members),
    )

    with progress:
        for member in members:
            source_id = member.source_item_id

            if _should_skip_member(source_id, wiki_source_dir_base, extraction_profile, force, skip_existing):
                skipped += 1
                progress.advance(task)
                continue

            progress.update(task, description=f"Processing [{extraction_profile.value}] {source_id}")
            _, succeeded, errored, pages = _process_member(
                member,
                wiki_source_dir_base,
                extraction_profile,
                force,
                md_yaml_frontmatter,
                docling_config,
                docx_direct,
            )
            if succeeded:
                processed += 1
                total_pages += pages
            if errored:
                failed += 1

            elapsed = time.monotonic() - start_time
            if elapsed > 0 and total_pages > 0:
                pps = total_pages / elapsed
                progress.update(
                    task,
                    description=f"Processing [{extraction_profile.value}] {source_id}  ({total_pages}p, {pps:.1f} p/s)",
                )
            else:
                progress.update(
                    task,
                    description=f"Processing [{extraction_profile.value}] {source_id}",
                )

            progress.advance(task)

    elapsed_total = time.monotonic() - start_time
    summary = f"Processing complete: {processed} succeeded, {failed} failed, {skipped} skipped"
    if total_pages > 0 and elapsed_total > 0:
        avg_pps = total_pages / elapsed_total
        summary += f"  ({total_pages} pages, {avg_pps:.1f} p/s avg)"
    console.print(f"[yellow]{summary}[/yellow]")
