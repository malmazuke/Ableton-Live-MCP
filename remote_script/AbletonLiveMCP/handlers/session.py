"""Session, transport, and recording command handlers for the Remote Script.

Handles ``session.*`` commands for song info, transport control, recording,
and playback position.
"""

import time
from typing import Any

from ..dispatcher import InvalidParamsError
from .base import BaseHandler

VALID_DENOMINATORS = frozenset({1, 2, 4, 8, 16, 32})
STATE_POLL_ATTEMPTS = 40
STATE_POLL_INTERVAL_SECONDS = 0.05
CAPTURE_MIDI_DESTINATIONS = {
    "auto": 0,
    "session": 1,
    "arrangement": 2,
}


class SessionHandler(BaseHandler):
    """Handle session and transport commands.

    All Live Object Model access runs on Ableton's main thread via
    ``_run_on_main_thread``.  Calling ``control_surface.song()`` or touching
    ``song.*`` from the TCP worker thread is unsafe and can crash or error
    (especially around project load).
    """

    def _read_recording_state(self) -> dict[str, Any]:
        """Read current arrangement recording and transport state."""

        def _read() -> dict[str, Any]:
            song = self._song
            return {
                "is_recording": song.record_mode,
                "is_playing": song.is_playing,
            }

        return self._run_on_main_thread(_read)

    def _wait_for_recording_state(
        self,
        *,
        action: str,
        expected_recording: bool,
        expected_playing: bool | None = None,
    ) -> dict[str, Any]:
        """Poll Live until recording state reflects the requested change."""
        last_state = self._read_recording_state()
        for _ in range(STATE_POLL_ATTEMPTS):
            last_state = self._read_recording_state()
            recording_matches = last_state["is_recording"] is expected_recording
            playing_matches = (
                expected_playing is None or last_state["is_playing"] is expected_playing
            )
            if recording_matches and playing_matches:
                return {"action": action, **last_state}
            time.sleep(STATE_POLL_INTERVAL_SECONDS)

        raise RuntimeError(
            "Timed out waiting for recording state update: "
            f"action={action}, expected_recording={expected_recording}, "
            f"expected_playing={expected_playing}, actual={last_state}"
        )

    def _wait_for_overdub_state(self, expected_overdub: bool) -> dict[str, Any]:
        """Poll Live until overdub reflects the requested change."""

        def _read() -> bool:
            return self._song.overdub

        last_state = self._run_on_main_thread(_read)
        for _ in range(STATE_POLL_ATTEMPTS):
            last_state = self._run_on_main_thread(_read)
            if last_state is expected_overdub:
                return {"overdub": last_state}
            time.sleep(STATE_POLL_INTERVAL_SECONDS)

        raise RuntimeError(
            "Timed out waiting for overdub state update: "
            f"expected={expected_overdub}, actual={last_state}"
        )

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

    def handle_start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Start arrangement recording and ensure transport is running."""

        def _start() -> None:
            song = self._song
            song.record_mode = True
            if not song.is_playing:
                song.start_playing()

        self._run_on_main_thread(_start)
        return self._wait_for_recording_state(
            action="start_recording",
            expected_recording=True,
            expected_playing=True,
        )

    def handle_stop_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stop arrangement recording without forcing transport stop."""

        def _stop() -> None:
            song = self._song
            song.record_mode = False

        self._run_on_main_thread(_stop)
        return self._wait_for_recording_state(
            action="stop_recording",
            expected_recording=False,
        )

    def handle_set_overdub(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set MIDI arrangement overdub state."""
        if "overdub" not in params:
            raise InvalidParamsError("'overdub' parameter is required")

        overdub = params["overdub"]
        if not isinstance(overdub, bool):
            raise InvalidParamsError("'overdub' must be a boolean")

        def _set() -> None:
            self._song.overdub = overdub

        self._run_on_main_thread(_set)
        return self._wait_for_overdub_state(overdub)

    def handle_capture_midi(self, params: dict[str, Any]) -> dict[str, Any]:
        """Capture recently played MIDI into Live."""
        destination = params.get("destination", "auto")
        if not isinstance(destination, str):
            raise InvalidParamsError("'destination' must be a string")

        destination_value = CAPTURE_MIDI_DESTINATIONS.get(destination)
        if destination_value is None:
            raise InvalidParamsError(
                "'destination' must be one of: auto, session, arrangement"
            )

        def _capture() -> dict[str, Any]:
            song = self._song
            if not song.can_capture_midi:
                raise InvalidParamsError("No MIDI available to capture")
            song.capture_midi(destination_value)
            return {"destination": destination, "captured": True}

        return self._run_on_main_thread(_capture)

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
