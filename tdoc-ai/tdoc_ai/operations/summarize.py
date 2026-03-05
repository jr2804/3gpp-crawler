"""Document summarization using LLMs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re

import litellm

from tdoc_ai.config import AiConfig
from tdoc_ai.container import AiServiceContainer
from tdoc_ai.models import DocumentSummary, LlmConfigError, SummarizeResult
from tdoc_ai.operations.workspace_names import normalize_workspace_name
from tdoc_ai.storage import AiStorage
from tdoc_crawler.tdocs.sources.whatthespec import resolve_via_whatthespec
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)
storage = None

# Summary settings
ABSTRACT_MIN_WORDS = 150
ABSTRACT_MAX_WORDS = 250

# Prompt templates
SUMMARY_SYSTEM_PROMPT = """You are a technical document analyzer specializing in 3GPP TDoc documents.
Generate concise, informative summaries following the specified structure."""

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


def _get_ai_config() -> AiConfig:
    """Load AI config and normalize configuration errors to LlmConfigError."""
    try:
        return AiServiceContainer.get_instance().get_config()
    except Exception as exc:
        msg = f"Invalid or missing LLM configuration: {exc}"
        raise LlmConfigError(msg) from exc


class LiteLLMClient:
    """Client for LiteLLM API."""

    _instance: LiteLLMClient | None = None

    def __new__(cls) -> LiteLLMClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        logger.info("LiteLLM client initialized")

    def complete(
        self,
        prompt: str,
        system_prompt: str = SUMMARY_SYSTEM_PROMPT,
        max_tokens: int = 2000,
        model: str | None = None,
    ) -> str:
        """Generate completion from prompt.

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            max_tokens: Maximum tokens in response.
            model: Model identifier (e.g., 'openai/gpt-4o-mini'). Defaults to config.llm_model.

        Returns:
            Generated text.
        """
        try:
            # Check for TDC_AI_LLM_API_KEY - takes precedence over provider-specific keys
            api_key = os.environ.get("TDC_AI_LLM_API_KEY")

            response = litellm.completion(
                model=model or AiConfig().llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                api_key=api_key,  # Pass TDC_AI_LLM_API_KEY if set, otherwise None (LiteLLM uses provider-specific env vars)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise


def _should_skip_summary(
    document_id: str,
    content_hash: str,
    storage_client: AiStorage | None = None,
) -> bool:
    """Check if summary should be skipped based on content hash.

    Args:
        document_id: Document identifier.
        content_hash: Hash of content.
        storage_client: Storage client instance.

    Returns:
        True if summary exists and is current.
    """
    try:
        if storage_client is not None:
            existing = storage_client.get_summary_hash(document_id)
            return existing == content_hash

        storage_client = AiServiceContainer.get_instance().get_storage()
        existing = storage_client.get_summary_hash(document_id)
        return existing == content_hash
    except Exception:
        return False


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
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> DocumentSummary:
    """Generate summary for a document.

    Args:
        document_id: Document identifier.
        markdown: Markdown content.
        storage: Optional storage instance.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        DocumentSummary object.
    """
    config = _get_ai_config()
    storage_client = storage or AiServiceContainer.get_instance().get_storage()

    normalized_workspace = normalize_workspace_name(workspace)

    # Compute content hash
    content_hash = hashlib.sha256(markdown.encode()).hexdigest()

    if _should_skip_summary(document_id, content_hash, storage_client=storage_client):
        logger.info(f"Skipping summary for {document_id} - content unchanged")
        existing = storage_client.get_summary(document_id, workspace=normalized_workspace)
        if existing:
            return existing

    # Get LLM client
    client = _get_llm_client()

    # Generate abstract
    abstract_prompt = ABSTRACT_PROMPT.format(content=markdown[:5000])  # Limit input
    try:
        abstract = client.complete(abstract_prompt, model=config.llm_model)
    except Exception as exc:
        msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
        raise LlmConfigError(msg) from exc

    structured_prompt = STRUCTURED_SUMMARY_PROMPT.format(
        abstract=abstract,
        content=markdown[:5000],
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

    # Save to storage
    storage_client.save_summary(summary, workspace=normalized_workspace)
    storage_client.save_summary_hash(document_id, content_hash)

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
CONCISE_SUMMARY_PROMPT = """Generate a summary of approximately {target_words} words for this document:

{content}

Provide a concise summary that captures the main purpose and key outcomes."""

# Prompt for keyword extraction
KEYWORDS_PROMPT = """Extract 5-10 relevant keywords from this document. Return ONLY a JSON array of strings, nothing else.

Document:
{content}

Example output format: ["keyword1", "keyword2", "keyword3"]"""


def summarize_tdoc(
    document_id: str,
    words: int = 200,
    format: str = "markdown",
    fetch_remote: bool = True,
) -> SummarizeResult:
    """Summarize a TDoc by ID.

    Args:
        document_id: Document identifier (e.g., "R1-2400001").
        words: Target word count for summary (default: 200).
        format: Output format - "markdown", "json", or "yaml" (default: "markdown").
        fetch_remote: If True, fetch TDoc metadata from WhatTheSpec if not local.

    Returns:
        SummarizeResult containing summary, keywords, metadata, and word count.

    Raises:
        LlmConfigError: If LLM endpoint is unreachable or misconfigured.
        ValueError: If format is not supported.
    """
    # Normalize TDoc ID

    normalized_id = document_id.strip().upper()

    # Try to get metadata from WhatTheSpec
    metadata = None
    content = ""
    source = "unknown"
    meeting_id = 0
    title = ""

    try:
        metadata = resolve_via_whatthespec(normalized_id)
        if metadata:
            title = metadata.title
            meeting_id = metadata.meeting_id
            source = "whatthespec"
            logger.info(f"Fetched metadata for {normalized_id} from WhatTheSpec")
    except Exception as e:
        logger.warning(f"Failed to fetch {normalized_id} from WhatTheSpec: {e}")
        if not fetch_remote:
            msg = f"TDoc {normalized_id} not found and fetch_remote=False"
            raise ValueError(msg) from e

    # If we don't have metadata and fetch_remote is False, raise error
    if metadata is None and not fetch_remote:
        msg = f"TDoc {normalized_id} not found locally and fetch_remote=False"
        raise ValueError(msg)

    # Use metadata info as content
    # In a full implementation, this would download and extract the actual TDoc content
    if metadata:
        content_parts = [
            f"Title: {metadata.title}",
            f"Type: {metadata.tdoc_type}",
            f"Purpose: {metadata.for_purpose}",
            f"Source: {metadata.source}",
            f"Contact: {metadata.contact}",
        ]
        content = "\n\n".join(content_parts)
    else:
        # Fallback - just use the tdoc_id as content placeholder
        content = f"TDoc ID: {normalized_id}"

    # Get LLM client
    config = _get_ai_config()
    client = _get_llm_client()

    # Generate summary
    summary_prompt = CONCISE_SUMMARY_PROMPT.format(
        target_words=words,
        content=content[:8000],  # Limit input size
    )
    try:
        summary = client.complete(summary_prompt, model=config.llm_model, max_tokens=words * 4)
    except Exception as exc:
        msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
        raise LlmConfigError(msg) from exc

    # Extract keywords
    keywords_prompt = KEYWORDS_PROMPT.format(content=content)  # TODO: limit content size for keyword extraction as well, maybe 5000 chars?
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
        "meeting_id": meeting_id,
        "source": source,
        "word_count": word_count,
    }
    if title:
        result_metadata["title"] = title

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
