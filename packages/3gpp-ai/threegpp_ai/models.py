"""Pydantic models for the AI document processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_tdoc_id

from threegpp_ai.config import AiConfig
from threegpp_ai.operations.workspace_names import normalize_workspace_name


class GraphNodeType(StrEnum):
    """Types of nodes in the knowledge graph."""

    DOCUMENT = auto()
    TDOC = auto()
    MEETING = auto()
    SPEC = auto()
    WORK_ITEM = "work_item"
    CHANGE_REQUEST = "cr"
    COMPANY = auto()


# Use LLM to synthesize answer from graph + embeddings (GraphRAG)


class GraphEdgeType(StrEnum):
    """Types of edges in the knowledge graph."""

    DISCUSSES = auto()
    REFERENCES = auto()
    AUTHORED_BY = auto()
    PRESENTED_AT = auto()
    REVISION_OF = auto()  # is_revision_of metadata relationship


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


class ConversionError(AiError):
    """Document conversion failed (LibreOffice or remote converter error)."""


class LlmConfigError(AiError):
    """LLM endpoint not configured or unreachable."""


class AiConfigError(AiError):
    """Invalid or missing AI configuration."""


class EmbeddingDimensionError(AiError):
    """Embedding model dimension mismatch with stored vectors."""


class WorkspaceNotFoundError(AiError):
    """Workspace does not exist in registry."""


@dataclass
class Workspace:
    """Logical workspace boundary for AI processing."""

    workspace_name: str = field(metadata={"description": "Normalized workspace identifier"})
    created_at: datetime = field(default_factory=utc_now, metadata={"description": "Creation timestamp"})
    updated_at: datetime = field(default_factory=utc_now, metadata={"description": "Last update timestamp"})
    is_default: bool = field(default=False, metadata={"description": "Whether this workspace is the default workspace"})
    auto_build: bool | None = field(default=False, metadata={"description": "Whether to auto-build embeddings on TDoc add"})

    def __post_init__(self) -> None:
        """Normalize workspace_name after initialization."""
        if not self.workspace_name.strip():
            msg = "workspace_name must not be empty"
            raise ValueError(msg)
        self.workspace_name = normalize_workspace_name(self.workspace_name)


@dataclass
class WorkspaceMember:
    """Source item assigned to one workspace corpus."""

    workspace_name: str = field(metadata={"description": "Workspace identifier"})
    source_item_id: str = field(metadata={"description": "Stable source item identifier"})
    source_path: str = field(metadata={"description": "Path or locator of the source item"})
    source_kind: SourceKind = field(metadata={"description": "Type of source item"})
    added_at: datetime = field(default_factory=utc_now, metadata={"description": "Registration timestamp"})
    added_by: str | None = field(default=None, metadata={"description": "Actor that registered the source"})
    is_active: bool = field(default=True, metadata={"description": "Membership active flag"})

    def __post_init__(self) -> None:
        """Normalize fields after initialization."""
        if not self.workspace_name.strip():
            msg = "workspace_name must not be empty"
            raise ValueError(msg)
        self.workspace_name = normalize_workspace_name(self.workspace_name)

        normalized = normalize_tdoc_id(self.source_item_id)
        if not normalized:
            msg = "source_item_id must not be empty"
            raise ValueError(msg)
        self.source_item_id = normalized


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


class ExtractedTableElement(BaseModel):
    """Structured representation of a table extracted from a document."""

    element_id: str = Field(..., description="Stable table identifier within document")
    page_number: int | None = Field(None, ge=1, description="1-based page number if available")
    row_count: int = Field(0, ge=0, description="Number of table rows")
    column_count: int = Field(0, ge=0, description="Number of table columns")
    cells: list[list[str]] = Field(default_factory=list, description="Normalized table cell matrix")
    markdown: str | None = Field(None, description="Markdown representation of the table")
    caption: str | None = Field(None, description="Detected table caption")


class ExtractedFigureElement(BaseModel):
    """Structured representation of an extracted figure/image."""

    element_id: str = Field(..., description="Stable figure identifier within document")
    page_number: int | None = Field(None, ge=1, description="1-based page number if available")
    image_path: str | None = Field(None, description="Path to stored figure artifact")
    image_format: str | None = Field(None, description="Image format, e.g. png, jpeg")
    caption: str | None = Field(None, description="Detected figure caption")
    description: str | None = Field(None, description="Optional generated figure description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Provider/extraction metadata")


class ExtractedEquationElement(BaseModel):
    """Structured representation of an extracted equation."""

    element_id: str = Field(..., description="Stable equation identifier within document")
    page_number: int | None = Field(None, ge=1, description="1-based page number if available")
    equation_number: str | None = Field(None, description="Equation label/number if available")
    latex: str = Field(..., description="Equation content in LaTeX-compatible format")
    raw_text: str | None = Field(None, description="Original extracted equation text")


class StructuredExtractionResult(BaseModel):
    """Canonical extraction payload shared by process, convert, and summarize flows."""

    content: str = Field(..., description="Primary extracted text/markdown content")
    tables: list[ExtractedTableElement] = Field(default_factory=list, description="Extracted tables")
    figures: list[ExtractedFigureElement] = Field(default_factory=list, description="Extracted figures")
    equations: list[ExtractedEquationElement] = Field(default_factory=list, description="Extracted equations")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document-level extraction metadata")

    @property
    def table_count(self) -> int:
        """Return the number of extracted tables."""
        return len(self.tables)

    @property
    def figure_count(self) -> int:
        """Return the number of extracted figures."""
        return len(self.figures)

    @property
    def equation_count(self) -> int:
        """Return the number of extracted equations."""
        return len(self.equations)


class DocumentSummary(BaseModel):
    """AI-generated summary for a TDoc."""

    document_id: str = Field(..., description="Document identifier (normalized via .upper())")
    abstract: str = Field(..., description="150-250 word abstract")
    key_points: list[str] = Field(default_factory=list, description="Key findings")
    action_items: list[str] = Field(default_factory=list, description="Action items")
    decisions: list[str] = Field(default_factory=list, description="Decisions recorded")
    affected_specs: list[str] = Field(default_factory=list, description="Affected specification IDs")
    llm_model: str = Field(
        default_factory=lambda: AiConfig.from_env().llm_model,
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


__all__ = [
    "AiConfigError",
    "AiError",
    "ConversionError",
    "DocumentClassification",
    "DocumentSummary",
    "EmbeddingDimensionError",
    "ExtractionError",
    "GraphEdge",
    "GraphEdgeType",
    "GraphNode",
    "GraphNodeType",
    "LlmConfigError",
    "SourceKind",
    "SummarizeResult",
    "TDocNotFoundError",
    "Workspace",
    "WorkspaceMember",
]
