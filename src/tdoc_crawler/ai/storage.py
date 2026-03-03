"""LanceDB storage layer for AI processing artifacts."""

from __future__ import annotations

import json
import math
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

DEFAULT_WORKSPACE = "default"
_SCOPE_DELIMITER = "::"


class AiStorage:
    """LanceDB storage layer for all AI-generated data."""

    def __init__(self, store_path: Path, embedding_dimension: int) -> None:
        """Initialize LanceDB connection at the given path.

        Args:
            store_path: Directory containing the LanceDB tables.
            embedding_dimension: Dimension of the embedding model, obtained from
                SentenceTransformer.get_sentence_embedding_dimension().
        """
        self._store_path = store_path
        self._store_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._store_path))
        self._tables: dict[str, Any] = {}
        self._embedding_hashes: dict[str, str] = {}
        self._summary_hashes: dict[str, str] = {}
        self._embedding_dimension = embedding_dimension
        self._ensure_tables()

    @property
    def embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return self._embedding_dimension

    def save_embedding_hash(self, document_id: str, content_hash: str) -> None:
        """Persist the latest embedding content hash for idempotency checks."""
        self._embedding_hashes[document_id.upper()] = content_hash

    def get_embedding_hash(self, document_id: str) -> str | None:
        """Return previously persisted embedding content hash if present."""
        return self._embedding_hashes.get(document_id.upper())

    def save_summary_hash(self, document_id: str, content_hash: str) -> None:
        """Persist the latest summary content hash for idempotency checks."""
        self._summary_hashes[document_id.upper()] = content_hash

    def get_summary_hash(self, document_id: str) -> str | None:
        """Return previously persisted summary content hash if present."""
        return self._summary_hashes.get(document_id.upper())

    def save_status(self, status: ProcessingStatus, workspace: str | None = None) -> None:
        """Persist processing status for a TDoc."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_document_id = _to_scoped_document_id(status.document_id, normalized_workspace)
        table = self._table("processing_status")
        table.delete(f"document_id = '{scoped_document_id}'")
        payload = status.model_dump()
        payload["document_id"] = scoped_document_id
        # Ensure keywords is always a list for pyarrow list<string> schema
        if payload.get("keywords") is None:
            payload["keywords"] = []
        # Handle NaT for optional datetime fields - convert to None for LanceDB
        for field in ["classified_at", "extracted_at", "embedded_at", "summarized_at", "graphed_at", "completed_at"]:
            if field in payload and _is_nat(payload[field]):
                payload[field] = None
        table.add([payload])

    def get_status(self, document_id: str, workspace: str | None = None) -> ProcessingStatus | None:
        """Return status for a single TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        table = self._table("processing_status")
        records = _table_to_records(table)
        for record in records:
            if record.get("document_id") == scoped_document_id:
                unscoped_record = dict(record)
                unscoped_record["document_id"] = _from_scoped_document_id(scoped_document_id)[1]
                # Handle NaN/NaT values from LanceDB
                for field in ["error_message", "source_hash", "detected_language"]:
                    if field in unscoped_record and (unscoped_record[field] is None or _is_nan(unscoped_record[field])):
                        unscoped_record[field] = None
                # Handle NaT for optional datetime fields
                for field in ["classified_at", "extracted_at", "embedded_at", "summarized_at", "graphed_at", "completed_at"]:
                    if field in unscoped_record and _is_nat(unscoped_record[field]):
                        unscoped_record[field] = None
                # Keywords is a list - handle NaN/None
                if "keywords" in unscoped_record and not isinstance(unscoped_record["keywords"], list):
                    unscoped_record["keywords"] = None
                return ProcessingStatus(**unscoped_record)
        return None

    def list_statuses(self, workspace: str | None = None) -> list[ProcessingStatus]:
        """Return all processing statuses."""
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("processing_status")
        statuses: list[ProcessingStatus] = []
        for record in _table_to_records(table):
            raw_document_id = str(record.get("document_id", ""))
            record_workspace, unscoped_document_id = _from_scoped_document_id(raw_document_id)
            if record_workspace != normalized_workspace:
                continue
            unscoped_record = dict(record)
            unscoped_record["document_id"] = unscoped_document_id
            # Handle NaN/NaT values from LanceDB
            for field in ["error_message", "source_hash", "detected_language"]:
                if field in unscoped_record and (unscoped_record[field] is None or _is_nan(unscoped_record[field])):
                    unscoped_record[field] = None
            # Handle NaT for optional datetime fields
            for field in ["classified_at", "extracted_at", "embedded_at", "summarized_at", "graphed_at", "completed_at"]:
                if field in unscoped_record and _is_nat(unscoped_record[field]):
                    unscoped_record[field] = None
            # Keywords is a list - handle NaN/None
            if "keywords" in unscoped_record and not isinstance(unscoped_record["keywords"], list):
                unscoped_record["keywords"] = None
            statuses.append(ProcessingStatus(**unscoped_record))
        return statuses

    def save_classifications(
        self,
        classifications: list[DocumentClassification],
        workspace: str | None = None,
    ) -> None:
        """Persist file classifications for a TDoc."""
        if not classifications:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        document_id = classifications[0].document_id.upper()
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        table = self._table("classifications")
        table.delete(f"document_id = '{scoped_document_id}'")
        payload: list[dict[str, Any]] = []
        for item in classifications:
            record = item.model_dump()
            record["document_id"] = _to_scoped_document_id(item.document_id, normalized_workspace)
            payload.append(record)
        table.add(payload)

    def get_classifications(self, document_id: str, workspace: str | None = None) -> list[DocumentClassification]:
        """Return classifications for a TDoc."""
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("classifications")
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        records = [record for record in _table_to_records(table) if record.get("document_id") == scoped_document_id]
        classifications: list[DocumentClassification] = []
        for record in records:
            unscoped_record = dict(record)
            unscoped_record["document_id"] = _from_scoped_document_id(str(record.get("document_id", "")))[1]
            classifications.append(DocumentClassification(**unscoped_record))
        return sorted(
            classifications,
            key=lambda item: (
                not item.is_main_document,
                -item.confidence,
                item.file_path.lower(),
            ),
        )

    def get_main_classification(self, document_id: str, workspace: str | None = None) -> DocumentClassification | None:
        """Return the main document classification for a TDoc if available."""
        classifications = self.get_classifications(document_id, workspace=workspace)
        for classification in classifications:
            if classification.is_main_document:
                return classification
        return None

    def save_chunks(self, chunks: list[DocumentChunk], workspace: str | None = None) -> None:
        """Persist embedded chunks for a TDoc."""
        if not chunks:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        document_id = chunks[0].document_id
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        table = self._table("chunks")
        table.delete(f"document_id = '{scoped_document_id}'")
        payload: list[dict[str, Any]] = []
        for item in chunks:
            record = item.model_dump()
            record["document_id"] = _to_scoped_document_id(item.document_id, normalized_workspace)
            payload.append(record)
        table.add(payload)

    def get_chunks(self, document_id: str, workspace: str | None = None) -> list[DocumentChunk]:
        """Return chunks for a TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        table = self._table("chunks")
        records = _table_to_records(table)
        chunks: list[DocumentChunk] = []
        for record in records:
            if record.get("document_id") == scoped_document_id:
                unscoped_record = dict(record)
                unscoped_record["document_id"] = _from_scoped_document_id(scoped_document_id)[1]
                # Handle NaN for optional fields
                for field in ["section_heading", "section_number"]:
                    if field in unscoped_record and (unscoped_record[field] is None or _is_nan(unscoped_record[field])):
                        unscoped_record[field] = None
                chunks.append(DocumentChunk(**unscoped_record))
        return chunks

    def search_chunks(
        self,
        query_vector: list[float],
        top_k: int,
        workspace: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return top-k similar chunks for a query vector."""
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("chunks")
        results = table.search(query_vector, vector_column_name="vector").limit(top_k * 4).to_list()
        output: list[tuple[DocumentChunk, float]] = []
        for record in results:
            score = record.get("_distance")
            cleaned_record = _strip_distance(record)
            record_workspace, unscoped_document_id = _from_scoped_document_id(str(cleaned_record.get("document_id", "")))
            if record_workspace != normalized_workspace:
                continue
            cleaned_record["document_id"] = unscoped_document_id
            # Handle NaN for optional fields
            for field in ["section_heading", "section_number"]:
                if field in cleaned_record and (cleaned_record[field] is None or _is_nan(cleaned_record[field])):
                    cleaned_record[field] = None
            chunk = DocumentChunk(**cleaned_record)
            output.append((chunk, float(score) if score is not None else 0.0))
            if len(output) >= top_k:
                break
        return output

    def save_summary(self, summary: DocumentSummary, workspace: str | None = None) -> None:
        """Persist summary for a TDoc."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_document_id = _to_scoped_document_id(summary.document_id, normalized_workspace)
        table = self._table("summaries")
        table.delete(f"document_id = '{scoped_document_id}'")
        payload = summary.model_dump()
        payload["document_id"] = scoped_document_id
        table.add([payload])

    def get_summary(self, document_id: str, workspace: str | None = None) -> DocumentSummary | None:
        """Return summary for a TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_document_id = _to_scoped_document_id(document_id, normalized_workspace)
        table = self._table("summaries")
        records = _table_to_records(table)
        for record in records:
            if record.get("document_id") == scoped_document_id:
                unscoped_record = dict(record)
                unscoped_record["document_id"] = _from_scoped_document_id(scoped_document_id)[1]
                return DocumentSummary(**unscoped_record)
        return None

    def clear_workspace_artifacts(self, workspace_name: str | None) -> int:
        """Clear all AI artifacts (embeddings, summaries, etc.) for a workspace while preserving members.

        Args:
            workspace_name: Name of workspace.

        Returns:
            Number of artifact records removed.
        """
        normalized_workspace = _normalize_workspace_name(workspace_name)
        removed_count = 0

        artifact_tables = ["processing_status", "classifications", "chunks", "summaries", "graph_nodes", "graph_edges"]

        for table_name in artifact_tables:
            try:
                table = self._table(table_name)
                all_records = _table_to_records(table)
                for record in all_records:
                    document_id = record.get("document_id", "")
                    record_workspace, _ = _from_scoped_document_id(document_id)
                    if record_workspace == normalized_workspace:
                        table.delete(f"document_id = '{document_id}'")
                        removed_count += 1
            except Exception as exc:
                _logger.warning(f"Failed to clear artifacts from {table_name}: {exc}")

        _logger.info(f"Cleared {removed_count} artifact(s) for workspace '{normalized_workspace}'")
        return removed_count

    def save_nodes(self, nodes: list[GraphNode], workspace: str | None = None) -> None:
        """Persist graph nodes."""
        if not nodes:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("graph_nodes")

        scoped_ids = [_to_scoped_document_id(node.node_id, normalized_workspace) for node in nodes]
        _delete_by_ids(table, "node_id", scoped_ids)

        payload = []
        for node in nodes:
            record = _node_record(node)
            record["node_id"] = _to_scoped_document_id(node.node_id, normalized_workspace)
            payload.append(record)

        table.add(payload)

    def save_edges(self, edges: list[GraphEdge], workspace: str | None = None) -> None:
        """Persist graph edges."""
        if not edges:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("graph_edges")

        scoped_ids = [_to_scoped_document_id(edge.edge_id, normalized_workspace) for edge in edges]
        _delete_by_ids(table, "edge_id", scoped_ids)

        payload = []
        for edge in edges:
            record = edge.model_dump()
            record["edge_id"] = _to_scoped_document_id(edge.edge_id, normalized_workspace)
            record["source_id"] = _to_scoped_document_id(edge.source_id, normalized_workspace)
            record["target_id"] = _to_scoped_document_id(edge.target_id, normalized_workspace)
            payload.append(record)

        table.add(payload)

    def query_graph(self, filters: dict[str, Any], workspace: str | None = None) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Return graph nodes and edges matching provided filters."""
        normalized_workspace = _normalize_workspace_name(workspace)

        raw_nodes = [_node_from_record(record) for record in _table_to_records(self._table("graph_nodes"))]
        raw_edges = [GraphEdge(**record) for record in _table_to_records(self._table("graph_edges"))]

        nodes: list[GraphNode] = []
        for node in raw_nodes:
            record_workspace, unscoped_node_id = _from_scoped_document_id(node.node_id)
            if record_workspace == normalized_workspace:
                node.node_id = unscoped_node_id
                nodes.append(node)

        edges: list[GraphEdge] = []
        for edge in raw_edges:
            record_workspace, unscoped_edge_id = _from_scoped_document_id(edge.edge_id)
            if record_workspace == normalized_workspace:
                edge.edge_id = unscoped_edge_id
                edge.source_id = _from_scoped_document_id(edge.source_id)[1]
                edge.target_id = _from_scoped_document_id(edge.target_id)[1]
                edges.append(edge)

        node_types = filters.get("node_types") if filters else None
        if node_types:
            nodes = [node for node in nodes if node.node_type.value in node_types]

        return nodes, edges

    def get_all_graph_nodes(self, workspace: str | None = None) -> list[GraphNode]:
        """Return all graph nodes for a workspace."""
        nodes, _ = self.query_graph(filters={}, workspace=workspace)
        return nodes

    def get_all_graph_edges(self, workspace: str | None = None) -> list[GraphEdge]:
        """Return all graph edges for a workspace."""
        _, edges = self.query_graph(filters={}, workspace=workspace)
        return edges

    def _ensure_tables(self) -> None:
        self._ensure_table("processing_status", _processing_status_schema())
        self._ensure_table("classifications", _classification_schema())
        self._ensure_table("chunks", _chunk_schema(self.embedding_dimension))
        self._ensure_table("summaries", _summary_schema())
        self._ensure_table("graph_nodes", _graph_node_schema())
        self._ensure_table("graph_edges", _graph_edge_schema())

    def _ensure_table(self, name: str, schema: pa.Schema) -> None:
        # First, try to open existing table (handles case where table exists on disk
        # but list_tables() doesn't return it - can happen with LanceDB)
        try:
            existing_table = self._db.open_table(name)
            existing_schema = existing_table.schema
            # Compare field names AND types (especially vector dimensions)
            existing_fields = {f.name: f.type for f in existing_schema}
            new_fields = {f.name: f.type for f in schema}
            if existing_fields != new_fields:
                # Schema mismatch - drop and recreate
                self._db.drop_table(name)
                self._tables[name] = self._db.create_table(name, schema=schema)
            else:
                self._tables[name] = existing_table
            return
        except FileNotFoundError:
            # Table doesn't exist, continue to create it
            pass

        # Create the table, handling race condition where it might be created
        # by another process/thread between our check and create
        try:
            self._tables[name] = self._db.create_table(name, schema=schema)
        except ValueError as exc:
            if "already exists" in str(exc).lower():
                # Race condition - table was created by another process
                # Open the existing table
                self._tables[name] = self._db.open_table(name)
            else:
                raise

    def _table(self, name: str) -> LanceDBTable:
        return self._tables[name]


def _table_to_records(table: LanceDBTable) -> list[dict[str, Any]]:
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


def _is_nan(val: Any) -> bool:
    """Check if value is NaN."""
    if val is None:
        return False
    if isinstance(val, float):
        return math.isnan(val)
    return False


def _is_nat(val: Any) -> bool:
    """Check if value is pandas NaT (Not-a-Time)."""
    if val is None:
        return False
    # Check for pandas NaT type
    return type(val).__name__ == "NaTType"


def _normalize_workspace_name(workspace: str | None) -> str:
    if workspace is None:
        return DEFAULT_WORKSPACE
    normalized = workspace.strip().lower()
    if not normalized:
        return DEFAULT_WORKSPACE
    return normalized


def _to_scoped_document_id(document_id: str, workspace: str | None) -> str:
    normalized_document_id = document_id.strip().upper()
    normalized_workspace = _normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        return normalized_document_id
    return f"{normalized_workspace}{_SCOPE_DELIMITER}{normalized_document_id}"


def _from_scoped_document_id(value: str) -> tuple[str, str]:
    if _SCOPE_DELIMITER not in value:
        return DEFAULT_WORKSPACE, value.strip().upper()
    workspace, document_id = value.split(_SCOPE_DELIMITER, maxsplit=1)
    return _normalize_workspace_name(workspace), document_id.strip().upper()


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
            pa.field("document_id", pa.string()),
            pa.field("current_stage", pa.string()),
            pa.field("classified_at", pa.timestamp("us"), nullable=True),
            pa.field("extracted_at", pa.timestamp("us"), nullable=True),
            pa.field("embedded_at", pa.timestamp("us"), nullable=True),
            pa.field("summarized_at", pa.timestamp("us"), nullable=True),
            pa.field("graphed_at", pa.timestamp("us"), nullable=True),
            pa.field("completed_at", pa.timestamp("us"), nullable=True),
            pa.field("error_message", pa.string(), nullable=True),
            pa.field("source_hash", pa.string(), nullable=True),
            pa.field("keywords", pa.list_(pa.string()), nullable=True),
            pa.field("detected_language", pa.string(), nullable=True),
        ]
    )


def _classification_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("document_id", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("is_main_document", pa.bool_()),
            pa.field("confidence", pa.float32()),
            pa.field("decisive_heuristic", pa.string()),
            pa.field("file_size_bytes", pa.int64()),
            pa.field("classified_at", pa.timestamp("us")),
        ]
    )


def _chunk_schema(embedding_dimension: int) -> pa.Schema:
    """Create schema for document chunks with fixed-size vector.

    Args:
        pa.field("vector", pa.list_(pa.float32(), embedding_dimension)),

    Returns:
        PyArrow schema with FixedSizeList vector field.
    """
    return pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("section_heading", pa.string(), nullable=True),
            pa.field("chunk_index", pa.int64()),
            pa.field("text", pa.large_string()),
            pa.field("char_offset_start", pa.int64()),
            pa.field("char_offset_end", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), embedding_dimension)),
            pa.field("embedding_model", pa.string()),
            pa.field("created_at", pa.timestamp("us")),
        ]
    )


def _summary_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("document_id", pa.string()),
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


__all__ = ["DEFAULT_WORKSPACE", "AiStorage"]
