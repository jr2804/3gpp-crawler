"""Core TEDDI client with protocol-based abstraction."""

import logging
from pathlib import Path
from typing import Protocol

import httpx

from teddi_mcp.http_client import create_cached_teddi_async_client
from teddi_mcp.models import (
    SearchIn,
    SearchPattern,
    SearchRequest,
    SearchResponse,
    TechnicalBody,
)
from teddi_mcp.parser import parse_teddi_response

logger = logging.getLogger(__name__)

TEDDI_SEARCH_URL = "https://webapp.etsi.org/Teddi/Main.asp"

# Map enums to TEDDI form parameter values
SEARCH_IN_TO_PARAM = {
    SearchIn.ABBREVIATIONS: 1,
    SearchIn.BOTH: 2,
    SearchIn.DEFINITIONS: 3,
}

SEARCH_PATTERN_TO_PARAM = {
    SearchPattern.EXACT_MATCH: 1,
    SearchPattern.STARTING_WITH: 2,
    SearchPattern.ALL_OCCURRENCES: 3,
    SearchPattern.ENDING_WITH: 4,
}


class TeddiSource(Protocol):
    """Protocol for TEDDI search sources (enables mocking/substitution)."""

    async def search_terms(self, request: SearchRequest) -> SearchResponse:
        """Search for terms in TEDDI.

        Args:
            request: Search request parameters.

        Returns:
            SearchResponse with matching terms and documents.
        """
        ...

    async def get_available_technical_bodies(self) -> list[TechnicalBody]:
        """Get list of available technical bodies in TEDDI.

        Returns:
            List of TechnicalBody enum values supported by TEDDI.
        """
        ...

    async def fetch_document(self, url: str) -> bytes:
        """Fetch document content from URL.

        Args:
            url: Full HTTP URL to document.

        Returns:
            Document content as bytes.

        Raises:
            httpx.HTTPError: If fetch fails.
        """
        ...


class TeddiClient:
    """Client for querying ETSI TEDDI search engine."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize TeddiClient.

        Args:
            client: Optional pre-configured httpx.AsyncClient.
            cache_dir: Optional cache directory for HTTP caching.
        """
        self._client = client
        self._cache_dir = cache_dir
        self._owned_client = False

    async def __aenter__(self) -> "TeddiClient":
        """Context manager entry."""
        if self._client is None:
            self._client = await create_cached_teddi_async_client(cache_dir=self._cache_dir)
            self._owned_client = True
        return self

    async def __aexit__(self, *args) -> None:
        """Context manager exit."""
        if self._owned_client and self._client:
            await self._client.aclose()
            self._client = None

    async def search_terms(self, request: SearchRequest) -> SearchResponse:
        """Search for terms in TEDDI.

        Args:
            request: Search request with term and filters.

        Returns:
            SearchResponse with matching terms and documents.

        Raises:
            httpx.HTTPError: If HTTP request fails.
            ValueError: If response cannot be parsed.
        """
        client = self._get_client()

        # Build form data with TEDDI parameter names
        form_data = {
            "qWhatToSearch": request.term,
            "qWhereOption": SEARCH_IN_TO_PARAM[request.search_in],
            "qWhatOption": SEARCH_PATTERN_TO_PARAM[request.search_pattern],
            "btnSearch.x": 0,
            "btnSearch.y": 0,
        }

        # Add technical bodies filter if specified
        if request.technical_bodies and len(request.technical_bodies) > 0:
            # Handle special case of "all"
            if request.technical_bodies == [TechnicalBody.ALL]:
                form_data["qShowTBs"] = "ALL"
            else:
                # Join TB values with comma (capitalized)
                tb_values = [tb.value.upper() for tb in request.technical_bodies]
                form_data["qShowTBs"] = ",".join(tb_values)
        else:
            form_data["qShowTBs"] = "ALL"

        logger.debug(f"Searching TEDDI: {request.term} with form data: {form_data}")

        # Make request to TEDDI
        response = await client.post(TEDDI_SEARCH_URL, data=form_data)
        response.raise_for_status()

        # Parse HTML response
        results = parse_teddi_response(response.text)

        return SearchResponse(
            query=request,
            results=results,
            total_count=len(results),
        )

    async def get_available_technical_bodies(self) -> list[TechnicalBody]:
        """Get list of available technical bodies.

        Currently returns static list of supported TBs.

        Returns:
            List of TechnicalBody enum values.
        """
        # Return all TB values except "all"
        return [tb for tb in TechnicalBody if tb != TechnicalBody.ALL]

    async def fetch_document(self, url: str) -> bytes:
        """Fetch document content from URL.

        Args:
            url: Full HTTP URL to document.

        Returns:
            Document content as bytes.

        Raises:
            httpx.HTTPError: If fetch fails.
        """
        client = self._get_client()
        logger.debug(f"Fetching document: {url}")
        response = await client.get(url)
        response.raise_for_status()
        return response.content

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create client."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async with statement.")
        return self._client
