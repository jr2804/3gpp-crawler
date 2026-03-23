"""TDoc processor for LightRAG integration.

Processes TDoc documents through LightRAG using kreuzberg for text extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kreuzberg import extract_file

from .config import LightRAGConfig
from .metadata import RAGMetadata, enrich_text
from .rag import TDocRAG

logger = logging.getLogger(__name__)

# Supported file formats for extraction
SUPPORTED_FORMATS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md"}


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
    entities_extracted: int = 0
    relations_extracted: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        result = {
            "file": self.file_path,
            "status": self.status.value,
            "chars_extracted": self.chars_extracted,
        }
        if self.reason:
            result["reason"] = self.reason
        if self.error:
            result["error"] = self.error
        return result


class TDocProcessor:
    """Processes TDoc documents through LightRAG.

    This class handles:
    - Text extraction from various document formats using kreuzberg
    - Insertion into LightRAG knowledge graph
    - Progress tracking and error handling

    Args:
        config: LightRAG configuration. If None, uses defaults.

    Example:
        >>> processor = TDocProcessor()
        >>> await processor.rag.start("default")
        >>> try:
        ...     result = await processor.process_file(Path("doc.docx"), "default")
        ...     print(result.status)
        ... finally:
        ...     await processor.rag.stop()
    """

    def __init__(self, config: LightRAGConfig | None = None):
        self.config = config or LightRAGConfig()
        self.rag = TDocRAG(self.config)

    @staticmethod
    def is_supported(file_path: Path) -> bool:
        """Check if a file format is supported for extraction."""
        return file_path.suffix.lower() in SUPPORTED_FORMATS

    @staticmethod
    async def extract_text(file_path: Path) -> str | None:
        """Extract text content from a file using kreuzberg.

        Args:
            file_path: Path to the document file.

        Returns:
            Extracted text content, or None if extraction failed.
        """
        try:
            result = await extract_file(file_path)
            if result and result.content:
                return result.content
            logger.warning("No content extracted from %s", file_path)
            return None
        except Exception as e:
            logger.error("Extraction failed for %s: %s", file_path, e)
            return None

    async def process_file(
        self,
        file_path: Path,
        workspace: str | None = None,
        metadata: RAGMetadata | None = None,
    ) -> ProcessingResult:
        """Process a single document file and insert into LightRAG.

        Args:
            file_path: Path to the document file.
            workspace: Workspace name for LightRAG (defaults to "default").
            metadata: Optional 3GPP metadata for enrichment. If provided,
                metadata is prepended to the text for deterministic extraction.

        Returns:
            ProcessingResult with status and metadata.
        """
        if not self.is_supported(file_path):
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.SKIPPED,
                reason=f"unsupported format: {file_path.suffix}",
            )

        text = await self.extract_text(file_path)
        if text is None:
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.ERROR,
                error="text extraction returned None",
            )

        # Check for minimum content
        if len(text.strip()) < 50:
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.SKIPPED,
                reason="insufficient content (less than 50 chars)",
                chars_extracted=len(text),
            )

        # Enrich text with metadata if provided
        if metadata is not None:
            text = enrich_text(metadata, text)
            logger.debug(
                "Enriched %s with metadata (tdoc_id=%s)",
                file_path.name,
                metadata.tdoc_id,
            )

        # Insert into LightRAG
        try:
            await self.rag.insert(text)
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
            )
        except Exception as e:
            logger.error("Failed to insert %s into LightRAG: %s", file_path, e)
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.ERROR,
                error=str(e),
                chars_extracted=len(text),
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
