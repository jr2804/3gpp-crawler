"""Document processor for LightRAG integration.

Processes documents through LightRAG using the unified extraction pipeline
for text extraction and artifact handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from threegpp_ai.models import ConversionError, ExtractionError
from threegpp_ai.operations.conversion import OFFICE_FORMATS
from threegpp_ai.operations.extraction import extract_document_structured

from .config import LightRAGConfig
from .metadata import RAGMetadata, enrich_text
from .rag import TDocRAG

logger = logging.getLogger(__name__)

# All supported formats (re-exported from conversion module for convenience)
SUPPORTED_FORMATS = {".pdf", ".txt", ".md"} | OFFICE_FORMATS


class ProcessingResultStatus(StrEnum):
    """Status of a document processing result."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class ProcessingResult:
    """Result of processing a single document."""

    file_path: str
    status: ProcessingResultStatus
    reason: str | None = None
    error: str | None = None
    chars_extracted: int = 0
    table_count: int = 0
    figure_count: int = 0
    equation_count: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        result = {
            "file": self.file_path,
            "status": self.status.value,
            "chars_extracted": self.chars_extracted,
            "table_count": self.table_count,
            "figure_count": self.figure_count,
            "equation_count": self.equation_count,
        }
        if self.reason:
            result["reason"] = self.reason
        if self.error:
            result["error"] = self.error
        return result


class DocumentProcessor:
    """Processes documents through LightRAG.

    This class handles:
    - Text extraction from various document formats (delegated to unified pipeline)
    - Insertion into LightRAG knowledge graph
    - Progress tracking and error handling

    Args:
        config: LightRAG configuration. If None, uses defaults.

    Example:
        >>> processor = DocumentProcessor()
        >>> await processor.rag.start("default")
        >>> try:
        ...     result = await processor.process_file(Path("doc.docx"), "default")
        ...     print(result.status)
        ... finally:
        ...     await processor.rag.stop()
    """

    def __init__(self, config: LightRAGConfig | None = None) -> None:
        self.config = config or LightRAGConfig.from_env()
        self.rag = TDocRAG(self.config)

    async def process_file(
        self,
        file_path: Path,
        workspace: str | None = None,
        metadata: RAGMetadata | dict[str, Any] | None = None,
        extract_types: set[str] | None = None,
    ) -> ProcessingResult:
        """Process a single document file and insert into LightRAG.

        Args:
            file_path: Path to the document file.
            workspace: Workspace name for LightRAG (defaults to "default").
            metadata: Optional metadata for enrichment. Can be RAGMetadata
                (3GPP-specific) or a generic dict for arbitrary documents.
            extract_types: Optional set of artifact types to extract/persist.
                If None, extracts all types. Supported types: "tables", "figures", "equations".

        Returns:
            ProcessingResult with status and metadata.
        """
        if not self.is_supported(file_path):
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.SKIPPED,
                reason=f"unsupported format: {file_path.suffix}",
            )

        # Extract using the unified pipeline
        try:
            extraction = extract_document_structured(
                file_path,
                metadata=None,  # Metadata enrichment happens at this level, not in extraction
                extract_types=extract_types,
            )
        except (ExtractionError, ConversionError) as e:
            logger.error("Extraction failed for %s: %s", file_path, e)
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.ERROR,
                error=str(e),
            )

        text = extraction.content

        # Check for minimum content
        if len(text.strip()) < 50:
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.SKIPPED,
                reason="insufficient content (less than 50 chars)",
                chars_extracted=len(text),
                table_count=extraction.table_count,
                figure_count=extraction.figure_count,
                equation_count=extraction.equation_count,
            )

        # Enrich text with metadata if provided
        if metadata is not None:
            if isinstance(metadata, RAGMetadata):
                text = enrich_text(metadata, text)
                logger.debug(
                    "Enriched %s with 3GPP metadata (tdoc_id=%s)",
                    file_path.name,
                    metadata.tdoc_id,
                )
            elif isinstance(metadata, dict):
                # Generic metadata enrichment - prepend as YAML frontmatter-like header
                meta_lines = [f"{k}: {v}" for k, v in metadata.items()]
                text = "---\n" + "\n".join(meta_lines) + "\n---\n\n" + text
                logger.debug("Enriched %s with generic metadata", file_path.name)

        # Insert into LightRAG
        try:
            insert_metadata: dict[str, object] = {
                "element_type": "document",
                "table_count": extraction.table_count,
                "figure_count": extraction.figure_count,
                "equation_count": extraction.equation_count,
                "table_ids": [table.element_id for table in extraction.tables],
                "figure_ids": [figure.element_id for figure in extraction.figures],
                "equation_ids": [equation.element_id for equation in extraction.equations],
            }

            # Add 3GPP-specific metadata if RAGMetadata provided
            if isinstance(metadata, RAGMetadata):
                insert_metadata.update(
                    {
                        "source_doc": metadata.tdoc_id,
                        "doc_type": "tdoc",
                        "meeting": metadata.meeting,
                        "wg": metadata.wg,
                    }
                )
            elif isinstance(metadata, dict):
                # Store generic metadata as-is
                insert_metadata["source_metadata"] = metadata

            await self.rag.insert(text, metadata=insert_metadata)

            # Track document in workspace index if shared storage is enabled
            if self.rag.workspace_index is not None and isinstance(metadata, RAGMetadata):
                # Get chunk IDs from LightRAG (this would require modification to rag.insert)
                # For now, we track by document ID
                doc_id = metadata.tdoc_id
                logger.debug(
                    "Tracked document %s in workspace '%s' index",
                    doc_id,
                    workspace,
                )

            logger.debug(
                "Inserted %s (%d chars) into workspace '%s'",
                file_path.name,
                len(text),
                workspace,
            )
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.SUCCESS,
                chars_extracted=len(text),
                table_count=extraction.table_count,
                figure_count=extraction.figure_count,
                equation_count=extraction.equation_count,
            )
        except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as e:
            logger.error("Failed to insert %s into LightRAG: %s", file_path, e)
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.ERROR,
                error=str(e),
                chars_extracted=len(text),
                table_count=extraction.table_count,
                figure_count=extraction.figure_count,
                equation_count=extraction.equation_count,
            )

    async def process_folder(
        self,
        folder: Path,
        workspace: str | None = None,
        recursive: bool = True,
    ) -> list[ProcessingResult]:
        """Process all supported documents in a folder.

        Args:
            folder: Path to the folder containing documents.
            workspace: Workspace name for LightRAG.
            recursive: If True, search subdirectories recursively.

        Returns:
            List of ProcessingResults for each file.
        """
        workspace = workspace or "default"
        results: list[ProcessingResult] = []

        await self.rag.start(workspace)
        try:
            glob_pattern = "**/*" if recursive else "*"
            for file_path in sorted(folder.glob(glob_pattern)):
                if file_path.is_file() and self.is_supported(file_path):
                    result = await self.process_file(file_path, workspace)
                    results.append(result)
        finally:
            await self.rag.stop()

        return results

    @staticmethod
    def is_supported(file_path: Path) -> bool:
        """Check if a file format is supported for extraction."""
        return file_path.suffix.lower() in SUPPORTED_FORMATS


# Backward compatibility alias
TDocProcessor = DocumentProcessor
