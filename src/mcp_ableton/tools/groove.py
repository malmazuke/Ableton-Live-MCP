"""MCP tools for Ableton Live groove pool operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


GrooveIndex = Annotated[
    int,
    Field(
        description="1-based groove index (the first groove is 1).",
        ge=1,
        strict=True,
    ),
]

SessionClipIndex = Annotated[
    int,
    Field(
        description="1-based index of the target session clip slot.",
        ge=1,
        strict=True,
    ),
]


class GrooveInfo(BaseModel):
    """One groove entry from the current groove pool."""

    groove_index: int
    name: str
    base: int
    quantization_amount: float
    timing_amount: float
    random_amount: float
    velocity_amount: float


class GroovePoolResult(BaseModel):
    """All grooves currently loaded in Ableton Live."""

    grooves: list[GrooveInfo]


class GrooveAppliedResult(BaseModel):
    """Result of applying a groove to a session clip."""

    track_index: int
    clip_slot_index: int
    groove_index: int
    groove_name: str


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_groove_pool(ctx: Context) -> GroovePoolResult:
    """Get the current groove pool."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="groove.get_pool")
    response = await connection.send_command(request)
    response.raise_on_error()
    return GroovePoolResult.model_validate(response.result)


@mcp.tool()
async def apply_groove(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index of the target track.",
            ge=1,
            strict=True,
        ),
    ],
    clip_slot_index: SessionClipIndex,
    groove_index: GrooveIndex,
) -> GrooveAppliedResult:
    """Apply a groove from the pool to an existing session clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="groove.apply",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "groove_index": groove_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return GrooveAppliedResult.model_validate(response.result)


__all__ = [
    "GrooveAppliedResult",
    "GrooveInfo",
    "GroovePoolResult",
    "apply_groove",
    "get_groove_pool",
]
