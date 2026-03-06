"""Pipeline orchestration for AI document processing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tdoc_ai.config import AiConfig
from tdoc_ai.models import (
    DocumentClassification,
    PipelineStage,
    ProcessingStatus,
)
from tdoc_ai.operations.classify import classify_document_files
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.extract import extract_from_folder
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.operations.workspaces import list_workspace_members
from tdoc_ai.storage import AiStorage
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)


def run_pipeline(  # noqa: PLR0915
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
    force_rerun: bool = False,
    workspace: str | None = None,
    config: AiConfig | None = None,
) -> ProcessingStatus:
    """Run the complete AI processing pipeline for a TDoc.

    Pipeline stages:
    1. CLASSIFY - Identify main document among multiple files
    2. EXTRACT - Convert DOCX to Markdown
    3. EMBED - Generate vector embeddings (local, no LLM required)
    4. GRAPH - Build knowledge graph (placeholder)

    Note: Summarization is NOT part of the pipeline. Use "ai summarize <doc>"
    command for on-demand LLM-based summarization.

    Args:
        document_id: Document identifier (e.g., "SP-123456").
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
    logger.info(f"Starting pipeline for {document_id}")
    normalized_workspace = normalize_workspace_name(workspace)

    # Get or create processing status
    try:
        status = storage.get_status(document_id, workspace=normalized_workspace)
        if status is None:
            status = ProcessingStatus(document_id=document_id)
    except Exception:
        status = ProcessingStatus(document_id=document_id)

    if not force_rerun and status.current_stage == PipelineStage.COMPLETED:
        logger.info(f"Skipping {document_id} - already completed")
        return status

    # Stage 1: CLASSIFY
    try:
        if not force_rerun and status.classified_at:
            logger.info(f"Skipping classification for {document_id} - already classified")
        else:
            _run_classify_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.CLASSIFYING, document_id)
    except Exception as e:
        logger.error(f"Classification failed for {document_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 2: EXTRACT
    try:
        if not force_rerun and status.extracted_at:
            logger.info(f"Skipping extraction for {document_id} - already extracted")
        else:
            _run_extract_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)
            if progress_callback:
                progress_callback(PipelineStage.EXTRACTING, document_id)
    except Exception as e:
        logger.error(f"Extraction failed for {document_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 3: EMBED
    try:
        if not force_rerun and status.embedded_at:
            logger.info(f"Skipping embedding for {document_id} - already embedded")
        else:
            _run_embedding_stage(
                document_id,
                folder_path,
                storage,
                status,
                workspace=normalized_workspace,
                config=config,
            )
            if progress_callback:
                progress_callback(PipelineStage.EMBEDDING, document_id)
    except Exception as e:
        logger.error(f"Embedding failed for {document_id}: {e}")
        status.error_message = str(e)
        status.current_stage = PipelineStage.FAILED
        storage.save_status(status, workspace=normalized_workspace)
        raise

    # Stage 4: GRAPH (placeholder for now)
    if not force_rerun and status.graphed_at is not None:
        logger.info(f"Skipping graphing for {document_id} - already completed")
    else:
        status.current_stage = PipelineStage.GRAPHING
        status.error_message = None
        status.graphed_at = utc_now()
        storage.save_status(status, workspace=normalized_workspace)
        if progress_callback:
            progress_callback(PipelineStage.GRAPHING, document_id)

    # Mark complete
    status.current_stage = PipelineStage.COMPLETED
    status.completed_at = utc_now()
    storage.save_status(status, workspace=normalized_workspace)

    logger.info(f"Pipeline completed for {document_id}")
    return status


def _run_classify_stage(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> DocumentClassification:
    """Run classification stage.

    Args:
        document_id: Document identifier.
        folder_path: Path to TDoc folder.
        storage: AiStorage instance.
        status: ProcessingStatus to update.
        workspace: Workspace name.

    Returns:
        DocumentClassification for the main document.
    """
    logger.info(f"Classifying files for {document_id}")
    classifications = classify_document_files(document_id, folder_path)

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

    logger.info(f"Classified {document_id}: main={main.file_path} confidence={main.confidence}")
    return main


def _run_extract_stage(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> str:
    """Run extraction stage.

    Args:
        document_id: Document identifier.
        folder_path: Path to TDoc folder.
        storage: AiStorage instance.
        status: ProcessingStatus to update.
        workspace: Workspace name.

    Returns:
        Extracted Markdown content.
    """
    logger.info(f"Extracting content for {document_id}")

    status.current_stage = PipelineStage.EXTRACTING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    main_classification = storage.get_main_classification(document_id, workspace=workspace)
    main_doc_path: Path | None = None
    if main_classification is not None:
        file_path = getattr(main_classification, "file_path", None)
        if isinstance(file_path, str) and file_path.strip():
            candidate_path = folder_path / file_path
            if candidate_path.exists():
                main_doc_path = candidate_path

    # Extract
    markdown = extract_from_folder(document_id, folder_path, storage, main_doc_path, workspace=workspace)

    # Update status
    status.extracted_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    logger.info(f"Extracted {document_id}: {len(markdown)} characters")
    return markdown


def _run_embedding_stage(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
    config: AiConfig | None = None,
) -> None:
    """Run embedding stage based on extracted markdown artifact."""
    status.current_stage = PipelineStage.EMBEDDING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    artifact_path = folder_path / ".ai" / f"{document_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"Extracted markdown artifact not found for embedding: {artifact_path}"
        raise FileNotFoundError(msg)

    # Get embeddings manager from config
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager.from_config(config)
    embeddings_manager.generate_embeddings(document_id, artifact_path, workspace=workspace)

    status.embedded_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)


def process_tdoc(
    document_id: str,
    checkout_path: Path,
    force_rerun: bool = False,
    workspace: str | None = None,
    config: AiConfig | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline.

    Public API function that initializes storage and runs the pipeline.

    Args:
        document_id: Document identifier (e.g., "SP-123456").
        checkout_path: Path to the TDoc checkout folder.
        force_rerun: If True, skip resume logic and run all stages.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        ProcessingStatus with final pipeline state.

    Raises:
        Exception: Re-raises pipeline exceptions after logging.
    """
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager.from_config(config)
    storage = embeddings_manager.storage
    return run_pipeline(
        document_id,
        checkout_path,
        storage,
        force_rerun=force_rerun,
        workspace=workspace,
        config=config,
    )


def process_all(
    document_ids: list[str],
    checkout_base: Path,
    new_only: bool = False,
    force_rerun: bool = False,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
    workspace: str | None = None,
    config: AiConfig | None = None,
) -> dict[str, ProcessingStatus]:
    """Process multiple TDocs through the AI pipeline.

    Args:
        document_ids: List of Document identifiers.
        checkout_base: Base path containing TDoc checkout folders.
        new_only: If True, process only TDocs not already completed.
        force_rerun: If True, skip resume logic and run all stages.
        progress_callback: Optional callback called after each stage.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Dict mapping document_id to ProcessingStatus.
    """
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager.from_config(config)
    storage = embeddings_manager.storage
    normalized_workspace = normalize_workspace_name(workspace)

    # Get workspace members and build a lookup map
    members_map: dict[str, Any] = {}
    if normalized_workspace != "default":
        members = list_workspace_members(normalized_workspace)
        member_ids = {m.source_item_id for m in members if m.is_active and m.source_kind == "tdoc"}
        members_map = {m.source_item_id: m for m in members if m.is_active and m.source_kind == "tdoc"}
        document_ids = [tid for tid in document_ids if tid in member_ids]
    results: dict[str, ProcessingStatus] = {}
    for document_id in document_ids:
        if new_only and not force_rerun:
            existing_status = storage.get_status(document_id, workspace=normalized_workspace)
            if existing_status and existing_status.current_stage == PipelineStage.COMPLETED:
                logger.info(f"Skipping {document_id} in new_only mode - already completed")
                continue

        # Use source_path from workspace member if available, otherwise fallback to default
        member = members_map.get(document_id)
        folder_path = Path(member.source_path) if member and member.source_path and Path(member.source_path).exists() else checkout_base / document_id

        if not folder_path.exists():
            logger.warning(f"Checkout folder not found: {folder_path}")
            continue
        try:
            status = run_pipeline(
                document_id,
                folder_path,
                storage,
                progress_callback=progress_callback,
                force_rerun=force_rerun,
                workspace=normalized_workspace,
                config=config,
            )
            results[document_id] = status
        except Exception as e:
            logger.error(f"Pipeline failed for {document_id}: {e}")
            # Continue with other TDocs - don't block batch processing

    return results


def get_status(document_id: str | None = None, workspace: str | None = None) -> ProcessingStatus | list[ProcessingStatus] | None:
    """Get processing status for a TDoc or all TDocs in workspace.

    Args:
        document_id: Document identifier. If None, returns all statuses in workspace.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        ProcessingStatus if document_id provided and found,
        list of ProcessingStatus if document_id is None,
        None if document_id provided but not found.
    """
    config = AiConfig.from_env()
    storage = EmbeddingsManager.from_config(config).storage
    normalized_workspace = normalize_workspace_name(workspace)

    if document_id is None:
        # Return all statuses in workspace
        return storage.list_statuses(normalized_workspace)

    return storage.get_status(document_id, workspace=normalized_workspace)


__all__ = [
    "get_status",
    "process_all",
    "process_tdoc",
    "run_pipeline",
]
