"""Session and transport command handlers for the Ableton Live MCP Remote Script.

Handles ``session.*`` commands: get_info, set_tempo, set_time_signature,
start_playback, stop_playback, get_playback_position.
"""

from typing import Any

from ..dispatcher import InvalidParamsError
from .base import BaseHandler

VALID_DENOMINATORS = frozenset({1, 2, 4, 8, 16, 32})


class SessionHandler(BaseHandler):
    """Handle session and transport commands.

    All Live Object Model access runs on Ableton's main thread via
    ``_run_on_main_thread``.  Calling ``control_surface.song()`` or touching
    ``song.*`` from the TCP worker thread is unsafe and can crash or error
    (especially around project load).
    """

    def handle_get_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return current session state."""

        def _read() -> dict[str, Any]:
            song = self._song
            return {
                "tempo": song.tempo,
                "signature_numerator": song.signature_numerator,
                "signature_denominator": song.signature_denominator,
                "track_count": len(song.tracks),
                "is_playing": song.is_playing,
                "is_recording": song.record_mode,
                "song_length": song.song_length,
            }

        return self._run_on_main_thread(_read)

    def handle_set_tempo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the song tempo in BPM (20--999)."""
        tempo = params.get("tempo")
        if tempo is None:
            raise InvalidParamsError("'tempo' parameter is required")
        if not isinstance(tempo, (int, float)):
            raise InvalidParamsError("'tempo' must be a number")
        if not (20.0 <= float(tempo) <= 999.0):
            raise InvalidParamsError(
                f"Tempo must be between 20 and 999 BPM, got {tempo}"
            )

        tempo_val = float(tempo)

        def _set() -> None:
            self._song.tempo = tempo_val

        self._run_on_main_thread(_set)
        return {"tempo": tempo_val}

    def handle_set_time_signature(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the song time signature (numerator / denominator)."""
        numerator = params.get("numerator")
        denominator = params.get("denominator")

        if numerator is None or denominator is None:
            raise InvalidParamsError(
                "'numerator' and 'denominator' parameters are required"
            )
        if not isinstance(numerator, int) or not isinstance(denominator, int):
            raise InvalidParamsError("'numerator' and 'denominator' must be integers")
        if not (1 <= numerator <= 32):
            raise InvalidParamsError(
                f"Numerator must be between 1 and 32, got {numerator}"
            )
        if denominator not in VALID_DENOMINATORS:
            raise InvalidParamsError(
                "Denominator must be a power of 2 "
                f"(1, 2, 4, 8, 16, 32), got {denominator}"
            )

        def _set() -> None:
            self._song.signature_numerator = numerator
            self._song.signature_denominator = denominator

        self._run_on_main_thread(_set)
        return {"numerator": numerator, "denominator": denominator}

    def handle_start_playback(self, params: dict[str, Any]) -> dict[str, Any]:
        """Start transport playback."""

        def _start() -> None:
            self._song.start_playing()

        self._run_on_main_thread(_start)
        return {"action": "start", "is_playing": True}

    def handle_stop_playback(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stop transport playback."""

        def _stop() -> None:
            self._song.stop_playing()

        self._run_on_main_thread(_stop)
        return {"action": "stop", "is_playing": False}

    def handle_get_playback_position(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return current playback position with derived bar/beat values."""

        def _read() -> dict[str, Any]:
            song = self._song
            current_time = song.current_song_time
            tempo = song.tempo
            numerator = song.signature_numerator

            bar = int(current_time // numerator) + 1
            beat_in_bar = (current_time % numerator) + 1
            time_seconds = current_time * 60.0 / tempo

            return {
                "beats": current_time,
                "bar": bar,
                "beat_in_bar": beat_in_bar,
                "time_seconds": time_seconds,
                "is_playing": song.is_playing,
            }

        return self._run_on_main_thread(_read)


__all__ = ["SessionHandler"]
