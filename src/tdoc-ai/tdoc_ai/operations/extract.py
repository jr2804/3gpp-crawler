"""Document-to-Markdown extraction using Kreuzberg (DOCX) and doc2txt (DOC)."""

from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from pathlib import Path

from doc2txt import extract_text as doc2txt_extract
from kreuzberg import ExtractionConfig, KeywordAlgorithm, KeywordConfig, LanguageDetectionConfig, extract_file_sync

from tdoc_ai.models import ExtractionError, ProcessingStatus
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.storage import AiStorage
from tdoc_crawler.tdocs.utils import normalize_tdoc_id
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)


def _artifact_path(docx_path: Path, document_id: str) -> Path:
    artifact_dir = docx_path.parent / ".ai"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir / f"{normalize_tdoc_id(document_id)}.md"


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


def extract_doc_to_markdown(
    document_id: str,
    doc_path: Path,
    storage: AiStorage,
    workspace: str | None = None,
) -> str:
    """Extract content from legacy Office 2003 .doc file to Markdown using doc2txt.

    Args:
        document_id: Document identifier.
        doc_path: Path to .doc file.
        storage: AiStorage instance for status tracking.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        Extracted content as Markdown string.

    Raises:
        ExtractionError: If extraction fails.
    """
    if not doc_path.exists():
        msg = f"DOC file not found: {doc_path}"
        raise ExtractionError(msg)

    if doc_path.suffix.lower() != ".doc":
        msg = f"File must be .doc format: {doc_path}"
        raise ExtractionError(msg)

    normalized_workspace = normalize_workspace_name(workspace)

    # Check for change detection (idempotency)
    current_hash = compute_source_hash(doc_path)
    artifact_path = _artifact_path(doc_path, document_id)

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
        # Extract .doc to text using doc2txt (antiword wrapper)
        logger.info(f"Extracting {doc_path.name} using doc2txt (antiword)")
        markdown = doc2txt_extract(str(doc_path), optimize_format=True)

        if not markdown:
            msg = f"No content extracted from {doc_path.name}"
            raise ExtractionError(msg)

        artifact_output = _write_markdown_artifact(doc_path, document_id, markdown)

        # Save hash for future idempotency
        try:
            status = storage.get_status(document_id, workspace=normalized_workspace)
            if status is None:
                status = ProcessingStatus(document_id=document_id)
            status.source_hash = current_hash
            status.extracted_at = utc_now()
            status.error_message = None
            # Note: doc2txt doesn't provide keywords or language detection
            storage.save_status(status, workspace=normalized_workspace)
        except Exception as e:
            logger.warning(f"Failed to save extraction status: {e}")

        logger.info(f"Extracted {len(markdown)} chars from {doc_path.name} to {artifact_output}")
        return markdown

    except Exception as e:
        msg = f"Failed to extract DOC: {e}"
        raise ExtractionError(msg) from e


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

    Supports both:
    - .doc files (Office 2003, uses doc2txt/antiword)
    - .docx files (Office 2007+, uses kreuzberg)

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

    # Find both .doc and .docx files
    doc_files = sorted(folder_path.glob("*.doc"))
    docx_files = sorted(folder_path.glob("*.docx"))

    if not doc_files and not docx_files:
        msg = f"No .doc or .docx files found in {folder_path}"
        logger.warning(msg)
        raise ExtractionError(msg)

    # Use specified main doc or auto-detect
    if main_doc_path:
        if not main_doc_path.exists():
            msg = f"Configured main document does not exist: {main_doc_path}"
            raise ExtractionError(msg)

        # Route based on file extension
        if main_doc_path.suffix.lower() == ".doc":
            return extract_doc_to_markdown(document_id, main_doc_path, storage, workspace=workspace)
        else:
            return extract_docx_to_markdown(document_id, main_doc_path, storage, workspace=workspace)

    # Auto-detect which file type to use
    # Prefer .docx over .doc if both exist
    if docx_files:
        docx_to_extract = docx_files[0]
        logger.info(f"Using DOCX file: {docx_to_extract.name}")
        if len(docx_files) > 1:
            logger.info(f"Multiple DOCX files found, using first: {docx_files}")
        return extract_docx_to_markdown(document_id, docx_to_extract, storage, workspace=workspace)
    elif doc_files:
        doc_to_extract = doc_files[0]
        logger.info(f"Using DOC file (Office 2003): {doc_to_extract.name}")
        if len(doc_files) > 1:
            logger.info(f"Multiple DOC files found, using first: {doc_files}")
        return extract_doc_to_markdown(document_id, doc_to_extract, storage, workspace=workspace)
    else:
        # Shouldn't reach here due to earlier check
        msg = f"No supported documents found in {folder_path}"
        raise ExtractionError(msg)


__all__ = [
    "compute_source_hash",
    "extract_doc_to_markdown",
    "extract_docx_to_markdown",
    "extract_from_folder",
]
