"""MCP tools for Ableton Live mixer control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


TrackIndex = Annotated[
    int,
    Field(
        description="1-based track index.",
        ge=1,
    ),
]

SendIndex = Annotated[
    int,
    Field(
        description="1-based send index on the track.",
        ge=1,
    ),
]

ReturnIndex = Annotated[
    int,
    Field(
        description="1-based return track index.",
        ge=1,
    ),
]


class MasterTrackInfo(BaseModel):
    """Snapshot of the master track mixer state."""

    name: str
    volume: float
    pan: float


class ReturnTrackInfo(BaseModel):
    """Snapshot of a return track mixer state."""

    return_index: int
    name: str
    volume: float
    pan: float


class ReturnTracksResult(BaseModel):
    """All return tracks currently in the song."""

    return_tracks: list[ReturnTrackInfo]


class TrackVolumeSetResult(BaseModel):
    """Result of ``set_track_volume``."""

    track_index: int
    volume: float


class TrackPanSetResult(BaseModel):
    """Result of ``set_track_pan``."""

    track_index: int
    pan: float


class SendLevelSetResult(BaseModel):
    """Result of ``set_send_level``."""

    track_index: int
    send_index: int
    level: float


class MasterVolumeSetResult(BaseModel):
    """Result of ``set_master_volume``."""

    volume: float


class ReturnVolumeSetResult(BaseModel):
    """Result of ``set_return_volume``."""

    return_index: int
    volume: float


class ReturnPanSetResult(BaseModel):
    """Result of ``set_return_pan``."""

    return_index: int
    pan: float


def _get_connection(ctx: Context) -> AbletonConnection:
    """Extract the Ableton TCP connection from the FastMCP context."""
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def set_track_volume(
    ctx: Context,
    track_index: TrackIndex,
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
    track_index: TrackIndex,
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
async def get_return_tracks(ctx: Context) -> ReturnTracksResult:
    """Get all return tracks with volume and pan metadata."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="mixer.get_return_tracks")
    response = await connection.send_command(request)
    response.raise_on_error()
    return ReturnTracksResult.model_validate(response.result)


@mcp.tool()
async def set_send_level(
    ctx: Context,
    track_index: TrackIndex,
    send_index: SendIndex,
    level: Annotated[
        float,
        Field(
            description="Send level value normalized to 0.0-1.0.",
            ge=0.0,
            le=1.0,
        ),
    ],
) -> SendLevelSetResult:
    """Set a send level on a normal track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_send_level",
        params={
            "track_index": track_index,
            "send_index": send_index,
            "level": level,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SendLevelSetResult.model_validate(response.result)


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


@mcp.tool()
async def set_return_volume(
    ctx: Context,
    return_index: ReturnIndex,
    volume: Annotated[
        float,
        Field(
            description="Return track volume value normalized to 0.0-1.0.",
            ge=0.0,
            le=1.0,
        ),
    ],
) -> ReturnVolumeSetResult:
    """Set a return track's volume."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_return_volume",
        params={"return_index": return_index, "volume": volume},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ReturnVolumeSetResult.model_validate(response.result)


@mcp.tool()
async def set_return_pan(
    ctx: Context,
    return_index: ReturnIndex,
    pan: Annotated[
        float,
        Field(
            description="Return track pan from -1.0 (left) to 1.0 (right).",
            ge=-1.0,
            le=1.0,
        ),
    ],
) -> ReturnPanSetResult:
    """Set a return track's pan."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="mixer.set_return_pan",
        params={"return_index": return_index, "pan": pan},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ReturnPanSetResult.model_validate(response.result)


__all__ = [
    "MasterTrackInfo",
    "MasterVolumeSetResult",
    "ReturnPanSetResult",
    "ReturnTrackInfo",
    "ReturnTracksResult",
    "ReturnVolumeSetResult",
    "SendLevelSetResult",
    "TrackPanSetResult",
    "TrackVolumeSetResult",
    "get_master_info",
    "get_return_tracks",
    "set_master_volume",
    "set_return_pan",
    "set_return_volume",
    "set_send_level",
    "set_track_pan",
    "set_track_volume",
]
