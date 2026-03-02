"""DOCX-to-Markdown extraction using Kreuzberg."""

from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from pathlib import Path

from kreuzberg import ExtractionConfig, KeywordAlgorithm, KeywordConfig, LanguageDetectionConfig, extract_file_sync

from tdoc_crawler.ai.models import ExtractionError, ProcessingStatus
from tdoc_crawler.ai.operations.workspaces import normalize_workspace_name
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)


def _normalize_document_id(document_id: str) -> str:
    return document_id.strip().upper()


def _artifact_path(docx_path: Path, document_id: str) -> Path:
    artifact_dir = docx_path.parent / ".ai"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir / f"{_normalize_document_id(document_id)}.md"


def _write_markdown_artifact(docx_path: Path, document_id: str, markdown: str) -> Path:
    output_path = _artifact_path(docx_path, document_id)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def compute_source_hash(docx_path: Path) -> str:
    """Compute SHA-256 hash of source file for change detection.

    Args:
        docx_path: Path to DOCX file.

    Returns:
        Hex string of SHA-256 hash.
    """
    hasher = hashlib.sha256()
    hasher.update(docx_path.read_bytes())
    return hasher.hexdigest()


def _fallback_extract_docx_to_markdown(docx_path: Path) -> str:
    """Fallback DOCX text extraction using document.xml parsing."""
    try:
        with zipfile.ZipFile(docx_path, "r") as archive:
            xml_content = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception as exc:
        msg = f"Fallback extraction failed for {docx_path}: {exc}"
        raise ExtractionError(msg) from exc

    text_nodes = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml_content)
    lines = [re.sub(r"\s+", " ", node).strip() for node in text_nodes if node.strip()]
    markdown = "\n\n".join(lines)

    if "<w:tbl" in xml_content:
        markdown = f"{markdown}\n\n| table | detected |"

    return markdown


def extract_docx_to_markdown(
    document_id: str,
    docx_path: Path,
    storage: AiStorage,
    workspace: str | None = None,
) -> str:
    """Extract content from DOCX file to Markdown using Kreuzberg.

    Args:
        document_id: Document identifier.
        docx_path: Path to DOCX file.
        storage: AiStorage instance for status tracking.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Extracted content as Markdown string.

    Raises:
        ExtractionError: If extraction fails.
    """
    if not docx_path.exists():
        msg = f"DOCX file not found: {docx_path}"
        raise ExtractionError(msg)

    normalized_workspace = normalize_workspace_name(workspace)

    # Check for change detection (idempotency)
    current_hash = compute_source_hash(docx_path)
    artifact_path = _artifact_path(docx_path, document_id)

    try:
        status = storage.get_status(document_id, workspace=normalized_workspace)
        if status and hasattr(status, "source_hash") and status.source_hash == current_hash and hasattr(status, "extracted_at") and status.extracted_at:
            logger.info(f"Skipping extraction for {document_id} - content unchanged")
            if artifact_path.exists():
                return artifact_path.read_text(encoding="utf-8")
            return ""
    except Exception as error:
        logger.debug(f"Unable to load prior extraction status for {document_id}: {error}")

    try:
        # Extract DOCX to Markdown using Kreuzberg with advanced features
        config = ExtractionConfig(
            keywords=KeywordConfig(
                algorithm=KeywordAlgorithm.Yake,
                max_keywords=15,
                ngram_range=(1, 3),
            ),
            language_detection=LanguageDetectionConfig(
                min_confidence=0.7,
            ),
            enable_quality_processing=True,
        )
        result = extract_file_sync(str(docx_path), config=config)

        # Get Markdown content
        markdown = result.content

        # Extract keywords and detected language from result
        keywords: list[str] | None = None
        if hasattr(result, "keywords") and result.keywords:
            keywords = [kw.text if hasattr(kw, "text") else str(kw) for kw in result.keywords]

        detected_language: str | None = None
        if hasattr(result, "detected_languages") and result.detected_languages:
            detected_language = str(result.detected_languages[0])

        artifact_output = _write_markdown_artifact(docx_path, document_id, markdown)

        # Save hash for future idempotency
        try:
            status = storage.get_status(document_id, workspace=normalized_workspace)
            if status is None:
                status = ProcessingStatus(document_id=document_id)
            status.source_hash = current_hash
            status.extracted_at = utc_now()
            status.error_message = None
            status.keywords = keywords
            status.detected_language = detected_language
            storage.save_status(status, workspace=normalized_workspace)
        except Exception as e:
            logger.warning(f"Failed to save extraction status: {e}")

        logger.info(f"Extracted {len(markdown)} chars from {docx_path.name} to {artifact_output}")
        return markdown

    except Exception as e:
        logger.warning(f"Kreuzberg extraction failed for {docx_path}, using fallback parser: {e}")
        fallback_markdown = _fallback_extract_docx_to_markdown(docx_path)
        if fallback_markdown:
            _write_markdown_artifact(docx_path, document_id, fallback_markdown)
            return fallback_markdown
        msg = f"Failed to extract DOCX: {e}"
        raise ExtractionError(msg) from e


def extract_from_folder(
    document_id: str,
    folder_path: Path,
    storage: AiStorage,
    main_doc_path: Path | None = None,
    workspace: str | None = None,
) -> str:
    """Extract content from all relevant files in a TDoc folder.

    Args:
        document_id: Document identifier.
        folder_path: Path to TDoc checkout folder.
        storage: AiStorage instance.
        main_doc_path: Optional path to main document.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Combined Markdown content.
    """
    if not folder_path.exists():
        msg = f"Folder not found: {folder_path}"
        logger.warning(msg)
        raise ExtractionError(msg)

    # Find DOCX files
    docx_files = sorted(folder_path.glob("*.docx"))

    if not docx_files:
        msg = f"No DOCX files found in {folder_path}"
        logger.warning(msg)
        raise ExtractionError(msg)

    # Use specified main doc or find it
    if main_doc_path:
        if not main_doc_path.exists():
            msg = f"Configured main document does not exist: {main_doc_path}"
            raise ExtractionError(msg)
        docx_to_extract = main_doc_path
    elif len(docx_files) == 1:
        docx_to_extract = docx_files[0]
    else:
        # Multiple files - need classification (defer to pipeline)
        logger.info(f"Multiple DOCX files found, classification needed: {docx_files}")
        docx_to_extract = docx_files[0]  # Just use first for now

    return extract_docx_to_markdown(document_id, docx_to_extract, storage, workspace=workspace)


__all__ = [
    "compute_source_hash",
    "extract_docx_to_markdown",
    "extract_from_folder",
]
