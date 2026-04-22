"""Document summarization using LLMs."""

from __future__ import annotations

import json
import re

from litellm import exceptions as litellm_exceptions
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.normalization import normalize_tdoc_id

from threegpp_ai.config import AiConfig, QualityPolicyMode
from threegpp_ai.models import LlmConfigError, SummarizeResult

from .convert import extract_document_structured_from_tdoc
from .llm_client import LiteLLMClient
from .metrics import MetricType, get_metrics_tracker, timed_operation

logger = get_logger(__name__)

# Input size limits for LLM prompts
ABSTRACT_INPUT_LIMIT = 5000
SUMMARY_INPUT_LIMIT = 8000
KEYWORDS_INPUT_LIMIT = 5000
STRUCTURED_CONTEXT_LIMIT = 2500


def _get_from_extraction(extraction: dict | object, key: str, default: object = None) -> object:
    """Get value from extraction dict or object flexibly."""
    if isinstance(extraction, dict):
        return extraction.get(key, default)
    return getattr(extraction, key, default)


def _resolve_extraction_status(extraction: dict | object) -> str:
    """Resolve extraction status from canonical metadata fields."""
    metadata = _get_from_extraction(extraction, "metadata", {}) or {}
    status = metadata.get("extraction_status")
    if isinstance(status, str) and status.strip():
        return status

    document_metadata = _get_from_extraction(extraction, "document_metadata", None)
    if document_metadata is not None:
        nested_status = getattr(document_metadata, "extraction_status", None)
        if isinstance(nested_status, str) and nested_status.strip():
            return nested_status

    return "ok"


def _enforce_quality_policy(
    extraction: dict | object,
    *,
    policy_mode: QualityPolicyMode,
    allow_failed_quality: bool,
) -> tuple[str, str | None]:
    """Enforce downstream summarize policy from extraction quality status."""
    status = _resolve_extraction_status(extraction)
    if status == "ok":
        return status, None

    if status == "partial":
        if policy_mode == "strict":
            raise ValueError("summarize blocked: extraction quality is partial under strict policy")
        return status, "summarize continuing with degraded extraction quality (partial status)"

    if status == "failed":
        if allow_failed_quality:
            return status, "summarize override enabled for failed extraction quality status"
        raise ValueError("summarize blocked: extraction quality is failed (use explicit override to proceed)")

    return status, f"summarize continuing with unrecognized extraction status '{status}'"


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to maximum character limit."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _get_llm_client() -> LiteLLMClient:
    """Get LLM client instance."""
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


def _clean_text(value: object) -> str:
    """Return safe single-line text for prompt serialization."""
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _safe_page(value: object) -> str:
    """Return a stable page label."""
    if isinstance(value, int) and value > 0:
        return str(value)
    return "unknown"


def _serialize_structured_context(extraction: dict | object, max_chars: int = STRUCTURED_CONTEXT_LIMIT) -> tuple[str, dict[str, int]]:
    """Serialize high-signal structured artifacts with deterministic ordering and budget."""
    equations = list(_get_from_extraction(extraction, "equations", []) or [])
    tables = list(_get_from_extraction(extraction, "tables", []) or [])
    figures = list(_get_from_extraction(extraction, "figures", []) or [])

    lines: list[str] = []
    selected = {"equations": 0, "tables": 0, "figures": 0}
    total = {
        "equations": len(equations),
        "tables": len(tables),
        "figures": len(figures),
    }

    sorted_equations = sorted(
        equations,
        key=lambda eq: (_safe_page(getattr(eq, "page_number", None)), _clean_text(getattr(eq, "element_id", ""))),
    )
    sorted_tables = sorted(
        tables,
        key=lambda tb: (_safe_page(getattr(tb, "page_number", None)), _clean_text(getattr(tb, "element_id", ""))),
    )
    sorted_figures = sorted(
        figures,
        key=lambda fg: (_safe_page(getattr(fg, "page_number", None)), _clean_text(getattr(fg, "element_id", ""))),
    )

    for eq in sorted_equations:
        eq_id = _clean_text(getattr(eq, "element_id", "equation"))
        page = _safe_page(getattr(eq, "page_number", None))
        norm = _clean_text(getattr(eq, "normalized_text", None) or getattr(eq, "raw_text", None) or getattr(eq, "latex", ""))
        if not norm:
            norm = "(no normalized equation text available)"
        lines.append(f"- Equation {eq_id} (p. {page}): {norm}")
        selected["equations"] += 1

    for table in sorted_tables:
        table_id = _clean_text(getattr(table, "element_id", "table"))
        page = _safe_page(getattr(table, "page_number", None))
        rows = getattr(table, "row_count", 0)
        cols = getattr(table, "column_count", 0)
        caption = _clean_text(getattr(table, "caption", None))
        caption_suffix = f"; caption: {caption}" if caption else ""
        lines.append(f"- Table {table_id} (p. {page}): {rows}x{cols}{caption_suffix}")
        selected["tables"] += 1

    for figure in sorted_figures:
        figure_id = _clean_text(getattr(figure, "element_id", "figure"))
        page = _safe_page(getattr(figure, "page_number", None))
        caption = _clean_text(getattr(figure, "caption", None))
        description = _clean_text(getattr(figure, "description", None))
        figure_text = caption or description or "(no figure description available)"
        lines.append(f"- Figure {figure_id} (p. {page}): {figure_text}")
        selected["figures"] += 1

    joined = "\n".join(lines)
    truncated = _truncate_text(joined, max_chars) if joined else ""

    return truncated, {
        "selected_equations": selected["equations"],
        "selected_tables": selected["tables"],
        "selected_figures": selected["figures"],
        "available_equations": total["equations"],
        "available_tables": total["tables"],
        "available_figures": total["figures"],
    }


def _build_prompt_source_content(extraction: dict | object) -> tuple[str, str, dict[str, int]]:
    """Build summarize source content with structured-first fallback behavior."""
    markdown_content = str(_get_from_extraction(extraction, "content", "") or "")

    try:
        structured_context, stats = _serialize_structured_context(extraction)
    except (KeyError, TypeError, ValueError) as e:
        # Log the specific error for debugging
        logger.debug("Structured context serialization failed: %s", e)
        return (
            markdown_content,
            "markdown_fallback",
            {
                "selected_equations": 0,
                "selected_tables": 0,
                "selected_figures": 0,
                "available_equations": 0,
                "available_tables": 0,
                "available_figures": 0,
            },
        )

    has_structured = any(stats[key] > 0 for key in ("selected_equations", "selected_tables", "selected_figures")) and bool(structured_context.strip())

    if not has_structured:
        return markdown_content, "markdown_fallback", stats

    prompt_source = (
        f"Primary extracted text:\n{markdown_content}\n\nStructured references (use inline citations with element ID and page):\n{structured_context}"
    )
    return prompt_source, "structured", stats


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


def _extract_key_points(abstract: str) -> list[str]:
    """Extract key points from text."""
    sentences = abstract.split(". ")
    return [s.strip() for s in sentences[:5] if len(s.strip()) > 20]


def _extract_action_items(markdown: str) -> list[str]:
    """Extract action items from markdown."""
    patterns = [
        r"action\s*(?:item)?:\s*(.+?)(?:\n|$)",
        r"todo:\s*(.+?)(?:\n|$)",
        r"to do:\s*(.+?)(?:\n|$)",
    ]

    action_items: list[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, markdown, re.IGNORECASE)
        action_items.extend(matches)

    return action_items[:10]


def _extract_decisions(markdown: str) -> list[str]:
    """Extract decisions from markdown."""
    pattern = r"decision:\s*(.+?)(?:\n|$)"
    matches = re.findall(pattern, markdown, re.IGNORECASE)
    return [m.strip() for m in matches[:10]]


def _extract_spec_references(markdown: str) -> list[str]:
    """Extract specification references from markdown."""
    pattern = r"(?:TS|TR|TS\s*:\s*)(\d{2}\.\d{3,4})"
    matches = re.findall(pattern, markdown)
    specs = list({f"TS {m}" for m in matches})
    return specs[:20]


CONCISE_SUMMARY_PROMPT = """Generate a summary of approximately {max_words} words or less for this document:

{content}

Provide a concise summary that captures the main purpose and key outcomes.
When using structured references, include inline citations with element IDs and page numbers.
Example: "[Equation equation_3, p. 14]" or "[Table table_7, p. 12]"."""

KEYWORDS_PROMPT = """Extract 5-10 relevant keywords from this document. Return ONLY a JSON array of strings, nothing else.

Document:
{content}

Example output format: ["keyword1", "keyword2", "keyword3"]"""


def summarize_tdoc(
    document_id: str,
    max_words: int = 200,
    force: bool = False,
    quality_policy_mode: QualityPolicyMode | None = None,
    allow_failed_quality: bool = False,
) -> SummarizeResult:
    """Summarize a TDoc by ID."""
    normalized_id = normalize_tdoc_id(document_id)

    with timed_operation(get_metrics_tracker(), normalized_id, MetricType.SUMMARIZATION):
        extraction = extract_document_structured_from_tdoc(normalized_id, force=force)
        source_content, context_mode, context_stats = _build_prompt_source_content(extraction)

        config = AiConfig()
        client = _get_llm_client()

        policy_mode = quality_policy_mode or getattr(config, "quality_policy_mode", "balanced")
        allow_failed = allow_failed_quality or bool(getattr(config, "allow_failed_quality", False))
        extraction_status, policy_message = _enforce_quality_policy(
            extraction,
            policy_mode=policy_mode,
            allow_failed_quality=allow_failed,
        )
        if policy_message:
            logger.warning(policy_message)

        truncated_for_summary = _truncate_text(source_content, SUMMARY_INPUT_LIMIT)
        summary_prompt = CONCISE_SUMMARY_PROMPT.format(
            max_words=max_words,
            content=truncated_for_summary,
        )
        try:
            summary = client.complete(summary_prompt, model=config.llm_model, max_tokens=max_words * 4)
        except (litellm_exceptions.OpenAIError, ValueError) as exc:
            msg = f"LLM endpoint is unreachable or misconfigured: {exc}"
            raise LlmConfigError(msg) from exc

        truncated_for_keywords = _truncate_text(source_content, KEYWORDS_INPUT_LIMIT)
        keywords_prompt = KEYWORDS_PROMPT.format(content=truncated_for_keywords)
        try:
            keywords_raw = client.complete(keywords_prompt, model=config.llm_model, max_tokens=200)
            keywords = _parse_keywords(keywords_raw)
        except (litellm_exceptions.OpenAIError, ValueError) as exc:
            logger.warning(f"Keyword extraction failed: {exc}")
            keywords = []

        word_count = _count_words(summary)

        result_metadata: dict = {
            "word_count": word_count,
            "extraction_status": extraction_status,
            "quality_policy_mode": policy_mode,
            "allow_failed_quality": allow_failed,
            "context_mode": context_mode,
            **context_stats,
        }

        result = SummarizeResult(
            summary=summary,
            keywords=keywords,
            metadata=result_metadata,
            word_count=word_count,
        )

        logger.info(f"Generated summary for {normalized_id}: {word_count} words, {len(keywords)} keywords")
        return result


def _parse_keywords(payload: str) -> list[str]:
    """Parse keywords from LLM JSON output."""
    try:
        cleaned = _strip_code_fences(payload)
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [str(kw).strip() for kw in data if str(kw).strip()]
    except json.JSONDecodeError, ValueError:
        pass

    cleaned = _strip_code_fences(payload)
    if "[" in cleaned:
        match = re.search(r"\[(.*?)\]", cleaned)
        if match:
            items = match.group(1).split(",")
            return [item.strip().strip("\"'").strip() for item in items if item.strip()]

    items = cleaned.replace(",", "\n").split("\n")
    return [item.strip().strip("\"'").strip() for item in items if item.strip()][:10]


__all__ = [
    "SummarizeResult",
    "_count_words",
    "summarize_tdoc",
]
