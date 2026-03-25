"""Clip command handlers for session-view clip slots (per track).

``track_index`` and ``clip_slot_index`` are **1-based**, matching other tools.
LOM uses 0-based indices on ``song.tracks`` and ``track.clip_slots``.
"""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class ClipHandler(BaseHandler):
    """Handle session clip slot commands."""

    def _resolve_track(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        """Return ``(track, track_index_1based, lo_track)`` or raise."""
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

    def _resolve_clip_slot(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, Any, int, int, int]:
        """Return ``(track, clip_slot, track_index_1, clip_slot_index_1, lo_slot)``."""
        track, track_index, _lo_track = self._resolve_track(params)
        raw_slot = params.get("clip_slot_index")
        if raw_slot is None:
            raise InvalidParamsError("'clip_slot_index' parameter is required")
        if not isinstance(raw_slot, int):
            raise InvalidParamsError("'clip_slot_index' must be an integer")
        if raw_slot < 1:
            raise InvalidParamsError("'clip_slot_index' must be at least 1")

        slots = track.clip_slots
        ns = len(slots)
        if raw_slot > ns:
            raise NotFoundError(
                f"Clip slot {raw_slot} does not exist "
                f"(track {track_index} has {ns} slot(s))"
            )
        lo = raw_slot - 1
        return track, slots[lo], track_index, raw_slot, lo

    def handle_create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create an empty MIDI clip in an empty slot (``length`` in beats)."""
        length = params.get("length", 4.0)
        if isinstance(length, bool) or not isinstance(length, (int, float)):
            raise InvalidParamsError("'length' must be a number")
        if float(length) <= 0:
            raise InvalidParamsError("'length' must be positive")

        def _do() -> dict[str, Any]:
            track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            if slot.has_clip:
                raise InvalidParamsError(
                    f"Clip slot {slot_index} on track {track_index} already has a clip"
                )
            if not bool(track.has_midi_input):
                raise InvalidParamsError(
                    "create_clip only applies to MIDI tracks (session MIDI slots)"
                )
            slot.create_clip(float(length))
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "length": float(length),
            }

        return self._run_on_main_thread(_do)

    def handle_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove the clip in the given slot."""

        def _do() -> dict[str, Any]:
            _track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            if not slot.has_clip:
                raise InvalidParamsError(
                    f"No clip in slot {slot_index} on track {track_index}"
                )
            slot.delete_clip()
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
            }

        return self._run_on_main_thread(_do)

    def handle_duplicate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Duplicate the clip in this slot (same semantics as Live's slot duplicate)."""

        def _do() -> dict[str, Any]:
            track, _slot, track_index, slot_index, lo = self._resolve_clip_slot(
                params,
            )
            if not track.clip_slots[lo].has_clip:
                raise InvalidParamsError(
                    f"No clip in slot {slot_index} on track {track_index}"
                )
            before = [bool(s.has_clip) for s in track.clip_slots]
            track.duplicate_clip_slot(lo)
            after = [bool(s.has_clip) for s in track.clip_slots]
            new_1based: int | None = None
            for i in range(len(after)):
                if after[i] and not before[i]:
                    new_1based = i + 1
                    break
            return {
                "track_index": track_index,
                "source_clip_slot_index": slot_index,
                "new_clip_slot_index": new_1based,
            }

        return self._run_on_main_thread(_do)

    def handle_set_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename the clip in the given slot."""
        name = params.get("name")
        if name is None or not isinstance(name, str) or not name.strip():
            raise InvalidParamsError("'name' must be a non-empty string")

        def _do() -> dict[str, Any]:
            _track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            if not slot.has_clip:
                raise InvalidParamsError(
                    f"No clip in slot {slot_index} on track {track_index}"
                )
            slot.clip.name = name
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "name": name,
            }

        return self._run_on_main_thread(_do)

    def handle_fire(self, params: dict[str, Any]) -> dict[str, Any]:
        """Launch the clip or trigger the slot's stop / record behavior."""

        def _do() -> dict[str, Any]:
            _track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            slot.fire()
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
            }

        return self._run_on_main_thread(_do)

    def handle_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stop playback or recording for this track's slot column."""

        def _do() -> dict[str, Any]:
            _track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            slot.stop()
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
            }

        return self._run_on_main_thread(_do)

    def handle_get_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return metadata for the clip in the given slot."""

        def _do() -> dict[str, Any]:
            _track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            if not slot.has_clip:
                raise NotFoundError(
                    f"No clip in slot {slot_index} on track {track_index}"
                )
            clip = slot.clip
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "name": clip.name,
                "length": float(clip.length),
                "is_audio_clip": bool(clip.is_audio_clip),
                "is_midi_clip": bool(clip.is_midi_clip),
                "is_playing": bool(clip.is_playing),
                "is_recording": bool(clip.is_recording),
            }

        return self._run_on_main_thread(_do)


__all__ = ["ClipHandler"]
