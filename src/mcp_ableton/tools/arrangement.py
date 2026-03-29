"""MCP tools for Ableton Live arrangement view clip operations."""

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
        description="1-based index of the track.",
        ge=1,
    ),
]
ClipIndex = Annotated[
    int,
    Field(
        description=(
            "1-based clip index within the track's arrangement_clips collection."
        ),
        ge=1,
    ),
]
StartTime = Annotated[
    float,
    Field(
        description="Beat time in arrangement space (must be >= 0).",
        ge=0.0,
    ),
]
PositiveLength = Annotated[
    float,
    Field(
        description="Clip length in beats (must be > 0).",
        gt=0.0,
    ),
]


class ArrangementClipInfo(BaseModel):
    """Arrangement clip metadata returned by ``get_arrangement_clips``."""

    track_index: int
    clip_index: int
    name: str
    start_time: float
    end_time: float
    length: float
    is_audio_clip: bool
    is_midi_clip: bool


class ArrangementClipsResult(BaseModel):
    """Arrangement clip listing for one track or the whole song."""

    track_index: int | None
    clips: list[ArrangementClipInfo]


class ArrangementClipCreatedResult(BaseModel):
    """Result of ``create_arrangement_clip``."""

    track_index: int
    clip_index: int
    start_time: float
    length: float
    name: str


class ArrangementClipMovedResult(BaseModel):
    """Result of ``move_arrangement_clip``."""

    source_track_index: int
    source_clip_index: int
    target_track_index: int
    target_clip_index: int
    start_time: float


class ArrangementLengthResult(BaseModel):
    """Total arrangement length returned by ``get_arrangement_length``."""

    song_length: float


class ArrangementLoopResult(BaseModel):
    """Result of ``set_arrangement_loop``."""

    start_time: float
    end_time: float
    enabled: bool


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_arrangement_clips(
    ctx: Context,
    track_index: Annotated[
        TrackIndex | None,
        Field(
            description=(
                "Optional 1-based track index. When omitted, returns clips across all "
                "tracks."
            ),
        ),
    ] = None,
) -> ArrangementClipsResult:
    """Get arrangement clips for one track or for all tracks."""
    connection = _get_connection(ctx)
    params: dict[str, int] = {}
    if track_index is not None:
        params["track_index"] = track_index
    request = CommandRequest(command="arrangement.get_clips", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementClipsResult.model_validate(response.result)


@mcp.tool()
async def create_arrangement_clip(
    ctx: Context,
    track_index: TrackIndex,
    start_time: StartTime,
    length: PositiveLength,
) -> ArrangementClipCreatedResult:
    """Create an empty MIDI arrangement clip on a MIDI track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.create_clip",
        params={
            "track_index": track_index,
            "start_time": start_time,
            "length": length,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementClipCreatedResult.model_validate(response.result)


@mcp.tool()
async def move_arrangement_clip(
    ctx: Context,
    track_index: TrackIndex,
    clip_index: ClipIndex,
    new_start_time: Annotated[
        float,
        Field(
            description="New arrangement start time in beats (must be >= 0).", ge=0.0
        ),
    ],
    new_track_index: Annotated[
        TrackIndex | None,
        Field(
            description=(
                "Optional 1-based target track index. When omitted, the clip stays "
                "on the source track."
            ),
        ),
    ] = None,
) -> ArrangementClipMovedResult:
    """Move an arrangement clip by duplicating it and deleting the original."""
    connection = _get_connection(ctx)
    params: dict[str, int | float] = {
        "track_index": track_index,
        "clip_index": clip_index,
        "new_start_time": new_start_time,
    }
    if new_track_index is not None:
        params["new_track_index"] = new_track_index
    request = CommandRequest(command="arrangement.move_clip", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementClipMovedResult.model_validate(response.result)


@mcp.tool()
async def get_arrangement_length(ctx: Context) -> ArrangementLengthResult:
    """Get the total arrangement length in beats."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="arrangement.get_length")
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementLengthResult.model_validate(response.result)


@mcp.tool()
async def set_arrangement_loop(
    ctx: Context,
    start_time: StartTime,
    end_time: Annotated[
        float,
        Field(description="Arrangement loop end time in beats (must be >= 0).", ge=0.0),
    ],
    enabled: Annotated[
        bool,
        Field(description="Whether the arrangement loop is enabled."),
    ] = True,
) -> ArrangementLoopResult:
    """Set the arrangement loop range and enabled state."""
    if end_time <= start_time:
        raise ValueError("'end_time' must be greater than 'start_time'")

    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.set_loop",
        params={
            "start_time": start_time,
            "end_time": end_time,
            "enabled": enabled,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementLoopResult.model_validate(response.result)


__all__ = [
    "ArrangementClipCreatedResult",
    "ArrangementClipInfo",
    "ArrangementClipMovedResult",
    "ArrangementClipsResult",
    "ArrangementLengthResult",
    "ArrangementLoopResult",
    "create_arrangement_clip",
    "get_arrangement_clips",
    "get_arrangement_length",
    "move_arrangement_clip",
    "set_arrangement_loop",
]
