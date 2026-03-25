"""Track command handlers for the Ableton Live MCP Remote Script.

Handles ``track.*`` commands. ``track_index`` in params is **1-based**;
Live's ``song.tracks`` and ``create_*_track`` insert indices use **0-based**
LOM semantics (``-1`` = append).
"""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class TrackHandler(BaseHandler):
    """Handle track CRUD and property commands."""

    def _resolve_track(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        """Return ``(track, track_index_1based, lo_index)`` or raise."""
        raw = params.get("track_index")
        if raw is None:
            raise InvalidParamsError("'track_index' parameter is required")
        if not isinstance(raw, int):
            raise InvalidParamsError("'track_index' must be an integer")
        if raw < 1:
            raise InvalidParamsError("'track_index' must be at least 1")

        song = self._song
        tracks = song.tracks
        n = len(tracks)
        if raw > n:
            raise NotFoundError(f"Track {raw} does not exist (song has {n} track(s))")
        lo = raw - 1
        return tracks[lo], raw, lo

    def handle_get_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a structured snapshot of one track (read-only)."""
        track, track_index, _lo = self._resolve_track(params)

        device_names = [d.name for d in track.devices]
        clip_slot_has_clip = [bool(slot.has_clip) for slot in track.clip_slots]

        return {
            "name": track.name,
            "track_index": track_index,
            "is_audio_track": bool(track.has_audio_input),
            "is_midi_track": bool(track.has_midi_input),
            "mute": bool(track.mute),
            "solo": bool(track.solo),
            "arm": bool(track.arm),
            "volume": float(track.mixer_device.volume.value),
            "pan": float(track.mixer_device.panning.value),
            "device_names": device_names,
            "clip_slot_has_clip": clip_slot_has_clip,
        }

    def handle_create_midi(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a MIDI track; optional ``name`` applied on the main thread."""
        return self._create_track(params, midi=True)

    def handle_create_audio(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create an audio track; optional ``name`` applied on the main thread."""
        return self._create_track(params, midi=False)

    def _create_track(self, params: dict[str, Any], *, midi: bool) -> dict[str, Any]:
        index = params.get("index", -1)
        if not isinstance(index, int):
            raise InvalidParamsError("'index' must be an integer")
        name = params.get("name")
        if name is not None:
            if not isinstance(name, str):
                raise InvalidParamsError("'name' must be a string")
            if not name.strip():
                raise InvalidParamsError("'name' must not be empty")

        song = self._song

        def _do_create() -> dict[str, Any]:
            track_count = len(song.tracks)
            if index < -1 or (index != -1 and (index < 0 or index > track_count - 1)):
                raise InvalidParamsError(
                    f"'index' must be -1 (append) or 0..{track_count - 1}, got {index}"
                )
            if midi:
                song.create_midi_track(index)
            else:
                song.create_audio_track(index)
            new_count = len(song.tracks)
            lo_new = new_count - 1 if index == -1 else index
            new_track = song.tracks[lo_new]
            if name is not None:
                new_track.name = name
            return {
                "track_index": lo_new + 1,
                "name": new_track.name if name is not None else None,
            }

        return self._run_on_main_thread(_do_create)

    def handle_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete a track by 1-based index."""
        _track, track_index, lo = self._resolve_track(params)

        def _do_delete() -> dict[str, Any]:
            self._song.delete_track(lo)
            return {"track_index": track_index}

        return self._run_on_main_thread(_do_delete)

    def handle_duplicate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Duplicate a track; copy is inserted immediately after the source."""
        _track, track_index, lo = self._resolve_track(params)

        def _do_duplicate() -> dict[str, Any]:
            self._song.duplicate_track(lo)
            new_lo = lo + 1
            return {
                "source_track_index": track_index,
                "new_track_index": new_lo + 1,
            }

        return self._run_on_main_thread(_do_duplicate)

    def handle_set_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename a track."""
        _track, track_index, lo = self._resolve_track(params)
        name = params.get("name")
        if name is None or not isinstance(name, str) or not name.strip():
            raise InvalidParamsError("'name' must be a non-empty string")

        def _set() -> dict[str, Any]:
            self._song.tracks[lo].name = name
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_mute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set track mute."""
        _track, track_index, lo = self._resolve_track(params)
        mute = params.get("mute")
        if mute is None or not isinstance(mute, bool):
            raise InvalidParamsError("'mute' must be a boolean")

        def _set() -> dict[str, Any]:
            self._song.tracks[lo].mute = mute
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_solo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set track solo."""
        _track, track_index, lo = self._resolve_track(params)
        solo = params.get("solo")
        if solo is None or not isinstance(solo, bool):
            raise InvalidParamsError("'solo' must be a boolean")

        def _set() -> dict[str, Any]:
            self._song.tracks[lo].solo = solo
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_arm(self, params: dict[str, Any]) -> dict[str, Any]:
        """Arm or disarm a track for recording."""
        track, track_index, lo = self._resolve_track(params)
        arm = params.get("arm")
        if arm is None or not isinstance(arm, bool):
            raise InvalidParamsError("'arm' must be a boolean")
        if not bool(track.can_be_armed):
            raise InvalidParamsError(
                f"Track {track_index} cannot be armed (e.g. return/master)"
            )

        def _set() -> dict[str, Any]:
            self._song.tracks[lo].arm = arm
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)


__all__ = ["TrackHandler"]
