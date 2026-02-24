"""LanceDB storage layer for AI processing artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from tdoc_crawler.ai.models import (
    DocumentChunk,
    DocumentClassification,
    DocumentSummary,
    GraphEdge,
    GraphNode,
    ProcessingStatus,
)
from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)


class AiStorage:
    """LanceDB storage layer for all AI-generated data."""

    def __init__(self, store_path: Path) -> None:
        """Initialize LanceDB connection at the given path.

        Args:
            store_path: Directory containing the LanceDB tables.
        """
        self._store_path = store_path
        self._store_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._store_path))
        self._tables: dict[str, Any] = {}
        self._ensure_tables()

    def save_status(self, status: ProcessingStatus) -> None:
        """Persist processing status for a TDoc."""
        table = self._table("processing_status")
        table.delete(f"tdoc_id = '{status.tdoc_id}'")
        table.add([status.model_dump()])

    def get_status(self, tdoc_id: str) -> ProcessingStatus | None:
        """Return status for a single TDoc if present."""
        table = self._table("processing_status")
        records = _table_to_records(table)
        for record in records:
            if record.get("tdoc_id") == tdoc_id:
                return ProcessingStatus(**record)
        return None

    def list_statuses(self) -> list[ProcessingStatus]:
        """Return all processing statuses."""
        table = self._table("processing_status")
        return [ProcessingStatus(**record) for record in _table_to_records(table)]

    def save_classifications(self, classifications: list[DocumentClassification]) -> None:
        """Persist file classifications for a TDoc."""
        if not classifications:
            return
        tdoc_id = classifications[0].tdoc_id
        table = self._table("classifications")
        table.delete(f"tdoc_id = '{tdoc_id}'")
        table.add([item.model_dump() for item in classifications])

    def get_classifications(self, tdoc_id: str) -> list[DocumentClassification]:
        """Return classifications for a TDoc."""
        table = self._table("classifications")
        records = [record for record in _table_to_records(table) if record.get("tdoc_id") == tdoc_id]
        return [DocumentClassification(**record) for record in records]

    def save_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Persist embedded chunks for a TDoc."""
        if not chunks:
            return
        tdoc_id = chunks[0].tdoc_id
        table = self._table("chunks")
        table.delete(f"tdoc_id = '{tdoc_id}'")
        table.add([item.model_dump() for item in chunks])

    def search_chunks(self, query_vector: list[float], top_k: int) -> list[tuple[DocumentChunk, float]]:
        """Return top-k similar chunks for a query vector."""
        table = self._table("chunks")
        results = table.search(query_vector).limit(top_k).to_list()
        output: list[tuple[DocumentChunk, float]] = []
        for record in results:
            score = record.get("_distance")
            chunk = DocumentChunk(**_strip_distance(record))
            output.append((chunk, float(score) if score is not None else 0.0))
        return output

    def save_summary(self, summary: DocumentSummary) -> None:
        """Persist summary for a TDoc."""
        table = self._table("summaries")
        table.delete(f"tdoc_id = '{summary.tdoc_id}'")
        table.add([summary.model_dump()])

    def get_summary(self, tdoc_id: str) -> DocumentSummary | None:
        """Return summary for a TDoc if present."""
        table = self._table("summaries")
        records = _table_to_records(table)
        for record in records:
            if record.get("tdoc_id") == tdoc_id:
                return DocumentSummary(**record)
        return None

    def save_nodes(self, nodes: list[GraphNode]) -> None:
        """Persist graph nodes."""
        if not nodes:
            return
        table = self._table("graph_nodes")
        _delete_by_ids(table, "node_id", [node.node_id for node in nodes])
        table.add([_node_record(node) for node in nodes])

    def save_edges(self, edges: list[GraphEdge]) -> None:
        """Persist graph edges."""
        if not edges:
            return
        table = self._table("graph_edges")
        _delete_by_ids(table, "edge_id", [edge.edge_id for edge in edges])
        table.add([edge.model_dump() for edge in edges])

    def query_graph(self, filters: dict[str, Any]) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Return graph nodes and edges matching provided filters."""
        nodes = [_node_from_record(record) for record in _table_to_records(self._table("graph_nodes"))]
        edges = [GraphEdge(**record) for record in _table_to_records(self._table("graph_edges"))]

        node_types = filters.get("node_types") if filters else None
        if node_types:
            nodes = [node for node in nodes if node.node_type.value in node_types]

        return nodes, edges

    def _ensure_tables(self) -> None:
        self._ensure_table("processing_status", _processing_status_schema())
        self._ensure_table("classifications", _classification_schema())
        self._ensure_table("chunks", _chunk_schema())
        self._ensure_table("summaries", _summary_schema())
        self._ensure_table("graph_nodes", _graph_node_schema())
        self._ensure_table("graph_edges", _graph_edge_schema())

    def _ensure_table(self, name: str, schema: pa.Schema) -> None:
        if name in self._db.table_names():
            self._tables[name] = self._db.open_table(name)
            return
        self._tables[name] = self._db.create_table(name, schema=schema)

    def _table(self, name: str) -> Any:
        return self._tables[name]


def _table_to_records(table: Any) -> list[dict[str, Any]]:
    try:
        dataframe = table.to_pandas()
        return dataframe.to_dict("records")
    except Exception as exc:
        _logger.warning("Failed to read LanceDB table; returning empty set: %s", exc)
        return []


def _strip_distance(record: dict[str, Any]) -> dict[str, Any]:
    data = dict(record)
    data.pop("_distance", None)
    return data


def _delete_by_ids(table: Any, field_name: str, ids: list[str]) -> None:
    if not ids:
        return
    predicates = " or ".join([f"{field_name} = '{item}'" for item in ids])
    table.delete(predicates)


def _node_record(node: GraphNode) -> dict[str, Any]:
    record = node.model_dump()
    record["properties"] = json.dumps(node.properties)
    return record


def _node_from_record(record: dict[str, Any]) -> GraphNode:
    record = dict(record)
    properties = record.get("properties")
    if isinstance(properties, str):
        try:
            record["properties"] = json.loads(properties)
        except json.JSONDecodeError:
            record["properties"] = {}
    return GraphNode(**record)


def _processing_status_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("tdoc_id", pa.string()),
            pa.field("current_stage", pa.string()),
            pa.field("classified_at", pa.timestamp("us"), nullable=True),
            pa.field("extracted_at", pa.timestamp("us"), nullable=True),
            pa.field("embedded_at", pa.timestamp("us"), nullable=True),
            pa.field("summarized_at", pa.timestamp("us"), nullable=True),
            pa.field("graphed_at", pa.timestamp("us"), nullable=True),
            pa.field("completed_at", pa.timestamp("us"), nullable=True),
            pa.field("error_message", pa.string(), nullable=True),
            pa.field("source_hash", pa.string(), nullable=True),
        ]
    )


def _classification_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("tdoc_id", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("is_main_document", pa.bool_()),
            pa.field("confidence", pa.float32()),
            pa.field("decisive_heuristic", pa.string()),
            pa.field("file_size_bytes", pa.int64()),
            pa.field("classified_at", pa.timestamp("us")),
        ]
    )


def _chunk_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("tdoc_id", pa.string()),
            pa.field("section_heading", pa.string(), nullable=True),
            pa.field("chunk_index", pa.int64()),
            pa.field("text", pa.large_string()),
            pa.field("char_offset_start", pa.int64()),
            pa.field("char_offset_end", pa.int64()),
            pa.field("vector", pa.list_(pa.float32())),
            pa.field("embedding_model", pa.string()),
            pa.field("created_at", pa.timestamp("us")),
        ]
    )


def _summary_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("tdoc_id", pa.string()),
            pa.field("abstract", pa.large_string()),
            pa.field("key_points", pa.list_(pa.string())),
            pa.field("action_items", pa.list_(pa.string())),
            pa.field("decisions", pa.list_(pa.string())),
            pa.field("affected_specs", pa.list_(pa.string())),
            pa.field("llm_model", pa.string()),
            pa.field("prompt_version", pa.string()),
            pa.field("generated_at", pa.timestamp("us")),
        ]
    )


def _graph_node_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("node_id", pa.string()),
            pa.field("node_type", pa.string()),
            pa.field("label", pa.string()),
            pa.field("valid_from", pa.timestamp("us"), nullable=True),
            pa.field("valid_to", pa.timestamp("us"), nullable=True),
            pa.field("properties", pa.large_string()),
            pa.field("created_at", pa.timestamp("us")),
        ]
    )


def _graph_edge_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("edge_id", pa.string()),
            pa.field("source_id", pa.string()),
            pa.field("target_id", pa.string()),
            pa.field("edge_type", pa.string()),
            pa.field("weight", pa.float32()),
            pa.field("temporal_context", pa.string(), nullable=True),
            pa.field("provenance", pa.string()),
            pa.field("created_at", pa.timestamp("us")),
        ]
    )


__all__ = ["AiStorage"]
