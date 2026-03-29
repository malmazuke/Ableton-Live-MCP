"""MCP tools for session, transport, and recording control.

Provides tools for querying and controlling Ableton Live's session state:
tempo, time signature, transport, recording, and playback position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


class SessionInfo(BaseModel):
    """Current session state returned by ``get_session_info``."""

    tempo: float
    signature_numerator: int
    signature_denominator: int
    track_count: int
    is_playing: bool
    is_recording: bool
    song_length: float


class TempoResult(BaseModel):
    """Result of a ``set_tempo`` operation."""

    tempo: float


class TimeSignatureResult(BaseModel):
    """Result of a ``set_time_signature`` operation."""

    numerator: int
    denominator: int


class TransportResult(BaseModel):
    """Result of a transport action (start/stop playback)."""

    action: str
    is_playing: bool


class RecordingResult(BaseModel):
    """Result of an arrangement recording action."""

    action: Literal["start_recording", "stop_recording"]
    is_recording: bool
    is_playing: bool


class MidiCaptureResult(BaseModel):
    """Result of a MIDI capture action."""

    destination: Literal["auto", "session", "arrangement"]
    captured: bool


class OverdubResult(BaseModel):
    """Result of an overdub state change."""

    overdub: bool


class UndoRedoResult(BaseModel):
    """Result of an undo or redo action."""

    action: Literal["undo", "redo"]
    can_undo: bool
    can_redo: bool


class PlaybackPosition(BaseModel):
    """Current playback position returned by ``get_playback_position``."""

    beats: float
    bar: int
    beat_in_bar: float
    time_seconds: float
    is_playing: bool


def _get_connection(ctx: Context) -> AbletonConnection:
    """Extract the AbletonConnection from the FastMCP context."""
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


async def _send_session_command(
    ctx: Context,
    command: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a ``session.*`` command and return the result payload."""
    connection = _get_connection(ctx)
    request = CommandRequest(command=command, params=params or {})
    response = await connection.send_command(request)
    response.raise_on_error()
    return response.result or {}


@mcp.tool()
async def get_session_info(ctx: Context) -> SessionInfo:
    """Get current session information.

    Returns tempo, time signature, track count, playback and recording
    state, and total song length.
    """
    result = await _send_session_command(ctx, "session.get_info")
    return SessionInfo.model_validate(result)


@mcp.tool()
async def set_tempo(
    ctx: Context,
    tempo: float = Field(description="Tempo in BPM (20–999)", ge=20.0, le=999.0),
) -> TempoResult:
    """Set the song tempo. Tempo must be between 20 and 999 BPM."""
    result = await _send_session_command(
        ctx,
        "session.set_tempo",
        {"tempo": tempo},
    )
    return TempoResult.model_validate(result)


@mcp.tool()
async def set_time_signature(
    ctx: Context,
    numerator: int = Field(description="Time signature numerator (1–32)", ge=1, le=32),
    denominator: Literal[1, 2, 4, 8, 16, 32] = Field(
        description="Time signature denominator (power of 2)",
    ),
) -> TimeSignatureResult:
    """Set the song time signature.

    Denominator must be a power of 2 (1, 2, 4, 8, 16, or 32).
    """
    result = await _send_session_command(
        ctx,
        "session.set_time_signature",
        {"numerator": numerator, "denominator": denominator},
    )
    return TimeSignatureResult.model_validate(result)


@mcp.tool()
async def start_playback(ctx: Context) -> TransportResult:
    """Start transport playback in Ableton Live."""
    result = await _send_session_command(ctx, "session.start_playback")
    return TransportResult.model_validate(result)


@mcp.tool()
async def stop_playback(ctx: Context) -> TransportResult:
    """Stop transport playback in Ableton Live."""
    result = await _send_session_command(ctx, "session.stop_playback")
    return TransportResult.model_validate(result)


@mcp.tool()
async def start_recording(ctx: Context) -> RecordingResult:
    """Start arrangement recording in Ableton Live."""
    result = await _send_session_command(ctx, "session.start_recording")
    return RecordingResult.model_validate(result)


@mcp.tool()
async def stop_recording(ctx: Context) -> RecordingResult:
    """Stop arrangement recording in Ableton Live."""
    result = await _send_session_command(ctx, "session.stop_recording")
    return RecordingResult.model_validate(result)


@mcp.tool()
async def undo(ctx: Context) -> UndoRedoResult:
    """Undo the last action in Ableton Live."""
    result = await _send_session_command(ctx, "session.undo")
    return UndoRedoResult.model_validate(result)


@mcp.tool()
async def redo(ctx: Context) -> UndoRedoResult:
    """Redo the last undone action in Ableton Live."""
    result = await _send_session_command(ctx, "session.redo")
    return UndoRedoResult.model_validate(result)


@mcp.tool()
async def capture_midi(
    ctx: Context,
    destination: Annotated[
        Literal["auto", "session", "arrangement"],
        Field(
            description=(
                "Capture destination: auto chooses Live's default behavior, "
                "session targets Session View, arrangement targets Arrangement View."
            ),
        ),
    ] = "auto",
) -> MidiCaptureResult:
    """Capture recently played MIDI into Ableton Live."""
    result = await _send_session_command(
        ctx,
        "session.capture_midi",
        {"destination": destination},
    )
    return MidiCaptureResult.model_validate(result)


@mcp.tool()
async def set_overdub(
    ctx: Context,
    overdub: Annotated[
        bool,
        Field(
            description="Whether overdub is enabled for arrangement MIDI recording.",
            strict=True,
        ),
    ],
) -> OverdubResult:
    """Set the song overdub state."""
    result = await _send_session_command(
        ctx,
        "session.set_overdub",
        {"overdub": overdub},
    )
    return OverdubResult.model_validate(result)


@mcp.tool()
async def get_playback_position(ctx: Context) -> PlaybackPosition:
    """Get the current playback position.

    Returns the position in beats, bar number, beat within the current
    bar, elapsed time in seconds, and whether playback is active.
    """
    result = await _send_session_command(ctx, "session.get_playback_position")
    return PlaybackPosition.model_validate(result)


__all__ = [
    "MidiCaptureResult",
    "OverdubResult",
    "PlaybackPosition",
    "RecordingResult",
    "SessionInfo",
    "TempoResult",
    "TimeSignatureResult",
    "TransportResult",
    "UndoRedoResult",
    "capture_midi",
    "get_playback_position",
    "get_session_info",
    "redo",
    "set_overdub",
    "set_tempo",
    "set_time_signature",
    "start_recording",
    "start_playback",
    "stop_recording",
    "stop_playback",
    "undo",
]
