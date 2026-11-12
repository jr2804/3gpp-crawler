"""Tests for the DOCX text extraction helper."""

from __future__ import annotations

import io
import zipfile

from tdoc_crawler.utils.office import extract_docx_blocks


def test_extract_docx_blocks_reads_paragraphs_and_rows() -> None:
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        "<w:p><w:r><w:t>Meeting agenda</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>4</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>ULBC-MED</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    )

    blocks = extract_docx_blocks(_make_docx(document))

    assert blocks == [["Meeting agenda"], ["4", "ULBC-MED"]]


def test_extract_docx_blocks_ignores_broken_archive() -> None:
    assert extract_docx_blocks(b"not a zip file") == []


def test_extract_docx_blocks_ignores_missing_document_part() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/styles.xml", "<styles/>")

    assert extract_docx_blocks(buffer.getvalue()) == []


def test_extract_docx_blocks_rejects_doctype() -> None:
    document = (
        '<!DOCTYPE document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        "<w:p><w:r><w:t>&xxe;</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )

    assert extract_docx_blocks(_make_docx(document)) == []


def _make_docx(document_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()
