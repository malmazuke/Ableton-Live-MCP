"""Mixin providing shared MIDI note logic for clip handlers.

Both session-view ``ClipHandler`` and ``ArrangementHandler`` inherit from
this mixin to reuse note reading, writing, serialization, and validation.

This module runs inside Ableton's embedded Python runtime — only standard
library and ``_Framework`` modules are available.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..dispatcher import InvalidParamsError

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


class NoteMixin:
    """Reusable note helpers shared by session and arrangement clip handlers.

    Requires the host class to provide ``_log(message)`` (from ``BaseHandler``).
    """

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


__all__ = ["NoteMixin", "NOTE_INPUT_KEYS"]
