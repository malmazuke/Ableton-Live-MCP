"""MCP server entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from mcp_ableton.connection import AbletonConnection

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Lifespan state shared with every MCP tool via ``ctx.request_context``."""

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

import mcp_ableton.tools  # noqa: E402, F401


def main() -> None:
    """Run the Ableton MCP server over stdio transport."""
    mcp.run()
