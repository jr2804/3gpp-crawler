"""TDoc file classification logic."""

from __future__ import annotations

import re
from pathlib import Path

from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.misc import utc_now

from threegpp_ai.models import DocumentClassification

logger = get_logger(__name__)

# Heuristic patterns for classifying TDoc files
FINAL_PATTERNS = [
    r"(?i)\bfinal\b",
    r"(?i)\bapproved\b",
    r"(?i)\brelease\b",
    r"(?i)\bv\d+\.\d+\b",  # Version numbers like v1.0
]

DRAFT_PATTERNS = [
    r"(?i)\bdraft\b",
    r"(?i)\bworking\b",
    r"(?i)\bpreliminary\b",
    r"(?i)\bwip\b",
    r"(?i)\binternal\b",
]

REVISION_PATTERNS = [
    r"(?i)\brev(?:ision)?\s*\d+",  # rev 1, revision 2
    r"(?i)\bcr\b",  # Change Request
    r"(?i)\bchange\s*request\b",
    r"(?i)\bcorrigendum\b",
]

STRUCTURED_PATTERNS = [
    r"\.(docx?|doc?|pdf)$",  # Word and PDF are structured
    r"(?i)\breport\b",
    r"(?i)\bspecification\b",
    r"(?i)\bstandard\b",
    r"(?i)\bprocedure\b",
    r"(?i)\bguideline\b",
]

UNSTRUCTURED_PATTERNS = [
    r"\.(pptx?|ppt)$",  # PowerPoint
    r"\.(xlsx?|xls)$",  # Excel
    r"\.(txt|csv)$",  # Misc. text data
]


def _score_filename(filename: str) -> float:
    """Calculate a heuristic score for a filename indicating likelihood of being main document.

    Args:
        filename: The filename to score (not full path).

    Returns:
        Score between 0.0 and 1.0.
    """
    score = 0.5  # Base score

    name_lower = filename.lower()

    # Check final patterns
    for pattern in FINAL_PATTERNS:
        if re.search(pattern, name_lower):
            score += 0.15

    # Check draft patterns (reduce score)
    for pattern in DRAFT_PATTERNS:
        if re.search(pattern, name_lower):
            score -= 0.2

    # Check revision patterns (increase score)
    for pattern in REVISION_PATTERNS:
        if re.search(pattern, name_lower):
            score += 0.2

    # Check structured document patterns (increase score)
    for pattern in STRUCTURED_PATTERNS:
        if re.search(pattern, name_lower):
            score += 0.1

    # Check unstructured patterns (decrease score)
    for pattern in UNSTRUCTURED_PATTERNS:
        if re.search(pattern, name_lower):
            score -= 0.15

    # TDoc ID in filename increases relevance
    if re.search(r"[A-Z]{1,3}-\d{6,}", filename):
        score += 0.1

    # Clamp to 0.0-1.0
    return max(0.0, min(1.0, score))


def _determine_heuristic(
    scores: dict[Path, float],
    file_sizes: dict[Path, int],
) -> tuple[Path, str, float]:
    """Determine the decisive heuristic and confidence.

    Args:
        scores: Dict mapping candidate files to classification score.
        file_sizes: Dict mapping candidate files to file size in bytes.

    Returns:
        Tuple of (main_file, heuristic_description, confidence).
    """
    best_file = max(
        scores,
        key=lambda path: (scores[path], file_sizes[path], path.name.lower()),
    )
    best_score = scores[best_file]

    if len(scores) == 1:
        return best_file, "single_file", 1.0

    ranked_files = sorted(
        scores,
        key=lambda path: (scores[path], file_sizes[path], path.name.lower()),
        reverse=True,
    )
    second_file = ranked_files[1]
    second_score = scores[second_file]
    best_size = file_sizes[best_file]
    second_size = file_sizes[second_file]

    if best_score - second_score >= 0.15:
        return best_file, "filename_heuristic_high", max(best_score, 0.7)

    if second_size > 0 and best_size >= second_size * 1.5:
        return best_file, "file_size_and_heuristic", max(best_score, 0.7)

    return best_file, "file_size_fallback", 0.5


# Extensions to scan when looking for document files
_DOCUMENT_EXTENSIONS = ["*.doc", "*.docx", "*.pdf", "*.ppt", "*.pptx", "*.xls", "*.xlsx", "*.txt", "*.csv"]


def _scan_document_files(folder_path: Path) -> list[Path]:
    """Scan a folder for document files, excluding hidden files.

    Args:
        folder_path: Directory to scan.

    Returns:
        Deduplicated list of document file paths.
    """
    files: list[Path] = []
    for ext in _DOCUMENT_EXTENSIONS:
        files.extend([p for p in folder_path.glob(ext) if p.is_file() and not p.name.startswith(".")])
    return list(dict.fromkeys(files))  # Preserves order, removes duplicates


def _score_file(file: Path) -> tuple[float, int]:
    """Combine filename heuristic score with file size factor.

    Args:
        file: Document file to score.

    Returns:
        Tuple of (combined_score, file_size_bytes).
    """
    filename_score = _score_filename(file.name)
    file_size_bytes = file.stat().st_size
    size_score = min(file_size_bytes / (1024 * 1024) / 10.0, 1.0) * 0.3
    return filename_score * 0.7 + size_score, file_size_bytes


def pick_main_document(folder_path: Path) -> Path | None:
    """Pick the main document from a folder using heuristic scoring.

    Uses filename patterns, file size, and file type to determine which file
    is most likely the primary document. Does not require a TDoc ID.

    Args:
        folder_path: Path to the folder containing document files.

    Returns:
        Path to the best document file, or None if no suitable files found.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return None

    files = _scan_document_files(folder_path)
    if not files:
        return None

    if len(files) == 1:
        return files[0]

    scores: dict[Path, float] = {}
    file_sizes: dict[Path, int] = {}
    for file in files:
        combined, size = _score_file(file)
        scores[file] = combined
        file_sizes[file] = size

    best_file, _, _ = _determine_heuristic(scores, file_sizes)
    logger.debug("Picked %s as main document from %d files in %s", best_file.name, len(files), folder_path)
    return best_file


def classify_document_files(
    document_id: str,
    folder_path: Path,
) -> list[DocumentClassification]:
    """Classify files in a document folder to identify the main document.

    Uses heuristic scoring based on filename patterns, file size, and file type
    to determine which file is likely the main document.

    Args:
        document_id: Document identifier (e.g., "SP-123456").
        folder_path: Path to the TDoc checkout folder.

    Returns:
        List of DocumentClassification objects, one per file.
        The is_main_document field indicates the primary file.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning("Folder not found: %s", folder_path)
        return []

    files = _scan_document_files(folder_path)
    if not files:
        # Log folder contents for debugging
        try:
            folder_contents = list(folder_path.iterdir())
            contents_summary = [f.name for f in folder_contents]
        except (OSError, PermissionError):
            contents_summary = ["<cannot read folder>"]
        
        logger.warning(
            "No document files found in %s for document %s. "
            "Expected: .pdf/.docx/.xlsx/.pptx files. "
            "Folder contents: %s. "
            "Run 'tdoc-crawler checkout %s' to re-download if folder is empty.",
            folder_path,
            document_id,
            contents_summary,
            document_id,
        )
        return []

    if len(files) == 1:
        file = files[0]
        return [
            DocumentClassification(
                document_id=document_id,
                file_path=str(file.relative_to(folder_path)),
                is_main_document=True,
                confidence=1.0,
                decisive_heuristic="single_file",
                file_size_bytes=file.stat().st_size,
                classified_at=utc_now(),
            )
        ]

    # Multiple files — score and classify
    scores: dict[Path, float] = {}
    file_sizes: dict[Path, int] = {}
    for file in files:
        combined, size = _score_file(file)
        scores[file] = combined
        file_sizes[file] = size

    best_file, heuristic, confidence = _determine_heuristic(scores, file_sizes)

    result: list[DocumentClassification] = []
    for file in files:
        is_main = file == best_file
        file_score = scores[file]

        if is_main:
            conf = confidence
            heur = heuristic
        else:
            conf = file_score
            heur = "secondary_file"

        result.append(
            DocumentClassification(
                document_id=document_id,
                file_path=str(file.relative_to(folder_path)),
                is_main_document=is_main,
                confidence=conf,
                decisive_heuristic=heur,
                file_size_bytes=file_sizes[file],
                classified_at=utc_now(),
            )
        )

    logger.info(
        "Classified %d files for %s, main: %s (confidence: %.2f)",
        len(files),
        document_id,
        best_file.name,
        confidence,
    )

    return result


__all__ = [
    "_score_filename",
    "classify_document_files",
    "pick_main_document",
]
