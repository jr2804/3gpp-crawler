"""HTML parser for TEDDI search results."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from teddi_mcp.models import DocumentRef, TermResult

logger = logging.getLogger(__name__)

TEDDI_BASE_URL = "https://webapp.etsi.org"


def parse_teddi_response(html_content: str) -> list[TermResult]:
    """Parse TEDDI HTML response to extract search results.

    Extracts term, definition, and document references with TB grouping logic.

    Args:
        html_content: Raw HTML response from TEDDI search endpoint.

    Returns:
        List of TermResult objects parsed from HTML.

    Raises:
        ValueError: If HTML structure cannot be parsed.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    results = []

    # Find main results table: typically has columns: Term | Description | Declared in document(s)
    tables = soup.find_all("table")
    if not tables:
        logger.warning("No tables found in TEDDI response HTML")
        return []

    results_table = None
    header_row_idx = None

    # Search all tables for one with a header row containing "Term"
    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        # Look for header row in all rows (not just first, due to form navigation)
        for row_idx, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            if len(cells) < 3:
                continue

            cell_texts_lower = [c.get_text(strip=True).lower() for c in cells[:3]]

            # Check if this row is the header (contains "term")
            if "term" in cell_texts_lower[0]:
                results_table = table
                header_row_idx = row_idx
                break

        if results_table:
            break

    # Fall back to first table with multiple rows if not found
    if not results_table and len(tables) > 0:
        # Use first table with more than just layout rows
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) > 5:  # Likely has content
                results_table = table
                header_row_idx = None
                break

    if not results_table:
        return []

    # Extract results starting after header row
    rows = results_table.find_all("tr")
    if header_row_idx is not None:
        header_row_idx + 1
    else:
        # Try to find first data row by skipping form/navigation rows
        max(1, len(rows) // 6)  # Skip likely navigation rows

    i = 0
    while i < len(rows):
        row = rows[i]
        cells = row.find_all(["td", "th"])

        if len(cells) < 3:
            i += 1
            continue

        term_cell = cells[0].get_text(strip=True)
        description_cell = cells[1].get_text(strip=True)

        # Skip the header row if it was included
        if term_cell.lower() == "term" and description_cell.lower() == "description":
            i += 1
            continue

        documents_cell = cells[2]  # May contain nested table

        if not term_cell or not description_cell:
            i += 1
            continue

        # Parse nested table in "Declared in document(s)" column
        documents = _parse_document_table(documents_cell)

        result = TermResult(
            term=term_cell,
            description=description_cell,
            documents=documents,
        )
        results.append(result)
        i += 1

    return results


def _parse_document_table(cell_content: Tag) -> list[DocumentRef]:
    """Parse nested table in 'Declared in document(s)' cell with TB grouping.

    Handles TB grouping: if TB column is empty, inherit from previous row.
    Each row of the nested table has 2 columns: [TB] [Document link]

    Args:
        cell_content: BeautifulSoup cell element containing nested table.

    Returns:
        List of DocumentRef objects with TB grouping applied.
    """
    documents = []
    nested_table = cell_content.find("table")

    if not nested_table:
        # No nested table, return empty
        return documents

    rows = nested_table.find_all("tr")
    last_tb = ""  # Track last seen technical body for grouping

    for row in rows:
        cells = row.find_all(["td", "th"])

        if len(cells) < 2:
            # Skip rows with less than 2 cells
            continue

        # First cell may contain TB name or be empty
        tb_cell = cells[0].get_text(strip=True)
        if tb_cell:
            last_tb = tb_cell

        # Second cell contains link or is empty
        doc_cell = cells[1]
        link = doc_cell.find("a")

        if not link:
            # No link in this row, skip
            continue

        spec_text = link.get_text(strip=True)
        if not spec_text:
            continue

        url = link.get("href", "")
        # Resolve relative URLs
        if url and not url.startswith(("http://", "https://", "//")):
            url = urljoin(TEDDI_BASE_URL, url)

        doc_ref = DocumentRef(
            technical_body=last_tb,
            specification=spec_text,
            url=url,
        )
        documents.append(doc_ref)

    return documents
