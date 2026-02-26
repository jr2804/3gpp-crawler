"""TDoc file classification logic."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from tdoc_crawler.ai.models import DocumentClassification
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)

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
    r"\.(docx?|pdf)$",  # Word and PDF are structured
    r"(?i)\breport\b",
    r"(?i)\bspecification\b",
    r"(?i)\bstandard\b",
    r"(?i)\bprocedure\b",
    r"(?i)\bguideline\b",
]

UNSTRUCTURED_PATTERNS = [
    r"\.(pptx?|ppt)$",  # PowerPoint
    r"\.(xlsx?|xls)$",  # Excel
    r"\.(txt|csv)$",
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


def classify_tdoc_files(
    tdoc_id: str,
    folder_path: Path,
) -> list[DocumentClassification]:
    """Classify files in a TDoc folder to identify the main document.

    Uses heuristic scoring based on filename patterns, file size, and file type
    to determine which file is likely the main document.

    Args:
        tdoc_id: TDoc identifier (e.g., "SP-123456").
        folder_path: Path to the TDoc checkout folder.

    Returns:
        List of DocumentClassification objects, one per file.
        The is_main_document field indicates the primary file.
    """
    if not folder_path.exists() or not folder_path.is_dir():
        logger.warning(f"Folder not found: {folder_path}")
        return []

    files = [file_path for file_path in folder_path.glob("*.docx") if file_path.is_file() and not file_path.name.startswith(".")]

    if not files:
        logger.warning(f"No DOCX files found in {folder_path} for TDoc {tdoc_id}")
        return []

    if len(files) == 1:
        # Single file - automatic main document
        file = files[0]
        return [
            DocumentClassification(
                tdoc_id=tdoc_id,
                file_path=str(file.relative_to(folder_path)),
                is_main_document=True,
                confidence=1.0,
                decisive_heuristic="single_file",
                file_size_bytes=file.stat().st_size,
                classified_at=utc_now(),
            )
        ]

    # Multiple DOCX files - need classification
    scores: dict[Path, float] = {}
    file_sizes: dict[Path, int] = {}
    for file in files:
        filename_score = _score_filename(file.name)
        file_size_bytes = file.stat().st_size
        file_sizes[file] = file_size_bytes
        size_score = file_size_bytes / (1024 * 1024)
        size_score = min(size_score / 10.0, 1.0) * 0.3

        combined = filename_score * 0.7 + size_score
        scores[file] = combined

    best_file, heuristic, confidence = _determine_heuristic(scores, file_sizes)

    # Build result list
    result: list[DocumentClassification] = []
    for file in files:
        is_main = file == best_file
        file_score = scores[file]

        # Adjust confidence for non-main documents
        if is_main:
            conf = confidence
            heur = heuristic
        else:
            conf = file_score
            heur = "secondary_file"

        result.append(
            DocumentClassification(
                tdoc_id=tdoc_id,
                file_path=str(file.relative_to(folder_path)),
                is_main_document=is_main,
                confidence=conf,
                decisive_heuristic=heur,
                file_size_bytes=file_sizes[file],
                classified_at=utc_now(),
            )
        )

    logger.info(f"Classified {len(files)} files for {tdoc_id}, main: {best_file.name} (confidence: {confidence:.2f})")

    return result


__all__ = [
    "_score_filename",
    "classify_tdoc_files",
]
