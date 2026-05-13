"""Markitdown converter — fast, no-ML Markdown extraction (no JSON, no models)."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from markitdown import MarkItDown

# Content type → file extension mapping for common image formats.
# EMF/WMF are vector formats — kept as-is since they're what's actually stored.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/x-emf": ".emf",
    "image/x-wmf": ".wmf",
    "image/svg+xml": ".svg",
}

# Matches `![alt](data:image/...;base64,...)` — mammoth embeds images as data URIs.
_DATA_URI_PATTERN = re.compile(r"!\[([^\]]*)\]\(data:image/[^;]+;base64,[^)]*\)")


def _extract_docx_images(docx_path: Path, output_dir: Path) -> list[Path]:
    """Extract all embedded images from a .docx file.

    Images are saved to ``output_dir / "media" /`` with sequential naming
    (``image_001.png``, ``image_002.emf``, …).  Returns the list of saved
    paths in extraction order (relationship order, which matches document
    order for practically all 3GPP documents).
    """
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    doc = Document(str(docx_path))
    extracted: list[Path] = []

    for rel in doc.part.rels.values():
        if rel.reltype == RT.IMAGE:
            image_part = rel.target_part
            ext = _CONTENT_TYPE_TO_EXT.get(image_part.content_type, ".bin")
            image_path = media_dir / f"image_{len(extracted) + 1:03d}{ext}"
            image_path.write_bytes(image_part.blob)
            extracted.append(image_path)

    return extracted


def _replace_data_uris(text: str, image_paths: list[Path]) -> str:
    """Replace data-URI image references with relative file references.

    Each ``![alt](data:image/…)`` occurrence is replaced in order by
    ``![alt](./media/image_NNN.ext)``.  If there are more data URIs than
    extracted images, the excess references are left untouched.
    """
    remaining = list(image_paths)  # shallow copy for pop(0)

    def _replacement(match: re.Match) -> str:
        if not remaining:
            return match.group(0)  # no more extracted images — leave as-is
        img_path = remaining.pop(0)
        alt_text = match.group(1)
        return f"![{alt_text}](./media/{img_path.name})"

    return _DATA_URI_PATTERN.sub(_replacement, text)


def _run_markitdown(
    primary: Path,
    output_dir: Path,
    *,
    extract_media: bool = False,
) -> Path:
    """Convert document to Markdown using markitdown (fast, no ML models).

    Handles .docx, .pdf, .pptx, .xlsx directly — no LibreOffice step needed.

    When *extract_media* is ``True`` and *primary* is a .docx file, embedded
    images are extracted to ``output_dir/media/`` and data-URI references in
    the markdown are rewritten to relative ``./media/…`` paths.
    """
    md = MarkItDown()
    result = md.convert(str(primary))
    text = result.text_content

    if extract_media and primary.suffix.lower() == ".docx":
        image_paths = _extract_docx_images(primary, output_dir)
        if image_paths:
            text = _replace_data_uris(text, image_paths)

    md_path = output_dir / f"{primary.stem}.md"
    md_path.write_text(text, encoding="utf-8")
    return md_path
