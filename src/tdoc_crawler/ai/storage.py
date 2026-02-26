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
    Workspace,
    WorkspaceMember,
    WorkspaceStatus,
)
from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)

DEFAULT_WORKSPACE = "default"
_SCOPE_DELIMITER = "::"


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
        self._embedding_hashes: dict[str, str] = {}
        self._summary_hashes: dict[str, str] = {}
        self._ensure_tables()

    def save_embedding_hash(self, tdoc_id: str, content_hash: str) -> None:
        """Persist the latest embedding content hash for idempotency checks."""
        self._embedding_hashes[tdoc_id.upper()] = content_hash

    def get_embedding_hash(self, tdoc_id: str) -> str | None:
        """Return previously persisted embedding content hash if present."""
        return self._embedding_hashes.get(tdoc_id.upper())

    def save_summary_hash(self, tdoc_id: str, content_hash: str) -> None:
        """Persist the latest summary content hash for idempotency checks."""
        self._summary_hashes[tdoc_id.upper()] = content_hash

    def get_summary_hash(self, tdoc_id: str) -> str | None:
        """Return previously persisted summary content hash if present."""
        return self._summary_hashes.get(tdoc_id.upper())

    def save_status(self, status: ProcessingStatus, workspace: str | None = None) -> None:
        """Persist processing status for a TDoc."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_tdoc_id = _to_scoped_tdoc_id(status.tdoc_id, normalized_workspace)
        table = self._table("processing_status")
        table.delete(f"tdoc_id = '{scoped_tdoc_id}'")
        payload = status.model_dump()
        payload["tdoc_id"] = scoped_tdoc_id
        # Ensure keywords is always a list for pyarrow list<string> schema
        if payload.get("keywords") is None:
            payload["keywords"] = []
        table.add([payload])

    def get_status(self, tdoc_id: str, workspace: str | None = None) -> ProcessingStatus | None:
        """Return status for a single TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        table = self._table("processing_status")
        records = _table_to_records(table)
        for record in records:
            if record.get("tdoc_id") == scoped_tdoc_id:
                unscoped_record = dict(record)
                unscoped_record["tdoc_id"] = _from_scoped_tdoc_id(scoped_tdoc_id)[1]
                # Handle NaN values for optional strings from LanceDB
                for field in ["error_message", "source_hash", "detected_language"]:
                    if field in unscoped_record and (unscoped_record[field] is None or _is_nan(unscoped_record[field])):
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
            raw_tdoc_id = str(record.get("tdoc_id", ""))
            record_workspace, unscoped_tdoc_id = _from_scoped_tdoc_id(raw_tdoc_id)
            if record_workspace != normalized_workspace:
                continue
            unscoped_record = dict(record)
            unscoped_record["tdoc_id"] = unscoped_tdoc_id
            # Handle NaN values for optional strings from LanceDB
            for field in ["error_message", "source_hash", "detected_language"]:
                if field in unscoped_record and (unscoped_record[field] is None or _is_nan(unscoped_record[field])):
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
        tdoc_id = classifications[0].tdoc_id.upper()
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        table = self._table("classifications")
        table.delete(f"tdoc_id = '{scoped_tdoc_id}'")
        payload: list[dict[str, Any]] = []
        for item in classifications:
            record = item.model_dump()
            record["tdoc_id"] = _to_scoped_tdoc_id(item.tdoc_id, normalized_workspace)
            payload.append(record)
        table.add(payload)

    def get_classifications(self, tdoc_id: str, workspace: str | None = None) -> list[DocumentClassification]:
        """Return classifications for a TDoc."""
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("classifications")
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        records = [record for record in _table_to_records(table) if record.get("tdoc_id") == scoped_tdoc_id]
        classifications: list[DocumentClassification] = []
        for record in records:
            unscoped_record = dict(record)
            unscoped_record["tdoc_id"] = _from_scoped_tdoc_id(str(record.get("tdoc_id", "")))[1]
            classifications.append(DocumentClassification(**unscoped_record))
        return sorted(
            classifications,
            key=lambda item: (
                not item.is_main_document,
                -item.confidence,
                item.file_path.lower(),
            ),
        )

    def get_main_classification(self, tdoc_id: str, workspace: str | None = None) -> DocumentClassification | None:
        """Return the main document classification for a TDoc if available."""
        classifications = self.get_classifications(tdoc_id, workspace=workspace)
        for classification in classifications:
            if classification.is_main_document:
                return classification
        return None

    def save_chunks(self, chunks: list[DocumentChunk], workspace: str | None = None) -> None:
        """Persist embedded chunks for a TDoc."""
        if not chunks:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        tdoc_id = chunks[0].tdoc_id
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        table = self._table("chunks")
        table.delete(f"tdoc_id = '{scoped_tdoc_id}'")
        payload: list[dict[str, Any]] = []
        for item in chunks:
            record = item.model_dump()
            record["tdoc_id"] = _to_scoped_tdoc_id(item.tdoc_id, normalized_workspace)
            payload.append(record)
        table.add(payload)

    def get_chunks(self, tdoc_id: str, workspace: str | None = None) -> list[DocumentChunk]:
        """Return chunks for a TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        table = self._table("chunks")
        records = _table_to_records(table)
        chunks: list[DocumentChunk] = []
        for record in records:
            if record.get("tdoc_id") == scoped_tdoc_id:
                unscoped_record = dict(record)
                unscoped_record["tdoc_id"] = _from_scoped_tdoc_id(scoped_tdoc_id)[1]
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
            record_workspace, unscoped_tdoc_id = _from_scoped_tdoc_id(str(cleaned_record.get("tdoc_id", "")))
            if record_workspace != normalized_workspace:
                continue
            cleaned_record["tdoc_id"] = unscoped_tdoc_id
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
        scoped_tdoc_id = _to_scoped_tdoc_id(summary.tdoc_id, normalized_workspace)
        table = self._table("summaries")
        table.delete(f"tdoc_id = '{scoped_tdoc_id}'")
        payload = summary.model_dump()
        payload["tdoc_id"] = scoped_tdoc_id
        table.add([payload])

    def get_summary(self, tdoc_id: str, workspace: str | None = None) -> DocumentSummary | None:
        """Return summary for a TDoc if present."""
        normalized_workspace = _normalize_workspace_name(workspace)
        scoped_tdoc_id = _to_scoped_tdoc_id(tdoc_id, normalized_workspace)
        table = self._table("summaries")
        records = _table_to_records(table)
        for record in records:
            if record.get("tdoc_id") == scoped_tdoc_id:
                unscoped_record = dict(record)
                unscoped_record["tdoc_id"] = _from_scoped_tdoc_id(scoped_tdoc_id)[1]
                return DocumentSummary(**unscoped_record)
        return None

    def create_workspace(self, workspace_name: str | None) -> Workspace:
        """Create or update a workspace entry."""
        normalized_workspace = _normalize_workspace_name(workspace_name)
        existing = self.get_workspace(normalized_workspace)
        now_record = Workspace(
            workspace_name=normalized_workspace,
            is_default=normalized_workspace == DEFAULT_WORKSPACE,
            status=WorkspaceStatus.ACTIVE,
        )
        if existing is not None:
            now_record.created_at = existing.created_at
            now_record.updated_at = now_record.created_at if existing.status == WorkspaceStatus.ARCHIVED else now_record.updated_at
        table = self._table("workspaces")
        table.delete(f"workspace_name = '{normalized_workspace}'")
        table.add([now_record.model_dump()])
        return self.get_workspace(normalized_workspace) or now_record

    def get_workspace(self, workspace_name: str | None) -> Workspace | None:
        """Return a workspace by name if present."""
        normalized_workspace = _normalize_workspace_name(workspace_name)
        table = self._table("workspaces")
        for record in _table_to_records(table):
            if record.get("workspace_name") == normalized_workspace:
                return Workspace(**record)
        return None

    def ensure_workspace(self, workspace_name: str | None) -> Workspace:
        """Ensure a workspace exists and return it."""
        normalized_workspace = _normalize_workspace_name(workspace_name)
        existing = self.get_workspace(normalized_workspace)
        if existing is not None:
            return existing
        return self.create_workspace(normalized_workspace)

    def list_workspaces(self) -> list[Workspace]:
        """Return all configured workspaces."""
        table = self._table("workspaces")
        return sorted(
            [Workspace(**record) for record in _table_to_records(table)],
            key=lambda item: (not item.is_default, item.workspace_name),
        )

    def delete_workspace(self, workspace_name: str | None, preserve_artifacts: bool = True) -> bool:
        """Delete a workspace and optionally its members.

        Artifacts (processing_status, classifications, chunks, summaries, graph nodes/edges)
        are PRESERVED by default to prevent data loss. They remain in storage but become
        orphaned (not associated with any active workspace).

        Args:
            workspace_name: Name of workspace to delete.
            preserve_artifacts: If True, keep artifacts. If False, also delete workspace artifacts.

        Returns:
            True if workspace was deleted, False if not found or if attempting to delete default.
        """
        normalized_workspace = _normalize_workspace_name(workspace_name)

        # Prevent deletion of default workspace
        if normalized_workspace == DEFAULT_WORKSPACE:
            _logger.warning("Cannot delete the default workspace")
            return False

        # Check if workspace exists
        existing = self.get_workspace(normalized_workspace)
        if existing is None:
            return False

        # Delete workspace members (always delete members, not artifacts)
        table = self._table("workspace_members")
        table.delete(f"workspace_name = '{normalized_workspace}'")

        # Delete the workspace record
        table = self._table("workspaces")
        table.delete(f"workspace_name = '{normalized_workspace}'")

        # Optionally delete artifacts (these become orphaned otherwise)
        if not preserve_artifacts:
            for table_name in ["processing_status", "classifications", "chunks", "summaries", "graph_nodes", "graph_edges"]:
                try:
                    table = self._table(table_name)
                    # Delete all scoped items for this workspace
                    all_records = _table_to_records(table)
                    for record in all_records:
                        tdoc_id = record.get("tdoc_id", "")
                        record_workspace, _ = _from_scoped_tdoc_id(tdoc_id)
                        if record_workspace == normalized_workspace:
                            table.delete(f"tdoc_id = '{tdoc_id}'")
                except Exception as exc:
                    _logger.warning(f"Failed to delete artifacts from {table_name}: {exc}")

        _logger.info(f"Deleted workspace '{normalized_workspace}' (artifacts preserved: {preserve_artifacts})")
        return True

    def add_workspace_members(self, workspace_name: str | None, members: list[WorkspaceMember]) -> int:
        """Add or reactivate source items for a workspace."""
        workspace = self.ensure_workspace(workspace_name)
        if not members:
            return 0

        table = self._table("workspace_members")
        added_count = 0
        for member in members:
            normalized_member = WorkspaceMember(
                workspace_name=workspace.workspace_name,
                source_item_id=member.source_item_id,
                source_path=member.source_path,
                source_kind=member.source_kind,
                added_by=member.added_by,
                is_active=True,
            )
            predicate = f"workspace_name = '{normalized_member.workspace_name}' and source_item_id = '{normalized_member.source_item_id}'"
            table.delete(predicate)
            table.add([normalized_member.model_dump()])
            added_count += 1
        return added_count

    def list_workspace_members(
        self,
        workspace_name: str | None,
        include_inactive: bool = False,
    ) -> list[WorkspaceMember]:
        """List members for a workspace."""
        workspace = self.ensure_workspace(workspace_name)
        table = self._table("workspace_members")
        members: list[WorkspaceMember] = []
        for record in _table_to_records(table):
            if record.get("workspace_name") != workspace.workspace_name:
                continue
            # Handle NaN values from LanceDB
            if "added_by" in record and (record["added_by"] is None or _is_nan(record["added_by"])):
                record["added_by"] = ""
            member = WorkspaceMember(**record)
            if not include_inactive and not member.is_active:
                continue
            members.append(member)
        return sorted(members, key=lambda item: item.source_item_id)

    def deactivate_workspace_member(self, workspace_name: str | None, source_item_id: str) -> bool:
        """Deactivate a workspace member if it exists."""
        workspace = self.ensure_workspace(workspace_name)
        normalized_source_item_id = source_item_id.strip().upper()
        if not normalized_source_item_id:
            return False

        table = self._table("workspace_members")
        records = _table_to_records(table)
        for record in records:
            if record.get("workspace_name") != workspace.workspace_name:
                continue
            if record.get("source_item_id") != normalized_source_item_id:
                continue
            # Handle NaN values from LanceDB
            if "added_by" in record:
                record["added_by"] = ""
            member = WorkspaceMember(**record)
            if not member.is_active:
                return True
            member.is_active = False
            predicate = f"workspace_name = '{member.workspace_name}' and source_item_id = '{member.source_item_id}'"
            table.delete(predicate)
            table.add([member.model_dump()])
            return True
        return False

    def remove_workspace_member(self, workspace_name: str | None, source_item_id: str) -> bool:
        """Alias for deactivate_workspace_member for API consistency."""
        return self.deactivate_workspace_member(workspace_name, source_item_id)

    def save_nodes(self, nodes: list[GraphNode], workspace: str | None = None) -> None:
        """Persist graph nodes."""
        if not nodes:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("graph_nodes")

        scoped_ids = [_to_scoped_tdoc_id(node.node_id, normalized_workspace) for node in nodes]
        _delete_by_ids(table, "node_id", scoped_ids)

        payload = []
        for node in nodes:
            record = _node_record(node)
            record["node_id"] = _to_scoped_tdoc_id(node.node_id, normalized_workspace)
            payload.append(record)

        table.add(payload)

    def save_edges(self, edges: list[GraphEdge], workspace: str | None = None) -> None:
        """Persist graph edges."""
        if not edges:
            return
        normalized_workspace = _normalize_workspace_name(workspace)
        table = self._table("graph_edges")

        scoped_ids = [_to_scoped_tdoc_id(edge.edge_id, normalized_workspace) for edge in edges]
        _delete_by_ids(table, "edge_id", scoped_ids)

        payload = []
        for edge in edges:
            record = edge.model_dump()
            record["edge_id"] = _to_scoped_tdoc_id(edge.edge_id, normalized_workspace)
            record["source_id"] = _to_scoped_tdoc_id(edge.source_id, normalized_workspace)
            record["target_id"] = _to_scoped_tdoc_id(edge.target_id, normalized_workspace)
            payload.append(record)

        table.add(payload)

    def query_graph(self, filters: dict[str, Any], workspace: str | None = None) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Return graph nodes and edges matching provided filters."""
        normalized_workspace = _normalize_workspace_name(workspace)

        raw_nodes = [_node_from_record(record) for record in _table_to_records(self._table("graph_nodes"))]
        raw_edges = [GraphEdge(**record) for record in _table_to_records(self._table("graph_edges"))]

        nodes: list[GraphNode] = []
        for node in raw_nodes:
            record_workspace, unscoped_node_id = _from_scoped_tdoc_id(node.node_id)
            if record_workspace == normalized_workspace:
                node.node_id = unscoped_node_id
                nodes.append(node)

        edges: list[GraphEdge] = []
        for edge in raw_edges:
            record_workspace, unscoped_edge_id = _from_scoped_tdoc_id(edge.edge_id)
            if record_workspace == normalized_workspace:
                edge.edge_id = unscoped_edge_id
                edge.source_id = _from_scoped_tdoc_id(edge.source_id)[1]
                edge.target_id = _from_scoped_tdoc_id(edge.target_id)[1]
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
        self._ensure_table("workspaces", _workspace_schema())
        self._ensure_table("workspace_members", _workspace_member_schema())
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


def _is_nan(val: Any) -> bool:
    """Check if value is NaN."""
    if val is None:
        return False
    if isinstance(val, float):
        return math.isnan(val)
    return False


def _normalize_workspace_name(workspace: str | None) -> str:
    if workspace is None:
        return DEFAULT_WORKSPACE
    normalized = workspace.strip().lower()
    if not normalized:
        return DEFAULT_WORKSPACE
    return normalized


def _to_scoped_tdoc_id(tdoc_id: str, workspace: str | None) -> str:
    normalized_tdoc_id = tdoc_id.strip().upper()
    normalized_workspace = _normalize_workspace_name(workspace)
    if normalized_workspace == DEFAULT_WORKSPACE:
        return normalized_tdoc_id
    return f"{normalized_workspace}{_SCOPE_DELIMITER}{normalized_tdoc_id}"


def _from_scoped_tdoc_id(value: str) -> tuple[str, str]:
    if _SCOPE_DELIMITER not in value:
        return DEFAULT_WORKSPACE, value.strip().upper()
    workspace, tdoc_id = value.split(_SCOPE_DELIMITER, maxsplit=1)
    return _normalize_workspace_name(workspace), tdoc_id.strip().upper()


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
            pa.field("keywords", pa.list_(pa.string()), nullable=True),
            pa.field("detected_language", pa.string(), nullable=True),
        ]
    )


def _workspace_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("workspace_name", pa.string()),
            pa.field("created_at", pa.timestamp("us")),
            pa.field("updated_at", pa.timestamp("us")),
            pa.field("is_default", pa.bool_()),
            pa.field("status", pa.string()),
        ]
    )


def _workspace_member_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("workspace_name", pa.string()),
            pa.field("source_item_id", pa.string()),
            pa.field("source_path", pa.string()),
            pa.field("source_kind", pa.string()),
            pa.field("added_at", pa.timestamp("us")),
            pa.field("added_by", pa.string(), nullable=True),
            pa.field("is_active", pa.bool_()),
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


__all__ = ["DEFAULT_WORKSPACE", "AiStorage"]
