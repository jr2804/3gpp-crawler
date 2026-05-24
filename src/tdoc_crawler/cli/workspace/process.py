"""Workspace process command and helpers."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
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
    RemoteFallbackOption,
    SkipExistingOption,
    SpreadsheetModeOption,
    TablesModeOption,
    VerbosityOption,
    WorkspaceProcessForceOption,
)
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.config.workspace_registry import WorkspaceMember
from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.oxyde_models import Specification, TDocMetadata
from tdoc_crawler.extraction.convert import ConversionError, DoclingConfig, convert_for_wiki
from tdoc_crawler.extraction.profiles import DEFAULT_EXTRACTION_PROFILE, DeviceType, ExtractionProfile, FiguresMode, SpreadsheetMode, TablesMode
from tdoc_crawler.logging import DEFAULT_LEVEL as DEFAULT_VERBOSITY
from tdoc_crawler.logging import get_logger, set_verbosity
from tdoc_crawler.models.workspaces import SourceKind
from tdoc_crawler.utils.async_helpers import run_async
from tdoc_crawler.utils.normalization import normalize_spec_number, normalize_tdoc_id
from tdoc_crawler.workspaces import (
    get_active_workspace,
    get_workspace,
    list_workspace_members,
    normalize_workspace_name,
)
from tdoc_crawler.workspaces.utils import resolve_spec_release_from_db

# Fields from DB models to include in YAML frontmatter.
_TDOC_FRONTMATTER_FIELDS = (
    "tdoc_id",
    "meeting_id",
    "title",
    "source",
    "contact",
    "tdoc_type",
    "for_purpose",
    "agenda_item_nbr",
    "agenda_item_text",
    "status",
    "date_created",
)
_SPEC_FRONTMATTER_FIELDS = (
    "spec_number",
    "title",
    "spec_type",
    "status",
    "working_group",
    "series",
    "latest_version",
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


def _resolve_spec_source_id(source_id: str) -> str:
    """For spec members without -REL suffix, resolve the full ID."""
    if "-REL" in source_id.upper():
        return source_id
    try:
        resolved, _ = run_async(resolve_spec_release_from_db(source_id, "latest", auto_crawl=True))
        # Only use resolved version if it's an actual version, not "latest"
        if resolved and resolved.lower() != "latest" and resolved[0].isdigit():
            return f"{source_id}-REL{resolved}"
    except Exception:
        logger.debug("Could not resolve release for spec %s", source_id)
    return source_id


def _fetch_db_metadata(document_id: str, source_kind: SourceKind) -> dict[str, object]:
    """Fetch relevant DB metadata fields for a document.

    Returns an empty dict when the DB is unavailable or the record is not found.
    """
    try:
        if source_kind == SourceKind.TDOC:
            raw = _fetch_tdoc_metadata(document_id)
        elif source_kind == SourceKind.SPEC:
            raw = _fetch_spec_metadata(document_id)
        else:
            return {}
        return _sanitize_metadata(raw)
    except Exception:
        logger.debug("Could not fetch DB metadata for %s", document_id, exc_info=True)
    return {}


def _sanitize_metadata(data: dict[str, object]) -> dict[str, object]:
    """Convert complex types to YAML-safe primitives."""
    result: dict[str, object] = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = str(v)
    return result


def _fetch_tdoc_metadata(tdoc_id: str) -> dict[str, object]:
    """Fetch TDoc metadata from the database."""
    normalized = normalize_tdoc_id(tdoc_id)
    db_path = PathConfig().db_file

    async def _query() -> dict[str, object]:
        async with DocDatabase(db_path):
            record = await TDocMetadata.objects.filter(tdoc_id=normalized).first()
        if record is None:
            return {}
        raw = record.model_dump(mode="python")
        return {k: v for k, v in raw.items() if k in _TDOC_FRONTMATTER_FIELDS}

    return run_async(_query())


def _fetch_spec_metadata(source_id: str) -> dict[str, object]:
    """Fetch spec metadata from the database."""
    # Strip -REL suffix to get the bare spec number
    match = re.match(r"^(\d+(?:\.\d+)?)(?:-REL(.+))?$", source_id)
    spec_number = normalize_spec_number(match.group(1)) if match else normalize_spec_number(source_id)
    db_path = PathConfig().db_file

    async def _query() -> dict[str, object]:
        async with DocDatabase(db_path):
            record = await Specification.objects.filter(spec_number=spec_number).first()
        if record is None:
            return {}
        raw = record.model_dump(mode="python")
        return {k: v for k, v in raw.items() if k in _SPEC_FRONTMATTER_FIELDS}

    return run_async(_query())


def _effective_source_id(member: WorkspaceMember) -> str:
    """Return the effective source ID for directory naming.

    For specs without a release suffix, resolves to SPEC-REL<version>.
    For TDocs and other kinds, returns the original ID.
    """
    if member.source_kind == SourceKind.SPEC:
        return _resolve_spec_source_id(member.source_item_id)
    return member.source_item_id


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
    remote_fallback: bool = True,
    spreadsheet_mode: SpreadsheetMode = SpreadsheetMode.DATA,
) -> tuple[str, bool, bool, int]:
    """Process a single workspace member.

    Returns:
        Tuple of ``(source_id, succeeded, failed, page_count)``.
    """
    source_id = _effective_source_id(member)
    wiki_source_dir = wiki_source_dir_base / source_id
    wiki_source_dir.mkdir(parents=True, exist_ok=True)

    # Fetch DB metadata for YAML frontmatter enrichment
    db_metadata = _fetch_db_metadata(source_id, member.source_kind)

    try:
        result_path = convert_for_wiki(
            document_id=source_id,
            wiki_source_dir=wiki_source_dir,
            source_kind=member.source_kind,
            source_path=member.source_path,
            profile=extraction_profile,
            force=force,
            docling_config=docling_config,
            docx_direct=docx_direct,
            md_yaml_frontmatter=md_yaml_frontmatter,
            db_metadata=db_metadata,
            remote_fallback=remote_fallback,
            spreadsheet_mode=spreadsheet_mode,
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


def _run_processing_loop(
    members: list[WorkspaceMember],
    wiki_source_dir_base: Path,
    extraction_profile: ExtractionProfile,
    force: bool,
    skip_existing: bool,
    md_yaml_frontmatter: bool,
    docling_config: DoclingConfig,
    docx_direct: bool,
    remote_fallback: bool,
    spreadsheet_mode: SpreadsheetMode = SpreadsheetMode.DATA,
) -> tuple[int, int, int, int]:
    """Run the processing loop over workspace members.

    Returns:
        Tuple of ``(processed, failed, skipped, total_pages)``.
    """
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
            source_id = _effective_source_id(member)

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
                remote_fallback,
                spreadsheet_mode,
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

    return processed, failed, skipped, total_pages


def workspace_process(
    workspace_name: str = typer.Argument(None, help="Workspace name (default: active workspace)"),
    force: WorkspaceProcessForceOption = False,
    limit: ProcessLimitOption = None,
    skip_existing: SkipExistingOption = True,
    profile: ProfileOption = DEFAULT_EXTRACTION_PROFILE,
    figures: FiguresModeOption = FiguresMode.EMBED,
    tables: TablesModeOption = TablesMode.EMBED,
    spreadsheet_mode: SpreadsheetModeOption = SpreadsheetMode.DATA,
    device: DeviceOption = DeviceType.AUTO,
    docx_direct: DocxDirectOption = False,
    remote_fallback: RemoteFallbackOption = True,
    md_yaml_frontmatter: MdYamlFrontmatterOption = True,
    verbosity: VerbosityOption = str(DEFAULT_VERBOSITY),
) -> None:
    """Extract structured data from all workspace members."""
    set_verbosity(verbosity)

    if workspace_name is None:
        workspace_name = get_active_workspace()

    normalized = normalize_workspace_name(workspace_name)
    extraction_profile = profile

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

    processed, failed, skipped, total_pages = _run_processing_loop(
        members,
        wiki_source_dir_base,
        extraction_profile,
        force,
        skip_existing,
        md_yaml_frontmatter,
        docling_config,
        docx_direct,
        remote_fallback,
        spreadsheet_mode,
    )

    summary = f"Processing complete: {processed} succeeded, {failed} failed, {skipped} skipped"
    if total_pages > 0:
        summary += f"  ({total_pages} pages)"
    console.print(f"[yellow]{summary}[/yellow]")
