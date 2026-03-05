"""Knowledge graph construction and querying for 3GPP TDocs."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from tdoc_ai.container import AiServiceContainer
from tdoc_ai.models import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType, GraphQueryResult
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.storage import AiStorage

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


def extract_company_entities(text: str) -> list[str]:
    """Extract company/organization names from text.

    Matches common 3GPP contributor names.
    """
    companies = [
        "Huawei",
        "Nokia",
        "Ericsson",
        "Samsung",
        "Qualcomm",
        "Intel",
        "LG",
        "Motorola",
        "ZTE",
        "Cisco",
        "Vivo",
        "Oppo",
        "Xiaomi",
        "Apple",
        "Google",
        "OnePlus",
        "Realme",
        "Sony",
        "NTT DOCOMO",
        "KDDI",
        "SoftBank",
        "SK Telecom",
        "KT",
        "China Mobile",
        "China Telecom",
        "China Unicom",
        "Deutsche Telekom",
        "Orange",
        "Telefonica",
        "TIM",
        "BT",
        "Vodafone",
        "AT&T",
        "Verizon",
        "T-Mobile",
        "MediaTek",
        "HiSilicon",
        "UNISOC",
        "Broadcom",
        "NXP",
        "Infineon",
        "InterDigital",
        "Panasonic",
        "Fujitsu",
        "NEC",
        "Mitsubishi",
        "Toshiba",
        "Lenovo",
        "HTC",
        "ASUS",
    ]
    found = []
    text_lower = text.lower()
    for company in companies:
        if company.lower() in text_lower:
            found.append(company)
    return sorted(set(found))


def extract_work_items(text: str) -> list[str]:
    """Extract 3GPP Work Item identifiers from text.

    Patterns: WI-12345, WI 12345, Work Item 12345
    """
    patterns = [
        r"\bWI[- ]?(\d{4,6})\b",
        r"\bWork Item[- ]?(\d{4,6})\b",
    ]
    wis = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            wis.add(f"WI-{m}")
    return sorted(wis)


def extract_change_requests(text: str) -> list[str]:
    """Extract 3GPP Change Request identifiers from text.

    Patterns: CR-1234, CR0001, Change Request 1234, CP-xxxxxx, SP-xxxxxx
    """
    patterns = [r"\bCR[- ]?(\d{3,6})\b", r"\bChange Request[- ]?(\d{3,6})\b", r"\bCP[- ]?(\d{2,3}\d{4,5})\b", r"\bSP[- ]?(\d{2,3}\d{4,5})\b"]
    crs = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            crs.add(f"CR-{m}")
    return sorted(crs)


def build_graph(
    document_id: str,
    markdown: str,
    meeting_id: str | None = None,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build knowledge graph from TDoc content with incremental updates."""
    if storage is None:
        storage = AiServiceContainer.get_instance().get_storage()

    existing_nodes, existing_edges = storage.query_graph(filters={}, workspace=workspace)
    existing_node_ids = {n.node_id for n in existing_nodes}
    existing_edge_ids = {e.edge_id for e in existing_edges}

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    now = datetime.now()

    if document_id not in existing_node_ids:
        nodes.append(
            GraphNode(
                node_id=document_id,
                node_type=GraphNodeType.DOCUMENT,
                label=f"TDoc {document_id}",
                properties={"title": f"TDoc {document_id}", "created_at": now.isoformat()},
                created_at=now,
            )
        )

    referenced_tdocs = extract_tdoc_references(markdown)
    referenced_specs = extract_spec_references(markdown)
    referenced_meetings = extract_meeting_references(markdown)
    company_entities = extract_company_entities(markdown)
    work_items = extract_work_items(markdown)
    change_requests = extract_change_requests(markdown)

    for ref_tdoc in referenced_tdocs:
        if ref_tdoc != document_id and ref_tdoc not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=ref_tdoc,
                    node_type=GraphNodeType.DOCUMENT,
                    label=f"TDoc {ref_tdoc}",
                    properties={"title": f"TDoc {ref_tdoc}"},
                    created_at=now,
                )
            )

        edge_id = f"{document_id}->{GraphEdgeType.REFERENCES.value}->{ref_tdoc}"
        if ref_tdoc != document_id and edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
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

        edge_id = f"{document_id}->{GraphEdgeType.REFERENCES.value}->{spec}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
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

        edge_id = f"{meeting}->{GraphEdgeType.DISCUSSES.value}->{document_id}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=meeting,
                    target_id=document_id,
                    edge_type=GraphEdgeType.DISCUSSES,
                    temporal_context=meeting_id,
                    provenance="extracted_meeting_reference",
                )
            )

    # Add company entities
    for company in company_entities:
        if company not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=company,
                    node_type=GraphNodeType.COMPANY,
                    label=company,
                    properties={"company_name": company},
                    created_at=now,
                )
            )
        edge_id = f"{document_id}->AUTHORED_BY->{company}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
                    target_id=company,
                    edge_type=GraphEdgeType.AUTHORED_BY,
                    temporal_context=meeting_id,
                    provenance="extracted_company_entity",
                )
            )

    # Add work items
    for wi in work_items:
        if wi not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=wi,
                    node_type=GraphNodeType.WORK_ITEM,
                    label=wi,
                    properties={"work_item_id": wi},
                    created_at=now,
                )
            )
        edge_id = f"{document_id}->DISCUSSES->{wi}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
                    target_id=wi,
                    edge_type=GraphEdgeType.DIScusSES,
                    temporal_context=meeting_id,
                    provenance="extracted_work_item",
                )
            )

    # Add change requests
    for cr in change_requests:
        if cr not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=cr,
                    node_type=GraphNodeType.CHANGE_REQUEST,
                    label=cr,
                    properties={"cr_id": cr},
                    created_at=now,
                )
            )
        edge_id = f"{document_id}->REFERENCES->{cr}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
                    target_id=cr,
                    edge_type=GraphEdgeType.REFERENCES,
                    temporal_context=meeting_id,
                    provenance="extracted_change_request",
                )
            )

    logger.info(f"Built graph for {document_id}: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


def query_graph(
    query: str,
    node_types: list[GraphNodeType] | None = None,
    meeting_ids: list[str] | None = None,
    date_range: tuple[datetime, datetime] | None = None,
    top_k: int = 10,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> dict:
    """Query knowledge graph for relevant nodes and edges.

    Args:
        query: Natural language query.
        node_types: Filter by node types.
        meeting_ids: Filter by meeting IDs.
        date_range: Filter by date range.
        top_k: Maximum number of results to return.
        storage: Optional storage instance.
        workspace: Workspace name for filtering.

    Returns:
        Dict with 'results' key containing list of GraphQueryResult objects.
    """
    if storage is None:
        storage = AiServiceContainer.get_instance().get_storage()

    normalized_workspace = normalize_workspace_name(workspace)

    nodes = storage.get_all_graph_nodes(workspace=normalized_workspace)
    edges = storage.get_all_graph_edges(workspace=normalized_workspace)

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
    return {"results": results}


def get_tdoc_evolution(document_id: str, storage: AiStorage) -> list[GraphNode]:
    """Get evolution chain for a TDoc (revisions, supersessions)."""
    nodes, edges = storage.query_graph(filters={})
    related_ids = {document_id}

    for edge in edges:
        if edge.edge_type in [GraphEdgeType.REVISES, GraphEdgeType.SUPERSEDES]:
            if edge.source_id == document_id:
                related_ids.add(edge.target_id)
            elif edge.target_id == document_id:
                related_ids.add(edge.source_id)

    related_nodes = [n for n in nodes if n.node_id in related_ids and n.node_type == GraphNodeType.DOCUMENT]
    related_nodes.sort(key=lambda n: n.created_at or datetime.min)
    return related_nodes
