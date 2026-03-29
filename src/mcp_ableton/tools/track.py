"""MCP tools for track management in Ableton Live."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection

TrackScope = Literal["main", "return", "master"]


class TrackInfo(BaseModel):
    """Per-track snapshot returned by ``get_track_info``."""

    name: str
    track_scope: TrackScope
    track_index: int | None
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

    track_scope: TrackScope
    track_index: int | None


def _validate_track_scope_and_index(
    track_scope: TrackScope,
    track_index: int | None,
) -> dict[str, object]:
    """Validate the scoped track address before sending a TCP command."""
    if track_scope in {"main", "return"}:
        if track_index is None:
            raise ValueError(
                f"'track_index' is required when track_scope='{track_scope}'"
            )
        if isinstance(track_index, bool) or not isinstance(track_index, int):
            raise ValueError("'track_index' must be an integer")
        if track_index < 1:
            raise ValueError("'track_index' must be at least 1")
        return {"track_scope": track_scope, "track_index": track_index}

    if track_index is not None:
        raise ValueError("'track_index' must be omitted when track_scope='master'")

    return {"track_scope": track_scope}


def _build_track_params(
    *,
    track_scope: TrackScope,
    track_index: int | None,
    extra_params: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a validated command payload for a scoped track request."""
    params: dict[str, object] = _validate_track_scope_and_index(
        track_scope,
        track_index,
    )
    if extra_params:
        params.update(extra_params)
    return params


class RoutingOption(BaseModel):
    """A routing option returned by Ableton Live."""

    identifier: str
    display_name: str


class TrackRoutingInfo(BaseModel):
    """Current routing selections for one track."""

    track_index: int
    input_routing_type: RoutingOption
    input_routing_channel: RoutingOption
    output_routing_type: RoutingOption
    output_routing_channel: RoutingOption


class AvailableRoutingResult(BaseModel):
    """Available routing choices for one track."""

    track_index: int
    available_input_routing_types: list[RoutingOption]
    available_input_routing_channels: list[RoutingOption]
    available_output_routing_types: list[RoutingOption]
    available_output_routing_channels: list[RoutingOption]


class TrackInputRoutingResult(BaseModel):
    """Result of ``set_track_input_routing``."""

    track_index: int
    input_routing_type: RoutingOption
    input_routing_channel: RoutingOption


class TrackOutputRoutingResult(BaseModel):
    """Result of ``set_track_output_routing``."""

    track_index: int
    output_routing_type: RoutingOption
    output_routing_channel: RoutingOption


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_track_info(
    ctx: Context,
    track_scope: Annotated[
        TrackScope,
        Field(
            description="Track scope: main, return, or master.",
        ),
    ] = "main",
    track_index: Annotated[
        int | None,
        Field(
            description=(
                "1-based track index for main/return tracks. Omit for master."
            ),
            ge=1,
        ),
    ] = None,
) -> TrackInfo:
    """Get information about a track (name, type, mixer, devices, clip slots).

    ``track_index`` is 1-based (the first track is 1). For deep device or clip
    data, use the dedicated device and clip tools (composition over this view).
    """
    connection = _get_connection(ctx)
    params = _build_track_params(
        track_scope=track_scope,
        track_index=track_index,
    )
    request = CommandRequest(command="track.get_info", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackInfo.model_validate(response.result)


@mcp.tool()
async def get_track_routing(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index of the track.",
            ge=1,
        ),
    ],
) -> TrackRoutingInfo:
    """Get the current input/output routing selections for a track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.get_routing",
        params={"track_index": track_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackRoutingInfo.model_validate(response.result)


@mcp.tool()
async def get_available_routing(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(
            description="1-based index of the track.",
            ge=1,
        ),
    ],
) -> AvailableRoutingResult:
    """Get the available input/output routing options for a track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.get_available_routing",
        params={"track_index": track_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return AvailableRoutingResult.model_validate(response.result)


@mcp.tool()
async def set_track_input_routing(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based index of the track.", ge=1),
    ],
    routing_type_identifier: Annotated[
        str,
        Field(
            description="Identifier of the target input routing type.",
            min_length=1,
        ),
    ],
    routing_channel_identifier: Annotated[
        str,
        Field(
            description="Identifier of the target input routing channel.",
            min_length=1,
        ),
    ],
) -> TrackInputRoutingResult:
    """Set a track's input routing using routing identifiers."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_input_routing",
        params={
            "track_index": track_index,
            "routing_type_identifier": routing_type_identifier,
            "routing_channel_identifier": routing_channel_identifier,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackInputRoutingResult.model_validate(response.result)


@mcp.tool()
async def set_track_output_routing(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based index of the track.", ge=1),
    ],
    routing_type_identifier: Annotated[
        str,
        Field(
            description="Identifier of the target output routing type.",
            min_length=1,
        ),
    ],
    routing_channel_identifier: Annotated[
        str,
        Field(
            description="Identifier of the target output routing channel.",
            min_length=1,
        ),
    ],
) -> TrackOutputRoutingResult:
    """Set a track's output routing using routing identifiers."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_output_routing",
        params={
            "track_index": track_index,
            "routing_type_identifier": routing_type_identifier,
            "routing_channel_identifier": routing_channel_identifier,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackOutputRoutingResult.model_validate(response.result)


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
    name: Annotated[
        str,
        Field(description="New track name.", min_length=1),
    ],
    track_scope: Annotated[
        TrackScope,
        Field(description="Track scope: main, return, or master."),
    ] = "main",
    track_index: Annotated[
        int | None,
        Field(description="1-based track index for main/return tracks.", ge=1),
    ] = None,
) -> TrackUpdatedResult:
    """Rename a track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_name",
        params=_build_track_params(
            track_scope=track_scope,
            track_index=track_index,
            extra_params={"name": name},
        ),
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_mute(
    ctx: Context,
    mute: Annotated[bool, Field(description="Whether the track is muted.")],
    track_scope: Annotated[
        TrackScope,
        Field(description="Track scope: main, return, or master."),
    ] = "main",
    track_index: Annotated[
        int | None,
        Field(description="1-based track index for main/return tracks.", ge=1),
    ] = None,
) -> TrackUpdatedResult:
    """Set a track's mute state."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_mute",
        params=_build_track_params(
            track_scope=track_scope,
            track_index=track_index,
            extra_params={"mute": mute},
        ),
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_solo(
    ctx: Context,
    solo: Annotated[bool, Field(description="Whether the track is soloed.")],
    track_scope: Annotated[
        TrackScope,
        Field(description="Track scope: main, return, or master."),
    ] = "main",
    track_index: Annotated[
        int | None,
        Field(description="1-based track index for main/return tracks.", ge=1),
    ] = None,
) -> TrackUpdatedResult:
    """Set a track's solo state."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_solo",
        params=_build_track_params(
            track_scope=track_scope,
            track_index=track_index,
            extra_params={"solo": solo},
        ),
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


@mcp.tool()
async def set_track_arm(
    ctx: Context,
    arm: Annotated[
        bool,
        Field(description="Whether the track is armed for recording."),
    ],
    track_scope: Annotated[
        TrackScope,
        Field(description="Track scope: main, return, or master."),
    ] = "main",
    track_index: Annotated[
        int | None,
        Field(description="1-based track index for main/return tracks.", ge=1),
    ] = None,
) -> TrackUpdatedResult:
    """Arm or disarm a track for recording (only if the track can be armed)."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="track.set_arm",
        params=_build_track_params(
            track_scope=track_scope,
            track_index=track_index,
            extra_params={"arm": arm},
        ),
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TrackUpdatedResult.model_validate(response.result)


__all__ = [
    "AvailableRoutingResult",
    "RoutingOption",
    "TrackCreatedResult",
    "TrackDeletedResult",
    "TrackDuplicatedResult",
    "TrackInfo",
    "TrackInputRoutingResult",
    "TrackOutputRoutingResult",
    "TrackRoutingInfo",
    "TrackUpdatedResult",
    "TrackScope",
    "create_audio_track",
    "create_midi_track",
    "delete_track",
    "duplicate_track",
    "get_available_routing",
    "get_track_info",
    "get_track_routing",
    "set_track_input_routing",
    "set_track_arm",
    "set_track_mute",
    "set_track_name",
    "set_track_output_routing",
    "set_track_solo",
]
