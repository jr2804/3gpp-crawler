"""FastMCP 3.0 server for TEDDI search."""

import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create FastMCP server
server = FastMCP("teddi-mcp")


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
