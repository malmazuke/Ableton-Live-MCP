"""MCP tools for session and transport control.

Provides tools for querying and controlling Ableton Live's session state:
tempo, time signature, transport (play/stop), and playback position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

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


@mcp.tool()
async def get_session_info(ctx: Context) -> SessionInfo:
    """Get current session information.

    Returns tempo, time signature, track count, playback and recording
    state, and total song length.
    """
    connection = _get_connection(ctx)
    request = CommandRequest(command="session.get_info")
    response = await connection.send_command(request)
    response.raise_on_error()
    return SessionInfo.model_validate(response.result)


@mcp.tool()
async def set_tempo(
    ctx: Context,
    tempo: float = Field(description="Tempo in BPM (20–999)", ge=20.0, le=999.0),
) -> TempoResult:
    """Set the song tempo. Tempo must be between 20 and 999 BPM."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="session.set_tempo",
        params={"tempo": tempo},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TempoResult.model_validate(response.result)


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
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="session.set_time_signature",
        params={"numerator": numerator, "denominator": denominator},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return TimeSignatureResult.model_validate(response.result)


@mcp.tool()
async def start_playback(ctx: Context) -> TransportResult:
    """Start transport playback in Ableton Live."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="session.start_playback")
    response = await connection.send_command(request)
    response.raise_on_error()
    return TransportResult.model_validate(response.result)


@mcp.tool()
async def stop_playback(ctx: Context) -> TransportResult:
    """Stop transport playback in Ableton Live."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="session.stop_playback")
    response = await connection.send_command(request)
    response.raise_on_error()
    return TransportResult.model_validate(response.result)


@mcp.tool()
async def get_playback_position(ctx: Context) -> PlaybackPosition:
    """Get the current playback position.

    Returns the position in beats, bar number, beat within the current
    bar, elapsed time in seconds, and whether playback is active.
    """
    connection = _get_connection(ctx)
    request = CommandRequest(command="session.get_playback_position")
    response = await connection.send_command(request)
    response.raise_on_error()
    return PlaybackPosition.model_validate(response.result)


__all__ = [
    "PlaybackPosition",
    "SessionInfo",
    "TempoResult",
    "TimeSignatureResult",
    "TransportResult",
    "get_playback_position",
    "get_session_info",
    "set_tempo",
    "set_time_signature",
    "start_playback",
    "stop_playback",
]
