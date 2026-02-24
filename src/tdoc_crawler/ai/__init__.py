"""AI document processing domain package."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import (
    DocumentChunk,
    DocumentClassification,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    PipelineStage,
    ProcessingStatus,
)


def process_tdoc(
    tdoc_id: str,
    config: AiConfig | None = None,
    stages: list[PipelineStage] | None = None,
) -> ProcessingStatus:
    """Process a single TDoc through the AI pipeline.

    Args:
            tdoc_id: TDoc identifier (e.g., "SP-123456").
            config: Pipeline configuration. Defaults to AiConfig.from_env().
            stages: Specific stages to run. If None, runs all applicable stages.

    Returns:
            Updated ProcessingStatus after pipeline execution.
    """
    raise NotImplementedError("AI pipeline is not implemented yet")


def process_all(
    config: AiConfig | None = None,
    new_only: bool = False,
    stages: list[PipelineStage] | None = None,
    progress_callback: Callable[[str, PipelineStage], None] | None = None,
) -> list[ProcessingStatus]:
    """Batch process all (or new-only) TDocs through the AI pipeline.

    Args:
            config: Pipeline configuration. Defaults to AiConfig.from_env().
            new_only: If True, only process TDocs not yet in processing_status.
            stages: Specific stages to run. If None, runs all applicable stages.
            progress_callback: Optional callback for reporting progress.

    Returns:
            List of ProcessingStatus entries for processed TDocs.
    """
    raise NotImplementedError("AI pipeline is not implemented yet")


def get_status(tdoc_id: str | None = None) -> ProcessingStatus | list[ProcessingStatus]:
    """Get processing status for one or all TDocs.

    Args:
            tdoc_id: If provided, return status for this TDoc. If None, return all.

    Returns:
            Single ProcessingStatus or list of ProcessingStatus entries.
    """
    raise NotImplementedError("AI status lookup is not implemented yet")


def query_embeddings(
    query: str,
    top_k: int = 5,
    tdoc_filter: list[str] | None = None,
    config: AiConfig | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Semantic search over embedded document chunks.

    Args:
            query: Natural language query text.
            top_k: Number of top results to return.
            tdoc_filter: Optional list of TDoc IDs to restrict search to.
            config: Pipeline configuration.

    Returns:
            List of (chunk, similarity_score) tuples sorted by descending score.
    """
    raise NotImplementedError("Embedding query is not implemented yet")


def query_graph(
    query: str,
    temporal_range: tuple[datetime, datetime] | None = None,
    node_types: list[str] | None = None,
    config: AiConfig | None = None,
) -> dict[str, Any]:
    """Query the temporal knowledge graph.

    Args:
            query: Natural language query about relationships/evolution.
            temporal_range: Optional (start, end) datetime filter.
            node_types: Optional filter for node types.
            config: Pipeline configuration.

    Returns:
            Dict with keys "nodes", "edges", and "answer".
    """
    raise NotImplementedError("Graph query is not implemented yet")


__all__ = [
    "AiConfig",
    "DocumentChunk",
    "DocumentClassification",
    "DocumentSummary",
    "GraphEdge",
    "GraphNode",
    "PipelineStage",
    "ProcessingStatus",
    "get_status",
    "process_all",
    "process_tdoc",
    "query_embeddings",
    "query_graph",
]
