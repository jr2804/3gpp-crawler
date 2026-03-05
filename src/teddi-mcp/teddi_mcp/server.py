"""FastMCP 3.0 server for TEDDI search."""

import logging

from fastmcp import FastMCP

from teddi_mcp.client import TeddiClient
from teddi_mcp.models import (
    SearchIn,
    SearchPattern,
    SearchRequest,
    TechnicalBody,
)

logger = logging.getLogger(__name__)

# Create FastMCP server
server = FastMCP("teddi-mcp")


@server.tool()
async def search_teddi(
    term: str,
    search_in: str = "both",
    search_pattern: str = "exactmatch",
    technical_bodies: str | None = None,
) -> dict:
    """Search TEDDI for terms and definitions.

    Args:
        term: Term or abbreviation to search for.
        search_in: Search scope - 'abbreviations', 'definitions', or 'both' (default: both).
        search_pattern: Pattern matching - 'exactmatch', 'startingwith', 'endingwith', or 'alloccurrences' (default: exactmatch).
        technical_bodies: Comma-separated list of technical bodies to filter by (default: all).

    Returns:
        JSON dict with search results including term, description, and document references.
    """
    try:
        # Parse enum values
        search_in_enum = SearchIn(search_in.lower())
        search_pattern_enum = SearchPattern(search_pattern.lower())

        # Parse technical bodies
        tbs = None
        if technical_bodies:
            tb_list = [tb.strip() for tb in technical_bodies.split(",")]
            tbs = []
            for tb_name in tb_list:
                try:
                    tb = TechnicalBody(tb_name.lower())
                    tbs.append(tb)
                except ValueError:
                    return {
                        "error": f"Unknown technical body: {tb_name}",
                        "available_tbs": [
                            tb.value for tb in TechnicalBody if tb != TechnicalBody.ALL
                        ],
                    }

        # Create search request
        request = SearchRequest(
            term=term,
            search_in=search_in_enum,
            search_pattern=search_pattern_enum,
            technical_bodies=tbs,
        )

        # Execute search
        async with TeddiClient() as client:
            response = await client.search_terms(request)

        # Convert response to JSON-serializable format
        return {
            "query": {
                "term": request.term,
                "search_in": request.search_in.value,
                "search_pattern": request.search_pattern.value,
                "technical_bodies": (
                    [tb.value for tb in request.technical_bodies]
                    if request.technical_bodies
                    else None
                ),
            },
            "total_count": response.total_count,
            "results": [
                {
                    "term": result.term,
                    "description": result.description,
                    "documents": [
                        {
                            "technical_body": doc.technical_body,
                            "specification": doc.specification,
                            "url": doc.url,
                        }
                        for doc in result.documents
                    ],
                }
                for result in response.results
            ],
        }

    except ValueError as e:
        return {"error": f"Invalid parameter: {e}"}
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return {"error": f"Search failed: {e}"}


@server.tool()
async def list_technical_bodies() -> dict:
    """List all available technical bodies in TEDDI.

    Returns:
        JSON dict with list of technical body codes and names.
    """
    try:
        async with TeddiClient() as client:
            tbs = await client.get_available_technical_bodies()

        display_names = {
            "3gpp": "3GPP",
            "3gpp2": "3GPP2",
            "bbcc": "BBCC",
            "ecma": "ECMA",
            "etsi": "ETSI",
            "ietf": "IETF",
            "ieee": "IEEE",
            "iso": "ISO",
            "itu": "ITU",
            "oma": "OMA",
            "zsm": "ZSM",
        }

        return {
            "technical_bodies": [
                {
                    "code": tb.value,
                    "name": display_names.get(tb.value, tb.value.upper()),
                }
                for tb in sorted(tbs, key=lambda x: x.value)
            ]
        }

    except Exception as e:
        logger.error(f"Error listing TBs: {e}", exc_info=True)
        return {"error": f"Failed to list technical bodies: {e}"}


@server.tool()
async def get_term_info(term: str) -> dict:
    """Get detailed information about a specific term.

    This is a convenience wrapper for exact match search.

    Args:
        term: Specific term to look up.

    Returns:
        JSON dict with term details (first exact match).
    """
    try:
        request = SearchRequest(
            term=term,
            search_in=SearchIn.BOTH,
            search_pattern=SearchPattern.EXACT_MATCH,
        )

        async with TeddiClient() as client:
            response = await client.search_terms(request)

        if not response.results:
            return {"term": term, "found": False}

        # Return first result
        result = response.results[0]
        return {
            "term": result.term,
            "found": True,
            "description": result.description,
            "documents": [
                {
                    "technical_body": doc.technical_body,
                    "specification": doc.specification,
                    "url": doc.url,
                }
                for doc in result.documents
            ],
        }

    except Exception as e:
        logger.error(f"Error getting term info: {e}", exc_info=True)
        return {"error": f"Failed to get term info: {e}"}


def main() -> None:
    """Main entry point for the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting TEDDI-MCP server")

    # Run the server on stdio
    server.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
