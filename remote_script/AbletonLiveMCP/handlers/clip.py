"""Clip command handlers for session-view clip slots and MIDI notes.

``track_index`` and ``clip_slot_index`` are **1-based**, matching other tools.
LOM uses 0-based indices on ``song.tracks`` and ``track.clip_slots``.
"""

from __future__ import annotations

import math
from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler
from .note_mixin import NoteMixin

AUTOMATION_POINT_KEYS = frozenset({"time", "value", "step_length"})


class ClipHandler(NoteMixin, BaseHandler):
    """Handle session clip slot commands."""

    def _require_index(self, params: dict[str, Any], name: str) -> int:
        """Return a validated 1-based index parameter."""
        raw_value = params.get(name)
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise InvalidParamsError(f"'{name}' must be an integer")
        if raw_value < 1:
            raise InvalidParamsError(f"'{name}' must be at least 1")
        return raw_value

    def _resolve_track(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        """Return ``(track, track_index_1based, lo_track)`` or raise."""
        raw = self._require_index(params, "track_index")

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
        raw_slot = self._require_index(params, "clip_slot_index")

        slots = track.clip_slots
        ns = len(slots)
        if raw_slot > ns:
            raise NotFoundError(
                f"Clip slot {raw_slot} does not exist "
                f"(track {track_index} has {ns} slot(s))"
            )
        lo = raw_slot - 1
        return track, slots[lo], track_index, raw_slot, lo

    def _resolve_existing_clip(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, Any, int, int]:
        """Return ``(track, clip, track_index_1based, clip_slot_index_1based)``."""
        track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(params)
        if not slot.has_clip:
            raise NotFoundError(f"No clip in slot {slot_index} on track {track_index}")
        return track, slot.clip, track_index, slot_index

    def _resolve_midi_clip(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        """Return ``(clip, track_index_1based, clip_slot_index_1based)`` or raise."""
        _track, clip, track_index, slot_index = self._resolve_existing_clip(params)
        if not bool(clip.is_midi_clip):
            raise InvalidParamsError(
                f"Clip slot {slot_index} on track {track_index} is not a MIDI clip"
            )

        return clip, track_index, slot_index

    def _resolve_audio_clip(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        """Return ``(clip, track_index_1based, clip_slot_index_1based)`` or raise."""
        _track, clip, track_index, slot_index = self._resolve_existing_clip(params)
        if not bool(clip.is_audio_clip):
            raise InvalidParamsError(
                f"Clip slot {slot_index} on track {track_index} is not an audio clip"
            )

        return clip, track_index, slot_index

    def _resolve_device(
        self,
        track: Any,
        track_index: int,
        device_index: int,
    ) -> Any:
        """Resolve a 1-based device index on a track."""
        devices = list(track.devices)
        device_count = len(devices)
        if device_index > device_count:
            raise NotFoundError(
                f"Device {device_index} does not exist on track {track_index} "
                f"(track has {device_count} device(s))"
            )
        return devices[device_index - 1]

    def _resolve_parameter(
        self,
        device: Any,
        track_index: int,
        device_index: int,
        parameter_index: int,
    ) -> Any:
        """Resolve a 1-based parameter index on a device."""
        parameters = list(device.parameters)
        parameter_count = len(parameters)
        if parameter_index > parameter_count:
            raise NotFoundError(
                f"Parameter {parameter_index} does not exist on device {device_index} "
                f"of track {track_index} (device has {parameter_count} parameter(s))"
            )
        return parameters[parameter_index - 1]

    def _resolve_clip_automation_target(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, Any, Any, int, int, int, int]:
        """Resolve clip, device, and parameter for clip automation commands."""
        track, clip, track_index, slot_index = self._resolve_existing_clip(params)
        device_index = self._require_index(params, "device_index")
        parameter_index = self._require_index(params, "parameter_index")
        device = self._resolve_device(track, track_index, device_index)
        parameter = self._resolve_parameter(
            device,
            track_index,
            device_index,
            parameter_index,
        )
        return (
            clip,
            device,
            parameter,
            track_index,
            slot_index,
            device_index,
            parameter_index,
        )

    def _normalize_automation_points(
        self,
        params: dict[str, Any],
        *,
        minimum_value: float | None = None,
        maximum_value: float | None = None,
    ) -> list[dict[str, float]]:
        """Validate clip automation points received over TCP."""
        raw_points = params.get("points")
        if raw_points is None:
            raise InvalidParamsError("'points' parameter is required")
        if not isinstance(raw_points, list):
            raise InvalidParamsError("'points' must be a list")
        if not raw_points:
            raise InvalidParamsError("'points' must contain at least one point")

        normalized: list[dict[str, float]] = []
        for index, point in enumerate(raw_points, start=1):
            label = f"'points[{index}]'"
            if not isinstance(point, dict):
                raise InvalidParamsError(f"{label} must be an object")

            unknown_keys = set(point) - AUTOMATION_POINT_KEYS
            if unknown_keys:
                keys = ", ".join(sorted(unknown_keys))
                raise InvalidParamsError(f"{label} has unexpected keys: {keys}")

            time = self._require_number(
                point,
                "time",
                label=label,
                minimum=0.0,
            )
            value = self._require_number(
                point,
                "value",
                label=label,
                minimum=minimum_value,
                maximum=maximum_value,
            )
            step_length = self._require_optional_number(
                point.get("step_length", 0.0),
                name="step_length",
                label=label,
                minimum=0.0,
            )

            normalized.append(
                {
                    "time": time,
                    "value": value,
                    "step_length": step_length,
                }
            )

        return normalized

    def _get_clip_gain_display_string(self, clip: Any) -> str:
        """Return Live's gain display string when the runtime exposes it."""
        display = getattr(clip, "gain_display_string", None)
        if display is None:
            return str(getattr(clip, "gain", ""))
        return str(display)

    def _get_available_warp_modes(self, clip: Any) -> tuple[int, ...] | None:
        """Return runtime-supported warp modes if the clip exposes them."""
        raw_modes = getattr(clip, "available_warp_modes", None)
        if raw_modes is None:
            return None

        try:
            return tuple(int(mode) for mode in raw_modes)
        except TypeError:
            return None

    def _clip_automation_envelope(self, clip: Any, parameter: Any) -> Any | None:
        """Return the envelope for a clip/parameter pair if the runtime exposes it."""
        get_envelope = getattr(clip, "automation_envelope", None)
        if callable(get_envelope):
            envelope = get_envelope(parameter)
            if envelope is not None:
                return envelope
        return None

    def _create_clip_automation_envelope(self, clip: Any, parameter: Any) -> Any | None:
        """Create and return the envelope for a clip/parameter pair."""
        envelope = self._clip_automation_envelope(clip, parameter)
        if envelope is not None:
            return envelope

        create_envelope = getattr(clip, "create_automation_envelope", None)
        if not callable(create_envelope):
            raise RuntimeError(
                "This Ableton Live runtime does not expose clip automation envelopes"
            )

        created = create_envelope(parameter)
        if created is not None:
            return created

        return self._clip_automation_envelope(clip, parameter)

    def _serialize_automation_point(self, point: Any) -> dict[str, float] | None:
        """Return the canonical outbound automation point representation."""
        if isinstance(point, dict):
            raw_value = point.get("value")
            if raw_value is None:
                return None
            time = float(point["time"])
            value = float(raw_value)
            step_length = float(point.get("step_length", 0.0))
        else:
            raw_value = getattr(point, "value", None)
            if raw_value is None:
                return None
            time = float(point.time)
            value = float(raw_value)
            step_length = float(getattr(point, "step_length", 0.0))
        components = (time, value, step_length)
        if not all(math.isfinite(component) for component in components):
            return None

        return {
            "time": time,
            "value": value,
            "step_length": step_length,
        }

    def _get_clip_automation_points(
        self,
        clip: Any,
        parameter: Any,
    ) -> list[dict[str, float]]:
        """Read automation events for one clip envelope using the runtime API."""
        envelope = self._clip_automation_envelope(clip, parameter)
        if envelope is None:
            return []

        events_in_range = getattr(envelope, "events_in_range", None)
        if not callable(events_in_range):
            raise RuntimeError(
                "Clip automation envelopes exist, but this Ableton Live runtime "
                "does not expose readable envelope events"
            )

        loop_start = float(getattr(clip, "loop_start", 0.0))
        loop_end = float(getattr(clip, "loop_end", getattr(clip, "length", 0.0)))
        clip_length = float(getattr(clip, "length", 0.0))
        ranges = [
            (loop_start, loop_end),
            (loop_start, max(0.0, loop_end - loop_start)),
            (0.0, clip_length),
        ]

        errors: list[str] = []
        for start, second_arg in ranges:
            try:
                raw_events = events_in_range(start, second_arg)
                points: list[dict[str, float]] = []
                for event in list(raw_events):
                    serialized = self._serialize_automation_point(event)
                    if serialized is not None:
                        points.append(serialized)
                return points
            except Exception as exc:
                errors.append(f"events_in_range({start}, {second_arg}) failed: {exc}")

        raise RuntimeError(
            "Clip automation envelopes are present, but envelope events could not "
            f"be read on this runtime ({'; '.join(errors)})"
        )

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

    def handle_import_audio(self, params: dict[str, Any]) -> dict[str, Any]:
        """Import an audio file into an empty session slot on an audio track."""
        file_path = self._require_absolute_file_path(params, "file_path")
        self._require_existing_file(file_path)

        def _do() -> dict[str, Any]:
            track, slot, track_index, slot_index, _lo = self._resolve_clip_slot(
                params,
            )
            if slot.has_clip:
                raise InvalidParamsError(
                    f"Clip slot {slot_index} on track {track_index} already has a clip"
                )
            if not bool(track.has_audio_input):
                raise InvalidParamsError(
                    f"Track {track_index} does not accept audio clips"
                )

            try:
                slot.create_audio_clip(file_path)
            except Exception as exc:
                raise InvalidParamsError(
                    "Failed to import audio into session clip slot "
                    f"{slot_index} on track {track_index}: {exc}"
                ) from exc

            if not slot.has_clip:
                raise RuntimeError(
                    "Audio import completed but no clip appeared in the target slot"
                )

            clip = slot.clip
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "name": str(clip.name),
                "file_path": file_path,
                "length": float(clip.length),
                "is_audio_clip": bool(clip.is_audio_clip),
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

    def handle_get_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all MIDI notes in the given clip."""

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_midi_clip(params)
            notes = [self._serialize_note(note) for note in self._get_clip_notes(clip)]
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "notes": notes,
            }

        return self._run_on_main_thread(_do)

    def handle_set_loop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set loop start/end and looping state for an existing session clip."""
        loop_start = self._require_optional_number(
            params.get("loop_start"),
            name="loop_start",
            label="params",
            minimum=0.0,
        )
        loop_end = self._require_optional_number(
            params.get("loop_end"),
            name="loop_end",
            label="params",
            minimum=0.0,
        )
        if loop_end <= loop_start:
            raise InvalidParamsError("'loop_end' must be greater than 'loop_start'")

        looping = params.get("looping", True)
        if not isinstance(looping, bool):
            raise InvalidParamsError("'looping' must be a boolean")

        def _do() -> dict[str, Any]:
            _track, clip, track_index, slot_index = self._resolve_existing_clip(params)
            try:
                clip.loop_start = loop_start
                clip.loop_end = loop_end
                clip.looping = looping
            except Exception as exc:
                raise InvalidParamsError(
                    f"Failed to set clip loop settings: {exc}"
                ) from exc

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "loop_start": float(clip.loop_start),
                "loop_end": float(clip.loop_end),
                "looping": bool(clip.looping),
            }

        return self._run_on_main_thread(_do)

    def handle_set_color(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the color index for an existing session clip."""
        color_index = params.get("color_index")
        if color_index is None:
            raise InvalidParamsError("'color_index' parameter is required")
        if isinstance(color_index, bool) or not isinstance(color_index, int):
            raise InvalidParamsError("'color_index' must be an integer")
        if color_index < 0:
            raise InvalidParamsError("'color_index' must be at least 0")

        def _do() -> dict[str, Any]:
            _track, clip, track_index, slot_index = self._resolve_existing_clip(params)
            clip.color_index = color_index
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "color_index": int(clip.color_index),
            }

        return self._run_on_main_thread(_do)

    def handle_set_gain(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set normalized gain for an existing session audio clip."""
        gain = self._require_number(
            params,
            "gain",
            label="params",
            minimum=0.0,
            maximum=1.0,
        )

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_audio_clip(params)
            try:
                clip.gain = gain
            except Exception as exc:
                raise InvalidParamsError(f"Failed to set clip gain: {exc}") from exc

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "gain": float(clip.gain),
                "gain_display_string": self._get_clip_gain_display_string(clip),
            }

        return self._run_on_main_thread(_do)

    def handle_set_pitch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set coarse transpose in semitones for an existing session audio clip."""
        semitones = self._require_int(
            params,
            "semitones",
            label="params",
            minimum=-48,
            maximum=48,
        )

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_audio_clip(params)
            try:
                clip.pitch_coarse = semitones
            except Exception as exc:
                raise InvalidParamsError(f"Failed to set clip pitch: {exc}") from exc

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "semitones": int(clip.pitch_coarse),
            }

        return self._run_on_main_thread(_do)

    def handle_set_warp_mode(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the warp mode for an existing session audio clip."""
        warp_mode = self._require_int(
            params,
            "warp_mode",
            label="params",
            minimum=0,
        )

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_audio_clip(params)
            try:
                if hasattr(clip, "warping") and not bool(clip.warping):
                    clip.warping = True

                available_warp_modes = self._get_available_warp_modes(clip)
                if (
                    available_warp_modes is not None
                    and warp_mode not in available_warp_modes
                ):
                    raise InvalidParamsError(
                        f"Warp mode {warp_mode} is not available for clip slot "
                        f"{slot_index} on track {track_index}; available modes: "
                        f"{list(available_warp_modes)}"
                    )

                clip.warp_mode = warp_mode
            except InvalidParamsError:
                raise
            except Exception as exc:
                raise InvalidParamsError(
                    f"Failed to set clip warp mode: {exc}"
                ) from exc

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "warp_mode": int(clip.warp_mode),
            }

        return self._run_on_main_thread(_do)

    def handle_get_automation(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return automation points for a clip envelope on one device parameter."""

        def _do() -> dict[str, Any]:
            (
                clip,
                device,
                parameter,
                track_index,
                slot_index,
                device_index,
                parameter_index,
            ) = self._resolve_clip_automation_target(params)
            points = self._get_clip_automation_points(clip, parameter)
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "device_index": device_index,
                "parameter_index": parameter_index,
                "device_name": str(getattr(device, "name", "")),
                "parameter_name": str(getattr(parameter, "name", "")),
                "points": points,
            }

        return self._run_on_main_thread(_do)

    def handle_set_automation(self, params: dict[str, Any]) -> dict[str, Any]:
        """Replace one clip envelope with the supplied automation points."""

        def _do() -> dict[str, Any]:
            (
                clip,
                device,
                parameter,
                track_index,
                slot_index,
                device_index,
                parameter_index,
            ) = self._resolve_clip_automation_target(params)
            points = self._normalize_automation_points(params)

            clear_envelope = getattr(clip, "clear_envelope", None)
            if not callable(clear_envelope):
                raise RuntimeError(
                    "This Ableton Live runtime does not expose clip.clear_envelope"
                )

            try:
                clear_envelope(parameter)
                envelope = self._create_clip_automation_envelope(clip, parameter)
                if envelope is None:
                    raise RuntimeError(
                        "Ableton Live did not return a clip automation envelope"
                    )
                for point in points:
                    envelope.insert_step(
                        point["time"],
                        point["step_length"],
                        point["value"],
                    )
            except InvalidParamsError:
                raise
            except Exception as exc:
                raise InvalidParamsError(
                    f"Failed to set clip automation: {exc}"
                ) from exc

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "device_index": device_index,
                "parameter_index": parameter_index,
                "device_name": str(getattr(device, "name", "")),
                "parameter_name": str(getattr(parameter, "name", "")),
                "point_count": len(points),
            }

        return self._run_on_main_thread(_do)

    def handle_add_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add canonical note dicts to the given MIDI clip."""
        normalized_notes = self._normalize_input_notes(params)

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_midi_clip(params)
            before_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            note_ids = self._write_notes(
                clip,
                normalized_notes,
                log_prefix="AbletonLiveMCP clip.add_notes",
                before_notes=before_notes,
            )
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "added_count": len(note_ids),
                "note_ids": note_ids,
            }

        return self._run_on_main_thread(_do)

    def handle_remove_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove notes by pitch/time region from the given MIDI clip."""
        from_pitch, pitch_span, from_time, time_span = self._get_remove_region(params)

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_midi_clip(params)
            existing_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            notes_to_remove = [
                note
                for note in existing_notes
                if self._note_matches_region(
                    note,
                    from_pitch=from_pitch,
                    pitch_span=pitch_span,
                    from_time=from_time,
                    time_span=time_span,
                )
            ]
            note_ids = self._extract_note_ids(notes_to_remove)
            if note_ids:
                clip.remove_notes_by_id(note_ids)
            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "removed_count": len(note_ids),
            }

        return self._run_on_main_thread(_do)

    def handle_set_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Replace the full MIDI note set in the given clip."""
        normalized_notes = self._normalize_input_notes(params)

        def _do() -> dict[str, Any]:
            clip, track_index, slot_index = self._resolve_midi_clip(params)
            existing_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            existing_note_ids = self._extract_note_ids(existing_notes)
            if existing_note_ids:
                clip.remove_notes_by_id(existing_note_ids)

            added_note_ids: list[int] = []
            if normalized_notes:
                added_note_ids = self._write_notes(
                    clip,
                    normalized_notes,
                    log_prefix="AbletonLiveMCP clip.set_notes",
                )

            return {
                "track_index": track_index,
                "clip_slot_index": slot_index,
                "removed_count": len(existing_note_ids),
                "added_count": len(added_note_ids),
                "note_ids": added_note_ids,
            }

        return self._run_on_main_thread(_do)


__all__ = ["ClipHandler"]
