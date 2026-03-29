"""Mixer command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class MixerHandler(BaseHandler):
    """Handle per-track and master mixer commands."""

    def _require_track_index(self, params: dict[str, Any]) -> int:
        """Return a validated 1-based track index."""
        track_index = params.get("track_index")
        if track_index is None:
            raise InvalidParamsError("'track_index' parameter is required")
        if isinstance(track_index, bool) or not isinstance(track_index, int):
            raise InvalidParamsError("'track_index' must be an integer")
        if track_index < 1:
            raise InvalidParamsError("'track_index' must be at least 1")
        return track_index

    def _require_float_range(
        self,
        params: dict[str, Any],
        name: str,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        """Return a validated numeric parameter within a closed range."""
        raw_value = params.get(name)
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise InvalidParamsError(f"'{name}' must be a number")

        value = float(raw_value)
        if value < minimum or value > maximum:
            raise InvalidParamsError(
                f"'{name}' must be between {minimum} and {maximum}, got {value}"
            )
        return value

    def _resolve_track(self, track_index: int) -> Any:
        """Resolve a 1-based track index to a normal track."""
        tracks = self._song.tracks
        track_count = len(tracks)
        if track_index > track_count:
            raise NotFoundError(
                f"Track {track_index} does not exist (song has {track_count} track(s))"
            )
        return tracks[track_index - 1]

    def handle_set_track_volume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set a normal track's volume."""
        track_index = self._require_track_index(params)
        volume = self._require_float_range(
            params,
            "volume",
            minimum=0.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            track = self._resolve_track(track_index)
            track.mixer_device.volume.value = volume
            return {
                "track_index": track_index,
                "volume": float(track.mixer_device.volume.value),
            }

        return self._run_on_main_thread(_write)

    def handle_set_track_pan(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set a normal track's pan."""
        track_index = self._require_track_index(params)
        pan = self._require_float_range(
            params,
            "pan",
            minimum=-1.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            track = self._resolve_track(track_index)
            track.mixer_device.panning.value = pan
            return {
                "track_index": track_index,
                "pan": float(track.mixer_device.panning.value),
            }

        return self._run_on_main_thread(_write)

    def handle_get_master_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the master track name and mixer state."""

        def _read() -> dict[str, Any]:
            master_track = self._song.master_track
            mixer = master_track.mixer_device
            return {
                "name": str(getattr(master_track, "name", "")),
                "volume": float(mixer.volume.value),
                "pan": float(mixer.panning.value),
            }

        return self._run_on_main_thread(_read)

    def handle_set_master_volume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the master track volume."""
        volume = self._require_float_range(
            params,
            "volume",
            minimum=0.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            mixer = self._song.master_track.mixer_device
            mixer.volume.value = volume
            return {"volume": float(mixer.volume.value)}

        return self._run_on_main_thread(_write)


__all__ = ["MixerHandler"]
