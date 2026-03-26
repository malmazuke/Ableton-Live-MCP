"""MCP tools for session-view clips and MIDI notes in Ableton Live."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, ConfigDict, Field

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
    "ClipNote",
    "ClipCreatedResult",
    "ClipDuplicatedResult",
    "ClipInfo",
    "ClipNotesResult",
    "ClipRenamedResult",
    "ClipSlotResult",
    "LeanNoteInput",
    "NoteInput",
    "NoteObjectInput",
    "NotesAddedResult",
    "NotesRemovedResult",
    "NotesSetResult",
    "add_notes_to_clip",
    "create_clip",
    "delete_clip",
    "duplicate_clip",
    "fire_clip",
    "get_clip_info",
    "get_clip_notes",
    "remove_notes",
    "set_clip_notes",
    "set_clip_name",
    "stop_clip",
]
