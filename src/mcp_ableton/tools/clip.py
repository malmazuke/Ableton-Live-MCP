"""MCP tools for session-view clips in Ableton Live."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


class ClipCreatedResult(BaseModel):
    """Result of ``create_clip``."""

    track_index: int
    clip_slot_index: int
    length: float


class ClipSlotResult(BaseModel):
    """Result of ``delete_clip``, ``fire_clip``, or ``stop_clip``."""

    track_index: int
    clip_slot_index: int


class ClipDuplicatedResult(BaseModel):
    """Result of ``duplicate_clip``."""

    track_index: int
    source_clip_slot_index: int
    new_clip_slot_index: int | None = None


class ClipRenamedResult(BaseModel):
    """Result of ``set_clip_name``."""

    track_index: int
    clip_slot_index: int
    name: str


class ClipInfo(BaseModel):
    """Session clip metadata from ``get_clip_info``."""

    track_index: int
    clip_slot_index: int
    name: str
    length: float
    is_audio_clip: bool
    is_midi_clip: bool
    is_playing: bool
    is_recording: bool


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


ClipSlotIndex = Annotated[
    int,
    Field(
        description=(
            "1-based scene/slot index on the track (first row in Session View is 1)."
        ),
        ge=1,
    ),
]


@mcp.tool()
async def create_clip(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based index of the track.", ge=1),
    ],
    clip_slot_index: ClipSlotIndex,
    length: Annotated[
        float,
        Field(
            description="Clip length in beats (positive).",
            gt=0,
        ),
    ] = 4.0,
) -> ClipCreatedResult:
    """Create an empty MIDI clip in a session slot.

    The slot must be empty and the track must accept MIDI clips (MIDI track).
    """
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.create",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "length": length,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipCreatedResult.model_validate(response.result)


@mcp.tool()
async def delete_clip(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipSlotResult:
    """Delete the clip in a session slot."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.delete",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipSlotResult.model_validate(response.result)


@mcp.tool()
async def duplicate_clip(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipDuplicatedResult:
    """Duplicate a session clip (same behavior as Live's clip-slot duplicate)."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.duplicate",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipDuplicatedResult.model_validate(response.result)


@mcp.tool()
async def set_clip_name(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    name: Annotated[str, Field(description="New clip name.", min_length=1)],
) -> ClipRenamedResult:
    """Rename the clip in a session slot."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_name",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "name": name,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipRenamedResult.model_validate(response.result)


@mcp.tool()
async def fire_clip(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipSlotResult:
    """Start or trigger the session slot (launch clip, record, or stop button)."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.fire",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipSlotResult.model_validate(response.result)


@mcp.tool()
async def stop_clip(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipSlotResult:
    """Stop playback or recording for this slot column on the track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.stop",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipSlotResult.model_validate(response.result)


@mcp.tool()
async def get_clip_info(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipInfo:
    """Get metadata for the clip in a session slot."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.get_info",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipInfo.model_validate(response.result)


__all__ = [
    "ClipCreatedResult",
    "ClipDuplicatedResult",
    "ClipInfo",
    "ClipRenamedResult",
    "ClipSlotResult",
    "create_clip",
    "delete_clip",
    "duplicate_clip",
    "fire_clip",
    "get_clip_info",
    "set_clip_name",
    "stop_clip",
]
