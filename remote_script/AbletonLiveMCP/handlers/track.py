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

    def _require_non_empty_string(self, params: dict[str, Any], name: str) -> str:
        """Return a required non-empty string parameter."""
        value = params.get(name)
        if not isinstance(value, str) or not value.strip():
            raise InvalidParamsError(f"'{name}' must be a non-empty string")
        return value

    def _routing_label(self, attribute_name: str) -> str:
        """Return a human-readable label for a routing attribute."""
        return attribute_name.replace("_", " ")

    def _routing_value(self, option: Any, field_name: str) -> str:
        """Read a routing field from either an object or mapping-like value."""
        if hasattr(option, field_name):
            value = getattr(option, field_name)
            if isinstance(value, (str, int)):
                return str(value)

        try:
            value = option[field_name]
        except (KeyError, TypeError, IndexError):
            value = None

        if isinstance(value, (str, int)):
            return str(value)

        if field_name == "identifier":
            return str(hash(option))

        raise InvalidParamsError(f"Routing option is missing '{field_name}'")

    def _serialize_routing_option(self, option: Any) -> dict[str, str]:
        """Normalize a routing option into the MCP response shape."""
        return {
            "identifier": self._routing_value(option, "identifier"),
            "display_name": self._routing_value(option, "display_name"),
        }

    def _read_routing_selection(
        self,
        track: Any,
        attribute_name: str,
        track_index: int,
    ) -> dict[str, str]:
        """Read and normalize a selected routing value from a track."""
        if not hasattr(track, attribute_name):
            raise InvalidParamsError(
                "Track "
                f"{track_index} does not support "
                f"{self._routing_label(attribute_name)}"
            )

        option = getattr(track, attribute_name)
        if option is None:
            raise InvalidParamsError(
                "Track "
                f"{track_index} does not support "
                f"{self._routing_label(attribute_name)}"
            )
        return self._serialize_routing_option(option)

    def _get_routing_collection(
        self,
        track: Any,
        attribute_name: str,
        track_index: int,
    ) -> list[Any]:
        """Read and validate an available routing collection from a track."""
        if not hasattr(track, attribute_name):
            raise InvalidParamsError(
                "Track "
                f"{track_index} does not support "
                f"{self._routing_label(attribute_name)}"
            )

        collection = getattr(track, attribute_name)
        if collection is None:
            raise InvalidParamsError(
                "Track "
                f"{track_index} does not support "
                f"{self._routing_label(attribute_name)}"
            )

        try:
            options = list(collection)
        except TypeError as exc:
            raise InvalidParamsError(
                "Track "
                f"{track_index} does not support "
                f"{self._routing_label(attribute_name)}"
            ) from exc
        if not options:
            raise InvalidParamsError(
                f"Track {track_index} has no {self._routing_label(attribute_name)}"
            )
        return options

    def _find_routing_option(
        self,
        options: list[Any],
        identifier: str,
        option_label: str,
        track_index: int,
    ) -> Any:
        """Resolve a routing option by its exact identifier."""
        for option in options:
            if self._routing_value(option, "identifier") == identifier:
                return option

        raise NotFoundError(
            f"Track {track_index} has no {option_label} with identifier '{identifier}'"
        )

    def handle_get_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a structured snapshot of one track (read-only)."""

        def _read() -> dict[str, Any]:
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

        return self._run_on_main_thread(_read)

    def handle_get_routing(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the current routing selections for one track."""

        def _read() -> dict[str, Any]:
            track, track_index, _lo = self._resolve_track(params)
            return {
                "track_index": track_index,
                "input_routing_type": self._read_routing_selection(
                    track,
                    "input_routing_type",
                    track_index,
                ),
                "input_routing_channel": self._read_routing_selection(
                    track,
                    "input_routing_channel",
                    track_index,
                ),
                "output_routing_type": self._read_routing_selection(
                    track,
                    "output_routing_type",
                    track_index,
                ),
                "output_routing_channel": self._read_routing_selection(
                    track,
                    "output_routing_channel",
                    track_index,
                ),
            }

        return self._run_on_main_thread(_read)

    def handle_get_available_routing(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all available routing choices for one track."""

        def _read() -> dict[str, Any]:
            track, track_index, _lo = self._resolve_track(params)
            return {
                "track_index": track_index,
                "available_input_routing_types": [
                    self._serialize_routing_option(option)
                    for option in self._get_routing_collection(
                        track,
                        "available_input_routing_types",
                        track_index,
                    )
                ],
                "available_input_routing_channels": [
                    self._serialize_routing_option(option)
                    for option in self._get_routing_collection(
                        track,
                        "available_input_routing_channels",
                        track_index,
                    )
                ],
                "available_output_routing_types": [
                    self._serialize_routing_option(option)
                    for option in self._get_routing_collection(
                        track,
                        "available_output_routing_types",
                        track_index,
                    )
                ],
                "available_output_routing_channels": [
                    self._serialize_routing_option(option)
                    for option in self._get_routing_collection(
                        track,
                        "available_output_routing_channels",
                        track_index,
                    )
                ],
            }

        return self._run_on_main_thread(_read)

    def handle_set_input_routing(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set input routing by type/channel identifiers."""
        return self._set_routing(params, direction="input")

    def handle_set_output_routing(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set output routing by type/channel identifiers."""
        return self._set_routing(params, direction="output")

    def _set_routing(self, params: dict[str, Any], *, direction: str) -> dict[str, Any]:
        """Set a track routing direction using exact routing identifiers."""
        routing_type_identifier = self._require_non_empty_string(
            params,
            "routing_type_identifier",
        )
        routing_channel_identifier = self._require_non_empty_string(
            params,
            "routing_channel_identifier",
        )

        type_property = f"{direction}_routing_type"
        channel_property = f"{direction}_routing_channel"
        type_collection_name = f"available_{direction}_routing_types"
        channel_collection_name = f"available_{direction}_routing_channels"

        def _set() -> dict[str, Any]:
            track, track_index, _lo = self._resolve_track(params)

            type_options = self._get_routing_collection(
                track,
                type_collection_name,
                track_index,
            )
            target_type = self._find_routing_option(
                type_options,
                routing_type_identifier,
                f"{direction} routing type",
                track_index,
            )

            current_type_identifier = self._read_routing_selection(
                track,
                type_property,
                track_index,
            )["identifier"]
            if current_type_identifier != routing_type_identifier:
                setattr(track, type_property, target_type)

            channel_options = self._get_routing_collection(
                track,
                channel_collection_name,
                track_index,
            )
            target_channel = self._find_routing_option(
                channel_options,
                routing_channel_identifier,
                f"{direction} routing channel",
                track_index,
            )
            setattr(track, channel_property, target_channel)

            return {
                "track_index": track_index,
                type_property: self._read_routing_selection(
                    track,
                    type_property,
                    track_index,
                ),
                channel_property: self._read_routing_selection(
                    track,
                    channel_property,
                    track_index,
                ),
            }

        return self._run_on_main_thread(_set)

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

        def _do_create() -> dict[str, Any]:
            song = self._song
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

        def _do_delete() -> dict[str, Any]:
            _track, track_index, lo = self._resolve_track(params)
            self._song.delete_track(lo)
            return {"track_index": track_index}

        return self._run_on_main_thread(_do_delete)

    def handle_duplicate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Duplicate a track; copy is inserted immediately after the source."""

        def _do_duplicate() -> dict[str, Any]:
            _track, track_index, lo = self._resolve_track(params)
            self._song.duplicate_track(lo)
            new_lo = lo + 1
            return {
                "source_track_index": track_index,
                "new_track_index": new_lo + 1,
            }

        return self._run_on_main_thread(_do_duplicate)

    def handle_set_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename a track."""
        name = params.get("name")
        if name is None or not isinstance(name, str) or not name.strip():
            raise InvalidParamsError("'name' must be a non-empty string")

        def _set() -> dict[str, Any]:
            _track, track_index, lo = self._resolve_track(params)
            self._song.tracks[lo].name = name
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_mute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set track mute."""
        mute = params.get("mute")
        if mute is None or not isinstance(mute, bool):
            raise InvalidParamsError("'mute' must be a boolean")

        def _set() -> dict[str, Any]:
            _track, track_index, lo = self._resolve_track(params)
            self._song.tracks[lo].mute = mute
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_solo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set track solo."""
        solo = params.get("solo")
        if solo is None or not isinstance(solo, bool):
            raise InvalidParamsError("'solo' must be a boolean")

        def _set() -> dict[str, Any]:
            _track, track_index, lo = self._resolve_track(params)
            self._song.tracks[lo].solo = solo
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)

    def handle_set_arm(self, params: dict[str, Any]) -> dict[str, Any]:
        """Arm or disarm a track for recording."""
        arm = params.get("arm")
        if arm is None or not isinstance(arm, bool):
            raise InvalidParamsError("'arm' must be a boolean")

        def _set() -> dict[str, Any]:
            track, track_index, lo = self._resolve_track(params)
            if not bool(track.can_be_armed):
                raise InvalidParamsError(
                    f"Track {track_index} cannot be armed (e.g. return/master)"
                )
            self._song.tracks[lo].arm = arm
            return {"track_index": track_index}

        return self._run_on_main_thread(_set)


__all__ = ["TrackHandler"]
