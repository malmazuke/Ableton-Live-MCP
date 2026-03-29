"""MCP tools for session-view clips and MIDI notes in Ableton Live."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mcp_ableton.connection import AbletonConnection


Pitch = Annotated[int, Field(ge=0, le=127)]
NoteStartTime = Annotated[float, Field(ge=0.0)]
NoteDuration = Annotated[float, Field(gt=0.0)]
NoteVelocity = Annotated[float, Field(ge=0.0, le=127.0)]
NoteProbability = Annotated[float, Field(ge=0.0, le=1.0)]
NoteVelocityDeviation = Annotated[float, Field(ge=-127.0, le=127.0)]


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


class ClipLoopResult(BaseModel):
    """Result of ``set_clip_loop``."""

    track_index: int
    clip_slot_index: int
    loop_start: float
    loop_end: float
    looping: bool


class ClipColorResult(BaseModel):
    """Result of ``set_clip_color``."""

    track_index: int
    clip_slot_index: int
    color_index: int


class ClipGainResult(BaseModel):
    """Result of ``set_clip_gain``."""

    track_index: int
    clip_slot_index: int
    gain: float
    gain_display_string: str


class ClipPitchResult(BaseModel):
    """Result of ``set_clip_pitch``."""

    track_index: int
    clip_slot_index: int
    semitones: int


class ClipWarpModeResult(BaseModel):
    """Result of ``set_clip_warp_mode``."""

    track_index: int
    clip_slot_index: int
    warp_mode: int


AbsoluteLocalFilePath = Annotated[
    str,
    AfterValidator(_validate_absolute_local_file_path),
    Field(description="Absolute local filesystem path to an audio file."),
]


class SessionAudioImportResult(BaseModel):
    """Result of ``import_audio_to_session``."""

    track_index: int
    clip_slot_index: int
    name: str
    file_path: str
    length: float
    is_audio_clip: bool


class NoteObjectInput(BaseModel):
    """Structured note input accepted by note-editing tools."""

    model_config = ConfigDict(extra="forbid")

    pitch: Pitch
    start_time: NoteStartTime
    duration: NoteDuration
    velocity: NoteVelocity
    mute: bool = False
    probability: NoteProbability | None = None
    velocity_deviation: NoteVelocityDeviation | None = None


LeanNoteInput = tuple[Pitch, NoteStartTime, NoteDuration, NoteVelocity]
NoteInput = NoteObjectInput | LeanNoteInput


class ClipNote(BaseModel):
    """Canonical MIDI note representation returned by clip note tools."""

    note_id: int
    pitch: int
    start_time: float
    duration: float
    velocity: float
    mute: bool
    probability: float | None = None
    velocity_deviation: float | None = None


class ClipAutomationPoint(BaseModel):
    """A single clip automation point or step."""

    model_config = ConfigDict(extra="forbid")

    time: float = Field(ge=0.0)
    value: float
    step_length: float = Field(default=0.0, ge=0.0)


class ClipAutomationResult(BaseModel):
    """Clip automation points for a specific device parameter."""

    track_index: int
    clip_slot_index: int
    device_index: int
    parameter_index: int
    device_name: str
    parameter_name: str
    points: list[ClipAutomationPoint]


class ClipAutomationSetResult(BaseModel):
    """Result of ``set_clip_automation``."""

    track_index: int
    clip_slot_index: int
    device_index: int
    parameter_index: int
    device_name: str
    parameter_name: str
    point_count: int


class ClipNotesResult(BaseModel):
    """All MIDI notes currently in a session clip."""

    track_index: int
    clip_slot_index: int
    notes: list[ClipNote]


class NotesAddedResult(BaseModel):
    """Result of ``add_notes_to_clip``."""

    track_index: int
    clip_slot_index: int
    added_count: int
    note_ids: list[int]


class NotesRemovedResult(BaseModel):
    """Result of ``remove_notes``."""

    track_index: int
    clip_slot_index: int
    removed_count: int


class NotesSetResult(BaseModel):
    """Result of ``set_clip_notes``."""

    track_index: int
    clip_slot_index: int
    removed_count: int
    added_count: int
    note_ids: list[int]


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


def _normalize_note_input(note: NoteInput | dict[str, Any]) -> dict[str, Any]:
    """Convert lean or object note input into the canonical protocol shape."""
    if isinstance(note, NoteObjectInput):
        payload: dict[str, Any] = {
            "pitch": note.pitch,
            "start_time": note.start_time,
            "duration": note.duration,
            "velocity": note.velocity,
            "mute": note.mute,
        }
        if note.probability is not None:
            payload["probability"] = note.probability
        if note.velocity_deviation is not None:
            payload["velocity_deviation"] = note.velocity_deviation
        return payload

    if isinstance(note, dict):
        return _normalize_note_input(NoteObjectInput.model_validate(note))

    pitch, start_time, duration, velocity = note
    return {
        "pitch": pitch,
        "start_time": start_time,
        "duration": duration,
        "velocity": velocity,
        "mute": False,
    }


def _normalize_note_inputs(
    notes: Sequence[NoteInput | dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize all note inputs before sending them to the Remote Script."""
    return [_normalize_note_input(note) for note in notes]


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


@mcp.tool()
async def set_clip_loop(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    loop_start: Annotated[
        float,
        Field(
            description="Loop start in clip beat time (must be >= 0).",
            ge=0.0,
        ),
    ],
    loop_end: Annotated[
        float,
        Field(
            description="Loop end in clip beat time (must be > loop_start).",
            gt=0.0,
        ),
    ],
    looping: Annotated[
        bool,
        Field(description="Whether clip looping should be enabled."),
    ] = True,
) -> ClipLoopResult:
    """Set loop start/end and loop enabled state for a session clip."""
    if loop_end <= loop_start:
        raise ValueError("'loop_end' must be greater than 'loop_start'")
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_loop",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "loop_start": loop_start,
            "loop_end": loop_end,
            "looping": looping,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipLoopResult.model_validate(response.result)


@mcp.tool()
async def set_clip_color(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    color_index: Annotated[
        int,
        Field(
            description="Clip color index (must be >= 0).",
            ge=0,
        ),
    ],
) -> ClipColorResult:
    """Set the color index for a session clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_color",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "color_index": color_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipColorResult.model_validate(response.result)


@mcp.tool()
async def set_clip_gain(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    gain: Annotated[
        float,
        Field(
            description=(
                "Audio clip gain using Live's native normalized 0.0-1.0 range."
            ),
            ge=0.0,
            le=1.0,
        ),
    ],
) -> ClipGainResult:
    """Set a session audio clip's gain using Live's native normalized range."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_gain",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "gain": gain,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipGainResult.model_validate(response.result)


@mcp.tool()
async def set_clip_pitch(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    semitones: Annotated[
        int,
        Field(
            description="Audio clip coarse transpose in semitones (-48 to 48).",
            ge=-48,
            le=48,
        ),
    ],
) -> ClipPitchResult:
    """Set coarse semitone transpose for a session audio clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_pitch",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "semitones": semitones,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipPitchResult.model_validate(response.result)


@mcp.tool()
async def set_clip_warp_mode(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    warp_mode: Annotated[
        int,
        Field(
            description=(
                "Integer warp mode selector. Valid values depend on the clip's "
                "runtime-supported available warp modes."
            ),
            ge=0,
        ),
    ],
) -> ClipWarpModeResult:
    """Set the warp mode for a session audio clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_warp_mode",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "warp_mode": warp_mode,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipWarpModeResult.model_validate(response.result)


@mcp.tool()
async def import_audio_to_session(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    file_path: AbsoluteLocalFilePath,
) -> SessionAudioImportResult:
    """Import an audio file into an empty session slot on an audio track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.import_audio",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "file_path": file_path,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SessionAudioImportResult.model_validate(response.result)


@mcp.tool()
async def get_clip_notes(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
) -> ClipNotesResult:
    """Get all MIDI notes from a session clip as canonical note objects."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.get_notes",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipNotesResult.model_validate(response.result)


@mcp.tool()
async def get_clip_automation(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    device_index: Annotated[
        int,
        Field(description="1-based device index on the track.", ge=1),
    ],
    parameter_index: Annotated[
        int,
        Field(description="1-based parameter index on the device.", ge=1),
    ],
) -> ClipAutomationResult:
    """Get clip automation points for a device parameter on the host track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.get_automation",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "device_index": device_index,
            "parameter_index": parameter_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipAutomationResult.model_validate(response.result)


@mcp.tool()
async def add_notes_to_clip(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
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
) -> NotesAddedResult:
    """Add MIDI notes to a session clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.add_notes",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "notes": _normalize_note_inputs(notes),
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return NotesAddedResult.model_validate(response.result)


@mcp.tool()
async def set_clip_automation(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    device_index: Annotated[
        int,
        Field(description="1-based device index on the track.", ge=1),
    ],
    parameter_index: Annotated[
        int,
        Field(description="1-based parameter index on the device.", ge=1),
    ],
    points: Annotated[
        list[ClipAutomationPoint],
        Field(
            description=(
                "Replacement automation points. Each point includes time, value, "
                "and optional step_length."
            ),
            min_length=1,
        ),
    ],
) -> ClipAutomationSetResult:
    """Replace clip automation for a device parameter with the supplied points."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_automation",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "device_index": device_index,
            "parameter_index": parameter_index,
            "points": [
                ClipAutomationPoint.model_validate(point).model_dump(mode="python")
                for point in points
            ],
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ClipAutomationSetResult.model_validate(response.result)


@mcp.tool()
async def remove_notes(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
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
) -> NotesRemovedResult:
    """Remove MIDI notes from a clip by pitch/time region."""
    connection = _get_connection(ctx)
    params: dict[str, Any] = {
        "track_index": track_index,
        "clip_slot_index": clip_slot_index,
        "from_pitch": from_pitch,
        "pitch_span": pitch_span,
        "from_time": from_time,
    }
    if time_span is not None:
        params["time_span"] = time_span

    request = CommandRequest(command="clip.remove_notes", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return NotesRemovedResult.model_validate(response.result)


@mcp.tool()
async def set_clip_notes(
    ctx: Context,
    track_index: Annotated[int, Field(description="1-based track index.", ge=1)],
    clip_slot_index: ClipSlotIndex,
    notes: Annotated[
        list[NoteInput],
        Field(
            description=(
                "Replacement note set. Accepts lean arrays or note objects. "
                "An empty list clears all notes from the clip."
            ),
        ),
    ],
) -> NotesSetResult:
    """Replace all MIDI notes in a session clip."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="clip.set_notes",
        params={
            "track_index": track_index,
            "clip_slot_index": clip_slot_index,
            "notes": _normalize_note_inputs(notes),
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return NotesSetResult.model_validate(response.result)


__all__ = [
    "AbsoluteLocalFilePath",
    "ClipAutomationPoint",
    "ClipAutomationResult",
    "ClipAutomationSetResult",
    "ClipColorResult",
    "ClipGainResult",
    "ClipNote",
    "ClipCreatedResult",
    "ClipDuplicatedResult",
    "ClipInfo",
    "ClipLoopResult",
    "ClipNotesResult",
    "ClipPitchResult",
    "ClipRenamedResult",
    "ClipSlotResult",
    "ClipWarpModeResult",
    "LeanNoteInput",
    "NoteInput",
    "NoteObjectInput",
    "NotesAddedResult",
    "NotesRemovedResult",
    "NotesSetResult",
    "SessionAudioImportResult",
    "add_notes_to_clip",
    "create_clip",
    "delete_clip",
    "duplicate_clip",
    "fire_clip",
    "get_clip_automation",
    "get_clip_info",
    "get_clip_notes",
    "import_audio_to_session",
    "remove_notes",
    "set_clip_automation",
    "set_clip_color",
    "set_clip_gain",
    "set_clip_loop",
    "set_clip_notes",
    "set_clip_name",
    "set_clip_pitch",
    "set_clip_warp_mode",
    "stop_clip",
]
