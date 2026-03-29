"""Mixer command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class MixerHandler(BaseHandler):
    """Handle per-track and master mixer commands."""

    def _require_positive_int_param(self, params: dict[str, Any], name: str) -> int:
        """Return a validated 1-based integer parameter."""
        value = params.get(name)
        if value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidParamsError(f"'{name}' must be an integer")
        if value < 1:
            raise InvalidParamsError(f"'{name}' must be at least 1")
        return value

    def _require_track_index(self, params: dict[str, Any]) -> int:
        """Return a validated 1-based track index."""
        return self._require_positive_int_param(params, "track_index")

    def _require_send_index(self, params: dict[str, Any]) -> int:
        """Return a validated 1-based send index."""
        return self._require_positive_int_param(params, "send_index")

    def _require_return_index(self, params: dict[str, Any]) -> int:
        """Return a validated 1-based return track index."""
        return self._require_positive_int_param(params, "return_index")

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

    def _resolve_return_track(self, return_index: int) -> Any:
        """Resolve a 1-based return track index."""
        return_tracks = self._song.return_tracks
        return_count = len(return_tracks)
        if return_index > return_count:
            raise NotFoundError(
                "Return track "
                f"{return_index} does not exist "
                f"(song has {return_count} return track(s))"
            )
        return return_tracks[return_index - 1]

    def _resolve_send(self, track: Any, track_index: int, send_index: int) -> Any:
        """Resolve a 1-based send index on a normal track."""
        sends = track.mixer_device.sends
        send_count = len(sends)
        if send_index > send_count:
            raise NotFoundError(
                f"Send {send_index} does not exist for track {track_index} "
                f"(track has {send_count} send(s))"
            )
        return sends[send_index - 1]

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

    def handle_get_return_tracks(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all return tracks with volume and pan metadata."""

        def _read() -> dict[str, Any]:
            return_tracks = [
                {
                    "return_index": index,
                    "name": str(getattr(return_track, "name", "")),
                    "volume": float(return_track.mixer_device.volume.value),
                    "pan": float(return_track.mixer_device.panning.value),
                }
                for index, return_track in enumerate(self._song.return_tracks, start=1)
            ]
            return {"return_tracks": return_tracks}

        return self._run_on_main_thread(_read)

    def handle_set_send_level(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set a send level on a normal track."""
        track_index = self._require_track_index(params)
        send_index = self._require_send_index(params)
        level = self._require_float_range(
            params,
            "level",
            minimum=0.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            track = self._resolve_track(track_index)
            send = self._resolve_send(track, track_index, send_index)
            send.value = level
            return {
                "track_index": track_index,
                "send_index": send_index,
                "level": float(send.value),
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

    def handle_set_return_volume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set a return track volume."""
        return_index = self._require_return_index(params)
        volume = self._require_float_range(
            params,
            "volume",
            minimum=0.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            return_track = self._resolve_return_track(return_index)
            return_track.mixer_device.volume.value = volume
            return {
                "return_index": return_index,
                "volume": float(return_track.mixer_device.volume.value),
            }

        return self._run_on_main_thread(_write)

    def handle_set_return_pan(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set a return track pan."""
        return_index = self._require_return_index(params)
        pan = self._require_float_range(
            params,
            "pan",
            minimum=-1.0,
            maximum=1.0,
        )

        def _write() -> dict[str, Any]:
            return_track = self._resolve_return_track(return_index)
            return_track.mixer_device.panning.value = pan
            return {
                "return_index": return_index,
                "pan": float(return_track.mixer_device.panning.value),
            }

        return self._run_on_main_thread(_write)


__all__ = ["MixerHandler"]
