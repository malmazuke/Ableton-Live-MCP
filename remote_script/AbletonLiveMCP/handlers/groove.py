"""Groove pool command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class GrooveHandler(BaseHandler):
    """Handle groove pool listing and groove assignment commands."""

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

    def _resolve_track(self, params: dict[str, Any]) -> tuple[Any, int]:
        """Return the requested track and its 1-based index."""
        track_index = self._require_index(params, "track_index")
        tracks = self._song.tracks
        track_count = len(tracks)
        if track_index > track_count:
            raise NotFoundError(
                f"Track {track_index} does not exist (song has {track_count} track(s))"
            )
        return tracks[track_index - 1], track_index

    def _resolve_clip_slot(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, Any, int, int]:
        """Return ``(track, clip_slot, track_index, clip_slot_index)``."""
        track, track_index = self._resolve_track(params)
        clip_slot_index = self._require_index(params, "clip_slot_index")
        clip_slots = track.clip_slots
        clip_slot_count = len(clip_slots)
        if clip_slot_index > clip_slot_count:
            raise NotFoundError(
                f"Clip slot {clip_slot_index} does not exist "
                f"(track {track_index} has {clip_slot_count} slot(s))"
            )
        return track, clip_slots[clip_slot_index - 1], track_index, clip_slot_index

    def _resolve_existing_clip(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, Any, int, int]:
        """Return ``(track, clip, track_index, clip_slot_index)``."""
        track, clip_slot, track_index, clip_slot_index = self._resolve_clip_slot(params)
        if not bool(getattr(clip_slot, "has_clip", False)):
            raise NotFoundError(
                f"No clip in slot {clip_slot_index} on track {track_index}"
            )
        return track, clip_slot.clip, track_index, clip_slot_index

    def _resolve_groove(self, groove_index: int) -> tuple[Any, int]:
        """Return the selected groove and its 1-based index."""
        grooves = list(self._song.groove_pool.grooves)
        groove_count = len(grooves)
        if groove_index > groove_count:
            raise NotFoundError(
                f"Groove {groove_index} does not exist "
                f"(groove pool has {groove_count} groove(s))"
            )
        return grooves[groove_index - 1], groove_index

    def _serialize_groove(self, groove: Any, groove_index: int) -> dict[str, Any]:
        """Normalize Live's groove object into the MCP response shape."""
        return {
            "groove_index": groove_index,
            "name": str(groove.name),
            "base": int(groove.base),
            "quantization_amount": float(groove.quantization_amount),
            "timing_amount": float(groove.timing_amount),
            "random_amount": float(groove.random_amount),
            "velocity_amount": float(groove.velocity_amount),
        }

    def handle_get_pool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the current groove pool."""

        def _read() -> dict[str, Any]:
            grooves = [
                self._serialize_groove(groove, groove_index)
                for groove_index, groove in enumerate(
                    self._song.groove_pool.grooves,
                    start=1,
                )
            ]
            return {"grooves": grooves}

        return self._run_on_main_thread(_read)

    def handle_apply(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply a groove to an existing session clip."""

        def _apply() -> dict[str, Any]:
            _track, clip, track_index, clip_slot_index = self._resolve_existing_clip(
                params
            )
            groove_index = self._require_index(params, "groove_index")
            groove, selected_index = self._resolve_groove(groove_index)

            try:
                clip.groove = groove
            except Exception as exc:
                raise RuntimeError(
                    "Failed to apply groove "
                    f"{selected_index} to clip slot {clip_slot_index} "
                    f"on track {track_index}: {exc}"
                ) from exc

            return {
                "track_index": track_index,
                "clip_slot_index": clip_slot_index,
                "groove_index": selected_index,
                "groove_name": str(groove.name),
            }

        return self._run_on_main_thread(_apply)


__all__ = ["GrooveHandler"]
