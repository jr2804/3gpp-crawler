"""Pydantic models for the AI document processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, Field, field_validator
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_tdoc_id

from threegpp_ai.operations.workspace_names import normalize_workspace_name


class ExtractionQualityStatus(StrEnum):
    """Deterministic extraction quality status."""

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractionQualityReasonCode(StrEnum):
    """Stable machine-readable reason codes for quality gate outcomes."""

    MISSING_ARTIFACT = "missing_artifact"
    MISSING_METADATA = "missing_metadata"
    INVALID_PROVENANCE = "invalid_provenance"
    COVERAGE_MISMATCH = "coverage_mismatch"


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
    cell_metadata: list[list[dict[str, Any] | None]] = Field(
        default_factory=list,
        description="Optional per-cell metadata matrix aligned with `cells`",
    )
    markdown: str | None = Field(None, description="Markdown representation of the table")
    caption: str | None = Field(None, description="Detected table caption")
    source_anchor_id: str | None = Field(None, description="Normalized source anchor identifier for provenance")


class ExtractedFigureElement(BaseModel):
    """Structured representation of an extracted figure/image."""

    element_id: str = Field(..., description="Stable figure identifier within document")
    page_number: int | None = Field(None, ge=1, description="1-based page number if available")
    image_path: str | None = Field(None, description="Path to stored figure artifact")
    image_format: str | None = Field(None, description="Image format, e.g. png, jpeg")
    caption: str | None = Field(None, description="Detected figure caption")
    description: str | None = Field(None, description="Optional generated figure description")
    source_anchor_id: str | None = Field(None, description="Normalized source anchor identifier for provenance")
    is_partial: bool = Field(False, description="Whether figure record is partial and contains degraded fields")
    partial_reason_codes: list[str] = Field(
        default_factory=list,
        description="Machine-readable diagnostics describing why figure payload is partial",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Provider/extraction metadata")


class ExtractedEquationElement(BaseModel):
    """Structured representation of an extracted equation."""

    element_id: str = Field(..., description="Stable equation identifier within document")
    page_number: int | None = Field(None, ge=1, description="1-based page number if available")
    equation_number: str | None = Field(None, description="Equation label/number if available")
    latex: str = Field(..., description="Equation content in LaTeX-compatible format")
    raw_text: str | None = Field(None, description="Original extracted equation text")
    source_anchor_id: str | None = Field(None, description="Normalized source anchor identifier for provenance")
    normalized_text: str | None = Field(None, description="Normalized equation text for machine-readable comparison")
    equation_type: str | None = Field(None, description="Equation syntax family, e.g. latex")
    display_mode: str | None = Field(None, description="Equation rendering mode: inline or display")


class PageMetadataContract(BaseModel):
    """Canonical page-level metadata contract for extraction artifacts."""

    page_number: int = Field(..., ge=1, description="1-based page number")
    table_count: int = Field(0, ge=0, description="Number of extracted tables on this page")
    figure_count: int = Field(0, ge=0, description="Number of extracted figures on this page")
    equation_count: int = Field(0, ge=0, description="Number of extracted equations on this page")


class DocumentMetadataContract(BaseModel):
    """Canonical document-level metadata contract for extraction outputs."""

    document_id: str | None = Field(None, description="Document identifier if available")
    title: str | None = Field(None, description="Document title if available")
    source_path: str | None = Field(None, description="Resolved source path if available")
    file_extension: str | None = Field(None, description="Source file extension, e.g. .pdf")
    total_pages: int | None = Field(None, ge=1, description="Detected total page count if available")
    extraction_profile: str | None = Field(None, description="Resolved extraction profile")
    extraction_status: str = Field("ok", description="Extraction status: ok|partial|failed")
    config_hash: str | None = Field(None, description="Deterministic extraction config fingerprint")


class QualityGateCheckResult(BaseModel):
    """Single quality gate check result."""

    gate: str = Field(..., description="Gate identifier")
    passed: bool = Field(..., description="Whether the gate passed")
    reason_code: ExtractionQualityReasonCode | None = Field(
        None,
        description="Reason code when gate fails",
    )
    message: str | None = Field(None, description="Optional human-readable gate detail")


class ExtractionQualityReport(BaseModel):
    """Deterministic quality report persisted per document."""

    status: ExtractionQualityStatus = Field(..., description="Final deterministic extraction status")
    reason_codes: list[ExtractionQualityReasonCode] = Field(
        default_factory=list,
        description="Unique reason codes for failed checks",
    )
    checks: list[QualityGateCheckResult] = Field(default_factory=list, description="Gate-by-gate outcomes")
    gate_metrics_summary: dict[str, int | float] = Field(
        default_factory=dict,
        description="Compact gate metrics summary",
    )


class StructuredExtractionResult(BaseModel):
    """Canonical extraction payload shared by process, convert, and summarize flows."""

    content: str = Field(..., description="Primary extracted text/markdown content")
    tables: list[ExtractedTableElement] = Field(default_factory=list, description="Extracted tables")
    figures: list[ExtractedFigureElement] = Field(default_factory=list, description="Extracted figures")
    equations: list[ExtractedEquationElement] = Field(default_factory=list, description="Extracted equations")
    document_metadata: DocumentMetadataContract | None = Field(
        None,
        description="Canonical document-level metadata contract",
    )
    pages: list[PageMetadataContract] = Field(default_factory=list, description="Canonical page-level metadata contracts")
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
    "AiError",
    "ConversionError",
    "DocumentClassification",
    "DocumentMetadataContract",
    "ExtractedEquationElement",
    "ExtractedFigureElement",
    "ExtractedTableElement",
    "ExtractionError",
    "ExtractionQualityReasonCode",
    "ExtractionQualityReport",
    "ExtractionQualityStatus",
    "LlmConfigError",
    "PageMetadataContract",
    "QualityGateCheckResult",
    "SourceKind",
    "StructuredExtractionResult",
    "SummarizeResult",
    "TDocNotFoundError",
    "Workspace",
    "WorkspaceNotFoundError",
]
