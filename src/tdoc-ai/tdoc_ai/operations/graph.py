"""Knowledge graph construction and querying for 3GPP TDocs."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from tdoc_ai.config import AiConfig, GraphQueryLevel
from tdoc_ai.models import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType, GraphQueryResult
from tdoc_ai.operations.embeddings import EmbeddingsManager
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.storage import AiStorage
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase

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


def build_graph(
    document_id: str,
    markdown: str,
    meeting_id: str | None = None,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build knowledge graph from TDoc content with incremental updates."""
    if storage is None:
        config = AiConfig.from_env()
        storage = EmbeddingsManager(config).storage

    db_path = resolve_cache_manager().db_file

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
                valid_from=None,
                valid_to=None,
                properties={"title": f"TDoc {document_id}", "created_at": now.isoformat()},
                created_at=now,
            )
        )

    referenced_tdocs = extract_tdoc_references(markdown)
    referenced_specs = extract_spec_references(markdown)
    referenced_meetings = extract_meeting_references(markdown)
    company_entities = extract_company_entities(markdown)
    work_items = extract_work_items(markdown)

    for ref_tdoc in referenced_tdocs:
        if ref_tdoc != document_id and ref_tdoc not in existing_node_ids:
            nodes.append(
                GraphNode(
                    node_id=ref_tdoc,
                    node_type=GraphNodeType.DOCUMENT,
                    label=f"TDoc {ref_tdoc}",
                    valid_from=None,
                    valid_to=None,
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
                    weight=1.0,
                    temporal_context=meeting_id or "",
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
                    valid_from=None,
                    valid_to=None,
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
                    weight=1.0,
                    temporal_context=meeting_id or "",
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
                    valid_from=None,
                    valid_to=None,
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
                    weight=1.0,
                    temporal_context=meeting_id or "",
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
                    valid_from=None,
                    valid_to=None,
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
                    weight=1.0,
                    temporal_context=meeting_id or "",
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
                    valid_from=None,
                    valid_to=None,
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
                    edge_type=GraphEdgeType.DISCUSSES,
                    weight=1.0,
                    temporal_context=meeting_id or "",
                    provenance="extracted_work_item",
                )
            )

    _apply_metadata_enhancements(
        document_id=document_id,
        meeting_id=meeting_id,
        referenced_specs=referenced_specs,
        db_path=db_path,
        existing_node_ids=existing_node_ids,
        existing_edge_ids=existing_edge_ids,
        nodes=nodes,
        edges=edges,
        now=now,
    )

    logger.info(f"Built graph for {document_id}: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


def _apply_metadata_enhancements(
    document_id: str,
    meeting_id: str | None,
    referenced_specs: list[str],
    db_path: Path,
    existing_node_ids: set[str],
    existing_edge_ids: set[str],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    now: datetime,
) -> None:
    """Add metadata-based nodes and edges from the crawler database."""
    tdoc_metadata = _load_tdoc_metadata(document_id, db_path)
    _enhance_document_node(document_id, tdoc_metadata, nodes)
    _add_revision_edges(document_id, meeting_id, tdoc_metadata, db_path, existing_edge_ids, edges)
    _add_meeting_edges(document_id, meeting_id, tdoc_metadata, db_path, existing_node_ids, existing_edge_ids, nodes, edges, now)
    _enhance_spec_nodes(referenced_specs, db_path, nodes)


def _load_tdoc_metadata(document_id: str, db_path: Path) -> dict[str, object]:
    tdoc_metadata: dict[str, object] = {}
    with TDocDatabase(db_path) as tdoc_db:
        tdoc_record = tdoc_db._get_tdoc(document_id)
        if tdoc_record is None:
            return tdoc_metadata
        tdoc_metadata = {
            "tdoc_id": tdoc_record.tdoc_id,
            "meeting_id": tdoc_record.meeting_id,
            "title": tdoc_record.title,
            "url": tdoc_record.url,
            "source": tdoc_record.source,
            "contact": tdoc_record.contact,
            "tdoc_type": tdoc_record.tdoc_type,
            "for_purpose": tdoc_record.for_purpose,
            "agenda_item_nbr": str(tdoc_record.agenda_item_nbr) if tdoc_record.agenda_item_nbr else None,
            "agenda_item_text": tdoc_record.agenda_item_text,
            "status": tdoc_record.status,
            "is_revision_of": tdoc_record.is_revision_of,
            "file_size": tdoc_record.file_size,
            "date_created": tdoc_record.date_created,
            "date_retrieved": tdoc_record.date_retrieved,
            "date_updated": tdoc_record.date_updated,
        }
    return tdoc_metadata


def _enhance_document_node(document_id: str, metadata: dict[str, object], nodes: list[GraphNode]) -> None:
    if not metadata or document_id not in {node.node_id for node in nodes}:
        return
    for node in nodes:
        if node.node_id != document_id:
            continue
        enhanced_props = dict(node.properties)
        if metadata.get("title"):
            enhanced_props["title"] = metadata["title"]
        if metadata.get("status"):
            enhanced_props["status"] = metadata["status"]
        if metadata.get("source"):
            enhanced_props["source"] = metadata["source"]
        if metadata.get("tdoc_type"):
            enhanced_props["tdoc_type"] = metadata["tdoc_type"]
        if metadata.get("is_revision_of"):
            enhanced_props["is_revision_of"] = metadata["is_revision_of"]
        if metadata.get("date_created"):
            enhanced_props["date_created"] = str(metadata["date_created"])
        if metadata.get("date_updated"):
            enhanced_props["date_updated"] = str(metadata["date_updated"])
        node.properties = enhanced_props
        node.label = metadata.get("title", node.label)
        return


def _add_revision_edges(
    document_id: str,
    meeting_id: str | None,
    metadata: dict[str, object],
    db_path: Path,
    existing_edge_ids: set[str],
    edges: list[GraphEdge],
) -> None:
    if metadata.get("is_revision_of"):
        prev_doc = str(metadata["is_revision_of"]).upper()
        edge_id = f"{document_id}->REVISION_OF->{prev_doc}"
        if edge_id not in existing_edge_ids:
            weight = _compute_revision_weight(metadata)
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=document_id,
                    target_id=prev_doc,
                    edge_type=GraphEdgeType.REVISION_OF,
                    weight=weight,
                    temporal_context=meeting_id or "",
                    provenance="tdoc_metadata_is_revision_of",
                )
            )

    revisions: list[dict[str, object]] = []
    with TDocDatabase(db_path) as tdoc_db:
        records = tdoc_db._table_rows("tdocs")
        current = next((record for record in records if record.tdoc_id == document_id.upper()), None)
        if current is not None and current.is_revision_of:
            previous = next((record for record in records if record.tdoc_id == current.is_revision_of.upper()), None)
            if previous is not None:
                revisions.append(
                    {
                        "tdoc_id": previous.tdoc_id,
                        "is_revision_of": previous.is_revision_of,
                        "direction": "previous",
                        "date_created": previous.date_created,
                        "date_updated": previous.date_updated,
                    }
                )

        for record in records:
            if record.is_revision_of and record.is_revision_of.upper() == document_id.upper():
                revisions.append(
                    {
                        "tdoc_id": record.tdoc_id,
                        "is_revision_of": record.is_revision_of,
                        "direction": "next",
                        "date_created": record.date_created,
                        "date_updated": record.date_updated,
                    }
                )

    for rev in revisions:
        if rev.get("direction") != "next":
            continue
        next_doc = str(rev["tdoc_id"]).upper()
        edge_id = f"{next_doc}->REVISION_OF->{document_id}"
        if edge_id not in existing_edge_ids:
            edges.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_id=next_doc,
                    target_id=document_id,
                    edge_type=GraphEdgeType.REVISION_OF,
                    weight=1.0,
                    temporal_context=meeting_id or "",
                    provenance="tdoc_metadata_revision_chain",
                )
            )


def _add_meeting_edges(
    document_id: str,
    meeting_id: str | None,
    metadata: dict[str, object],
    db_path: Path,
    existing_node_ids: set[str],
    existing_edge_ids: set[str],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    now: datetime,
) -> None:
    if not metadata.get("meeting_id"):
        return
    meeting_num = metadata["meeting_id"]
    meeting_info: dict[str, object] = {}
    with MeetingDatabase(db_path) as meeting_db:
        resolved_id = int(meeting_num) if isinstance(meeting_num, str) and meeting_num.isdigit() else meeting_num
        meeting_record = meeting_db._get_meeting(resolved_id)
        if meeting_record is not None:
            meeting_info = {
                "meeting_id": meeting_record.meeting_id,
                "tsg": meeting_record.tsg,
                "wg": meeting_record.wg,
                "meeting_number": meeting_record.meeting_number,
                "location": meeting_record.location,
                "start_date": meeting_record.start_date,
                "end_date": meeting_record.end_date,
            }

    meeting_node_id = f"meeting_{meeting_num}"
    if meeting_node_id not in existing_node_ids and not any(node.node_id == meeting_node_id for node in nodes) and meeting_info:
        nodes.append(
            GraphNode(
                node_id=meeting_node_id,
                node_type=GraphNodeType.MEETING,
                label=f"{meeting_info.get('wg', 'Meeting')} {meeting_info.get('meeting_number', meeting_num)}",
                valid_from=None,
                valid_to=None,
                properties={
                    "meeting_id": meeting_num,
                    "tsg": meeting_info.get("tsg"),
                    "wg": meeting_info.get("wg"),
                    "meeting_number": meeting_info.get("meeting_number"),
                    "location": meeting_info.get("location"),
                    "start_date": str(meeting_info.get("start_date")) if meeting_info.get("start_date") else None,
                    "end_date": str(meeting_info.get("end_date")) if meeting_info.get("end_date") else None,
                },
                created_at=now,
            )
        )

    edge_id = f"{document_id}->PRESENTED_AT->{meeting_node_id}"
    if edge_id not in existing_edge_ids:
        edges.append(
            GraphEdge(
                edge_id=edge_id,
                source_id=document_id,
                target_id=meeting_node_id,
                edge_type=GraphEdgeType.PRESENTED_AT,
                weight=1.0,
                temporal_context=meeting_id or "",
                provenance="tdoc_metadata_meeting",
            )
        )


def _enhance_spec_nodes(referenced_specs: list[str], db_path: Path, nodes: list[GraphNode]) -> None:
    if not referenced_specs:
        return
    spec_metadata_map: dict[str, dict[str, object]] = {}
    with SpecDatabase(db_path) as spec_db:
        for record in spec_db._spec_table_rows():
            payload = {
                "spec_number": record.spec_number,
                "spec_type": record.spec_type,
                "title": record.title,
                "status": record.status,
                "working_group": record.working_group,
                "series": record.series,
                "latest_version": record.latest_version,
            }
            spec_metadata_map[record.spec_number] = payload
            spec_metadata_map[record.spec_number_compact] = payload

    for spec in referenced_specs:
        spec_meta = spec_metadata_map.get(spec) or spec_metadata_map.get(spec.replace(".", ""))
        if spec_meta:
            for node in nodes:
                if node.node_id == spec:
                    enhanced_props = dict(node.properties)
                    if spec_meta.get("title"):
                        enhanced_props["title"] = spec_meta["title"]
                    if spec_meta.get("working_group"):
                        enhanced_props["working_group"] = spec_meta["working_group"]
                    if spec_meta.get("status"):
                        enhanced_props["status"] = spec_meta["status"]
                    if spec_meta.get("series"):
                        enhanced_props["series"] = spec_meta["series"]
                    if spec_meta.get("latest_version"):
                        enhanced_props["latest_version"] = spec_meta["latest_version"]
                    node.properties = enhanced_props
                    node.label = spec_meta.get("title", node.label)
                    break


def _compute_revision_weight(metadata: dict[str, object]) -> float:
    """Compute revision edge weight based on metadata timestamps."""
    updated = metadata.get("date_updated")
    created = metadata.get("date_created")
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))

    if not updated or not created:
        return 1.0

    try:
        days_diff = (updated - created).days
    except TypeError:
        return 1.0

    if days_diff <= 7:
        return 1.5
    if days_diff > 30:
        return 0.5
    return 1.0


def query_graph(
    query: str,
    node_types: list[GraphNodeType] | None = None,
    meeting_ids: list[str] | None = None,
    date_range: tuple[datetime, datetime] | None = None,
    top_k: int = 10,
    storage: AiStorage | None = None,
    workspace: str | None = None,
    query_level: GraphQueryLevel | str | None = None,
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
        query_level: Query sophistication level (simple|medium|advanced).
            If None, uses config default.

    Returns:
        Dict with 'answer', 'nodes', and 'edges' keys for CLI compatibility.
    """
    if storage is None:
        config = AiConfig.from_env()
        storage = EmbeddingsManager(config).storage

    # Resolve query level from parameter or config
    if query_level is None:
        config = AiConfig.from_env()
        query_level = config.graph_query_level
    elif isinstance(query_level, str):
        query_level = query_level.strip().lower()

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

    # Build result with edges for each node
    results = []
    for node in matching_nodes:
        node_edges = [e for e in edges if node.node_id in (e.source_id, e.target_id)]
        results.append(GraphQueryResult(node=node, connected_edges=node_edges))

    # Generate answer based on query level
    answer = _generate_answer(query, matching_nodes, edges, query_level)

    # Log level - handle both string and Literal types
    level_str = query_level if isinstance(query_level, str) else str(query_level)
    logger.info(f"Graph query '{query}' returned {len(results)} results (level: {level_str})")

    # Return format expected by CLI: {"answer": str, "nodes": [...], "edges": [...]}
    return {
        "answer": answer,
        "nodes": [n.model_dump() for n in matching_nodes],
        "edges": [e.model_dump() for e in edges],
    }


def _generate_answer(
    query: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    query_level: GraphQueryLevel | str,
) -> str:
    """Generate answer string based on query level.

    Args:
        query: Original query string.
        nodes: Matching graph nodes.
        edges: All graph edges.
        query_level: Level of sophistication.

    Returns:
        Generated answer string.
    """
    # Handle both string and Literal type comparisons
    if query_level is None:
        query_level_str = "simple"
    elif hasattr(query_level, "value"):
        query_level_str = query_level.value
    else:
        query_level_str = str(query_level)

    if query_level_str == "simple":
        # Simple: Just return count
        return f"Found {len(nodes)} nodes and {len(edges)} edges in the knowledge graph."

    if query_level_str == "medium":
        # Medium: Parse query keywords and generate simple summary
        query_lower = query.lower()

        # Extract entity types from query
        entity_keywords = {
            GraphNodeType.TDOC: ["tdoc", "t-doc", "document", "work item"],
            GraphNodeType.SPEC: ["spec", "specification", "ts ", "tr "],
            GraphNodeType.MEETING: ["meeting", "session", "plenary"],
            GraphNodeType.COMPANY: ["company", "vendor", "operator", "organisation"],
            GraphNodeType.WORK_ITEM: ["work item", "wi", "feature"],
            GraphNodeType.CHANGE_REQUEST: ["cr", "change request", "change proposal"],
        }

        # Count by type
        type_counts: dict[GraphNodeType, int] = {}
        for node in nodes:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        # Build summary
        parts = []
        if nodes:
            parts.append(f"Found {len(nodes)} relevant nodes:")
            for ntype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                parts.append(f"  - {ntype.value}: {count}")
        else:
            parts.append("No relevant nodes found in the knowledge graph.")

        if edges:
            parts.append(f"Found {len(edges)} related edges.")

        # Try to identify what user is asking about
        for ntype, keywords in entity_keywords.items():
            if any(kw in query_lower for kw in keywords):
                filtered = [n for n in nodes if n.node_type == ntype]
                if filtered:
                    parts.append(f"\n{len(filtered)} {ntype.value.upper()} nodes match your query.")

        return "\n".join(parts)

    # Advanced: Use LLM for synthesis (Phase 6)
    # For now, fall back to medium behavior
    logger.warning("Advanced query level not yet implemented, falling back to medium")
    return _generate_answer(query, nodes, edges, "medium")


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
