"""Document summarization using LLMs."""

from __future__ import annotations

import json
import logging
import re

from tdoc_crawler.utils.misc import utc_now

from threegpp_ai.config import AiConfig
from threegpp_ai.models import DocumentSummary, LlmConfigError, SummarizeResult

from .convert import extract_tdoc_structured
from .llm_client import LiteLLMClient
from .metrics import MetricType, get_metrics_tracker, timed_operation

logger = logging.getLogger(__name__)

# Input size limits for LLM prompts
ABSTRACT_INPUT_LIMIT = 5000
SUMMARY_INPUT_LIMIT = 8000
KEYWORDS_INPUT_LIMIT = 5000


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to maximum character limit.

    Args:
        text: Text to truncate.
        max_chars: Maximum number of characters.

    Returns:
        Truncated text with ellipsis if truncated.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


# Prompt templates
ABSTRACT_PROMPT = """Generate a brief abstract (150-250 words) for this document:

{content}

Provide a concise summary capturing the main purpose and key outcomes."""

STRUCTURED_SUMMARY_PROMPT = """Based on this abstract and source document, return JSON only.

Required keys:
- key_points: list[str]
- action_items: list[str]
- decisions: list[str]
- affected_specs: list[str]

Abstract:
{abstract}

Source document:
{content}
"""


def _count_words(text: str) -> int:
    """Count words in text.

    Args:
        text: Text to count.

    Returns:
        Word count.
    """
    return len(text.split())


def _get_llm_client() -> LiteLLMClient:
    """Get LLM client instance.

    Returns:
        LiteLLMClient instance.
    """
    return LiteLLMClient()


def _strip_code_fences(payload: str | None) -> str:
    """Strip optional markdown code fences from LLM payloads."""
    if payload is None:
        return ""
    value = payload.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _coerce_string_list(raw: object) -> list[str]:
    """Normalize mixed payload shapes into a list of non-empty strings."""
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _parse_structured_summary(payload: str) -> dict[str, list[str]]:
    """Parse JSON structured summary fields from LLM output."""
    try:
        data = json.loads(_strip_code_fences(payload))
    except json.JSONDecodeError:
        return {
            "key_points": [],
            "action_items": [],
            "decisions": [],
            "affected_specs": [],
        }

    return {
        "key_points": _coerce_string_list(data.get("key_points")),
        "action_items": _coerce_string_list(data.get("action_items")),
        "decisions": _coerce_string_list(data.get("decisions")),
        "affected_specs": _coerce_string_list(data.get("affected_specs")),
    }


def summarize_document(
    document_id: str,
    markdown: str,
) -> DocumentSummary:
    """Generate summary for a document.

    Args:
        document_id: Document identifier.
        markdown: Markdown content.

    Returns:
        DocumentSummary object.
    """
    config = AiConfig.from_env()

    # Get LLM client
    client = _get_llm_client()

    # Generate abstract
    truncated_markdown = _truncate_text(markdown, ABSTRACT_INPUT_LIMIT)
    abstract_prompt = ABSTRACT_PROMPT.format(content=truncated_markdown)
    try:
        abstract = client.complete(abstract_prompt, model=config.llm_model)
    except Exception as exc:
        msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
        raise LlmConfigError(msg) from exc

    # Generate structured summary
    truncated_for_structured = _truncate_text(markdown, SUMMARY_INPUT_LIMIT)
    structured_prompt = STRUCTURED_SUMMARY_PROMPT.format(
        abstract=abstract,
        content=truncated_for_structured,
    )
    try:
        structured_payload = client.complete(structured_prompt)
    except Exception as exc:
        msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
        raise LlmConfigError(msg) from exc

    structured = _parse_structured_summary(structured_payload)

    # Count words in original content for intelligent warning
    original_word_count = _count_words(markdown)

    # Validate abstract word count
    word_count = _count_words(abstract)

    # Only warn if summary is short BUT original document has enough content
    # If original is already shorter than minimum, summary can't be longer
    if word_count < config.abstract_min_words:
        if original_word_count >= config.abstract_min_words:
            # Original has enough content, summary should be longer
            logger.warning(
                f"Abstract for {document_id} shorter than minimum: {word_count} words "
                f"(minimum: {config.abstract_min_words}, original document: {original_word_count} words)"
            )
        else:
            # Original is too short - don't warn, summary can't be longer than source
            logger.debug(
                f"Abstract for {document_id} has {word_count} words, "
                f"but original document is short ({original_word_count} words, minimum: {config.abstract_min_words})"
            )
    elif word_count > config.abstract_max_words:
        logger.warning(f"Abstract for {document_id} exceeds maximum: {word_count} words (maximum: {config.abstract_max_words})")

    key_points = structured["key_points"] or _extract_key_points(abstract)
    action_items = structured["action_items"] or _extract_action_items(markdown)
    decisions = structured["decisions"] or _extract_decisions(markdown)
    affected_specs = structured["affected_specs"] or _extract_spec_references(markdown)

    # Create summary
    summary = DocumentSummary(
        document_id=document_id,
        abstract=abstract,
        key_points=key_points,
        action_items=action_items,
        decisions=decisions,
        affected_specs=affected_specs,
        llm_model=config.llm_model,
        prompt_version="v2",
        generated_at=utc_now(),
    )

    logger.info(f"Generated summary for {document_id}")
    return summary


def _extract_key_points(abstract: str) -> list[str]:
    """Extract key points from text.

    Args:
        abstract: Abstract text.

    Returns:
        List of key points.
    """
    # Simplified - would use LLM in production
    sentences = abstract.split(". ")
    return [s.strip() for s in sentences[:5] if len(s.strip()) > 20]


def _extract_action_items(markdown: str) -> list[str]:
    """Extract action items from markdown.

    Args:
        markdown: Markdown content.

    Returns:
        List of action items.
    """
    # Look for common action item patterns
    patterns = [
        r"action\s*(?:item)?:\s*(.+?)(?:\n|$)",
        r"todo:\s*(.+?)(?:\n|$)",
        r"to do:\s*(.+?)(?:\n|$)",
    ]

    action_items: list[str] = []

    for pattern in patterns:
        matches = re.findall(pattern, markdown, re.IGNORECASE)
        action_items.extend(matches)

    return action_items[:10]  # Limit to 10


def _extract_decisions(markdown: str) -> list[str]:
    """Extract decisions from markdown.

    Args:
        markdown: Markdown content.

    Returns:
        List of decisions.
    """
    # Look for decision patterns
    pattern = r"decision:\s*(.+?)(?:\n|$)"
    matches = re.findall(pattern, markdown, re.IGNORECASE)

    return [m.strip() for m in matches[:10]]


def _extract_spec_references(markdown: str) -> list[str]:
    """Extract specification references from markdown.

    Args:
        markdown: Markdown content.

    Returns:
        List of spec references (e.g., "TS 26.260").
    """
    # Match 3GPP spec patterns: TS/TR XX.XXX, TS/TS XX.XXX
    pattern = r"(?:TS|TR|TS\s*:\s*)(\d{2}\.\d{3,4})"
    matches = re.findall(pattern, markdown)

    # Deduplicate and format
    specs = list({f"TS {m}" for m in matches})
    return specs[:20]  # Limit to 20


# Prompt for concise summary with word count constraint
CONCISE_SUMMARY_PROMPT = """Generate a summary of approximately {max_words} words or less for this document:

{content}

Provide a concise summary that captures the main purpose and key outcomes."""

# Prompt for keyword extraction
KEYWORDS_PROMPT = """Extract 5-10 relevant keywords from this document. Return ONLY a JSON array of strings, nothing else.

Document:
{content}

Example output format: ["keyword1", "keyword2", "keyword3"]"""


def summarize_tdoc(
    document_id: str,
    max_words: int = 200,
    force: bool = False,
) -> SummarizeResult:
    """Summarize a TDoc by ID.

    Args:
        document_id: Document identifier (e.g., "R1-2400001").
        max_words: Maximum word count for summary (default: 200).
        force: Force reconversion even if cached.

    Returns:
        SummarizeResult containing summary, keywords, metadata, and word count.

    Raises:
        LlmConfigError: If LLM endpoint is unreachable or misconfigured.
        ValueError: If format is not supported.
    """
    normalized_id = document_id.strip().upper()

    with timed_operation(get_metrics_tracker(), normalized_id, MetricType.SUMMARIZATION):
        extraction = extract_tdoc_structured(normalized_id, force=force)
        content = extraction.content

        # Get LLM client
        config = AiConfig.from_env()
        client = _get_llm_client()

        # Generate summary
        truncated_for_summary = _truncate_text(content, SUMMARY_INPUT_LIMIT)
        summary_prompt = CONCISE_SUMMARY_PROMPT.format(
            max_words=max_words,
            content=truncated_for_summary,
        )
        try:
            summary = client.complete(summary_prompt, model=config.llm_model, max_tokens=max_words * 4)
        except Exception as exc:
            msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
            raise LlmConfigError(msg) from exc

        # Extract keywords
        truncated_for_keywords = _truncate_text(content, KEYWORDS_INPUT_LIMIT)
        keywords_prompt = KEYWORDS_PROMPT.format(content=truncated_for_keywords)
        try:
            keywords_raw = client.complete(keywords_prompt, model=config.llm_model, max_tokens=200)
            keywords = _parse_keywords(keywords_raw)
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            keywords = []

        # Count actual words
        word_count = _count_words(summary)

        # Build metadata dict
        result_metadata: dict = {
            "word_count": word_count,
        }

        # Create result
        result = SummarizeResult(
            summary=summary,
            keywords=keywords,
            metadata=result_metadata,
            word_count=word_count,
        )

        logger.info(f"Generated summary for {normalized_id}: {word_count} words, {len(keywords)} keywords")
        return result


def _parse_keywords(payload: str) -> list[str]:
    """Parse keywords from LLM JSON output.

    Args:
        payload: Raw LLM output containing JSON array.

    Returns:
        List of keyword strings.
    """
    try:
        # Try to parse as JSON
        cleaned = _strip_code_fences(payload)
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [str(kw).strip() for kw in data if str(kw).strip()]
    except json.JSONDecodeError, ValueError:
        pass

    # Fallback: extract keywords by splitting on common delimiters
    cleaned = _strip_code_fences(payload)
    if "[" in cleaned:
        # Extract content between brackets
        match = re.search(r"\[(.*?)\]", cleaned)
        if match:
            items = match.group(1).split(",")
            return [item.strip().strip("\"'").strip() for item in items if item.strip()]

    # Last resort: split on newlines or commas
    items = cleaned.replace(",", "\n").split("\n")
    return [item.strip().strip("\"'").strip() for item in items if item.strip()][:10]


__all__ = [
    "SummarizeResult",
    "_count_words",
    "summarize_document",
    "summarize_tdoc",
]
