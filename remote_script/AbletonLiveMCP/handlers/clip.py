"""Clip command handlers for session-view clip slots and MIDI notes.

``track_index`` and ``clip_slot_index`` are **1-based**, matching other tools.
LOM uses 0-based indices on ``song.tracks`` and ``track.clip_slots``.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler

NOTE_INPUT_KEYS = frozenset(
    {
        "pitch",
        "start_time",
        "duration",
        "velocity",
        "mute",
        "probability",
        "velocity_deviation",
    }
)

AUTOMATION_POINT_KEYS = frozenset({"time", "value", "step_length"})


class ClipHandler(BaseHandler):
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

    def _get_clip_notes(self, clip: Any) -> list[dict[str, Any]]:
        """Read notes from Ableton and normalize the response container shape."""
        try:
            raw_notes = clip.get_all_notes_extended()
        except Exception as exc:
            self._log(
                f"AbletonLiveMCP clip.get_notes get_all_notes_extended failed: {exc}"
            )
            get_notes_extended = getattr(clip, "get_notes_extended", None)
            if not callable(get_notes_extended):
                raise
            raw_notes = get_notes_extended(0, 128, 0.0, float(clip.length))

        notes = raw_notes.get("notes") if isinstance(raw_notes, dict) else raw_notes

        if isinstance(notes, list):
            return notes
        if isinstance(notes, tuple):
            return list(notes)

        try:
            coerced = list(notes)
        except TypeError as exc:
            self._log(
                "AbletonLiveMCP clip.get_notes unsupported payload: "
                f"{type(raw_notes).__name__} / {type(notes).__name__}"
            )
            raise RuntimeError("Clip note API returned an unexpected payload") from exc

        self._log(
            "AbletonLiveMCP clip.get_notes payload: "
            f"raw={type(raw_notes).__name__}, notes={type(notes).__name__}, "
            f"count={len(coerced)}"
        )
        return coerced

    def _serialize_note(self, note: Any) -> dict[str, Any]:
        """Return the canonical outbound note representation."""
        if isinstance(note, dict):
            note_id = int(note["note_id"])
            pitch = int(note["pitch"])
            start_time = float(note["start_time"])
            duration = float(note["duration"])
            velocity = float(note["velocity"])
            mute = bool(note.get("mute", False))
            probability = note.get("probability")
            velocity_deviation = note.get("velocity_deviation")
        else:
            note_id = int(note.note_id)
            pitch = int(note.pitch)
            start_time = float(note.start_time)
            duration = float(note.duration)
            velocity = float(note.velocity)
            mute = bool(note.mute) if hasattr(note, "mute") else False
            probability = note.probability if hasattr(note, "probability") else None
            velocity_deviation = (
                note.velocity_deviation if hasattr(note, "velocity_deviation") else None
            )

        result = {
            "note_id": note_id,
            "pitch": pitch,
            "start_time": start_time,
            "duration": duration,
            "velocity": velocity,
            "mute": mute,
        }

        if probability is not None:
            result["probability"] = float(probability)
        if velocity_deviation is not None:
            result["velocity_deviation"] = float(velocity_deviation)

        return result

    def _normalize_input_notes(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate canonical note payloads received over TCP."""
        raw_notes = params.get("notes")
        if raw_notes is None:
            raise InvalidParamsError("'notes' parameter is required")
        if not isinstance(raw_notes, list):
            raise InvalidParamsError("'notes' must be a list")

        normalized: list[dict[str, Any]] = []
        for index, note in enumerate(raw_notes, start=1):
            label = f"'notes[{index}]'"
            if not isinstance(note, dict):
                raise InvalidParamsError(f"{label} must be an object")

            unknown_keys = set(note) - NOTE_INPUT_KEYS
            if unknown_keys:
                keys = ", ".join(sorted(unknown_keys))
                raise InvalidParamsError(f"{label} has unexpected keys: {keys}")

            pitch = self._require_int(
                note,
                "pitch",
                label=label,
                minimum=0,
                maximum=127,
            )
            start_time = self._require_number(
                note,
                "start_time",
                label=label,
                minimum=0.0,
            )
            duration = self._require_number(
                note,
                "duration",
                label=label,
                minimum=0.0,
                exclusive_minimum=True,
            )
            velocity = self._require_number(
                note,
                "velocity",
                label=label,
                minimum=0.0,
                maximum=127.0,
            )

            mute = note.get("mute", False)
            if not isinstance(mute, bool):
                raise InvalidParamsError(f"{label}.mute must be a boolean")

            normalized_note: dict[str, Any] = {
                "pitch": pitch,
                "start_time": start_time,
                "duration": duration,
                "velocity": velocity,
                "mute": mute,
            }

            probability = note.get("probability")
            if probability is not None:
                normalized_note["probability"] = self._require_optional_number(
                    probability,
                    name="probability",
                    label=label,
                    minimum=0.0,
                    maximum=1.0,
                )

            velocity_deviation = note.get("velocity_deviation")
            if velocity_deviation is not None:
                normalized_note["velocity_deviation"] = self._require_optional_number(
                    velocity_deviation,
                    name="velocity_deviation",
                    label=label,
                )

            normalized.append(normalized_note)

        return normalized

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

    def _require_int(
        self,
        note: dict[str, Any],
        key: str,
        *,
        label: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        """Require an integer value in a dict field."""
        value = note.get(key)
        if value is None:
            raise InvalidParamsError(f"{label}.{key} is required")
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidParamsError(f"{label}.{key} must be an integer")
        if minimum is not None and value < minimum:
            raise InvalidParamsError(f"{label}.{key} must be at least {minimum}")
        if maximum is not None and value > maximum:
            raise InvalidParamsError(f"{label}.{key} must be at most {maximum}")
        return value

    def _require_number(
        self,
        note: dict[str, Any],
        key: str,
        *,
        label: str,
        minimum: float | None = None,
        maximum: float | None = None,
        exclusive_minimum: bool = False,
    ) -> float:
        """Require a numeric value in a dict field."""
        value = note.get(key)
        if value is None:
            raise InvalidParamsError(f"{label}.{key} is required")
        return self._require_optional_number(
            value,
            name=key,
            label=label,
            minimum=minimum,
            maximum=maximum,
            exclusive_minimum=exclusive_minimum,
        )

    def _require_optional_number(
        self,
        value: Any,
        *,
        name: str,
        label: str,
        minimum: float | None = None,
        maximum: float | None = None,
        exclusive_minimum: bool = False,
    ) -> float:
        """Validate a numeric scalar and return it as a float."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidParamsError(f"{label}.{name} must be a number")

        float_value = float(value)
        if minimum is not None:
            if exclusive_minimum and float_value <= minimum:
                raise InvalidParamsError(
                    f"{label}.{name} must be greater than {minimum}"
                )
            if not exclusive_minimum and float_value < minimum:
                raise InvalidParamsError(f"{label}.{name} must be at least {minimum}")
        if maximum is not None and float_value > maximum:
            raise InvalidParamsError(f"{label}.{name} must be at most {maximum}")
        return float_value

    def _get_remove_region(
        self,
        params: dict[str, Any],
    ) -> tuple[int, int, float, float | None]:
        """Validate and return note removal region parameters."""
        from_pitch = params.get("from_pitch", 0)
        pitch_span = params.get("pitch_span", 128)
        from_time = params.get("from_time", 0.0)
        time_span = params.get("time_span")

        if isinstance(from_pitch, bool) or not isinstance(from_pitch, int):
            raise InvalidParamsError("'from_pitch' must be an integer")
        if from_pitch < 0 or from_pitch > 127:
            raise InvalidParamsError("'from_pitch' must be between 0 and 127")

        if isinstance(pitch_span, bool) or not isinstance(pitch_span, int):
            raise InvalidParamsError("'pitch_span' must be an integer")
        if pitch_span < 1 or pitch_span > 128:
            raise InvalidParamsError("'pitch_span' must be between 1 and 128")
        if from_pitch + pitch_span > 128:
            raise InvalidParamsError("'from_pitch' + 'pitch_span' must not exceed 128")

        if isinstance(from_time, bool) or not isinstance(from_time, (int, float)):
            raise InvalidParamsError("'from_time' must be a number")
        normalized_from_time = float(from_time)
        if normalized_from_time < 0.0:
            raise InvalidParamsError("'from_time' must be at least 0")

        normalized_time_span: float | None = None
        if time_span is not None:
            if isinstance(time_span, bool) or not isinstance(time_span, (int, float)):
                raise InvalidParamsError("'time_span' must be a number when provided")
            normalized_time_span = float(time_span)
            if normalized_time_span <= 0.0:
                raise InvalidParamsError("'time_span' must be greater than 0")

        return from_pitch, pitch_span, normalized_from_time, normalized_time_span

    def _note_matches_region(
        self,
        note: dict[str, Any],
        *,
        from_pitch: int,
        pitch_span: int,
        from_time: float,
        time_span: float | None,
    ) -> bool:
        """Return ``True`` when a note falls inside the removal region."""
        pitch = int(note["pitch"])
        start_time = float(note["start_time"])

        in_pitch = from_pitch <= pitch < from_pitch + pitch_span
        if not in_pitch:
            return False

        if start_time < from_time:
            return False

        if time_span is None:
            return True

        return start_time < from_time + time_span

    def _extract_note_ids(self, notes: list[dict[str, Any]]) -> list[int]:
        """Return note IDs from a list of note dicts."""
        return [int(note["note_id"]) for note in notes]

    def _coerce_note_ids(self, note_ids: Any) -> list[int] | None:
        """Normalize Ableton's add-note return payload when IDs are provided."""
        if note_ids is None:
            return None
        if isinstance(note_ids, tuple):
            return [int(note_id) for note_id in note_ids]
        if isinstance(note_ids, list):
            return [int(note_id) for note_id in note_ids]
        return None

    def _to_live_note_spec(
        self,
        note: dict[str, Any],
    ) -> tuple[int, float, float, int, bool]:
        """Convert a canonical note dict into Live's note-spec tuple shape."""
        return (
            int(note["pitch"]),
            float(note["start_time"]),
            float(note["duration"]),
            int(round(float(note["velocity"]))),
            bool(note.get("mute", False)),
        )

    def _to_midi_note_specification(self, note: dict[str, Any]) -> Any:
        """Build Live's ``MidiNoteSpecification`` when available."""
        try:
            import Live  # type: ignore
        except ImportError:
            return dict(note)

        return Live.Clip.MidiNoteSpecification(**note)

    def _note_key(self, note: dict[str, Any]) -> tuple[int, float, float, float, bool]:
        """Return a comparable identity tuple for matching notes before/after writes."""
        return (
            int(note["pitch"]),
            float(note["start_time"]),
            float(note["duration"]),
            float(note["velocity"]),
            bool(note["mute"]),
        )

    def _find_added_note_ids(
        self,
        before_notes: list[dict[str, Any]],
        after_notes: list[dict[str, Any]],
    ) -> list[int]:
        """Compute newly added note IDs by multiset-diffing note identities."""
        before_counts = Counter(self._note_key(note) for note in before_notes)
        added_note_ids: list[int] = []
        for note in after_notes:
            key = self._note_key(note)
            if before_counts[key] > 0:
                before_counts[key] -= 1
                continue
            added_note_ids.append(int(note["note_id"]))
        return added_note_ids

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

    def _write_notes(
        self,
        clip: Any,
        normalized_notes: list[dict[str, Any]],
        *,
        log_prefix: str,
        before_notes: list[dict[str, Any]] | None = None,
    ) -> list[int]:
        """Write notes using the first payload shape the runtime accepts."""
        tuple_payload = tuple(
            self._to_midi_note_specification(note) for note in normalized_notes
        )

        try:
            raw_result = clip.add_new_notes(tuple_payload)
        except Exception as exc:
            self._log(f"{log_prefix} add_new_notes(tuple(...)) failed: {exc}")
        else:
            note_ids = self._coerce_note_ids(raw_result)
            if note_ids is not None:
                return note_ids

            self._log(
                f"{log_prefix} add_new_notes(tuple(...)) returned "
                f"{type(raw_result).__name__}; inferring note IDs from clip state"
            )
            after_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            if before_notes is None:
                return self._extract_note_ids(after_notes)
            return self._find_added_note_ids(before_notes, after_notes)

        try:
            raw_result = clip.add_new_notes({"notes": normalized_notes})
            note_ids = self._coerce_note_ids(raw_result)
            if note_ids is not None:
                return note_ids
            self._log(
                f"{log_prefix} add_new_notes({{'notes': ...}}) returned "
                f"{type(raw_result).__name__}; inferring note IDs from clip state"
            )
            after_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            if before_notes is None:
                return self._extract_note_ids(after_notes)
            return self._find_added_note_ids(before_notes, after_notes)
        except Exception as exc:
            self._log(f"{log_prefix} add_new_notes({{'notes': ...}}) failed: {exc}")

        set_notes = getattr(clip, "set_notes", None)
        if not callable(set_notes):
            raise RuntimeError("Clip note API rejected all supported add-note payloads")

        set_notes(tuple(self._to_live_note_spec(note) for note in normalized_notes))
        after_notes = [
            self._serialize_note(note) for note in self._get_clip_notes(clip)
        ]

        if before_notes is None:
            return self._extract_note_ids(after_notes)
        return self._find_added_note_ids(before_notes, after_notes)

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
