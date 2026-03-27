"""MCP tools for browsing Ableton Live's Browser."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


BrowserCategory = Literal[
    "all",
    "instruments",
    "sounds",
    "drums",
    "audio_effects",
    "midi_effects",
]


class BrowserTreeNode(BaseModel):
    """Hierarchical Browser node returned by ``get_browser_tree``."""

    name: str
    uri: str | None = None
    is_folder: bool
    is_loadable: bool
    children: list[BrowserTreeNode] = Field(default_factory=list)


BrowserTreeNode.model_rebuild()


class BrowserTree(BaseModel):
    """Fixed-depth Browser tree rooted at one or more top-level categories."""

    categories: list[BrowserTreeNode]


class BrowserItem(BaseModel):
    """Immediate child item returned by ``get_browser_items``."""

    name: str
    uri: str | None = None
    is_loadable: bool


class BrowserItemsResult(BaseModel):
    """Immediate Browser children for a resolved path."""

    path: str
    items: list[BrowserItem]


class BrowserSearchItem(BaseModel):
    """One Browser search hit."""

    name: str
    path: str
    uri: str | None = None
    is_loadable: bool


class BrowserSearchResult(BaseModel):
    """Search results for ``search_browser``."""

    query: str
    category: BrowserCategory
    items: list[BrowserSearchItem]


def _get_connection(ctx: Context) -> AbletonConnection:
    """Extract the AbletonConnection from the FastMCP context."""
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_browser_tree(
    ctx: Context,
    category: Annotated[
        BrowserCategory,
        Field(
            description=(
                "Browser root to inspect: one category or 'all' for every "
                "supported Phase 1 Browser category."
            ),
        ),
    ] = "all",
) -> BrowserTree:
    """Get a shallow hierarchical Browser tree for supported categories."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="browser.get_tree",
        params={"category": category},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return BrowserTree.model_validate(response.result)


@mcp.tool()
async def get_browser_items(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description=(
                "Slash-separated Browser path rooted at a supported category, "
                "for example 'instruments' or 'instruments/Synths'."
            ),
            min_length=1,
        ),
    ],
) -> BrowserItemsResult:
    """Get the immediate Browser items at a slash-separated path."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="browser.get_items",
        params={"path": path},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return BrowserItemsResult.model_validate(response.result)


@mcp.tool()
async def search_browser(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            description="Case-insensitive Browser search query.",
            min_length=1,
        ),
    ],
    category: Annotated[
        BrowserCategory,
        Field(
            description=(
                "Browser root to search: one category or 'all' for every "
                "supported Phase 1 Browser category."
            ),
        ),
    ] = "all",
) -> BrowserSearchResult:
    """Search Browser items recursively by name."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="browser.search",
        params={"query": query, "category": category},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return BrowserSearchResult.model_validate(response.result)


__all__ = [
    "BrowserItem",
    "BrowserItemsResult",
    "BrowserSearchItem",
    "BrowserSearchResult",
    "BrowserTree",
    "BrowserTreeNode",
    "get_browser_items",
    "get_browser_tree",
    "search_browser",
]
