"""Pydantic models for the AI document processing pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from tdoc_crawler.utils.misc import utc_now


def _normalize_tdoc_id(value: str) -> str:
    return value.strip().upper()


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


class GraphNodeType(StrEnum):
    """Types of nodes in the knowledge graph."""

    TDOC = "tdoc"
    MEETING = "meeting"
    SPEC = "spec"
    WORK_ITEM = "work_item"
    CHANGE_REQUEST = "cr"
    COMPANY = "company"
    CONCEPT = "concept"


class GraphEdgeType(StrEnum):
    """Types of edges in the knowledge graph."""

    DISCUSSES = "discusses"
    REVISES = "revises"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    AUTHORED_BY = "authored_by"
    MERGED_INTO = "merged_into"
    PRESENTED_AT = "presented_at"


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


class ProcessingStatus(BaseModel):
    """Processing state for a single TDoc."""

    tdoc_id: str = Field(..., description="TDoc identifier (normalized via .upper())")
    current_stage: PipelineStage = Field(PipelineStage.PENDING, description="Current pipeline stage")
    classified_at: datetime | None = Field(None, description="Timestamp when classification completed")
    extracted_at: datetime | None = Field(None, description="Timestamp when extraction completed")
    embedded_at: datetime | None = Field(None, description="Timestamp when embedding completed")
    summarized_at: datetime | None = Field(None, description="Timestamp when summarization completed")
    graphed_at: datetime | None = Field(None, description="Timestamp when graphing completed")
    completed_at: datetime | None = Field(None, description="Timestamp when pipeline completed")
    error_message: str | None = Field(None, description="Error details for failed stage")
    source_hash: str | None = Field(None, description="Hash of source DOCX for change detection")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        return _normalize_tdoc_id(value)


class DocumentClassification(BaseModel):
    """Classification of a file within a TDoc folder."""

    tdoc_id: str = Field(..., description="TDoc identifier (normalized via .upper())")
    file_path: str = Field(..., description="Relative path within checkout folder")
    is_main_document: bool = Field(..., description="Whether this file is the main document")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    decisive_heuristic: str = Field(..., description="Rule that determined the classification")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    classified_at: datetime = Field(default_factory=utc_now, description="Classification timestamp")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        return _normalize_tdoc_id(value)

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class DocumentChunk(BaseModel):
    """A chunk of extracted document text with its embedding."""

    chunk_id: str = Field(..., description="Unique chunk identifier '{tdoc_id}:{chunk_index}'")
    tdoc_id: str = Field(..., description="TDoc identifier (normalized via .upper())")
    section_heading: str | None = Field(None, description="Heading for the chunk's section")
    chunk_index: int = Field(..., ge=0, description="Position within the document")
    text: str = Field(..., description="Chunk text content")
    char_offset_start: int = Field(..., ge=0, description="Start offset in Markdown")
    char_offset_end: int = Field(..., ge=0, description="End offset in Markdown")
    vector: list[float] = Field(..., description="Embedding vector")
    embedding_model: str = Field(..., description="Embedding model identifier")
    created_at: datetime = Field(default_factory=utc_now, description="Embedding creation timestamp")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        return _normalize_tdoc_id(value)


class DocumentSummary(BaseModel):
    """AI-generated summary for a TDoc."""

    tdoc_id: str = Field(..., description="TDoc identifier (normalized via .upper())")
    abstract: str = Field(..., description="150-250 word abstract")
    key_points: list[str] = Field(default_factory=list, description="Key findings")
    action_items: list[str] = Field(default_factory=list, description="Action items")
    decisions: list[str] = Field(default_factory=list, description="Decisions recorded")
    affected_specs: list[str] = Field(default_factory=list, description="Affected specification IDs")
    llm_model: str = Field(..., description="Model used for generation")
    prompt_version: str = Field(..., description="Prompt template version")
    generated_at: datetime = Field(default_factory=utc_now, description="Generation timestamp")

    @field_validator("tdoc_id")
    @classmethod
    def _normalize_tdoc_id(cls, value: str) -> str:
        return _normalize_tdoc_id(value)


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


__all__ = [
    "AiConfigError",
    "AiError",
    "DocumentChunk",
    "DocumentClassification",
    "DocumentSummary",
    "EmbeddingDimensionError",
    "ExtractionError",
    "GraphEdge",
    "GraphEdgeType",
    "GraphNode",
    "GraphNodeType",
    "LlmConfigError",
    "PipelineStage",
    "ProcessingStatus",
    "TDocNotFoundError",
]
