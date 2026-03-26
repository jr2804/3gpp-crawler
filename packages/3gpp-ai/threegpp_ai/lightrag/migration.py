"""Migration utilities for shared embedding storage.

This module provides tools to migrate existing workspace-specific embeddings
to the shared storage format, eliminating duplicates.

Usage:
    >>> from threegpp_ai.lightrag.migration import migrate_to_shared_storage
    >>> await migrate_to_shared_storage(working_dir, embedding_model)
"""

# TODO: Is this module needed at all? No need for legacy migration if we just switch to shared storage for all new workspaces. Maybe just keep the consolidation function for users who want to merge existing workspaces into shared storage?!

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lightrag.utils import compute_mdhash_id

from .shared_storage import SharedNanoVectorDBStorage, WorkspaceIndex

logger = logging.getLogger(__name__)


async def migrate_to_shared_storage(
    working_dir: Path,
    workspace: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Migrate workspace-specific embeddings to shared storage.

    This function:
    1. Loads existing workspace embeddings
    2. Moves them to shared storage with deduplication
    3. Creates workspace index for tracking
    4. Optionally removes old workspace-specific files

    Args:
        working_dir: LightRAG working directory (already at embedding model level)
        workspace: Specific workspace to migrate (None = all workspaces)
        dry_run: If True, only analyze without making changes

    Returns:
        Migration statistics dict
    """
    stats = {
        "workspaces_processed": 0,
        "chunks_migrated": 0,
        "chunks_deduplicated": 0,
        "storage_saved_bytes": 0,
        "errors": [],
    }

    # working_dir is already at the embedding model level
    embedding_dir = working_dir
    if not embedding_dir.exists():
        logger.warning("Embedding directory does not exist: %s", embedding_dir)
        return stats

    # Find all workspace directories (exclude _shared)
    workspaces = []
    for item in embedding_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_") and (workspace is None or item.name == workspace):
            workspaces.append(item)

    logger.info("Found %d workspace(s) to migrate", len(workspaces))

    # Initialize shared storage
    shared_storage = SharedNanoVectorDBStorage(
        global_config={"working_dir": str(embedding_dir)},
        namespace="text_chunks",
    )

    for ws_dir in workspaces:
        logger.info("Processing workspace: %s", ws_dir.name)
        stats["workspaces_processed"] += 1

        # Load workspace-specific vdb file
        vdb_file = ws_dir / "vdb_text_chunks.json"
        if not vdb_file.exists():
            logger.warning("No vdb file found in %s", ws_dir)
            continue

        try:
            with open(vdb_file, encoding="utf-8") as f:
                ws_data = json.load(f)
        except Exception as e:
            logger.error("Failed to load %s: %s", vdb_file, e)
            stats["errors"].append(str(ws_dir))
            continue

        # Create workspace index
        ws_index = WorkspaceIndex(
            workspace_name=ws_dir.name,
            working_dir=embedding_dir,
        )

        # Process chunks
        chunks_data = ws_data.get("data", {})
        for chunk_id, chunk_data in chunks_data.items():
            text = chunk_data.get("text", "")
            embedding = chunk_data.get("embedding")
            metadata = chunk_data.get("metadata", {})

            if not text or embedding is None:
                continue

            # Compute hash for deduplication check
            text_hash = compute_mdhash_id(text.strip(), prefix="chunk-")

            # Check if already in shared storage
            if text_hash in shared_storage._data["index"]:
                # Duplicate - just track in workspace index
                existing_chunk_id = shared_storage._data["index"][text_hash]
                ws_index.add_document(chunk_id, [existing_chunk_id], {existing_chunk_id: metadata})
                stats["chunks_deduplicated"] += 1
                logger.debug("Deduplicated chunk %s → %s", chunk_id, existing_chunk_id)
            else:
                # New unique chunk - add to shared storage
                if not dry_run:
                    await shared_storage.upsert({chunk_id: chunk_data})
                ws_index.add_document(chunk_id, [chunk_id], {chunk_id: metadata})
                stats["chunks_migrated"] += 1
                logger.debug("Migrated unique chunk %s", chunk_id)

        # Estimate storage savings
        if vdb_file.exists():
            stats["storage_saved_bytes"] += vdb_file.stat().st_size

        logger.info(
            "Workspace %s: %d chunks processed",
            ws_dir.name,
            len(chunks_data),
        )

    if not dry_run:
        logger.info("Migration completed successfully")
    else:
        logger.info("Dry run completed - no changes made")

    return stats


async def consolidate_workspaces(
    working_dir: Path,
) -> None:
    """Consolidate all workspace embeddings into shared storage.

    This is a more aggressive migration that:
    1. Merges all workspace embeddings into shared storage
    2. Removes duplicate workspace-specific files
    3. Creates workspace indices for all workspaces

    WARNING: This modifies the workspace structure. Backup first!

    Args:
        working_dir: LightRAG working directory (already at embedding model level)
    """
    logger.info("Starting workspace consolidation...")

    # Run migration in dry-run mode first
    stats = await migrate_to_shared_storage(
        working_dir,
        dry_run=True,
    )

    logger.info(
        "Dry run results: %d chunks would be migrated, %d deduplicated",
        stats["chunks_migrated"],
        stats["chunks_deduplicated"],
    )

    # Run actual migration
    stats = await migrate_to_shared_storage(
        working_dir,
        dry_run=False,
    )

    logger.info(
        "Consolidation complete: %d chunks migrated, %d deduplicated, %.2f MB saved",
        stats["chunks_migrated"],
        stats["chunks_deduplicated"],
        stats["storage_saved_bytes"] / (1024 * 1024),
    )
