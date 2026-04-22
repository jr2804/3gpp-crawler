"""Workspace business-logic helpers extracted from CLI commands.

These functions are async/sync bridges and orchestration helpers that keep
CLI command bodies focused on argument parsing and presentation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import OutputFormat, SortOrder
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.date_parser import parse_partial_date

from threegpp_ai import SourceKind
from threegpp_ai.operations.checkout import checkout_single_item as _checkout_single_item_op
from threegpp_ai.operations.classify import pick_main_document
from threegpp_ai.operations.conversion import OFFICE_FORMATS, convert_to_pdf
from threegpp_ai.operations.convert import extract_document_structured_from_tdoc
from threegpp_ai.operations.workspaces import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    ensure_ai_subfolder,
    make_workspace_member,
)

from ._shared import create_progress_bar

_logger = get_logger(__name__)


async def checkout_single_item(
    *,
    item: str,
    workspace: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
    path_config: PathConfig,
) -> tuple[Any | None, str | None]:
    """Checkout a single workspace item and return a member record.

    Delegates to :func:`threegpp_ai.operations.checkout.checkout_single_item`.
    """
    return await _checkout_single_item_op(
        item=item,
        workspace=workspace,
        source_kind=source_kind,
        checkout=checkout,
        release=release,
        path_config=path_config,
    )


def resolve_process_file(path: Path) -> Path | None:
    """Resolve the actual document file from a path or directory.

    Uses heuristic classification (filename patterns + file size scoring)
    to pick the best document when multiple files exist in a directory.

    Args:
        path: Path to a file or directory containing documents.

    Returns:
        Path to the document file, or None if not found.
    """
    if path.is_file():
        return path
    if not path.is_dir():
        return None

    main_file = pick_main_document(path)
    if main_file is not None:
        return main_file

    for extension in (".pdf", ".docx", ".doc", ".md", ".txt"):
        matches = list(path.rglob(f"*{extension}"))
        if matches:
            _logger.debug("Found document file in subdirectory: %s", matches[0])
            return matches[0]

    _logger.warning("No document file found in: %s", path)
    return None


def convert_member_to_pdf(member: Any) -> Path | None:
    """Convert a workspace member's document to PDF if it's an office format.

    Args:
        member: WorkspaceMember with source_path to the document.

    Returns:
        Path to converted PDF in .ai subfolder, or None if conversion not needed/failed.
    """
    source_path = Path(member.source_path)
    doc_file = resolve_process_file(source_path)
    if doc_file is None:
        _logger.debug("No document file found for %s", member.source_item_id)
        return None

    if doc_file.suffix.lower() not in OFFICE_FORMATS:
        _logger.debug("Document %s is not an office format, skipping PDF conversion", doc_file.name)
        return None

    ai_dir = ensure_ai_subfolder(doc_file.parent)
    existing_pdf = ai_dir / f"{doc_file.stem}.pdf"
    if existing_pdf.exists():
        _logger.debug("PDF already exists for %s at %s", doc_file.name, existing_pdf)
        return existing_pdf

    try:
        return convert_to_pdf(doc_file)
    except Exception as e:
        _logger.error("PDF conversion failed for %s: %s", doc_file.name, e)
        return None


async def process_workspace_members(
    workspace: str,
    members: list[Any],
    *,
    on_progress: Callable[[int, str], None] | None = None,
    checkout: bool = True,
    convert_md: bool = False,
    skip_existing: bool = False,
) -> list[dict[str, Any]]:
    """Process workspace members with optional progress callback.

    Args:
        workspace: Workspace name.
        members: List of workspace members to process.
        on_progress: Optional callback(completed_count, source_item_id) called after each member.
        checkout: Whether to checkout documents if not available.
        convert_md: Whether to extract markdown (implies PDF conversion).
        skip_existing: If True, skip extraction for components that already exist.

    Returns:
        List of processing results.
    """
    results: list[dict[str, Any]] = []
    path_config = PathConfig()

    for member in members:
        file_path = resolve_process_file(Path(member.source_path))

        if (file_path is None or not file_path.exists()) and checkout and member.source_kind in (SourceKind.TDOC, SourceKind.SPEC):
            checkout_path: Path | None = None
            if member.source_kind == SourceKind.TDOC:
                checkout_path = await checkout_tdoc_to_workspace(
                    member.source_item_id,
                    path_config.checkout_dir,
                    workspace,
                    db_file=path_config.db_file,
                )
            elif member.source_kind == SourceKind.SPEC:
                checkout_path = await checkout_spec_to_workspace(
                    member.source_item_id,
                    path_config.checkout_dir,
                    workspace,
                    "latest",
                    db_file=path_config.db_file,
                )
            if checkout_path is not None:
                file_path = resolve_process_file(checkout_path)

        if file_path is None or not file_path.exists():
            results.append({
                "source_item_id": member.source_item_id,
                "status": "skipped",
                "reason": "path or supported file not found",
            })
            if on_progress:
                on_progress(len(results), member.source_item_id)
            continue

        if convert_md:
            doc_file = resolve_process_file(Path(member.source_path))
            if doc_file is not None and doc_file.suffix.lower() in OFFICE_FORMATS:
                pdf_path = convert_member_to_pdf(make_workspace_member(member.source_item_id, member.source_path, member.source_kind))
                if pdf_path is not None:
                    file_path = pdf_path
                elif doc_file.suffix.lower() not in {".pdf", ".txt", ".md"}:
                    results.append({
                        "source_item_id": member.source_item_id,
                        "status": "skipped",
                        "reason": "office document could not be converted to PDF",
                    })
                    if on_progress:
                        on_progress(len(results), member.source_item_id)
                    continue

        try:
            extract_document_structured_from_tdoc(member.source_item_id, force=False)
            results.append({
                "source_item_id": member.source_item_id,
                "file": str(file_path),
                "status": "success",
                "chars_extracted": 0,
                "reason": None,
                "error": None,
            })
        except Exception as exc:
            results.append({
                "source_item_id": member.source_item_id,
                "file": str(file_path),
                "status": "error",
                "chars_extracted": 0,
                "reason": "extraction_failed",
                "error": str(exc),
            })

        if on_progress:
            on_progress(len(results), member.source_item_id)

    return results


def resolve_workspace_items(
    *,
    items: list[str] | None,
    source_kind: SourceKind,
    start_date: str | None,
    end_date: str | None,
    source: list[str] | None,
    source_ex: list[str] | None,
    title: list[str] | None,
    title_ex: list[str] | None,
    agenda: list[str] | None,
    agenda_ex: list[str] | None,
    limit: int | None,
) -> list[str]:
    """Resolve workspace item IDs from explicit list or database query.

    Args:
        items: Explicit list of item IDs (optional).
        source_kind: Kind of source items.
        start_date: Filter start date string.
        end_date: Filter end date string.
        source: Include source patterns.
        source_ex: Exclude source patterns.
        title: Include title patterns.
        title_ex: Exclude title patterns.
        agenda: Include agenda patterns.
        agenda_ex: Exclude agenda patterns.
        limit: Maximum items to return.

    Returns:
        List of resolved item IDs.

    Raises:
        typer.Exit: If filtering without explicit items is attempted for non-TDOC sources.
    """
    if items is not None:
        return items

    if source_kind != SourceKind.TDOC:
        raise ValueError("Filtering without explicit items is only supported for TDocs")

    manager = PathConfig()
    config = TDocQueryConfig(
        output_format=OutputFormat.TABLE,
        tdoc_ids=None,
        working_groups=None,
        start_date=datetime.combine(parse_partial_date(start_date), datetime.min.time(), tzinfo=UTC) if start_date else None,
        end_date=datetime.combine(parse_partial_date(end_date, is_end=True), datetime.max.time(), tzinfo=UTC) if end_date else None,
        meeting_start_date=None,
        meeting_end_date=None,
        source_pattern=source,
        source_pattern_exclude=source_ex,
        title_pattern=title,
        title_pattern_exclude=title_ex,
        agenda_pattern=agenda,
        agenda_pattern_exclude=agenda_ex,
        limit=limit,
        order=SortOrder.DESC,
    )

    async def _fetch_tdocs() -> list[Any]:
        async with TDocDatabase(manager.db_file) as db:
            return await db.query_tdocs(config)

    rows = asyncio.run(_fetch_tdocs())
    return [row.tdoc_id for row in rows]


async def checkout_items(
    resolved_items: list[str],
    *,
    workspace_name: str,
    source_kind: SourceKind,
    checkout: bool,
    release: str | None,
) -> tuple[list[Any], list[tuple[str, str]]]:
    """Checkout items and return member records for workspace registration.

    Args:
        resolved_items: List of item IDs to checkout.
        workspace_name: Target workspace name.
        source_kind: Source kind enum.
        checkout: Whether to perform checkout.
        release: Optional release specifier.

    Returns:
        Tuple of (members, skipped_items).
    """
    manager = PathConfig()
    members: list[Any] = []
    skipped: list[tuple[str, str]] = []

    with create_progress_bar(
        f"[cyan]Checking out {len(resolved_items)} item(s)...",
        total=len(resolved_items),
    ) as progress:
        task = progress.add_task(
            f"[cyan]Checking out {len(resolved_items)} item(s)...",
            total=len(resolved_items),
        )

        async def _process_items() -> None:
            for item in resolved_items:
                member, skip_reason = await checkout_single_item(
                    item=item,
                    workspace=workspace_name,
                    source_kind=source_kind,
                    checkout=checkout,
                    release=release,
                    path_config=manager,
                )
                if skip_reason:
                    skipped.append((item, skip_reason))
                    progress.update(task, advance=1, description=f"[cyan]{item} (skipped)")
                else:
                    members.append(member)
                    progress.update(task, advance=1, description=f"[cyan]{item}")

        await _process_items()

    return members, skipped
