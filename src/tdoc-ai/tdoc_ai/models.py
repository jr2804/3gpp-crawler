"""Pydantic models for the AI document processing pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from tdoc_ai.config import AiConfig
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_crawler.tdocs.utils import normalize_tdoc_id
from tdoc_crawler.utils.misc import utc_now


class PipelineStage(StrEnum):
    """Stages of the AI processing pipeline."""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    GRAPHING = "graphing"
    COMPLETED = "completed"
    FAILED = "failed"


class GraphNodeType(StrEnum):
    """Types of nodes in the knowledge graph."""

    DOCUMENT = "document"
    TDOC = "tdoc"
    MEETING = "meeting"
    SPEC = "spec"
    WORK_ITEM = "work_item"
    CHANGE_REQUEST = "cr"
    COMPANY = "company"


# Use LLM to synthesize answer from graph + embeddings (GraphRAG)


class GraphEdgeType(StrEnum):
    """Types of edges in the knowledge graph."""

    DISCUSSES = "discusses"
    REFERENCES = "references"
    AUTHORED_BY = "authored_by"
    PRESENTED_AT = "presented_at"
    REVISION_OF = "revision_of"  # is_revision_of metadata relationship


class ProcessingFailureType(StrEnum):
    """Classification of processing failures to determine retry behavior.

    Permanent failures - do NOT retry:
    - NOT_FOUND_ONLINE: Document withdrawn or never existed
    - DOWNLOAD_FAILED: Could not download source file
    - BROKEN_SOURCE: Downloaded file is corrupt/invalid
    - CLASSIFICATION_FAILED: Could not identify main document

    Retryable failures - CAN retry in next run:
    - EXTRACTION_FAILED: DOCX to Markdown conversion failed
    - EMBEDDING_FAILED: Embedding generation failed
    - GRAPH_FAILED: Graph building failed
    """

    GRAPH_FAILED = "graph_failed"


# TODO: Unnecessary? We can infer from presence of WorkspaceMember records and their is_active flag - or simply use a bool variable?
class WorkspaceStatus(StrEnum):
    """Lifecycle state of a workspace."""

    ACTIVE = "active"


class SourceKind(StrEnum):
    """Kinds of source items that can be part of a workspace corpus."""

    TDOC = auto()
    SPEC = auto()
    OTHER = auto()  # catch-all for any other source types


class AiError(Exception):
    """Base exception for AI processing errors."""


class TDocNotFoundError(AiError):
    """TDoc not found in database or has no files."""


class ExtractionError(AiError):
    """DOCX extraction failed (corrupt, password-protected, etc.)."""


class LlmConfigError(AiError):
    """LLM endpoint not configured or unreachable."""


class AiConfigError(AiError):
    """Invalid or missing AI configuration."""


class EmbeddingDimensionError(AiError):
    """Embedding model dimension mismatch with stored vectors."""


class Workspace(BaseModel):
    """Logical workspace boundary for AI processing."""

    workspace_name: str = Field(..., description="Normalized workspace identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update timestamp")
    is_default: bool = Field(False, description="Whether this workspace is the default workspace")
    auto_build: bool | None = Field(default=False, description="Whether to auto-build embeddings on TDoc add")
    status: WorkspaceStatus = Field(WorkspaceStatus.ACTIVE, description="Workspace lifecycle status")

    @field_validator("workspace_name")
    @classmethod
    def _normalize_workspace_name(cls, value: str) -> str:
        if not value.strip():
            msg = "workspace_name must not be empty"
            raise ValueError(msg)
        return normalize_workspace_name(value)


class WorkspaceMember(BaseModel):
    """Source item assigned to one workspace corpus."""

    workspace_name: str = Field(..., description="Workspace identifier")
    source_item_id: str = Field(..., description="Stable source item identifier")
    source_path: str = Field(..., description="Path or locator of the source item")
    source_kind: SourceKind = Field(..., description="Type of source item")
    added_at: datetime = Field(default_factory=utc_now, description="Registration timestamp")
    added_by: str | None = Field(None, description="Actor that registered the source")
    is_active: bool = Field(True, description="Membership active flag")

    @field_validator("workspace_name")
    @classmethod
    def _normalize_workspace_name(cls, value: str) -> str:
        if not value.strip():
            msg = "workspace_name must not be empty"
            raise ValueError(msg)
        return normalize_workspace_name(value)

    @field_validator("source_item_id")
    @classmethod
    def _normalize_source_item_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "source_item_id must not be empty"
            raise ValueError(msg)
        return normalized


class ArtifactScope(BaseModel):
    """Workspace association metadata for generated artifacts."""

    workspace_name: str = Field(..., description="Workspace identifier")
    artifact_type: str = Field(..., description="Artifact type")
    artifact_id: str = Field(..., description="Artifact identifier")
    source_item_id: str | None = Field(None, description="Optional source item identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Association timestamp")

    @field_validator("workspace_name")
    @classmethod
    def _normalize_workspace_name(cls, value: str) -> str:
        if not value.strip():
            msg = "workspace_name must not be empty"
            raise ValueError(msg)
        return normalize_workspace_name(value)


class ProcessingStatus(BaseModel):
    """Processing state for a single TDoc."""

    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    current_stage: PipelineStage = Field(PipelineStage.PENDING, description="Current pipeline stage")
    classified_at: datetime | None = Field(None, description="Timestamp when classification completed")
    extracted_at: datetime | None = Field(None, description="Timestamp when extraction completed")
    embedded_at: datetime | None = Field(None, description="Timestamp when embedding completed")
    summarized_at: datetime | None = Field(None, description="Timestamp when summarization completed")
    graphed_at: datetime | None = Field(None, description="Timestamp when graphing completed")
    completed_at: datetime | None = Field(None, description="Timestamp when pipeline completed")
    error_message: str | None = Field(None, description="Error details for failed stage")
    failure_type: ProcessingFailureType | None = Field(None, description="Type of failure if permanent")
    source_hash: str | None = Field(None, description="Hash of source DOCX for change detection")
    keywords: list[str] | None = Field(None, description="Keywords extracted from document content")
    detected_language: str | None = Field(None, description="Primary language detected in document")

    @field_validator("document_id")
    @classmethod
    def _normalize_document_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "document_id must not be empty"
            raise ValueError(msg)
        return normalized


class DocumentClassification(BaseModel):
    """Classification of a file within a TDoc folder."""

    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    file_path: str = Field(..., description="Relative path within checkout folder")
    is_main_document: bool = Field(..., description="Whether this file is the main document")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    decisive_heuristic: str = Field(..., description="Rule that determined the classification")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    classified_at: datetime = Field(default_factory=utc_now, description="Classification timestamp")

    @field_validator("document_id")
    @classmethod
    def _normalize_document_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "document_id must not be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class DocumentChunk(BaseModel):
    """A chunk of extracted document text with its embedding."""

    chunk_id: str = Field(..., description="Unique chunk identifier '{document_id}:{chunk_index}'")
    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    section_heading: str | None = Field(None, description="Heading for the chunk's section")
    chunk_index: int = Field(..., ge=0, description="Position within the document")
    text: str = Field(..., description="Chunk text content")
    char_offset_start: int = Field(..., ge=0, description="Start offset in Markdown")
    char_offset_end: int = Field(..., ge=0, description="End offset in Markdown")
    vector: list[float] = Field(..., description="Embedding vector")
    embedding_model: str = Field(..., description="Embedding model identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Embedding creation timestamp")

    @property
    def section(self) -> str | None:
        return self.section_heading

    @property
    def content(self) -> str:
        return self.text

    @property
    def embedding(self) -> list[float]:
        return self.vector

    @embedding.setter
    def embedding(self, value: list[float]) -> None:
        self.vector = value

    @field_validator("document_id")
    @classmethod
    def _normalize_document_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "document_id must not be empty"
            raise ValueError(msg)
        return normalized


class QueryResult(BaseModel):
    """Result from embedding similarity query."""

    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    section: str = Field("", description="Section heading or empty string")
    content: str = Field(..., description="Text content that matched the query")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0.0-1.0)")

    @field_validator("document_id")
    @classmethod
    def _normalize_document_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "document_id must not be empty"
            raise ValueError(msg)
        return normalized


class DocumentSummary(BaseModel):
    """AI-generated summary for a TDoc."""

    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    abstract: str = Field(..., description="150-250 word abstract")
    key_points: list[str] = Field(default_factory=list, description="Key findings")
    action_items: list[str] = Field(default_factory=list, description="Action items")
    decisions: list[str] = Field(default_factory=list, description="Decisions recorded")
    affected_specs: list[str] = Field(default_factory=list, description="Affected specification IDs")
    llm_model: str = Field(
        default_factory=lambda: AiConfig().llm_model,
        description="Model used for generation",
    )
    prompt_version: str = Field("v1", description="Prompt template version")
    generated_at: datetime = Field(default_factory=utc_now, description="Generation timestamp")

    @field_validator("document_id")
    @classmethod
    def _normalize_document_id(cls, value: str) -> str:
        normalized = normalize_tdoc_id(value)
        if not normalized:
            msg = "document_id must not be empty"
            raise ValueError(msg)
        return normalized


class GraphNode(BaseModel):
    """A node in the temporal knowledge graph."""

    node_id: str = Field(..., description="Unique node identifier")
    node_type: GraphNodeType = Field(..., description="Node type")
    label: str = Field(..., description="Human-readable label")
    valid_from: datetime | None = Field(None, description="Temporal validity start")
    valid_to: datetime | None = Field(None, description="Temporal validity end")
    properties: dict[str, Any] = Field(default_factory=dict, description="Type-specific properties")
    created_at: datetime = Field(default_factory=utc_now, description="Node creation timestamp")


class GraphEdge(BaseModel):
    """An edge in the temporal knowledge graph."""

    edge_id: str = Field(..., description="Edge identifier '{source}->{edge_type}->{target}'")
    source_id: str = Field(..., description="Source node id")
    target_id: str = Field(..., description="Target node id")
    edge_type: GraphEdgeType = Field(..., description="Edge type")
    weight: float = Field(1.0, description="Relationship strength")
    temporal_context: str | None = Field(None, description="Meeting or date context")
    provenance: str = Field(..., description="How this edge was derived")
    created_at: datetime = Field(default_factory=utc_now, description="Edge creation timestamp")

    @model_validator(mode="after")
    def _validate_weight(self) -> GraphEdge:
        if self.weight <= 0:
            msg = "weight must be positive"
            raise ValueError(msg)
        return self


class SummarizeResult(BaseModel):
    """Result of TDoc summarization operation."""

    summary: str = Field(..., description="Generated summary text")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")
    metadata: dict = Field(
        default_factory=dict,
        description="Metadata including meeting_id, source, word_count",
    )
    word_count: int = Field(..., ge=0, description="Actual word count of summary")

    @field_validator("keywords", mode="before")
    @classmethod
    def _normalize_keywords(cls, value: list[str] | None) -> list[str]:
        """Normalize keywords to a list of strings."""
        if value is None:
            return []
        return [str(kw).strip() for kw in value if str(kw).strip()]


class GraphQueryResult(BaseModel):
    """Knowledge graph query result."""

    node: GraphNode = Field(..., description="Matched graph node")
    connected_edges: list[GraphEdge] = Field(default_factory=list, description="Connected edges for context")


__all__ = [
    "AiConfigError",
    "AiError",
    "ArtifactScope",
    "DocumentChunk",
    "DocumentClassification",
    "DocumentSummary",
    "EmbeddingDimensionError",
    "ExtractionError",
    "GraphEdge",
    "GraphEdgeType",
    "GraphNode",
    "GraphNodeType",
    "GraphQueryResult",
    "LlmConfigError",
    "PipelineStage",
    "ProcessingStatus",
    "QueryResult",
    "SourceKind",
    "SummarizeResult",
    "TDocNotFoundError",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceStatus",
]
