"""Pydantic data models and enums for TEDDI search integration."""

from dataclasses import dataclass
from enum import StrEnum


class OutputFormat(StrEnum):
    """Output format for CLI results."""

    JSON = "json"
    ISON = "ison"
    TOON = "toon"
    TABLE = "table"


class SearchIn(StrEnum):
    """Search scope: where to search for the term."""

    ABBREVIATIONS = "abbreviations"
    DEFINITIONS = "definitions"
    BOTH = "both"


class SearchPattern(StrEnum):
    """Search pattern: how to match the term."""

    ALL_OCCURRENCES = "alloccurrences"
    EXACT_MATCH = "exactmatch"
    STARTING_WITH = "startingwith"
    ENDING_WITH = "endingwith"


class TechnicalBody(StrEnum):
    """ETSI and standardization body identifiers."""

    ALL = "all"


@dataclass
class DocumentRef:
    """Reference to a specification document from TEDDI results."""

    technical_body: str
    """Technical body that published this specification (e.g., '3GPP')."""

    specification: str
    """Specification identifier (e.g., 'TS 24.008')."""

    url: str
    """Full HTTP URL to the specification."""


@dataclass
class TermResult:
    """A single term found in TEDDI with its definition and document references."""

    term: str
    """The term/abbreviation found."""

    description: str
    """Definition or description of the term."""

    documents: list[DocumentRef]
    """List of documents where this term is declared, grouped by technical body."""


@dataclass
class SearchRequest:
    """Request parameters for TEDDI search."""

    term: str
    """Term to search for."""

    search_in: SearchIn = SearchIn.BOTH
    """Scope: search in abbreviations, definitions, or both."""

    search_pattern: SearchPattern = SearchPattern.ALL_OCCURRENCES
    """Pattern: exact match, starts with, etc."""

    technical_bodies: list[TechnicalBody] | None = None
    """Filter by technical bodies. None or empty = all TBs."""


@dataclass
class SearchResponse:
    """Response from TEDDI search containing all matching terms."""

    query: SearchRequest
    """Original search request."""

    results: list[TermResult]
    """List of terms found matching the search criteria."""

    total_count: int
    """Total number of matching results."""
