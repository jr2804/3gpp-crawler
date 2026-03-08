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
    ProcessingFailureType,
    ProcessingStatus,
)
from tdoc_ai.operations.classify import classify_document_files
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.extract import extract_from_folder
from tdoc_ai.operations.graph import build_graph
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.operations.workspaces import (
    checkout_spec_to_workspace,
    checkout_tdoc_to_workspace,
    list_workspace_members,
    resolve_tdoc_checkout_path,
)
from tdoc_ai.storage import AiStorage
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)


def run_pipeline(  # noqa: PLR0915
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    force_rerun: bool = False,
    workspace: str | None = None,
    config: AiConfig | None = None,
) -> ProcessingStatus:
    """Run complete AI processing pipeline for a TDoc.

    Pipeline stages:
    1. CLASSIFY - Identify main document among multiple files
    2. EXTRACT - Convert DOCX to Markdown
    3. EMBED - Generate vector embeddings (local, no LLM required)
    4. GRAPH - Build knowledge graph

    Note: Summarization is NOT part of the pipeline. Use "ai summarize <doc>"
    command for on-demand LLM-based summarization.

    Note: Progress tracking is handled by process_all() at the workspace level,
    not by this function.

    Args:
        document_id: Document identifier (e.g., "SP-123456").
        folder_path: Path to TDoc checkout folder.
        storage: AiStorage instance for status tracking.
        force_rerun: If True, skip resume logic and run all stages.
        workspace: Optional workspace scope (defaults to "default").
        config: Optional AiConfig instance.

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
    if not force_rerun and status.classified_at:
        logger.info(f"Skipping classification for {document_id} - already classified")
    else:
        _run_classify_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

    # Stage 2: EXTRACT
    if not force_rerun and status.extracted_at:
        logger.info(f"Skipping extraction for {document_id} - already extracted")
    else:
        _run_extract_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

    # Stage 3: EMBED
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

    # Stage 4: GRAPH
    if not force_rerun and status.graphed_at is not None:
        logger.info(f"Skipping graphing for {document_id} - already completed")
    else:
        _run_graph_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

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
    embeddings_manager = EmbeddingsManager(config)
    embeddings_manager.generate_embeddings(document_id, artifact_path, workspace=workspace)

    status.embedded_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)


def _run_graph_stage(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str | None = None,
) -> None:
    """Run graph building stage based on extracted markdown artifact."""
    status.current_stage = PipelineStage.GRAPHING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    artifact_path = folder_path / ".ai" / f"{document_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"Extracted markdown artifact not found for graph building: {artifact_path}"
        raise FileNotFoundError(msg)

    markdown = artifact_path.read_text(encoding="utf-8")

    # Extract meeting_id from folder_path
    # Path structure: .../checkout/<TSG>/<WG>/<Meeting>/Docs/<TDoc>
    # Example: .../TSG_SA/WG4_CODEC/TSGS4_131-bis-e/Docs/S4-241373
    meeting_id = None
    path_parts = folder_path.parts
    if "Docs" in path_parts:
        docs_index = path_parts.index("Docs")
        if docs_index >= 3:
            meeting_id = path_parts[docs_index - 1]  # e.g., "TSGS4_131-bis-e"

    nodes, edges = build_graph(document_id, markdown, meeting_id=meeting_id, storage=storage, workspace=workspace)
    storage.save_nodes(nodes, workspace=workspace)
    storage.save_edges(edges, workspace=workspace)

    status.graphed_at = utc_now()
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    logger.info(f"Built graph for {document_id}: {len(nodes)} nodes, {len(edges)} edges")


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
    embeddings_manager = EmbeddingsManager(config)
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
    limit: int | None = None,
) -> dict[str, ProcessingStatus]:
    """Process multiple TDocs through the AI pipeline using three-phase approach.

    Pipeline phases:
    Phase 1: CLASSIFY → EXTRACT (create markdown artifacts for all docs)
    Phase 2: EMBED (create embeddings for all extracted docs)
    Phase 3: GRAPH (build knowledge graph for all embedded docs)

    This phased approach ensures:
    - Failed docs don't propagate to later phases
    - Efficient batch processing
    - Clear separation of concerns

    Args:
        document_ids: List of Document identifiers.
        checkout_base: Base path containing TDoc checkout folders.
        new_only: If True, process only TDocs not already completed.
        force_rerun: If True, skip resume logic and run all stages.
        progress_callback: Optional callback called after each stage.
        workspace: Optional workspace scope (defaults to "default").
        config: Optional AiConfig instance.
        limit: Optional limit on number of documents to process (for testing).

    Returns:
        Dict mapping document_id to ProcessingStatus.
    """
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager(config)
    storage = embeddings_manager.storage
    normalized_workspace = normalize_workspace_name(workspace)

    # Get workspace members and build a lookup map
    members_map: dict[str, Any] = {}
    if normalized_workspace != "default":
        members = list_workspace_members(normalized_workspace)
        # Include both tdocs and specs
        member_ids = {m.source_item_id for m in members if m.is_active and m.source_kind in ("tdoc", "spec")}
        members_map = {m.source_item_id: m for m in members if m.is_active and m.source_kind in ("tdoc", "spec")}
        # If no document_ids provided, use all workspace members
        document_ids = list(member_ids) if not document_ids else [tid for tid in document_ids if tid in member_ids]

    # Apply limit for testing
    if limit is not None and limit > 0:
        document_ids = document_ids[:limit]
        logger.info(f"Limited processing to {limit} documents")
    results: dict[str, ProcessingStatus] = {}

    # =============================================================================
    # PHASE 1: CLASSIFY → EXTRACT (create markdown artifacts for all docs)
    # =============================================================================
    extracted_ids: list[str] = []
    for document_id in document_ids:
        if new_only and not force_rerun:
            existing_status = storage.get_status(document_id, workspace=normalized_workspace)
            if existing_status and existing_status.extracted_at is not None:
                logger.info(f"Skipping {document_id} - already extracted")
                extracted_ids.append(document_id)
                if progress_callback:
                    progress_callback(PipelineStage.EXTRACTING, document_id)
                continue

        member = members_map.get(document_id)
        if not member:
            logger.warning(f"No workspace member found for {document_id}")
            if progress_callback:
                progress_callback(PipelineStage.FAILED, document_id)
            continue

        # Determine folder path using metadata-based resolution
        folder_path = None
        cache_manager = resolve_cache_manager()

        if member.source_kind == "tdoc":
            # First try to resolve from existing checkout structure
            folder_path = resolve_tdoc_checkout_path(document_id, cache_manager.checkout_dir)
            # If not found, perform checkout
            if not folder_path:
                folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, normalized_workspace, db_file=cache_manager.db_file)
        elif member.source_kind == "spec":
            # Extract base spec number and release from source_item_id (e.g., "21905-REL19" -> spec="21905", release="19")
            base_spec = member.source_item_id
            release = "latest"
            if member.source_item_id and "-REL" in member.source_item_id:
                parts = member.source_item_id.split("-REL")
                base_spec = parts[0]
                release = parts[1]
            folder_path = checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, normalized_workspace, release=release)

        if not folder_path or not folder_path.exists():
            logger.warning(f"Checkout folder not found for {document_id}")
            if progress_callback:
                progress_callback(PipelineStage.FAILED, document_id)
            continue

        # Check if folder has actual files (not just empty folder)
        has_files = any(f.is_file() for f in folder_path.iterdir())
        if not has_files:
            logger.warning(f"Checkout folder is empty for {document_id}, attempting re-checkout...")
            # Try to re-checkout with fresh download
            if member.source_kind == "tdoc":
                folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, normalized_workspace, db_file=cache_manager.db_file)
            elif member.source_kind == "spec":
                folder_path = checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, normalized_workspace, release=release)

            # Verify re-checkout worked
            if not folder_path or not folder_path.exists():
                logger.error(f"Re-checkout failed for {document_id}")
                if progress_callback:
                    progress_callback(PipelineStage.FAILED, document_id)
                continue

            # Check again after re-checkout
            has_files = any(f.is_file() for f in folder_path.iterdir())
            if not has_files:
                logger.error(f"Re-checkout produced empty folder for {document_id}")
                if progress_callback:
                    progress_callback(PipelineStage.FAILED, document_id)
                continue

        try:
            # Get or create status for this document
            status = storage.get_status(document_id, workspace=normalized_workspace)
            if status is None:
                status = ProcessingStatus(document_id=document_id)

            # Run CLASSIFY stage
            if not force_rerun and status.classified_at:
                logger.info(f"Skipping classification for {document_id} - already classified")
            else:
                _run_classify_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

            # Run EXTRACT stage
            if not force_rerun and status.extracted_at:
                logger.info(f"Skipping extraction for {document_id} - already extracted")
            else:
                _run_extract_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

            results[document_id] = status
            if status.extracted_at is not None:
                extracted_ids.append(document_id)

        except Exception as e:
            logger.error(f"Phase 1 failed for {document_id}: {e}")
            if progress_callback:
                progress_callback(PipelineStage.FAILED, document_id)

    # =============================================================================
    # PHASE 2: EMBED (create embeddings for all extracted documents)
    # =============================================================================
    embedded_ids: list[str] = []
    if extracted_ids:
        logger.info(f"Starting Phase 2: Embedding {len(extracted_ids)} documents")
        for document_id in extracted_ids:
            member = members_map.get(document_id)
            if not member:
                logger.warning(f"No workspace member found for {document_id} in Phase 2")
                if progress_callback:
                    progress_callback(PipelineStage.FAILED, document_id)
                continue

            # Determine folder path using metadata-based resolution
            folder_path = None
            cache_manager = resolve_cache_manager()

            if member.source_kind == "tdoc":
                folder_path = resolve_tdoc_checkout_path(document_id, cache_manager.checkout_dir)
                if not folder_path:
                    folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, normalized_workspace, db_file=cache_manager.db_file)
            elif member.source_kind == "spec":
                # Extract base spec number and release from source_item_id (e.g., "21905-REL19" -> spec="21905", release="19")
                base_spec = member.source_item_id
                release = "latest"
                if member.source_item_id and "-REL" in member.source_item_id:
                    parts = member.source_item_id.split("-REL")
                    base_spec = parts[0]
                    release = parts[1]
                folder_path = checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, normalized_workspace, release=release)

            if not folder_path or not folder_path.exists():
                logger.warning(f"Checkout folder not found for {document_id} in Phase 2")
                if progress_callback:
                    progress_callback(PipelineStage.FAILED, document_id)
                continue

            # Check if folder has actual files (not just empty folder)
            has_files = any(f.is_file() for f in folder_path.iterdir())
            if not has_files:
                logger.warning(f"Checkout folder is empty for {document_id} in Phase 2, attempting re-checkout...")
                if member.source_kind == "tdoc":
                    folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, normalized_workspace, db_file=cache_manager.db_file)
                elif member.source_kind == "spec":
                    folder_path = checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, normalized_workspace, release=release)

                # Verify re-checkout worked
                if not folder_path or not folder_path.exists():
                    logger.error(f"Re-checkout failed for {document_id} in Phase 2")
                    if progress_callback:
                        progress_callback(PipelineStage.FAILED, document_id)
                    continue

                has_files = any(f.is_file() for f in folder_path.iterdir())
                if not has_files:
                    logger.error(f"Re-checkout produced empty folder for {document_id} in Phase 2")
                    if progress_callback:
                        progress_callback(PipelineStage.FAILED, document_id)
                    continue

            # Check if already embedded (skip if already done)
            # Note: If embeddings were manually deleted, use --force to reprocess
            status = storage.get_status(document_id, workspace=normalized_workspace)
            if status and status.embedded_at is not None and not force_rerun:
                logger.info(f"Skipping {document_id} - already embedded")
                embedded_ids.append(document_id)
                results[document_id] = status
                if progress_callback:
                    progress_callback(PipelineStage.EMBEDDING, document_id)
                continue

            try:
                if status is None:
                    status = ProcessingStatus(document_id=document_id)

                # Run just the embedding stage
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

                embedded_ids.append(document_id)
                results[document_id] = status
            except Exception as e:
                logger.error(f"Phase 2 failed for {document_id}: {e}")
                # Advance progress for failed docs
                if progress_callback:
                    progress_callback(PipelineStage.FAILED, document_id)

    # =============================================================================
    # PHASE 3: GRAPH (build knowledge graph with full visibility)
    # =============================================================================
    if embedded_ids:
        logger.info(f"Starting Phase 3: Building graphs for {len(embedded_ids)} documents")
        graph_results = build_all_graphs(
            document_ids=embedded_ids,
            checkout_base=checkout_base,
            workspace=normalized_workspace,
            config=config,
            progress_callback=progress_callback,
        )
        # Update results with graph statuses
        for doc_id, status in graph_results.items():
            status.current_stage = PipelineStage.COMPLETED
            status.completed_at = utc_now()
            storage.save_status(status, workspace=normalized_workspace)
            results[doc_id] = status

    return results


# TODO: ambigious name, ambiguous argument, ambiguous return type - consider splitting into get_status(document_id) and list_statuses(workspace)
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
    storage = EmbeddingsManager(config).storage
    normalized_workspace = normalize_workspace_name(workspace)

    if document_id is None:
        # Return all statuses in workspace
        return storage.list_statuses(normalized_workspace)

    return storage.get_status(document_id, workspace=normalized_workspace)


def build_all_graphs(
    document_ids: list[str],
    checkout_base: Path,
    workspace: str | None = None,
    config: AiConfig | None = None,
    progress_callback: Callable[[PipelineStage, str], None] | None = None,
) -> dict[str, ProcessingStatus]:
    """Build knowledge graphs for all processed documents (second pass).

    This function should be called AFTER process_all with skip_graph=True.
    It builds the graph for all documents with full visibility of all nodes.

    Args:
        document_ids: List of document IDs that have already been processed.
        checkout_base: Base path containing TDoc checkout folders.
        workspace: Optional workspace scope (defaults to "default").
        config: Optional AiConfig instance.
        progress_callback: Optional callback for progress updates.

    Returns:
        Dict mapping document_id to ProcessingStatus.
    """
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager(config)
    storage = embeddings_manager.storage
    normalized_workspace = normalize_workspace_name(workspace)

    # Get workspace members for path resolution
    members_map: dict[str, Any] = {}
    if normalized_workspace != "default":
        members = list_workspace_members(normalized_workspace)
        # Include both tdocs and specs
        members_map = {m.source_item_id: m for m in members if m.is_active and m.source_kind in ("tdoc", "spec")}

    results: dict[str, ProcessingStatus] = {}

    for document_id in document_ids:
        # Get existing status (should have embedded_at but not graphed_at)
        status = storage.get_status(document_id, workspace=normalized_workspace)
        if status is None:
            logger.warning(f"No status found for {document_id}, skipping graph build")
            continue

        # Skip if already graphed (unless force_rerun - but we don't have that here)
        if status.graphed_at is not None:
            logger.info(f"Skipping {document_id} - already graphed")
            results[document_id] = status
            if progress_callback:
                progress_callback(PipelineStage.GRAPHING, document_id)
            continue

        # Determine folder path using metadata-based resolution
        member = members_map.get(document_id)
        cache_manager = resolve_cache_manager()

        if not member:
            # For specs, try to construct path from document_id
            if "-REL" in document_id:
                # Spec format: 26260-REL19
                spec_number = document_id.split("-REL")[0]
                release = document_id.split("-REL")[1]
                folder_path = checkout_base / "specs" / f"{spec_number}-REL{release}" / spec_number
            else:
                logger.warning(f"No workspace member found for {document_id} in graph phase")
                continue
        elif member.source_kind == "tdoc":
            folder_path = resolve_tdoc_checkout_path(document_id, cache_manager.checkout_dir)
            if not folder_path:
                folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, normalized_workspace, db_file=cache_manager.db_file)
        else:  # member.source_kind == "spec"
            # Extract base spec number and release from source_item_id (e.g., "21905-REL19" -> spec="21905", release="19")
            base_spec = member.source_item_id
            release = "latest"
            if member.source_item_id and "-REL" in member.source_item_id:
                parts = member.source_item_id.split("-REL")
                base_spec = parts[0]
                release = parts[1]
            folder_path = checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, normalized_workspace, release=release)

        if not folder_path or not folder_path.exists():
            logger.warning(f"Checkout folder not found for {document_id} in graph phase")
            continue

        try:
            artifact_path = folder_path / ".ai" / f"{document_id.strip().upper()}.md"
            if not artifact_path.exists():
                logger.warning(f"No markdown artifact found for {document_id}")
                continue

            markdown = artifact_path.read_text(encoding="utf-8")

            # Extract meeting_id from folder path
            meeting_id = None
            path_parts = folder_path.parts
            if "Docs" in path_parts:
                docs_index = path_parts.index("Docs")
                if docs_index >= 3:
                    meeting_id = path_parts[docs_index - 1]

            # Build graph with full visibility of all nodes
            nodes, edges = build_graph(
                document_id,
                markdown,
                meeting_id=meeting_id,
                storage=storage,
                workspace=normalized_workspace,
            )

            storage.save_nodes(nodes, workspace=normalized_workspace)
            storage.save_edges(edges, workspace=normalized_workspace)

            # Update status
            status.graphed_at = utc_now()
            status.current_stage = PipelineStage.GRAPHING
            storage.save_status(status, workspace=normalized_workspace)

            results[document_id] = status

            if progress_callback:
                progress_callback(PipelineStage.GRAPHING, document_id)

            logger.info(f"Built graph for {document_id}: {len(nodes)} nodes, {len(edges)} edges")

        except Exception as e:
            logger.warning(f"Graph building failed for {document_id}: {e}")
            # Set failure type and mark as failed
            status.failure_type = ProcessingFailureType.GRAPH_FAILED
            status.current_stage = PipelineStage.FAILED
            status.error_message = str(e)
            storage.save_status(status, workspace=normalized_workspace)
            results[document_id] = status
            # Advance progress for failed docs
            if progress_callback:
                progress_callback(PipelineStage.FAILED, document_id)
            continue

    return results


__all__ = [
    "build_all_graphs",
    "get_status",
    "process_all",
    "process_tdoc",
    "run_pipeline",
]
