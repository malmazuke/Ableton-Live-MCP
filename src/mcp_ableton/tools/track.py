"""MCP tools for track management in Ableton Live."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


class TrackInfo(BaseModel):
    """Per-track snapshot returned by ``get_track_info``."""

    name: str
    track_index: int
    is_audio_track: bool
    is_midi_track: bool
    mute: bool
    solo: bool
    arm: bool
    volume: float
    pan: float
    device_names: list[str]
    clip_slot_has_clip: list[bool]


class TrackCreatedResult(BaseModel):
    """Result of ``create_midi_track`` or ``create_audio_track``."""

    track_index: int
    name: str | None = None


class TrackDeletedResult(BaseModel):
    """Result of ``delete_track``."""

    track_index: int


class TrackDuplicatedResult(BaseModel):
    """Result of ``duplicate_track``."""

    source_track_index: int
    new_track_index: int


class TrackUpdatedResult(BaseModel):
    """Result of ``set_track_name``, ``set_track_mute``, etc."""

    track_index: int


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_track_info(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index into the song's track list (first track is 1).",
            ge=1,
        ),
    ],
) -> TrackInfo:
    """Get information about a track (name, type, mixer, devices, clip slots).

    ``track_index`` is 1-based (the first track is 1). For deep device or clip
    data, use the dedicated device and clip tools (composition over this view).
    """
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.get_info",
        params={"track_index": track_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackInfo.model_validate(response.result)


@mcp.tool()
async def create_midi_track(
    ctx: Context,
    index: Annotated[
        int,
        Field(
            description=(
                "Insert position using Live's API: -1 appends at the end; "
                "0..N-1 inserts before that 0-based slot (not the same as 1-based "
                "track_index)."
            ),
        ),
    ] = -1,
    name: Annotated[
        str | None,
        Field(
            description=(
                "Optional track name applied after creation (non-empty if set)."
            ),
        ),
    ] = None,
) -> TrackCreatedResult:
    """Create a new MIDI track.

    The ``index`` parameter follows Live's ``create_midi_track`` semantics
    (0-based insert index, or -1 for end), not 1-based ``track_index``.
    """
    connection = _get_connection(ctx)
    params: dict = {"index": index}
    if name is not None:
        params["name"] = name
    request = CommandRequest(command="track.create_midi", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackCreatedResult.model_validate(response.result)


@mcp.tool()
async def create_audio_track(
    ctx: Context,
    index: Annotated[
        int,
        Field(
            description=(
                "Insert position using Live's API: -1 appends at the end; "
                "0..N-1 inserts before that 0-based slot."
            ),
        ),
    ] = -1,
    name: Annotated[
        str | None,
        Field(
            description=(
                "Optional track name applied after creation (non-empty if set)."
            ),
        ),
    ] = None,
) -> TrackCreatedResult:
    """Create a new audio track.

    The ``index`` parameter follows Live's ``create_audio_track`` semantics
    (0-based insert index, or -1 for end), not 1-based ``track_index``.
    """
    connection = _get_connection(ctx)
    params: dict = {"index": index}
    if name is not None:
        params["name"] = name
    request = CommandRequest(command="track.create_audio", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackCreatedResult.model_validate(response.result)


@mcp.tool()
async def delete_track(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index of the track to remove.",
            ge=1,
        ),
    ],
) -> TrackDeletedResult:
    """Delete a track from the song."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.delete",
        params={"track_index": track_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackDeletedResult.model_validate(response.result)


@mcp.tool()
async def duplicate_track(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index of the track to duplicate.",
            ge=1,
        ),
    ],
) -> TrackDuplicatedResult:
    """Duplicate a track; the copy is inserted after the source track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.duplicate",
        params={"track_index": track_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackDuplicatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_name(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    name: Annotated[
        str,
        Field(description="New track name.", min_length=1),
    ],
) -> TrackUpdatedResult:
    """Rename a track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_name",
        params={"track_index": track_index, "name": name},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_mute(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    mute: Annotated[bool, Field(description="Whether the track is muted.")],
) -> TrackUpdatedResult:
    """Set a track's mute state."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_mute",
        params={"track_index": track_index, "mute": mute},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_solo(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    solo: Annotated[bool, Field(description="Whether the track is soloed.")],
) -> TrackUpdatedResult:
    """Set a track's solo state."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_solo",
        params={"track_index": track_index, "solo": solo},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_arm(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    arm: Annotated[
        bool,
        Field(description="Whether the track is armed for recording."),
    ],
) -> TrackUpdatedResult:
    """Arm or disarm a track for recording (only if the track can be armed)."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_arm",
        params={"track_index": track_index, "arm": arm},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


__all__ = [
    "TrackCreatedResult",
    "TrackDeletedResult",
    "TrackDuplicatedResult",
    "TrackInfo",
    "TrackUpdatedResult",
    "create_audio_track",
    "create_midi_track",
    "delete_track",
    "duplicate_track",
    "get_track_info",
    "set_track_arm",
    "set_track_mute",
    "set_track_name",
    "set_track_solo",
]
