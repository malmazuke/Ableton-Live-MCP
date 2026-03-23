"""MCP server entry point."""

from mcp.server.fastmcp import FastMCP


def main() -> None:
    """Run the Ableton MCP server over stdio transport."""
    mcp = FastMCP("AbletonLiveMCP")
    mcp.run()
