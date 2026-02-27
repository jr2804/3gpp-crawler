"""Pipeline orchestration for AI document processing."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import (
    DocumentClassification,
    DocumentSummary,
    LlmConfigError,
    PipelineStage,
    ProcessingStatus,
)
from tdoc_crawler.ai.operations.classify import classify_tdoc_files
from tdoc_crawler.ai.operations.embeddings import generate_embeddings
from tdoc_crawler.ai.operations.extract import extract_from_folder
from tdoc_crawler.ai.operations.summarize import summarize_document
from tdoc_crawler.ai.operations.workspaces import normalize_workspace_name
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)


def run_pipeline(  # noqa: PLR0915
    tdoc_id: str,
    folder_path: Path,
    storage: AiStorage,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
    force_rerun: bool = False,
    workspace: str | None = None,
) -> ProcessingStatus:
    """Run the complete AI processing pipeline for a TDoc.

    Pipeline stages:
    1. CLASSIFY - Identify main document among multiple files
    2. EXTRACT - Convert DOCX to Markdown
    3. EMBED - Generate embeddings (placeholder)
    4. SUMMARIZE - Generate summary (placeholder)
    5. GRAPH - Build knowledge graph (placeholder)

    Args:
        tdoc_id: TDoc identifier (e.g., "SP-123456").
        folder_path: Path to the TDoc checkout folder.
        storage: AiStorage instance for status tracking.
        progress_callback: Optional callback called after each stage.
        force_rerun: If True, skip resume logic and run all stages.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Updated ProcessingStatus with stage timestamps.

    Raises:
        Exception: Per-TDoc errors are isolated and re-raised after logging.
    """
    logger.info(f"Starting pipeline for {tdoc_id}")
    normalized_workspace = normalize_workspace_name(workspace)

    # Get or create processing status
    try:
        status = storage.get_status(tdoc_id, workspace=normalized_workspace)
        if status is None:
            status = ProcessingStatus(tdoc_id=tdoc_id)
    except Exception:
        status = ProcessingStatus(tdoc_id=tdoc_id)

    if not force_rerun and status.current_stage == PipelineStage.COMPLETED:
        logger.info(f"Skipping {tdoc_id} - already completed")
        return status

    # Stage 1: CLASSIFY
    try:
        if not force_rerun and status.classified_at:
            logger.info(f"Skipping classification for {tdoc_id} - already classified")
        else:
            _run_classify_stage(tdoc_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.CLASSIFYING, tdoc_id)
    except Exception as e:
        logger.error(f"Classification failed for {tdoc_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 2: EXTRACT
    try:
        if not force_rerun and status.extracted_at:
            logger.info(f"Skipping extraction for {tdoc_id} - already extracted")
        else:
            _run_extract_stage(tdoc_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.EXTRACTING, tdoc_id)
    except Exception as e:
        logger.error(f"Extraction failed for {tdoc_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 3: EMBED
    try:
        if not force_rerun and status.embedded_at:
            logger.info(f"Skipping embedding for {tdoc_id} - already embedded")
        else:
            _run_embedding_stage(tdoc_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.EMBEDDING, tdoc_id)
    except Exception as e:
        logger.error(f"Embedding failed for {tdoc_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 4: SUMMARIZE
    try:
        if not force_rerun and status.summarized_at:
            logger.info(f"Skipping summarization for {tdoc_id} - already summarized")
        else:
            _run_summarize_stage(tdoc_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.SUMMARIZING, tdoc_id)
    except Exception as e:
        logger.error(f"Summarization failed for {tdoc_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 5: GRAPH (placeholder for now)
    if not force_rerun and status.graphed_at is not None:
        logger.info(f"Skipping graphing for {tdoc_id} - already completed")
    else:
        status.current_stage = PipelineStage.GRAPHING
        status.error_message = None
        status.graphed_at = utc_now()
        storage.save_status(status, workspace=normalized_workspace)
        if progress_callback:
            progress_callback(PipelineStage.GRAPHING, tdoc_id)

    # Mark complete
    status.current_stage = PipelineStage.COMPLETED
    status.completed_at = utc_now()
    storage.save_status(status, workspace=normalized_workspace)

    logger.info(f"Pipeline completed for {tdoc_id}")
    return status


def _run_classify_stage(
    tdoc_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> DocumentClassification:
    """Run classification stage.

    Args:
        tdoc_id: TDoc identifier.
        folder_path: Path to TDoc folder.
        storage: AiStorage instance.
        status: ProcessingStatus to update.
        workspace: Workspace name.

    Returns:
        DocumentClassification for the main document.
    """
    logger.info(f"Classifying files for {tdoc_id}")
    classifications = classify_tdoc_files(tdoc_id, folder_path)

    if not classifications:
        msg = f"No files found in {folder_path}"
        raise ValueError(msg)

    # Find main document
    main = next((c for c in classifications if c.is_main_document), classifications[0])

    storage.save_classifications(classifications, workspace=workspace)

    # Update status
    status.current_stage = PipelineStage.CLASSIFYING
    status.classified_at = utc_now()
    storage.save_status(status, workspace=workspace)

    logger.info(f"Classified {tdoc_id}: main={main.file_path} confidence={main.confidence}")
    return main


def _run_extract_stage(
    tdoc_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> str:
    """Run extraction stage.

    Args:
        tdoc_id: TDoc identifier.
        folder_path: Path to TDoc folder.
        storage: AiStorage instance.
        status: ProcessingStatus to update.
        workspace: Workspace name.

    Returns:
        Extracted Markdown content.
    """
    logger.info(f"Extracting content for {tdoc_id}")

    status.current_stage = PipelineStage.EXTRACTING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    main_classification = storage.get_main_classification(tdoc_id, workspace=workspace)
    main_doc_path: Path | None = None
    if main_classification is not None:
        file_path = getattr(main_classification, "file_path", None)
        if isinstance(file_path, str) and file_path.strip():
            candidate_path = folder_path / file_path
            if candidate_path.exists():
                main_doc_path = candidate_path

    # Extract
    markdown = extract_from_folder(tdoc_id, folder_path, storage, main_doc_path, workspace=workspace)

    # Update status
    status.extracted_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    logger.info(f"Extracted {tdoc_id}: {len(markdown)} characters")
    return markdown


def _run_embedding_stage(
    tdoc_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> None:
    """Run embedding stage based on extracted markdown artifact."""
    status.current_stage = PipelineStage.EMBEDDING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    artifact_path = folder_path / ".ai" / f"{tdoc_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"Extracted markdown artifact not found for embedding: {artifact_path}"
        raise FileNotFoundError(msg)

    generate_embeddings(tdoc_id, artifact_path, storage=storage, workspace=workspace)

    status.embedded_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)


def _run_summarize_stage(
    tdoc_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> None:
    """Run summarization stage from extracted markdown artifact."""
    status.current_stage = PipelineStage.SUMMARIZING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    artifact_path = folder_path / ".ai" / f"{tdoc_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"Extracted markdown artifact not found for summarization: {artifact_path}"
        raise FileNotFoundError(msg)

    markdown = artifact_path.read_text(encoding="utf-8")
    try:
        summarize_document(tdoc_id, markdown, storage=storage, workspace=workspace)
    except LlmConfigError as exc:
        logger.warning(f"Falling back to extractive summary for {tdoc_id}: {exc}")
        words = markdown.split()
        abstract = " ".join(words[:220]).strip() or markdown[:1000]
        key_points = [line.strip(" -\t") for line in markdown.splitlines() if line.strip() and not line.lstrip().startswith("#")][:5]
        affected_specs = sorted(set(re.findall(r"(?:TS|TR)\s*\d{2}\.\d{3,4}", markdown)))
        storage.save_summary(
            DocumentSummary(
                tdoc_id=tdoc_id,
                abstract=abstract,
                key_points=key_points,
                action_items=[],
                decisions=[],
                affected_specs=affected_specs,
                llm_model="fallback/extractive",
                prompt_version="fallback-v1",
            ),
            workspace=workspace,
        )

    status.summarized_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)


def process_tdoc(
    tdoc_id: str,
    checkout_path: Path,
    force_rerun: bool = False,
    workspace: str | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline.

    Public API function that initializes storage and runs the pipeline.

    Args:
        tdoc_id: TDoc identifier (e.g., "SP-123456").
        checkout_path: Path to the TDoc checkout folder.
        force_rerun: If True, skip resume logic and run all stages.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        ProcessingStatus with final pipeline state.

    Raises:
        Exception: Re-raises pipeline exceptions after logging.
    """
    from tdoc_crawler.ai.operations.embeddings import get_embedding_model

    config = AiConfig.from_env(cache_manager_name="default")
    model = get_embedding_model()
    storage = AiStorage(config.ai_store_path, embedding_dimension=model.dimension)
    return run_pipeline(
        tdoc_id,
        checkout_path,
        storage,
        force_rerun=force_rerun,
        workspace=workspace,
    )


def process_all(
    tdoc_ids: list[str],
    checkout_base: Path,
    new_only: bool = False,
    force_rerun: bool = False,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
    workspace: str | None = None,
) -> dict[str, ProcessingStatus]:
    """Process multiple TDocs through the AI pipeline.

    Args:
        tdoc_ids: List of TDoc identifiers.
        checkout_base: Base path containing TDoc checkout folders.
        new_only: If True, process only TDocs not already completed.
        force_rerun: If True, skip resume logic and run all stages.
        progress_callback: Optional callback called after each stage.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Dict mapping tdoc_id to ProcessingStatus.
    """
    from tdoc_crawler.ai.operations.embeddings import get_embedding_model

    config = AiConfig.from_env(cache_manager_name="default")
    model = get_embedding_model()
    storage = AiStorage(config.ai_store_path, embedding_dimension=model.dimension)
    normalized_workspace = normalize_workspace_name(workspace)

    # Get workspace members and build a lookup map
    members_map: dict[str, Any] = {}
    if normalized_workspace != "default":
        members = storage.list_workspace_members(normalized_workspace)
        member_ids = {m.source_item_id for m in members if m.is_active and m.source_kind == "tdoc"}
        members_map = {m.source_item_id: m for m in members if m.is_active and m.source_kind == "tdoc"}
        tdoc_ids = [tid for tid in tdoc_ids if tid in member_ids]
    results: dict[str, ProcessingStatus] = {}
    for tdoc_id in tdoc_ids:
        if new_only and not force_rerun:
            existing_status = storage.get_status(tdoc_id, workspace=normalized_workspace)
            if existing_status and existing_status.current_stage == PipelineStage.COMPLETED:
                logger.info(f"Skipping {tdoc_id} in new_only mode - already completed")
                continue

        # Use source_path from workspace member if available, otherwise fallback to default
        member = members_map.get(tdoc_id)
        folder_path = Path(member.source_path) if member and member.source_path and Path(member.source_path).exists() else checkout_base / tdoc_id

        if not folder_path.exists():
            logger.warning(f"Checkout folder not found: {folder_path}")
            continue
        try:
            status = run_pipeline(
                tdoc_id,
                folder_path,
                storage,
                progress_callback=progress_callback,
                force_rerun=force_rerun,
                workspace=normalized_workspace,
            )
            results[tdoc_id] = status
        except Exception as e:
            logger.error(f"Pipeline failed for {tdoc_id}: {e}")
            # Continue with other TDocs - don't block batch processing

    return results


def get_status(tdoc_id: str, workspace: str | None = None) -> ProcessingStatus | None:
    """Get processing status for a TDoc.

    Args:
        tdoc_id: TDoc identifier.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        ProcessingStatus if found, None otherwise.
    """
    from tdoc_crawler.ai.operations.embeddings import get_embedding_model

    config = AiConfig.from_env(cache_manager_name="default")
    model = get_embedding_model()
    storage = AiStorage(config.ai_store_path, embedding_dimension=model.dimension)
    normalized_workspace = normalize_workspace_name(workspace)
    return storage.get_status(tdoc_id, workspace=normalized_workspace)


__all__ = [
    "get_status",
    "process_all",
    "process_tdoc",
    "run_pipeline",
]
