"""MCP server entry point."""

import mcp_ableton.tools  # noqa: F401
from mcp_ableton._app import AppContext, mcp  # noqa: F401


def main() -> None:
    """Run the Ableton MCP server over stdio transport."""
    mcp.run()
