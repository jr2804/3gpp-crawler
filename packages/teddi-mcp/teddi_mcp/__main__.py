"""Entry point for running teddi_mcp as a module (python -m teddi_mcp)."""

import asyncio

from teddi_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
