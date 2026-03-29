"""MCP tools for Ableton Live mixer control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


class MasterTrackInfo(BaseModel):
    """Snapshot of the master track mixer state."""

    name: str
    volume: float
    pan: float


class TrackVolumeSetResult(BaseModel):
    """Result of ``set_track_volume``."""

    track_index: int
    volume: float


class TrackPanSetResult(BaseModel):
    """Result of ``set_track_pan``."""

    track_index: int
    pan: float


class MasterVolumeSetResult(BaseModel):
    """Result of ``set_master_volume``."""

    volume: float


def _get_connection(ctx: Context) -> AbletonConnection:
    """Extract the Ableton TCP connection from the FastMCP context."""
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def set_track_volume(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based track index.",
            ge=1,
        ),
    ],
    volume: Annotated[
        float,
        Field(
            description="Track volume value normalized to 0.0-1.0.",
            ge=0.0,
            le=1.0,
        ),
    ],
) -> TrackVolumeSetResult:
    """Set a track's volume."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_track_volume",
        params={"track_index": track_index, "volume": volume},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackVolumeSetResult.model_validate(response.result)


@mcp.tool()
async def set_track_pan(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based track index.",
            ge=1,
        ),
    ],
    pan: Annotated[
        float,
        Field(
            description="Track pan from -1.0 (left) to 1.0 (right).",
            ge=-1.0,
            le=1.0,
        ),
    ],
) -> TrackPanSetResult:
    """Set a track's pan."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_track_pan",
        params={"track_index": track_index, "pan": pan},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackPanSetResult.model_validate(response.result)


@mcp.tool()
async def get_master_info(ctx: Context) -> MasterTrackInfo:
    """Get the master track mixer state."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="mixer.get_master_info")
    response = await connection.send_command(request)
    response.raise_on_error()
    return MasterTrackInfo.model_validate(response.result)


@mcp.tool()
async def set_master_volume(
    ctx: Context,
    volume: Annotated[
        float,
        Field(
            description="Master volume value normalized to 0.0-1.0.",
            ge=0.0,
            le=1.0,
        ),
    ],
) -> MasterVolumeSetResult:
    """Set the master track volume."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_master_volume",
        params={"volume": volume},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return MasterVolumeSetResult.model_validate(response.result)


__all__ = [
    "MasterTrackInfo",
    "MasterVolumeSetResult",
    "TrackPanSetResult",
    "TrackVolumeSetResult",
    "get_master_info",
    "set_master_volume",
    "set_track_pan",
    "set_track_volume",
]
