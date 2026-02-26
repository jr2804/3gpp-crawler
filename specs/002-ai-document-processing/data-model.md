# Data Model: AI Document Processing Pipeline

**Date**: 2026-02-24
**Source**: [spec.md](spec.md) Key Entities + [research.md](research.md) storage decisions

## Storage Architecture

All AI data is stored in LanceDB (file-based) under `<cache_dir>/.ai/lancedb/`.
The existing tdoc-crawler SQLite database is read-only from the AI module.

```
<cache_dir>/
├── tdoc_crawler.db          # Existing SQLite DB (read-only from AI module)
├── checkout/                # Existing TDoc file checkouts
└── .ai/
    └── lancedb/
        ├── processing_status.lance
        ├── classifications.lance
        ├── chunks.lance         # Includes embedded vectors
        ├── summaries.lance
        ├── graph_nodes.lance
        └── graph_edges.lance
```

## Entity Definitions

### 1. AiConfig

Configuration model for the AI pipeline. Not stored in LanceDB — loaded from
a config file or environment variables.

```python
class AiConfig(BaseModel):
    """Configuration for the AI processing pipeline."""

    # Storage
    ai_store_path: Path  # Default: <cache_dir>/.ai/lancedb/

    # Extraction
    # Extraction
    # (No configurable params for extraction in v1 — uses defaults. Note: Docling used in Phases 1-8, replaced by Kreuzberg in Phase 9 with full refactoring)

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    max_chunk_size: int = 1000    # tokens
    chunk_overlap: int = 100      # tokens

    # Summarization
    llm_model: str = "ollama/llama3.2"        # litellm model identifier
    llm_api_base: str | None = None           # Override for remote endpoints
    abstract_min_words: int = 150
    abstract_max_words: int = 250

    # Pipeline
    parallelism: int = 4         # Concurrent TDoc processing
```

### 2. ProcessingStatus

Tracks the current AI processing state for each TDoc.

```python
class PipelineStage(StrEnum):
    """Stages of the AI processing pipeline."""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    SUMMARIZING = "summarizing"
    GRAPHING = "graphing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(BaseModel):
    """Processing state for a single TDoc."""

    tdoc_id: str                            # PK; normalized via .upper()
    current_stage: PipelineStage = PipelineStage.PENDING
    classified_at: datetime | None = None
    extracted_at: datetime | None = None
    embedded_at: datetime | None = None
    summarized_at: datetime | None = None
    graphed_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    source_hash: str | None = None          # Hash of source DOCX for change detection
```

**LanceDB table**: `processing_status`
**Primary key**: `tdoc_id`

### 3. DocumentClassification

Records main/secondary classification for each file in a TDoc folder.

```python
class DocumentClassification(BaseModel):
    """Classification of a file within a TDoc folder."""

    tdoc_id: str                 # FK to ProcessingStatus
    file_path: str               # Relative path within checkout folder
    is_main_document: bool
    confidence: float            # 0.0 to 1.0
    decisive_heuristic: str      # Which rule determined the classification
    file_size_bytes: int
    classified_at: datetime
```

**LanceDB table**: `classifications`
**Composite key**: `(tdoc_id, file_path)`

### 4. DocumentChunk

A segment of extracted Markdown with position metadata. Also stores the
embedding vector (combined in one table for efficient vector search).

```python
class DocumentChunk(BaseModel):
    """A chunk of extracted document text with its embedding."""

    chunk_id: str                  # "{tdoc_id}:{chunk_index}"
    tdoc_id: str                   # FK to ProcessingStatus
    section_heading: str | None    # Heading of the section this chunk belongs to
    chunk_index: int               # Position within the document
    text: str                      # The chunk text content
    char_offset_start: int         # Start offset in the full Markdown
    char_offset_end: int           # End offset in the full Markdown
    vector: list[float]            # Embedding vector (384-dim for bge-small)
    embedding_model: str           # Model used to generate the vector
    created_at: datetime
```

**LanceDB table**: `chunks`
**Primary key**: `chunk_id`
**Vector column**: `vector` (used for similarity search)

### 5. DocumentSummary

LLM-generated abstract and structured summary.

```python
class DocumentSummary(BaseModel):
    """AI-generated summary for a TDoc."""

    tdoc_id: str                     # PK; FK to ProcessingStatus
    abstract: str                    # 150-250 word abstract
    key_points: list[str]            # Bullet-point key findings
    action_items: list[str]          # Identified action items
    decisions: list[str]             # Decisions recorded in the TDoc
    affected_specs: list[str]        # Spec numbers mentioned (e.g., "TS 26.132")
    llm_model: str                   # Model used for generation
    prompt_version: str              # Version of the prompt template
    generated_at: datetime
```

**LanceDB table**: `summaries`
**Primary key**: `tdoc_id`

### 6. GraphNode

An entity in the temporal knowledge graph.

```python
class GraphNodeType(StrEnum):
    """Types of nodes in the knowledge graph."""

    TDOC = "tdoc"
    MEETING = "meeting"
    SPEC = "spec"
    WORK_ITEM = "work_item"
    CHANGE_REQUEST = "cr"
    COMPANY = "company"
    CONCEPT = "concept"


class GraphNode(BaseModel):
    """A node in the temporal knowledge graph."""

    node_id: str                     # Unique identifier (type-prefixed)
    node_type: GraphNodeType
    label: str                       # Human-readable label
    valid_from: datetime | None      # Temporal validity start
    valid_to: datetime | None        # Temporal validity end
    properties: dict[str, Any]       # Additional type-specific properties
    created_at: datetime
```

**LanceDB table**: `graph_nodes`
**Primary key**: `node_id`

### 7. GraphEdge

A typed relationship between two GraphNodes.

```python
class GraphEdgeType(StrEnum):
    """Types of edges in the knowledge graph."""

    DISCUSSES = "discusses"         # TDoc discusses a Spec/WorkItem/Concept
    REVISES = "revises"            # TDoc revises another TDoc
    REFERENCES = "references"      # TDoc references another TDoc
    SUPERSEDES = "supersedes"      # TDoc supersedes another TDoc
    AUTHORED_BY = "authored_by"    # TDoc authored by Company
    MERGED_INTO = "merged_into"    # TDoc merged into a Spec
    PRESENTED_AT = "presented_at"  # TDoc presented at Meeting


class GraphEdge(BaseModel):
    """An edge in the temporal knowledge graph."""

    edge_id: str                    # "{source_id}->{edge_type}->{target_id}"
    source_id: str                  # FK to GraphNode.node_id
    target_id: str                  # FK to GraphNode.node_id
    edge_type: GraphEdgeType
    weight: float = 1.0             # Relationship strength
    temporal_context: str | None    # Meeting or date context
    provenance: str                 # How this edge was derived
    created_at: datetime
```

**LanceDB table**: `graph_edges`
**Primary key**: `edge_id`

## Entity Relationships

```
ProcessingStatus (1) --- (0..N) DocumentClassification
ProcessingStatus (1) --- (0..N) DocumentChunk
ProcessingStatus (1) --- (0..1) DocumentSummary
GraphNode (1) --- (0..N) GraphEdge (as source)
GraphNode (1) --- (0..N) GraphEdge (as target)
```

## State Transitions

```
ProcessingStatus.current_stage:

  pending --> classifying --> extracting --> embedding --> summarizing --> graphing --> completed
      |            |              |             |              |             |
      +-----+------+------+------+------+------+------+------+------+------+
            |                                                        |
            +---------------------> failed <-------------------------+
```

Each stage transition updates the corresponding `*_at` timestamp.
A `failed` status records the `error_message` and can be retried.

## Idempotency and Change Detection

- `ProcessingStatus.source_hash` stores SHA-256 of the source DOCX file
- Before processing, the current hash is compared to the stored hash
- If unchanged, the TDoc is skipped (FR-013: idempotent)
- If changed, all downstream stages are re-run from extraction

## Validation Rules

| Field | Rule |
|-------|------|
| `tdoc_id` | Normalized via `.upper()`; must match 3GPP TDoc pattern |
| `DocumentClassification.confidence` | Must be in range [0.0, 1.0] |
| `DocumentSummary.abstract` | Word count must be in [abstract_min_words, abstract_max_words] |
| `DocumentChunk.vector` | Length must match embedding model dimension |
| `GraphNode.node_id` | Must be prefixed with `node_type` (e.g., "tdoc:SP-123456") |
| `GraphEdge.edge_id` | Must follow "{source_id}->{edge_type}->{target_id}" format |
