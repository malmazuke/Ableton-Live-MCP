"""Shared FastMCP application instance.

Separated from server.py so that ``mcp dev`` (which loads server.py via
importlib) and the normal import path both resolve to the *same* FastMCP
instance.  Without this, tools registered by ``mcp_ableton.tools`` would
end up on a different instance than the one ``mcp dev`` inspects.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from mcp_ableton.connection import AbletonConnection

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Lifespan state shared with every MCP tool.

    Access via ``ctx.request_context.lifespan_context``.
    """

    connection: AbletonConnection


@asynccontextmanager
async def app_lifespan(app: FastMCP) -> AsyncIterator[AppContext]:
    """Manage the Ableton TCP connection across the server lifecycle."""
    connection = AbletonConnection()
    try:
        await connection.connect()
    except OSError:
        logger.warning(
            "Could not connect to Ableton on startup — "
            "is Ableton Live running with the Remote Script installed?"
        )
    try:
        yield AppContext(connection=connection)
    finally:
        await connection.disconnect()


mcp = FastMCP("AbletonLiveMCP", lifespan=app_lifespan)

__all__ = ["AppContext", "app_lifespan", "mcp"]
