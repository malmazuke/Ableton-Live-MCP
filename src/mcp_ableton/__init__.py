"""Ableton Live MCP server package."""

from mcp_ableton.connection import AbletonConnection
from mcp_ableton.protocol import CommandRequest, CommandResponse, ErrorDetail
from mcp_ableton.server import main

__all__ = [
    "AbletonConnection",
    "CommandRequest",
    "CommandResponse",
    "ErrorDetail",
    "main",
]
