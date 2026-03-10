"""Pipeline orchestration for AI document processing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tdoc_ai.config import AiConfig
from tdoc_ai.models import DocumentClassification, PipelineStage, ProcessingFailureType, ProcessingStatus
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


def run_pipeline(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    force_rerun: bool = False,
    workspace: str | None = None,
    config: AiConfig | None = None,
    embeddings_manager: EmbeddingsManager | None = None,
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
        embeddings_manager: Optional embeddings manager to reuse across stages.

    Returns:
        Updated ProcessingStatus with stage timestamps.

    Raises:
        Exception: Per-TDoc errors are isolated and re-raised after logging.
    """
    logger.info(f"Starting pipeline for {document_id}")
    normalized_workspace = normalize_workspace_name(workspace)

    status = _get_or_create_status(document_id, storage, normalized_workspace)
    if not force_rerun and status.current_stage == PipelineStage.COMPLETED:
        logger.info(f"Skipping {document_id} - already completed")
        return status

    _run_classify_extract_pipeline(document_id, folder_path, storage, status, normalized_workspace, force_rerun)
    _run_embedding_pipeline(
        document_id,
        folder_path,
        storage,
        status,
        normalized_workspace,
        force_rerun,
        config,
        embeddings_manager=embeddings_manager,
    )
    _run_graph_pipeline(document_id, folder_path, storage, status, normalized_workspace, force_rerun)
    _complete_pipeline(document_id, status, storage, normalized_workspace)

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
    embeddings_manager: EmbeddingsManager | None = None,
) -> None:
    """Run embedding stage based on extracted markdown artifact.

    Args:
        document_id: Document identifier.
        folder_path: Path to TDoc folder.
        storage: AiStorage instance.
        status: ProcessingStatus to update.
        workspace: Workspace name.
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.
    """
    status.current_stage = PipelineStage.EMBEDDING
    status.error_message = None
    storage.save_status(status, workspace=workspace)

    artifact_path = folder_path / ".ai" / f"{document_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"Extracted markdown artifact not found for embedding: {artifact_path}"
        raise FileNotFoundError(msg)

    # Get embeddings manager from config
    if embeddings_manager is None:
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
        config: Optional AI configuration (defaults to environment config).

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
        embeddings_manager=embeddings_manager,
    )


def process_all(
    document_ids: list[str],
    checkout_base: Path,
    new_only: bool = False,
    force_rerun: bool = False,
    progress_callback: Callable[[str], None] | None = None,
    workspace: str | None = None,
    config: AiConfig | None = None,
    limit: int | None = None,
) -> dict[str, ProcessingStatus]:
    """Process multiple TDocs through the AI pipeline using three-phase approach.

    Args:
        document_ids: Document identifiers to process.
        checkout_base: Base checkout directory for document folders.
        new_only: Whether to process only documents without existing extraction.
        force_rerun: Whether to re-run stages regardless of status.
        progress_callback: Optional callback invoked after each document.
        workspace: Optional workspace name (defaults to "default").
        config: Optional AI configuration override.
        limit: Optional maximum number of IDs to process.

    Returns:
        Mapping of document IDs to ProcessingStatus.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    document_ids = _resolve_workspace_document_ids(document_ids, normalized_workspace, limit)
    results: dict[str, ProcessingStatus] = {}
    config = config or AiConfig.from_env()
    embeddings_manager = EmbeddingsManager(config)

    extracted_ids, extract_results = process_extract_phase(
        document_ids=document_ids,
        checkout_base=checkout_base,
        new_only=new_only,
        force_rerun=force_rerun,
        progress_callback=progress_callback,
        workspace=normalized_workspace,
        config=config,
        embeddings_manager=embeddings_manager,
        limit=limit,
    )
    results.update(extract_results)

    embedded_ids, embed_results = process_embed_phase(
        document_ids=extracted_ids,
        checkout_base=checkout_base,
        force_rerun=force_rerun,
        progress_callback=progress_callback,
        workspace=normalized_workspace,
        config=config,
        embeddings_manager=embeddings_manager,
        limit=limit,
    )
    results.update(embed_results)

    _, graph_results = process_graph_phase(
        document_ids=embedded_ids,
        checkout_base=checkout_base,
        progress_callback=progress_callback,
        workspace=normalized_workspace,
        config=config,
        embeddings_manager=embeddings_manager,
        limit=limit,
    )
    results.update(graph_results)
    return results


def get_status(document_id: str, workspace: str | None = None) -> ProcessingStatus | None:
    """Get processing status for a single TDoc.

    Args:
        document_id: Document identifier.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        ProcessingStatus if found, None otherwise.
    """
    config = AiConfig.from_env()
    storage = EmbeddingsManager(config).storage
    normalized_workspace = normalize_workspace_name(workspace)

    return storage.get_status(document_id, workspace=normalized_workspace)


def list_statuses(workspace: str | None = None) -> list[ProcessingStatus]:
    """List processing statuses for all TDocs in workspace.

    Args:
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        List of ProcessingStatus for all documents in workspace.
    """
    config = AiConfig.from_env()
    storage = EmbeddingsManager(config).storage
    normalized_workspace = normalize_workspace_name(workspace)

    return storage.list_statuses(normalized_workspace)


def process_extract_phase(
    document_ids: list[str],
    checkout_base: Path,
    new_only: bool = False,
    force_rerun: bool = False,
    progress_callback: Callable[[str], None] | None = None,
    workspace: str | None = None,
    config: AiConfig | None = None,
    embeddings_manager: EmbeddingsManager | None = None,
    limit: int | None = None,
) -> tuple[list[str], dict[str, ProcessingStatus]]:
    """Run the classify and extract phase for all documents.

    This phase identifies the primary document in each folder, then converts it
    to Markdown and records status updates in storage. Documents with completed
    extraction are skipped unless force_rerun is set. Failures are logged and do
    not interrupt processing of other documents.

    Args:
        document_ids: Document identifiers to process.
        checkout_base: Base checkout directory for document folders.
        new_only: Whether to return already-extracted documents in results.
        force_rerun: Whether to re-run classification/extraction regardless of status.
        progress_callback: Optional callback invoked after each document.
        workspace: Optional workspace name (defaults to "default").
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.
        limit: Optional maximum number of documents to process.

    Returns:
        Tuple of (extracted_ids, results) where extracted_ids contains document IDs
        that completed extraction and results maps document IDs to ProcessingStatus.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    storage = _resolve_storage(config, embeddings_manager)
    members_map = _resolve_members_map(normalized_workspace)
    results: dict[str, ProcessingStatus] = {}
    extracted_ids: list[str] = []

    # Apply limit for testing
    if limit is not None and limit > 0:
        document_ids = document_ids[:limit]

    for document_id in document_ids:
        existing_status = storage.get_status(document_id, workspace=normalized_workspace)
        if not force_rerun and existing_status and existing_status.extracted_at is not None:
            logger.debug(f"Skipping {document_id} - already extracted")
            if not new_only:
                results[document_id] = existing_status
                extracted_ids.append(document_id)
            if progress_callback:
                progress_callback(document_id)
            continue

        folder_path = _resolve_document_folder(
            document_id=document_id,
            checkout_base=checkout_base,
            workspace=normalized_workspace,
            members_map=members_map,
        )
        if not folder_path or not folder_path.exists():
            logger.warning(f"Checkout folder not found for {document_id}")
            if progress_callback:
                progress_callback(document_id)
            continue

        try:
            status = existing_status or ProcessingStatus(document_id=document_id)

            if not force_rerun and status.classified_at:
                logger.info(f"Skipping classification for {document_id} - already classified")
            else:
                _run_classify_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

            if not force_rerun and status.extracted_at:
                logger.info(f"Skipping extraction for {document_id} - already extracted")
            else:
                _run_extract_stage(document_id, folder_path, storage, status, workspace=normalized_workspace)

            results[document_id] = status
            if status.extracted_at is not None:
                extracted_ids.append(document_id)
        except Exception as exc:
            logger.error(f"Phase 1 failed for {document_id}: {exc}")
        finally:
            if progress_callback:
                progress_callback(document_id)

    return extracted_ids, results


def process_embed_phase(
    document_ids: list[str],
    checkout_base: Path,
    force_rerun: bool = False,
    progress_callback: Callable[[str], None] | None = None,
    workspace: str | None = None,
    config: AiConfig | None = None,
    embeddings_manager: EmbeddingsManager | None = None,
    limit: int | None = None,
) -> tuple[list[str], dict[str, ProcessingStatus]]:
    """Run the embedding phase for extracted documents.

    This phase generates vector embeddings from Markdown artifacts and persists
    them to storage. Failures are logged and do not interrupt remaining documents.

    Args:
        document_ids: Document identifiers to process.
        checkout_base: Base checkout directory for document folders.
        force_rerun: Whether to re-run embedding even if already embedded.
        progress_callback: Optional callback invoked after each document.
        workspace: Optional workspace name (defaults to "default").
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.
        limit: Optional maximum number of documents to process.

    Returns:
        Tuple of (embedded_ids, results) where embedded_ids contains document IDs
        that completed embedding and results maps document IDs to ProcessingStatus.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    storage = _resolve_storage(config, embeddings_manager)
    members_map = _resolve_members_map(normalized_workspace)
    results: dict[str, ProcessingStatus] = {}
    embedded_ids: list[str] = []

    # Apply limit for testing
    if limit is not None and limit > 0:
        document_ids = document_ids[:limit]

    for document_id in document_ids:
        folder_path = _resolve_document_folder(
            document_id=document_id,
            checkout_base=checkout_base,
            workspace=normalized_workspace,
            members_map=members_map,
        )
        if not folder_path or not folder_path.exists():
            logger.warning(f"Checkout folder not found for {document_id} in Phase 2")
            if progress_callback:
                progress_callback(document_id)
            continue

        if not any(f.is_file() for f in folder_path.iterdir()):
            logger.warning(f"Checkout folder is empty for {document_id} in Phase 2")
            if progress_callback:
                progress_callback(document_id)
            continue

        status = storage.get_status(document_id, workspace=normalized_workspace)
        if status and status.embedded_at is not None and not force_rerun:
            logger.info(f"Skipping {document_id} - already embedded")
            results[document_id] = status
            embedded_ids.append(document_id)
            if progress_callback:
                progress_callback(document_id)
            continue

        try:
            if status is None:
                status = ProcessingStatus(document_id=document_id)

            _run_embedding_stage(
                document_id,
                folder_path,
                storage,
                status,
                workspace=normalized_workspace,
                config=config,
                embeddings_manager=embeddings_manager,
            )
            embedded_ids.append(document_id)
            results[document_id] = status
        except Exception as exc:
            logger.error(f"Phase 2 failed for {document_id}: {exc}")
        finally:
            if progress_callback:
                progress_callback(document_id)

    return embedded_ids, results


def process_graph_phase(
    document_ids: list[str],
    checkout_base: Path,
    progress_callback: Callable[[str], None] | None = None,
    workspace: str | None = None,
    config: AiConfig | None = None,
    embeddings_manager: EmbeddingsManager | None = None,
    limit: int | None = None,
) -> tuple[list[str], dict[str, ProcessingStatus]]:
    """Run the graph phase for embedded documents.

    This phase builds knowledge graph nodes and edges from Markdown artifacts
    and updates processing status. Failures are logged and do not interrupt other
    documents.

    Args:
        document_ids: Document identifiers to process.
        checkout_base: Base checkout directory for document folders.
        progress_callback: Optional callback invoked after each document.
        workspace: Optional workspace name (defaults to "default").
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.
        limit: Optional maximum number of documents to process.

    Returns:
        Tuple of (graphed_ids, results) where graphed_ids contains document IDs
        that completed graph construction and results maps document IDs to ProcessingStatus.
    """
    normalized_workspace = normalize_workspace_name(workspace)
    storage = _resolve_storage(config, embeddings_manager)
    members_map = _resolve_members_map(normalized_workspace)
    results: dict[str, ProcessingStatus] = {}
    graphed_ids: list[str] = []

    # Apply limit for testing
    if limit is not None and limit > 0:
        document_ids = document_ids[:limit]

    for document_id in document_ids:
        status = _resolve_graph_status(storage, document_id, normalized_workspace)
        if status is None:
            if progress_callback:
                progress_callback(document_id)
            continue

        if status.graphed_at is not None:
            logger.info(f"Skipping {document_id} - already graphed")
            results[document_id] = status
            graphed_ids.append(document_id)
            if progress_callback:
                progress_callback(document_id)
            continue

        folder_path = _resolve_document_folder(
            document_id=document_id,
            checkout_base=checkout_base,
            workspace=normalized_workspace,
            members_map=members_map,
        )
        if not folder_path or not folder_path.exists():
            logger.warning(f"Checkout folder not found for {document_id} in graph phase")
            if progress_callback:
                progress_callback(document_id)
            continue

        try:
            _build_graph_for_document(document_id, folder_path, storage, status, normalized_workspace)
            results[document_id] = status
            graphed_ids.append(document_id)
        except Exception as exc:
            logger.warning(f"Graph building failed for {document_id}: {exc}")
            status.failure_type = ProcessingFailureType.GRAPH_FAILED
            status.current_stage = PipelineStage.FAILED
            status.error_message = str(exc)
            storage.save_status(status, workspace=normalized_workspace)
            results[document_id] = status
        finally:
            if progress_callback:
                progress_callback(document_id)

    return graphed_ids, results


def _resolve_workspace_document_ids(
    document_ids: list[str],
    workspace: str,
    limit: int | None,
) -> list[str]:
    """Resolve document identifiers for a workspace scope.

    Args:
        document_ids: Optional document IDs to filter against workspace members.
        workspace: Workspace name to resolve members from.
        limit: Optional maximum number of IDs to return.

    Returns:
        Filtered list of document IDs for the workspace.
    """
    if workspace == "default":
        resolved_ids = document_ids
    else:
        members = list_workspace_members(workspace)
        member_ids = {m.source_item_id for m in members if m.is_active and m.source_kind in ("tdoc", "spec")}
        resolved_ids = list(member_ids) if not document_ids else [tid for tid in document_ids if tid in member_ids]

    if limit is not None and limit > 0:
        logger.info(f"Limited processing to {limit} documents")
        return resolved_ids[:limit]
    return resolved_ids


def _resolve_members_map(workspace: str) -> dict[str, Any]:
    """Build a workspace member lookup map.

    Args:
        workspace: Workspace name to resolve members for.

    Returns:
        Mapping from source_item_id to workspace member metadata. Returns an
        empty dict for the default workspace.
    """
    if workspace == "default":
        return {}
    members = list_workspace_members(workspace)
    return {m.source_item_id: m for m in members if m.is_active and m.source_kind in ("tdoc", "spec")}


def _resolve_storage(config: AiConfig | None, embeddings_manager: EmbeddingsManager | None = None) -> AiStorage:
    """Resolve the AI storage instance from configuration.

    Args:
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.

    Returns:
        Initialized AiStorage instance.
    """
    if embeddings_manager is not None:
        return embeddings_manager.storage
    config = config or AiConfig.from_env()
    return EmbeddingsManager(config).storage


def _resolve_document_folder(
    document_id: str,
    checkout_base: Path,
    workspace: str,
    members_map: dict[str, Any],
) -> Path | None:
    """Resolve a document folder path for the given workspace.

    Handles default workspace lookups and workspace members for TDocs and
    specifications. Performs checkouts when necessary.

    Args:
        document_id: Document identifier to resolve.
        checkout_base: Base checkout directory for default workspace lookups.
        workspace: Workspace name to resolve against.
        members_map: Mapping of workspace members keyed by source_item_id.

    Returns:
        Document folder path if found, otherwise None.
    """
    cache_manager = resolve_cache_manager()
    if workspace == "default":
        return _resolve_default_document_folder(document_id, checkout_base, cache_manager.checkout_dir)

    member = members_map.get(document_id)
    if not member:
        return None

    if member.source_kind == "tdoc":
        folder_path = resolve_tdoc_checkout_path(document_id, cache_manager.checkout_dir)
        if not folder_path:
            folder_path = checkout_tdoc_to_workspace(document_id, cache_manager.checkout_dir, workspace, db_file=cache_manager.db_file)
        return folder_path

    base_spec, release = _parse_spec_release(member.source_item_id)
    return checkout_spec_to_workspace(base_spec, cache_manager.checkout_dir, workspace, release=release)


def _resolve_default_document_folder(document_id: str, checkout_base: Path, checkout_dir: Path) -> Path | None:
    """Resolve a document folder in the default workspace.

    Args:
        document_id: Document identifier to resolve.
        checkout_base: Optional base path for checkouts.
        checkout_dir: Default checkout directory for cached artifacts.

    Returns:
        Document folder path if found, otherwise None.
    """
    if checkout_base:
        return checkout_base / document_id
    resolved_path = resolve_tdoc_checkout_path(document_id, checkout_dir)
    if resolved_path is None:
        return None
    return resolved_path


def _parse_spec_release(source_item_id: str) -> tuple[str, str]:
    """Extract base specification number and release string.

    Args:
        source_item_id: Workspace source identifier like "21905-REL19".

    Returns:
        Tuple of (base_spec, release) where release defaults to "latest" when
        not specified.
    """
    base_spec = source_item_id
    release = "latest"
    if source_item_id and "-REL" in source_item_id:
        parts = source_item_id.split("-REL")
        base_spec = parts[0]
        release = parts[1]
    return base_spec, release


def _extract_meeting_id(folder_path: Path) -> str | None:
    """Extract a meeting ID from a checkout folder path.

    Args:
        folder_path: Document checkout folder path.

    Returns:
        Meeting identifier if the path contains a "Docs" segment, otherwise None.
    """
    path_parts = folder_path.parts
    if "Docs" in path_parts:
        docs_index = path_parts.index("Docs")
        if docs_index >= 3:
            return path_parts[docs_index - 1]
    return None


def _resolve_graph_status(storage: AiStorage, document_id: str, workspace: str) -> ProcessingStatus | None:
    """Resolve processing status for the graph phase.

    Args:
        storage: AI storage instance.
        document_id: Document identifier.
        workspace: Workspace name for status lookup.

    Returns:
        Existing ProcessingStatus or None if not found.
    """
    status = storage.get_status(document_id, workspace=workspace)
    if status is None:
        logger.warning(f"No status found for {document_id}, skipping graph build")
        return None
    return status


def _build_graph_for_document(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str,
) -> None:
    """Build and persist a knowledge graph for a single document.

    Reads the Markdown artifact, extracts a meeting ID from the folder path,
    saves nodes and edges, and updates processing status.

    Args:
        document_id: Document identifier.
        folder_path: Checkout folder containing the Markdown artifact.
        storage: AI storage instance.
        status: Processing status to update.
        workspace: Workspace name for storage operations.

    Raises:
        FileNotFoundError: If the Markdown artifact does not exist.
    """
    artifact_path = folder_path / ".ai" / f"{document_id.strip().upper()}.md"
    if not artifact_path.exists():
        msg = f"No markdown artifact found for {document_id}"
        raise FileNotFoundError(msg)

    markdown = artifact_path.read_text(encoding="utf-8")
    meeting_id = _extract_meeting_id(folder_path)
    nodes, edges = build_graph(
        document_id,
        markdown,
        meeting_id=meeting_id,
        storage=storage,
        workspace=workspace,
    )

    storage.save_nodes(nodes, workspace=workspace)
    storage.save_edges(edges, workspace=workspace)

    status.graphed_at = utc_now()
    status.current_stage = PipelineStage.COMPLETED
    status.completed_at = utc_now()
    storage.save_status(status, workspace=workspace)

    logger.info(f"Built graph for {document_id}: {len(nodes)} nodes, {len(edges)} edges")


def _get_or_create_status(document_id: str, storage: AiStorage, workspace: str) -> ProcessingStatus:
    """Get existing status or create a new ProcessingStatus.

    Args:
        document_id: Document identifier.
        storage: AI storage instance.
        workspace: Workspace name for status lookup.

    Returns:
        ProcessingStatus for the document.
    """
    try:
        status = storage.get_status(document_id, workspace=workspace)
        if status is None:
            status = ProcessingStatus(document_id=document_id)
    except Exception:
        status = ProcessingStatus(document_id=document_id)
    return status


def _run_classify_extract_pipeline(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str,
    force_rerun: bool,
) -> None:
    """Run classify and extract stages for a single document.

    Args:
        document_id: Document identifier.
        folder_path: Checkout folder containing the document files.
        storage: AI storage instance.
        status: Processing status to update.
        workspace: Workspace name for storage operations.
        force_rerun: Whether to run stages even if already completed.
    """
    if not force_rerun and status.classified_at:
        logger.info(f"Skipping classification for {document_id} - already classified")
    else:
        _run_classify_stage(document_id, folder_path, storage, status, workspace=workspace)

    if not force_rerun and status.extracted_at:
        logger.info(f"Skipping extraction for {document_id} - already extracted")
    else:
        _run_extract_stage(document_id, folder_path, storage, status, workspace=workspace)


def _run_embedding_pipeline(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str,
    force_rerun: bool,
    config: AiConfig | None,
    embeddings_manager: EmbeddingsManager | None,
) -> None:
    """Run the embedding stage for a single document.

    Args:
        document_id: Document identifier.
        folder_path: Checkout folder containing the Markdown artifact.
        storage: AI storage instance.
        status: Processing status to update.
        workspace: Workspace name for storage operations.
        force_rerun: Whether to run embedding even if already completed.
        config: Optional AI configuration override.
        embeddings_manager: Optional embeddings manager to reuse.
    """
    if not force_rerun and status.embedded_at:
        logger.info(f"Skipping embedding for {document_id} - already embedded")
        return

    _run_embedding_stage(
        document_id,
        folder_path,
        storage,
        status,
        workspace=workspace,
        config=config,
        embeddings_manager=embeddings_manager,
    )


def _run_graph_pipeline(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    status: ProcessingStatus,
    workspace: str,
    force_rerun: bool,
) -> None:
    """Run the graph stage for a single document.

    Args:
        document_id: Document identifier.
        folder_path: Checkout folder containing the Markdown artifact.
        storage: AI storage instance.
        status: Processing status to update.
        workspace: Workspace name for storage operations.
        force_rerun: Whether to run graphing even if already completed.
    """
    if not force_rerun and status.graphed_at is not None:
        logger.info(f"Skipping graphing for {document_id} - already completed")
        return
    _run_graph_stage(document_id, folder_path, storage, status, workspace=workspace)


def _complete_pipeline(
    document_id: str,
    status: ProcessingStatus,
    storage: AiStorage,
    workspace: str,
) -> None:
    """Finalize pipeline status for a document.

    Args:
        document_id: Document identifier.
        status: Processing status to update.
        storage: AI storage instance.
        workspace: Workspace name for storage operations.
    """
    status.current_stage = PipelineStage.COMPLETED
    status.completed_at = utc_now()
    storage.save_status(status, workspace=workspace)
    logger.info(f"Pipeline completed for {document_id}")


__all__ = [
    "get_status",
    "process_all",
    "process_embed_phase",
    "process_extract_phase",
    "process_graph_phase",
    "process_tdoc",
    "run_pipeline",
]
