"""MCP tools for Ableton Live arrangement view clip operations."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest
from mcp_ableton.tools.clip import (
    ClipNote,
    NoteInput,
    _normalize_note_inputs,
)

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
LocatorIndex = Annotated[
    int,
    Field(
        description="1-based index of the locator.",
        ge=1,
    ),
]
LocatorTime = Annotated[
    float,
    Field(
        description="Arrangement beat time (must be >= 0).",
        ge=0.0,
    ),
]


LocatorName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(description="New locator name."),
]
OptionalLocatorName = (
    Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
        Field(
            description=(
                "Optional locator name applied after creation (non-empty if set)."
            )
        ),
    ]
    | None
)


def _validate_absolute_local_file_path(value: str) -> str:
    """Require an absolute local filesystem path without URI schemes."""
    if "://" in value:
        raise ValueError("'file_path' must be an absolute local filesystem path")

    is_absolute = (
        PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    )
    if not is_absolute:
        raise ValueError("'file_path' must be an absolute local filesystem path")
    return value


AudioFilePath = Annotated[
    str,
    AfterValidator(_validate_absolute_local_file_path),
    Field(description="Absolute local filesystem path to an audio file."),
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


class ArrangementAudioImportResult(BaseModel):
    """Result of ``import_audio_to_arrangement``."""

    track_index: int
    clip_index: int
    name: str
    file_path: str
    start_time: float
    length: float
    is_audio_clip: bool


class LocatorInfo(BaseModel):
    """Locator metadata returned by ``get_locators``."""

    locator_index: int
    name: str
    time: float


class LocatorsResult(BaseModel):
    """All locators currently in the song."""

    locators: list[LocatorInfo]


class LocatorCreatedResult(BaseModel):
    """Result of ``create_locator``."""

    locator_index: int
    name: str
    time: float


class LocatorDeletedResult(BaseModel):
    """Result of ``delete_locator``."""

    locator_index: int
    name: str
    time: float


class LocatorRenamedResult(BaseModel):
    """Result of ``set_locator_name``."""

    locator_index: int
    name: str
    time: float


class JumpToTimeResult(BaseModel):
    """Result of ``jump_to_time``."""

    time: float


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


@mcp.tool()
async def import_audio_to_arrangement(
    ctx: Context,
    track_index: TrackIndex,
    file_path: AudioFilePath,
    start_time: StartTime,
) -> ArrangementAudioImportResult:
    """Import an audio file into arrangement view on an audio track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.import_audio",
        params={
            "track_index": track_index,
            "file_path": file_path,
            "start_time": start_time,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementAudioImportResult.model_validate(response.result)


@mcp.tool()
async def get_locators(ctx: Context) -> LocatorsResult:
    """Get all locators in the arrangement."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="arrangement.get_locators")
    response = await connection.send_command(request)
    response.raise_on_error()
    return LocatorsResult.model_validate(response.result)


@mcp.tool()
async def create_locator(
    ctx: Context,
    time: LocatorTime,
    name: OptionalLocatorName = None,
) -> LocatorCreatedResult:
    """Create a locator at a beat time."""
    connection = _get_connection(ctx)
    params: dict[str, Any] = {"time": time}
    if name is not None:
        params["name"] = name
    request = CommandRequest(command="arrangement.create_locator", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return LocatorCreatedResult.model_validate(response.result)


@mcp.tool()
async def delete_locator(
    ctx: Context,
    locator_index: LocatorIndex,
) -> LocatorDeletedResult:
    """Delete a locator by 1-based index."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.delete_locator",
        params={"locator_index": locator_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return LocatorDeletedResult.model_validate(response.result)


@mcp.tool()
async def set_locator_name(
    ctx: Context,
    locator_index: LocatorIndex,
    name: LocatorName,
) -> LocatorRenamedResult:
    """Rename a locator."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.set_locator_name",
        params={"locator_index": locator_index, "name": name},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return LocatorRenamedResult.model_validate(response.result)


@mcp.tool()
async def jump_to_time(
    ctx: Context,
    time: LocatorTime,
) -> JumpToTimeResult:
    """Jump the arrangement playhead to an absolute beat time."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.jump_to_time",
        params={"time": time},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return JumpToTimeResult.model_validate(response.result)


class ArrangementClipNotesResult(BaseModel):
    """All MIDI notes currently in an arrangement clip."""

    track_index: int
    clip_index: int
    notes: list[ClipNote]
    count: int


class ArrangementNotesAddedResult(BaseModel):
    """Result of ``add_notes_to_arrangement_clip``."""

    track_index: int
    clip_index: int
    added_count: int
    note_ids: list[int]


class ArrangementNotesSetResult(BaseModel):
    """Result of ``set_arrangement_clip_notes``."""

    track_index: int
    clip_index: int
    removed_count: int
    added_count: int
    note_ids: list[int]


class ArrangementNotesRemovedResult(BaseModel):
    """Result of ``remove_arrangement_clip_notes``."""

    track_index: int
    clip_index: int
    removed_count: int


@mcp.tool()
async def get_arrangement_clip_notes(
    ctx: Context,
    track_index: TrackIndex,
    clip_index: ClipIndex,
) -> ArrangementClipNotesResult:
    """Get all MIDI notes from an arrangement clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.get_notes",
        params={
            "track_index": track_index,
            "clip_index": clip_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementClipNotesResult.model_validate(response.result)


@mcp.tool()
async def add_notes_to_arrangement_clip(
    ctx: Context,
    track_index: TrackIndex,
    clip_index: ClipIndex,
    notes: Annotated[
        list[NoteInput],
        Field(
            description=(
                "Notes to add. Each note may be a lean array "
                "[pitch, start_time, duration, velocity] or an object with "
                "pitch/start_time/duration/velocity plus optional mute, "
                "probability, and velocity_deviation."
            ),
            min_length=1,
        ),
    ],
) -> ArrangementNotesAddedResult:
    """Add MIDI notes to an arrangement clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.add_notes",
        params={
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": _normalize_note_inputs(notes),
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementNotesAddedResult.model_validate(response.result)


@mcp.tool()
async def set_arrangement_clip_notes(
    ctx: Context,
    track_index: TrackIndex,
    clip_index: ClipIndex,
    notes: Annotated[
        list[NoteInput],
        Field(
            description=(
                "Replacement note set. Accepts lean arrays or note objects. "
                "An empty list clears all notes from the clip."
            ),
        ),
    ],
) -> ArrangementNotesSetResult:
    """Replace all MIDI notes in an arrangement clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="arrangement.set_notes",
        params={
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": _normalize_note_inputs(notes),
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementNotesSetResult.model_validate(response.result)


@mcp.tool()
async def remove_arrangement_clip_notes(
    ctx: Context,
    track_index: TrackIndex,
    clip_index: ClipIndex,
    from_pitch: Annotated[
        int,
        Field(
            description="Lowest pitch in the removal region (inclusive).",
            ge=0,
            le=127,
        ),
    ] = 0,
    pitch_span: Annotated[
        int,
        Field(
            description="Pitch span from from_pitch. 128 covers the full MIDI range.",
            ge=1,
            le=128,
        ),
    ] = 128,
    from_time: Annotated[
        float,
        Field(
            description="Start beat of the removal region (inclusive).",
            ge=0.0,
        ),
    ] = 0.0,
    time_span: Annotated[
        float | None,
        Field(
            description=(
                "Length of the time region in beats. When omitted, notes are "
                "removed from from_time onward."
            ),
            gt=0.0,
        ),
    ] = None,
) -> ArrangementNotesRemovedResult:
    """Remove notes from an arrangement clip by pitch/time range."""
    connection = _get_connection(ctx)
    params: dict[str, Any] = {
        "track_index": track_index,
        "clip_index": clip_index,
        "from_pitch": from_pitch,
        "pitch_span": pitch_span,
        "from_time": from_time,
    }
    if time_span is not None:
        params["time_span"] = time_span

    request = CommandRequest(command="arrangement.remove_notes", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return ArrangementNotesRemovedResult.model_validate(response.result)


__all__ = [
    "ArrangementAudioImportResult",
    "ArrangementClipCreatedResult",
    "ArrangementClipInfo",
    "ArrangementClipMovedResult",
    "ArrangementClipNotesResult",
    "ArrangementClipsResult",
    "ArrangementLengthResult",
    "ArrangementLoopResult",
    "ArrangementNotesAddedResult",
    "ArrangementNotesRemovedResult",
    "ArrangementNotesSetResult",
    "AudioFilePath",
    "JumpToTimeResult",
    "LocatorCreatedResult",
    "LocatorDeletedResult",
    "LocatorInfo",
    "LocatorName",
    "LocatorRenamedResult",
    "LocatorIndex",
    "LocatorTime",
    "LocatorsResult",
    "add_notes_to_arrangement_clip",
    "create_arrangement_clip",
    "create_locator",
    "get_arrangement_clip_notes",
    "get_arrangement_clips",
    "get_arrangement_length",
    "get_locators",
    "import_audio_to_arrangement",
    "jump_to_time",
    "move_arrangement_clip",
    "remove_arrangement_clip_notes",
    "delete_locator",
    "set_arrangement_clip_notes",
    "set_arrangement_loop",
    "set_locator_name",
]
