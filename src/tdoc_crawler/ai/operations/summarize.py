"""Document summarization using LLMs."""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import re

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.models import DocumentSummary, LlmConfigError
from tdoc_crawler.ai.operations.workspaces import normalize_workspace_name
from tdoc_crawler.ai.storage import AiStorage
from tdoc_crawler.config import CacheManager
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
        manager = CacheManager().register()
        return AiConfig.from_env(cache_manager_name=manager.name)
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
        self._client = None
        self._load_client()

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
        if self._client is None:
            msg = "litellm not installed"
            raise RuntimeError(msg)

        try:
            response = self._client.completion(
                model=model or AiConfig().llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise

    def _load_client(self) -> None:
        """Load the litellm client."""
        try:
            self._client = importlib.import_module("litellm")
            logger.info("Loaded litellm client")
        except ImportError:
            logger.warning("litellm not installed")
            self._client = None


def _should_skip_summary(
    tdoc_id: str,
    content_hash: str,
    storage_client: AiStorage | None = None,
) -> bool:
    """Check if summary should be skipped based on content hash.

    Args:
        tdoc_id: TDoc identifier.
        content_hash: Hash of content.
        storage_client: Storage client instance.

    Returns:
        True if summary exists and is current.
    """
    try:
        if storage_client is not None:
            existing = storage_client.get_summary_hash(tdoc_id)
            return existing == content_hash

        if storage is not None:
            existing = storage.get_summary_hash(tdoc_id)
            return existing == content_hash

        config = _get_ai_config()
        storage_client = AiStorage(config.ai_store_path)  # type: ignore[arg-type]
        existing = storage_client.get_summary_hash(tdoc_id)
        return existing == content_hash
    except Exception:
        return False


def _strip_code_fences(payload: str) -> str:
    """Strip optional markdown code fences from LLM payloads."""
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
    tdoc_id: str,
    markdown: str,
    storage: AiStorage | None = None,
    workspace: str | None = None,
) -> DocumentSummary:
    """Generate summary for a document.

    Args:
        tdoc_id: TDoc identifier.
        markdown: Markdown content.
        storage: Optional storage instance.
        workspace: Optional workspace scope (defaults to "default").

    Returns:
        DocumentSummary object.
    """
    config = _get_ai_config()

    if storage is None:
        storage = AiStorage(config.ai_store_path)  # type: ignore[arg-type]

    normalized_workspace = normalize_workspace_name(workspace)

    # Compute content hash
    content_hash = hashlib.sha256(markdown.encode()).hexdigest()

    if _should_skip_summary(tdoc_id, content_hash, storage_client=storage):
        logger.info(f"Skipping summary for {tdoc_id} - content unchanged")
        existing = storage.get_summary(tdoc_id, workspace=normalized_workspace)
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

    # Validate abstract word count
    word_count = _count_words(abstract)
    if word_count < config.abstract_min_words or word_count > config.abstract_max_words:
        logger.warning(f"Abstract for {tdoc_id} outside recommended range: {word_count} words")

    key_points = structured["key_points"] or _extract_key_points(abstract)
    action_items = structured["action_items"] or _extract_action_items(markdown)
    decisions = structured["decisions"] or _extract_decisions(markdown)
    affected_specs = structured["affected_specs"] or _extract_spec_references(markdown)

    # Create summary
    summary = DocumentSummary(
        tdoc_id=tdoc_id,
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
    storage.save_summary(summary, workspace=normalized_workspace)
    storage.save_summary_hash(tdoc_id, content_hash)

    logger.info(f"Generated summary for {tdoc_id}")
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


__all__ = [
    "_count_words",
    "summarize_document",
]
