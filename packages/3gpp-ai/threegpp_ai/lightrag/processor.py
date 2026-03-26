"""TDoc processor for LightRAG integration.

Processes TDoc documents through LightRAG using convert-lo and kreuzberg for text extraction.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from convert_lo import LibreOfficeFormat
from convert_lo.converter import Converter
from kreuzberg import extract_file, extract_file_sync

from threegpp_ai.operations.extraction_result import (
    StructuredExtractionResult,
    build_structured_extraction_result,
    from_kreuzberg_result,
    has_cached_artifacts,
    persist_equations_from_extraction,
    persist_figures_from_extraction,
    persist_figures_from_kreuzberg_result,
    persist_tables_from_extraction,
    read_cached_artifacts,
)
from threegpp_ai.operations.figure_descriptor import describe_figures

from .config import LightRAGConfig
from .metadata import RAGMetadata, enrich_text
from .rag import TDocRAG

logger = logging.getLogger(__name__)

# File formats that need PDF conversion
OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
# All supported formats
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

    def __init__(self, config: LightRAGConfig | None = None) -> None:
        self.config = config or LightRAGConfig.from_env()
        self.rag = TDocRAG(self.config)

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

        extraction = await self.extract_text(file_path)
        if extraction is None:
            return ProcessingResult(
                file_path=str(file_path),
                status=ProcessingResultStatus.ERROR,
                error="text extraction returned None",
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
            text = enrich_text(metadata, text)
            logger.debug(
                "Enriched %s with metadata (tdoc_id=%s)",
                file_path.name,
                metadata.tdoc_id,
            )

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
            if metadata is not None:
                insert_metadata.update(
                    {
                        "source_doc": metadata.tdoc_id,
                        "doc_type": "tdoc",
                        "meeting": metadata.meeting,
                        "wg": metadata.wg,
                    }
                )

            await self.rag.insert(text, metadata=insert_metadata)

            # Track document in workspace index if shared storage is enabled
            if self.rag.workspace_index is not None and metadata is not None:
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
        except Exception as e:
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

    @staticmethod
    async def extract_text(
        file_path: Path,
        force: bool = False,
        extract_types: set[str] | None = None,
    ) -> StructuredExtractionResult | None:
        """Extract structured content from a file using kreuzberg.

        For office documents, first converts to PDF using convert-lo.
        Saves extracted content as markdown in .ai subfolder.

        Args:
            file_path: Path to the document file.
            force: If True, re-extract even if artifacts exist.
            extract_types: Optional set of artifact types to extract/persist.
                If None, extracts all types. Supported types: "tables", "figures", "equations".

        Returns:
            Structured extraction result, or None if extraction failed.
        """
        if extract_types is None:
            extract_types = {"tables", "figures", "equations"}

        pdf_path: Path | None = None

        try:
            # Convert office documents to PDF first
            if file_path.suffix.lower() in OFFICE_FORMATS:
                pdf_path = TDocProcessor._convert_to_pdf(file_path)
                if pdf_path is None:
                    logger.error("PDF conversion failed for %s", file_path)
                    return None
                # Use sync extraction for PDF
                result = extract_file_sync(str(pdf_path))
                # Don't clean up - keep the PDF in .ai folder
            else:
                # Direct extraction for PDF, TXT, MD
                result = await extract_file(file_path)

            ai_dir = file_path.parent / ".ai"
            ai_dir.mkdir(parents=True, exist_ok=True)
            doc_stem = file_path.stem

            # Check for cached artifacts to skip re-extraction (only for types in extract_types)
            if not force and has_cached_artifacts(ai_dir, doc_stem, extract_types):
                md_path = ai_dir / f"{doc_stem}.md"
                if md_path.exists():
                    cached_content = md_path.read_text(encoding="utf-8")
                    cached = read_cached_artifacts(ai_dir, doc_stem)
                    if cached is not None:
                        # Filter based on extract_types
                        tables = cached.tables if "tables" in extract_types else []
                        figures = cached.figures if "figures" in extract_types else []
                        equations = cached.equations if "equations" in extract_types else []
                        return build_structured_extraction_result(
                            cached_content,
                            tables=tables,
                            figures=figures,
                            equations=equations,
                        )

            figures_dir = ai_dir / "figures"
            figure_paths: dict[str, Path] = {}
            if "figures" in extract_types:
                figure_paths = persist_figures_from_kreuzberg_result(
                    result,
                    figures_dir,
                    doc_stem=doc_stem,
                )
            figure_descriptions = describe_figures(figure_paths, enabled=True) if figure_paths else None
            extraction = from_kreuzberg_result(
                result,
                figure_paths={key: str(path) for key, path in figure_paths.items()} if figure_paths else None,
                figure_descriptions=figure_descriptions,
            )
            if extraction.content:
                extracted_content = extraction.content
            else:
                logger.warning("No content extracted from %s", file_path)
                return None

            # Persist artifacts based on extract_types
            if extraction.table_count > 0 and "tables" in extract_types:
                persist_tables_from_extraction(extraction.tables, ai_dir, doc_stem)
            if extraction.figure_count > 0 and "figures" in extract_types:
                persist_figures_from_extraction(extraction.figures, figures_dir, doc_stem)
            if extraction.equation_count > 0 and "equations" in extract_types:
                persist_equations_from_extraction(extraction.equations, ai_dir, doc_stem)

            # Save extracted content as markdown in .ai subfolder
            md_path = ai_dir / f"{doc_stem}.md"
            md_path.write_text(extracted_content, encoding="utf-8")
            logger.info("Saved markdown: %s", md_path)

            return extraction
        except Exception as e:
            logger.error("Extraction failed for %s: %s", file_path, e)
            return None

    @staticmethod
    def _convert_to_pdf(file_path: Path) -> Path | None:
        """Convert office document to PDF and save in .ai subfolder.

        Args:
            file_path: Path to office document.

        Returns:
            Path to converted PDF in .ai subfolder, or None if conversion failed.
        """
        try:
            # Create .ai subfolder next to original file
            ai_dir = file_path.parent / ".ai"
            ai_dir.mkdir(parents=True, exist_ok=True)

            converter = Converter()
            with tempfile.TemporaryDirectory() as tmpdir:
                result = converter.convert(file_path, LibreOfficeFormat.PDF, Path(tmpdir))
                if result and result.output_path:
                    # Save to .ai subfolder with same stem
                    output_pdf = ai_dir / f"{file_path.stem}.pdf"
                    output_pdf.write_bytes(result.output_path.read_bytes())
                    logger.info("Converted %s to PDF: %s", file_path.name, output_pdf)
                    return output_pdf
                else:
                    logger.error("PDF conversion returned empty result for %s", file_path)
                    return None
        except Exception as e:
            logger.error("PDF conversion failed for %s: %s", file_path, e)
            return None
