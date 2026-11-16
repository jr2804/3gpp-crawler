"""Main-file selection for extracted TDoc archives.

One TDoc zip usually holds a single "main" document plus attachments.
Selection has a fixed precedence:

1. A stored manual override for the TDoc (see
   :mod:`tdoc_crawler.database.main_files`) — always wins.
2. The external System One decision model (TypeSafe) — only when the
   configured :class:`~tdoc_crawler.models.main_files.MainFileSelector`
   is ``decision_model``, the API key is set, and the answer reaches the
   confidence threshold.
3. Heuristic ranking (offline, deterministic) — the default fallback.

The heuristic is the default and never requires network access. Selecting
``manual`` turns the automatic chain off: without a stored override the
archive cannot be opened.
"""

from __future__ import annotations

import difflib
import re
import zipfile
from pathlib import Path

import niquests as requests

from tdoc_crawler.config.settings import CheckoutConfig
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import DocumentType
from tdoc_crawler.models.main_files import MainFileSelection, MainFileSelector, MainFileSource
from tdoc_crawler.utils.clutter import is_clutter
from tdoc_crawler.utils.json_types import JSONObject, coerce_json_value

# Main-file type preference, best first. Declaration order of the
# ``DocumentType`` StrEnum (see ``models/base.py``) IS the preference
# order — keep the enum sorted accordingly.
_TDOC_DOCUMENT_TYPE_ORDER: tuple[str, ...] = tuple(t.value for t in DocumentType)
_TDOC_DOCUMENT_SUFFIXES: frozenset[str] = frozenset(_TDOC_DOCUMENT_TYPE_ORDER)

# Tracked-change (revision marks) elements in OOXML word-processing parts.
_REVISION_MARK_ELEMENTS = re.compile(rb"<w:(?:ins|del|moveFrom|moveTo)[ />]")

# Minimum difflib similarity for the optional title match to count.
_TITLE_MATCH_THRESHOLD = 0.6

# Noul threshold below which "this archive has a main document" counts as
# false (TypeSafe guidance: < 0.3 reads as no, > 0.7 as yes).
_NO_MAIN_DOCUMENT_THRESHOLD = 0.3

_SYSTEMONE_PATH = "/v1/systemone"
_SYSTEMONE_CHOICE_QUESTION = "main_file"
_SYSTEMONE_HAS_MAIN_QUESTION = "has_main_document"

logger = get_logger(__name__)


def resolve_main_file(
    extract_dir: Path,
    tdoc_id: str,
    *,
    title: str | None = None,
    override_member: str | None = None,
    config: CheckoutConfig | None = None,
    session: requests.Session | None = None,
) -> MainFileSelection:
    """Resolve the main file of an extracted TDoc archive.

    Precedence: manual override > decision model (when configured and
    confident) > heuristic.

    Args:
        extract_dir: Directory holding the extracted TDoc contents.
        tdoc_id: TDoc identifier, used by the heuristic and the model.
        title: Optional portal title, used by the heuristic and the model.
        override_member: Stored manual override (archive-relative path).
        config: Checkout settings; defaults to ``CheckoutConfig()``.
        session: Optional HTTP session reused for the decision-model call.

    Returns:
        The resolved main file together with its source.

    Raises:
        FileNotFoundError: If no usable file is present, or the override
            no longer exists in the archive.
    """
    settings = config or CheckoutConfig()

    if override_member is not None:
        overridden = _resolve_override(extract_dir, override_member)
        return MainFileSelection(
            path=overridden,
            relative_path=overridden.relative_to(extract_dir).as_posix(),
            source=MainFileSource.MANUAL_OVERRIDE,
        )

    if settings.selector is MainFileSelector.MANUAL:
        raise FileNotFoundError(f"no main file override stored for {tdoc_id}; selector 'manual' disables heuristic and decision-model selection")

    if settings.selector is MainFileSelector.DECISION_MODEL and settings.systemone_api_key:
        decision = _decide_with_model(extract_dir, tdoc_id, title, settings, session)
        if decision is not None:
            relative, confidence = decision
            return MainFileSelection(
                path=extract_dir / relative,
                relative_path=relative,
                source=MainFileSource.DECISION_MODEL,
                confidence=confidence,
            )

    picked = select_heuristic_main_file(extract_dir, tdoc_id, title=title)
    return MainFileSelection(
        path=picked,
        relative_path=picked.relative_to(extract_dir).as_posix(),
        source=MainFileSource.HEURISTIC,
    )


def select_heuristic_main_file(extract_dir: Path, tdoc_id: str, *, title: str | None = None) -> Path:
    """Pick the most likely "main" file inside an extracted TDoc directory.

    Candidates are filtered by the gitignore-style clutter patterns
    (``<cache-dir>/clutter-ignore``, see :mod:`tdoc_crawler.utils.clutter`)
    so that OS metadata (``__MACOSX/``, ``._*``, ``~$*`` ...) is never
    picked — even from checkout directories created before extraction
    filtering existed.

    When an archive holds two versions of the same document (one with,
    one without revision marks), the tracked-changes version wins —
    decided by inspecting the document *content* via
    :func:`has_revision_marks`, never by filename conventions.

    Among the remaining document-suffix files the best-ranked candidate
    wins, by these criteria in order:

        1. Name is exactly the TDoc ID (e.g. ``S4-261599.docx``).
        2. Highest similarity to ``<tdoc_id> <title>`` (only when *title*
           is given; scores below the threshold count as zero).
        3. Name starts with the TDoc ID (case-insensitive).
        4. Document carries revision marks (content probe, ``.docx`` only).
        5. Document type, in ``DocumentType`` declaration order.
        6. Most recent file timestamp, then name (deterministic tie-break).

    Fallbacks: largest remaining document-suffix file, then largest
    non-clutter file of any type.

    Args:
        extract_dir: Directory holding the extracted TDoc contents.
        tdoc_id: TDoc identifier (e.g. ``S4-261599``).
        title: Optional portal title of the TDoc, used for fuzzy matching.

    Returns:
        Path to the selected main file.

    Raises:
        FileNotFoundError: If no usable file is present.
    """
    documents = [
        p
        for p in extract_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _TDOC_DOCUMENT_SUFFIXES and not is_clutter(p.relative_to(extract_dir).as_posix())
    ]
    if documents:
        if len(documents) == 1:
            return documents[0]
        id_folded = tdoc_id.casefold()
        title_folded = re.sub(r"\W+", " ", f"{tdoc_id} {title or ''}".casefold()).strip()

        def rank(path: Path) -> tuple[bool, float, bool, bool, int, float, str]:
            stem_folded = path.stem.casefold()
            exact = stem_folded == id_folded
            title_score = 0.0
            if title:
                ratio = difflib.SequenceMatcher(None, stem_folded, title_folded).ratio()
                if ratio >= _TITLE_MATCH_THRESHOLD:
                    title_score = round(ratio, 3)
            prefixed = stem_folded.startswith(id_folded)
            marked = has_revision_marks(path)
            type_rank = -_TDOC_DOCUMENT_TYPE_ORDER.index(path.suffix.lower())
            return (exact, title_score, prefixed, marked, type_rank, path.stat().st_mtime, path.name)

        return max(documents, key=rank)

    all_files = [p for p in extract_dir.rglob("*") if p.is_file() and not is_clutter(p.relative_to(extract_dir).as_posix())]
    if not all_files:
        msg = "no-files-in-archive"
        raise FileNotFoundError(msg)
    return max(all_files, key=lambda p: p.stat().st_size)


def has_revision_marks(path: Path) -> bool:
    """True when an OOXML document carries tracked changes (revision marks).

    Scans the ``word/`` XML parts for insert/delete/move revision elements.
    Non-OOXML files (PDF, legacy ``.doc``/``.xls``) cannot be checked
    cheaply and count as unmarked; unreadable files likewise.

    This is the *only* signal used to prefer a tracked-changes version
    over a clean one — filename markers (``_clean``, ``_rm``, ...) are
    inconsistent across authors and are never consulted.
    """
    if path.suffix.lower() != ".docx":
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return any(_REVISION_MARK_ELEMENTS.search(archive.read(name)) for name in archive.namelist() if name.startswith("word/") and name.endswith(".xml"))
    except (zipfile.BadZipFile, OSError):
        return False


def _resolve_override(extract_dir: Path, member_path: str) -> Path:
    """Map a stored override to an existing file inside *extract_dir*.

    Raises:
        FileNotFoundError: If the path escapes the directory or no longer
            exists (for example after an archive was replaced upstream).
    """
    root = extract_dir.resolve()
    candidate = (root / member_path).resolve()
    if not candidate.is_relative_to(root):
        msg = f"override-escapes-archive: {member_path}"
        raise FileNotFoundError(msg)
    if not candidate.is_file():
        msg = f"override-missing-from-archive: {member_path}"
        raise FileNotFoundError(msg)
    return candidate


def _decide_with_model(
    extract_dir: Path,
    tdoc_id: str,
    title: str | None,
    settings: CheckoutConfig,
    session: requests.Session | None,
) -> tuple[str, float] | None:
    """Ask the System One model which member is the main file.

    Returns ``(relative_path, confidence)`` when the model answers above
    the confidence threshold with a candidate that exists, else None so
    the caller falls back to the heuristic.
    """
    candidates = member_candidates(extract_dir)[: settings.max_model_candidates]
    if len(candidates) < 2:
        return None

    payload = _build_systemone_payload(extract_dir, candidates, tdoc_id, title, settings.systemone_model)
    try:
        response = _post_systemone(payload, settings, session)
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"System One main-file decision failed for {tdoc_id}: {exc}")
        return None

    answers = response.get("answers")
    if not isinstance(answers, dict):
        return None
    has_main = answers.get(_SYSTEMONE_HAS_MAIN_QUESTION, {})
    if isinstance(has_main, dict) and isinstance(has_main.get("noul"), int | float) and has_main["noul"] < _NO_MAIN_DOCUMENT_THRESHOLD:
        return None

    choice = answers.get(_SYSTEMONE_CHOICE_QUESTION, {})
    if not isinstance(choice, dict):
        return None
    selected = choice.get("choice")
    confidence = choice.get("confidence")
    if not isinstance(selected, str) or not isinstance(confidence, int | float):
        return None
    if confidence < settings.systemone_min_confidence:
        logger.debug(f"System One main-file choice for {tdoc_id} below threshold ({confidence}): keeping heuristic")
        return None
    relative = selected
    if not (extract_dir / relative).is_file():
        logger.warning(f"System One picked a member that is not on disk for {tdoc_id}: {relative}")
        return None
    return relative, float(confidence)


def member_candidates(extract_dir: Path) -> list[Path]:
    """Non-clutter files of an extracted TDoc directory, sorted by path."""
    return sorted(
        (p for p in extract_dir.rglob("*") if p.is_file() and not is_clutter(p.relative_to(extract_dir).as_posix())),
        key=lambda p: p.relative_to(extract_dir).as_posix(),
    )


def _build_systemone_payload(
    extract_dir: Path,
    candidates: list[Path],
    tdoc_id: str,
    title: str | None,
    model: str,
) -> JSONObject:
    """System One request: state is the TDoc plus its candidate files."""
    relative_paths = [p.relative_to(extract_dir).as_posix() for p in candidates]
    criteria = {
        relative: f"File named {relative.rsplit('/', 1)[-1]} ({p.suffix or 'no extension'}, {p.stat().st_size} bytes)"
        for relative, p in zip(relative_paths, candidates, strict=True)
    }
    state = {
        "tdoc_id": tdoc_id,
        "title": title or "",
        "candidates": [{"path": relative, "size": p.stat().st_size} for relative, p in zip(relative_paths, candidates, strict=True)],
    }
    return {
        "model": model,
        "state": state,
        "questions": {
            _SYSTEMONE_HAS_MAIN_QUESTION: {
                "type": "noul",
                "instructions": "Does the state list a main document for this TDoc, meaning the contribution itself rather than only attachments?",
            },
            _SYSTEMONE_CHOICE_QUESTION: {
                "type": "choice",
                "instructions": (
                    "Which candidate is the main document of this TDoc, as opposed to an attachment, cover sheet, meeting notice, or background document?"
                ),
                "criteria": criteria,
            },
        },
    }


def _post_systemone(payload: JSONObject, settings: CheckoutConfig, session: requests.Session | None) -> JSONObject:
    """POST one System One request and return the parsed JSON body."""
    url = settings.systemone_base_url.rstrip("/") + _SYSTEMONE_PATH
    headers = {"Authorization": f"Bearer {settings.systemone_api_key}"}
    owns_session = session is None
    http = session or create_cached_session()
    try:
        response = http.post(url, json=payload, headers=headers, timeout=settings.systemone_timeout)
        response.raise_for_status()
        body = response.json()
    finally:
        if owns_session:
            http.close()
    if not isinstance(body, dict):
        msg = "unexpected System One response body"
        raise ValueError(msg)
    try:
        return {str(key): coerce_json_value(value) for key, value in body.items()}
    except TypeError as exc:
        msg = "unexpected System One response body"
        raise ValueError(msg) from exc


__all__ = [
    "has_revision_marks",
    "member_candidates",
    "resolve_main_file",
    "select_heuristic_main_file",
]
