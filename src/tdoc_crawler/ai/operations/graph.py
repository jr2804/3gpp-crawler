"""Knowledge graph construction and querying for 3GPP TDocs."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType, GraphQueryResult
from tdoc_crawler.ai.storage import AiStorage

logger = logging.getLogger(__name__)


def extract_tdoc_references(text: str) -> list[str]:
    """Extract TDoc IDs from text using regex patterns."""
    patterns = [r"\b([A-Z]{1,2}\d+-\d+)\b", r"\b(\d{5}-j\d+)\b"]
    tdocs = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        tdocs.update(matches)
    return sorted(tdocs)


def extract_spec_references(text: str) -> list[str]:
    """Extract 3GPP spec numbers from text."""
    pattern = r"\b((?:TS|TR|TG)\s*\d+\.\d+(?:\.\d+)?)\b"
    specs = re.findall(pattern, text, re.IGNORECASE)
    return sorted(set(specs))


def extract_meeting_references(text: str) -> list[str]:
    """Extract meeting codes from text."""
    pattern = r"\b((?:SA|RP|RAN|CT)\d*#\d+[a-z]?)\b"
    meetings = re.findall(pattern, text, re.IGNORECASE)
    return sorted(set(meetings))


def build_graph(
    tdoc_id: str,
    markdown: str,
    meeting_id: str | None = None,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build knowledge graph from TDoc content with incremental updates."""
    if storage is None:
        config = AiConfig.from_env(cache_manager_name="default")
        store_path = config.ai_store_path
        if store_path is None:
            msg = "AI store path not configured"
            raise ValueError(msg)
        storage = AiStorage(store_path)

    existing_nodes, existing_edges = storage.query_graph(filters={}, workspace=workspace)
    existing_node_ids = {n.node_id for n in existing_nodes}
    existing_edge_ids = {e.edge_id for e in existing_edges}

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    now = datetime.now()

    if tdoc_id not in existing_node_ids:
        nodes.append(
            GraphNode(
                node_id=tdoc_id,
                node_type=GraphNodeType.TDOC,
                label=f"TDoc {tdoc_id}",
                properties={"title": f"TDoc {tdoc_id}", "created_at": now.isoformat()},
                created_at=now,
            )
        )

    referenced_tdocs = extract_tdoc_references(markdown)
    referenced_specs = extract_spec_references(markdown)
    referenced_meetings = extract_meeting_references(markdown)

    for ref_tdoc in referenced_tdocs:
        if ref_tdoc != tdoc_id and ref_tdoc not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=ref_tdoc,
                    node_type=GraphNodeType.TDOC,
                    label=f"TDoc {ref_tdoc}",
                    properties={"title": f"TDoc {ref_tdoc}"},
                    created_at=now,
                )
            )

        edge_id = f"{tdoc_id}->{GraphEdgeType.REFERENCES.value}->{ref_tdoc}"
        if ref_tdoc != tdoc_id and edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=tdoc_id,
                    target_id=ref_tdoc,
                    edge_type=GraphEdgeType.REFERENCES,
                    temporal_context=meeting_id,
                    provenance="extracted_tdoc_reference",
                )
            )

    for spec in referenced_specs:
        if spec not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=spec,
                    node_type=GraphNodeType.SPEC,
                    label=spec,
                    properties={"spec_id": spec},
                    created_at=now,
                )
            )

        edge_id = f"{tdoc_id}->{GraphEdgeType.REFERENCES.value}->{spec}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=tdoc_id,
                    target_id=spec,
                    edge_type=GraphEdgeType.REFERENCES,
                    temporal_context=meeting_id,
                    provenance="extracted_spec_reference",
                )
            )

    for meeting in referenced_meetings:
        if meeting not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=meeting,
                    node_type=GraphNodeType.MEETING,
                    label=meeting,
                    properties={"meeting_id": meeting},
                    created_at=now,
                )
            )

        edge_id = f"{meeting}->{GraphEdgeType.DISCUSSES.value}->{tdoc_id}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=meeting,
                    target_id=tdoc_id,
                    edge_type=GraphEdgeType.DISCUSSES,
                    temporal_context=meeting_id,
                    provenance="extracted_meeting_reference",
                )
            )

    logger.info(f"Built graph for {tdoc_id}: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


def query_graph(
    query: str,
    node_types: list[GraphNodeType] | None = None,
    top_k: int = 10,
    meeting_ids: list[str] | None = None,
    date_range: tuple[datetime, datetime] | None = None,
    storage: AiStorage | None = None,
) -> list[GraphQueryResult]:
    """Query the knowledge graph with temporal filtering and chronological sorting."""
    if storage is None:
        config = AiConfig.from_env(cache_manager_name="default")
        store_path = config.ai_store_path
        if store_path is None:
            msg = "AI store path not configured"
            raise ValueError(msg)
        storage = AiStorage(store_path)

    nodes = storage.get_all_graph_nodes()
    edges = storage.get_all_graph_edges()

    matching_nodes = [n for n in nodes if not node_types or n.node_type in node_types]

    if meeting_ids:
        filtered = []
        for node in matching_nodes:
            node_meeting = (node.properties or {}).get("meeting_id", "")
            if any(mid.upper() in node_meeting.upper() for mid in meeting_ids):
                filtered.append(node)
        matching_nodes = filtered

    if date_range:
        start_date, end_date = date_range
        matching_nodes = [n for n in matching_nodes if n.created_at and start_date <= n.created_at <= end_date]

    matching_nodes.sort(key=lambda n: n.created_at or datetime.min)
    matching_nodes = matching_nodes[:top_k]

    results = []
    for node in matching_nodes:
        node_edges = [e for e in edges if node.node_id in (e.source_id, e.target_id)]
        results.append(GraphQueryResult(node=node, connected_edges=node_edges))

    logger.info(f"Graph query '{query}' returned {len(results)} results")
    return results


def get_tdoc_evolution(tdoc_id: str, storage: AiStorage | None = None) -> list[GraphNode]:
    """Get evolution chain for a TDoc (revisions, supersessions)."""
    if storage is None:
        config = AiConfig.from_env(cache_manager_name="default")
        store_path = config.ai_store_path
        if store_path is None:
            msg = "AI store path not configured"
            raise ValueError(msg)
        storage = AiStorage(store_path)

    nodes, edges = storage.query_graph(filters={})
    related_ids = {tdoc_id}

    for edge in edges:
        if edge.edge_type in [GraphEdgeType.REVISES, GraphEdgeType.SUPERSEDES]:
            if edge.source_id == tdoc_id:
                related_ids.add(edge.target_id)
            elif edge.target_id == tdoc_id:
                related_ids.add(edge.source_id)

    related_nodes = [n for n in nodes if n.node_id in related_ids and n.node_type == GraphNodeType.TDOC]
    related_nodes.sort(key=lambda n: n.created_at or datetime.min)
    return related_nodes
