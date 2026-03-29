"""Arrangement command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class ArrangementHandler(BaseHandler):
    """Handle arrangement clip and loop commands."""

    def _resolve_track(self, track_index: int) -> tuple[Any, int, int]:
        """Return ``(track, track_index_1based, lo_track)`` or raise."""
        tracks = self._song.tracks
        track_count = len(tracks)
        if track_index > track_count:
            raise NotFoundError(
                f"Track {track_index} does not exist (song has {track_count} track(s))"
            )
        lo_track = track_index - 1
        return tracks[lo_track], track_index, lo_track

    def _require_track_index(
        self,
        params: dict[str, Any],
        key: str,
        *,
        required: bool = True,
    ) -> int | None:
        raw = params.get(key)
        if raw is None:
            if required:
                raise InvalidParamsError(f"'{key}' parameter is required")
            return None
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidParamsError(f"'{key}' must be an integer")
        if raw < 1:
            raise InvalidParamsError(f"'{key}' must be at least 1")
        return raw

    def _require_clip_index(self, params: dict[str, Any]) -> int:
        raw = params.get("clip_index")
        if raw is None:
            raise InvalidParamsError("'clip_index' parameter is required")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidParamsError("'clip_index' must be an integer")
        if raw < 1:
            raise InvalidParamsError("'clip_index' must be at least 1")
        return raw

    def _require_number(
        self,
        params: dict[str, Any],
        key: str,
        *,
        minimum: float | None = None,
        exclusive_minimum: bool = False,
    ) -> float:
        raw = params.get(key)
        if raw is None:
            raise InvalidParamsError(f"'{key}' parameter is required")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise InvalidParamsError(f"'{key}' must be a number")

        value = float(raw)
        if minimum is not None:
            if exclusive_minimum and value <= minimum:
                raise InvalidParamsError(f"'{key}' must be greater than {minimum}")
            if not exclusive_minimum and value < minimum:
                raise InvalidParamsError(f"'{key}' must be at least {minimum}")
        return value

    def _serialize_clip(
        self,
        clip: Any,
        *,
        track_index: int,
        clip_index: int,
    ) -> dict[str, Any]:
        start_time = float(clip.start_time)
        end_time = float(clip.end_time)
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "name": str(clip.name),
            "start_time": start_time,
            "end_time": end_time,
            "length": float(clip.length),
            "is_audio_clip": bool(clip.is_audio_clip),
            "is_midi_clip": bool(clip.is_midi_clip),
        }

    def _clip_signature(self, clip: Any) -> tuple[str, float, float, float, bool, bool]:
        return (
            str(clip.name),
            float(clip.start_time),
            float(clip.end_time),
            float(clip.length),
            bool(clip.is_audio_clip),
            bool(clip.is_midi_clip),
        )

    def _get_arrangement_clips(
        self,
        track: Any,
        track_index: int,
    ) -> list[dict[str, Any]]:
        clips: list[dict[str, Any]] = []
        for clip_index, clip in enumerate(track.arrangement_clips, start=1):
            clips.append(
                self._serialize_clip(
                    clip,
                    track_index=track_index,
                    clip_index=clip_index,
                )
            )
        return clips

    def _resolve_arrangement_clip(
        self,
        track: Any,
        *,
        track_index: int,
        clip_index: int,
    ) -> Any:
        clips = track.arrangement_clips
        clip_count = len(clips)
        if clip_index > clip_count:
            raise NotFoundError(
                "Arrangement clip "
                f"{clip_index} does not exist on track {track_index} "
                f"(track has {clip_count} arrangement clip(s))"
            )
        return clips[clip_index - 1]

    def _find_new_clip(
        self,
        before: list[Any],
        after: list[Any],
        *,
        action: str,
    ) -> tuple[int, Any]:
        before_counts = Counter(id(clip) for clip in before)
        seen_counts: Counter[int] = Counter()
        candidates: list[tuple[int, Any]] = []

        for clip_index, clip in enumerate(after, start=1):
            clip_id = id(clip)
            seen_counts[clip_id] += 1
            if seen_counts[clip_id] > before_counts[clip_id]:
                candidates.append((clip_index, clip))

        if len(candidates) == 1:
            return candidates[0]

        signature_before_counts = Counter(self._clip_signature(clip) for clip in before)
        signature_seen_counts: Counter[tuple[str, float, float, float, bool, bool]]
        signature_seen_counts = Counter()
        signature_candidates: list[tuple[int, Any]] = []

        for clip_index, clip in enumerate(after, start=1):
            signature = self._clip_signature(clip)
            signature_seen_counts[signature] += 1
            if signature_seen_counts[signature] > signature_before_counts[signature]:
                signature_candidates.append((clip_index, clip))

        if not signature_candidates:
            raise RuntimeError(
                f"No new arrangement clip appeared after {action} completed"
            )
        if len(signature_candidates) > 1:
            raise RuntimeError(
                f"Could not uniquely identify the arrangement clip after {action}"
            )
        return signature_candidates[0]

    def _find_clip_index(self, track: Any, clip: Any, track_index: int) -> int:
        for clip_index, candidate in enumerate(track.arrangement_clips, start=1):
            if candidate is clip:
                return clip_index

        clip_signature = self._clip_signature(clip)
        signature_matches = [
            clip_index
            for clip_index, candidate in enumerate(track.arrangement_clips, start=1)
            if self._clip_signature(candidate) == clip_signature
        ]
        if len(signature_matches) == 1:
            return signature_matches[0]

        raise RuntimeError(
            f"Could not locate arrangement clip on track {track_index} after update"
        )

    def _validate_target_track(
        self,
        clip: Any,
        target_track: Any,
        target_track_index: int,
    ) -> None:
        if bool(clip.is_midi_clip) and not bool(target_track.has_midi_input):
            raise InvalidParamsError(
                f"Track {target_track_index} does not accept MIDI arrangement clips"
            )
        if bool(clip.is_audio_clip) and not bool(target_track.has_audio_input):
            raise InvalidParamsError(
                f"Track {target_track_index} does not accept audio arrangement clips"
            )

    def handle_get_clips(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return arrangement clips for one track or all tracks."""
        track_index = self._require_track_index(params, "track_index", required=False)

        def _read() -> dict[str, Any]:
            if track_index is not None:
                track, resolved_track_index, _ = self._resolve_track(track_index)
                return {
                    "track_index": resolved_track_index,
                    "clips": self._get_arrangement_clips(track, resolved_track_index),
                }

            clips: list[dict[str, Any]] = []
            for resolved_track_index, track in enumerate(self._song.tracks, start=1):
                clips.extend(self._get_arrangement_clips(track, resolved_track_index))
            return {"track_index": None, "clips": clips}

        return self._run_on_main_thread(_read)

    def handle_create_clip(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create an empty MIDI arrangement clip on a MIDI track."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        start_time = self._require_number(params, "start_time", minimum=0.0)
        length = self._require_number(
            params,
            "length",
            minimum=0.0,
            exclusive_minimum=True,
        )

        def _create() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            if not bool(track.has_midi_input):
                raise InvalidParamsError(
                    f"Track {resolved_track_index} does not accept MIDI clips"
                )

            before = list(track.arrangement_clips)
            track.create_midi_clip(start_time, length)
            clip_index, clip = self._find_new_clip(
                before,
                list(track.arrangement_clips),
                action="create_arrangement_clip",
            )
            return {
                "track_index": resolved_track_index,
                "clip_index": clip_index,
                "start_time": start_time,
                "length": length,
                "name": str(clip.name),
            }

        return self._run_on_main_thread(_create)

    def handle_move_clip(self, params: dict[str, Any]) -> dict[str, Any]:
        """Move an arrangement clip to a new track/time by duplicate-then-delete."""
        source_track_index = self._require_track_index(params, "track_index")
        assert source_track_index is not None
        source_clip_index = self._require_clip_index(params)
        new_start_time = self._require_number(params, "new_start_time", minimum=0.0)
        target_track_index = self._require_track_index(
            params,
            "new_track_index",
            required=False,
        )
        if target_track_index is None:
            target_track_index = source_track_index

        def _move() -> dict[str, Any]:
            source_track, resolved_source_track_index, _ = self._resolve_track(
                source_track_index
            )
            source_clip = self._resolve_arrangement_clip(
                source_track,
                track_index=resolved_source_track_index,
                clip_index=source_clip_index,
            )
            target_track, resolved_target_track_index, _ = self._resolve_track(
                target_track_index
            )
            self._validate_target_track(
                source_clip,
                target_track,
                resolved_target_track_index,
            )

            before_target = list(target_track.arrangement_clips)
            try:
                target_track.duplicate_clip_to_arrangement(source_clip, new_start_time)
            except Exception as exc:
                raise InvalidParamsError(
                    "Unable to duplicate arrangement clip to the target track/time: "
                    f"{exc}"
                ) from exc

            _target_clip_index, moved_clip = self._find_new_clip(
                before_target,
                list(target_track.arrangement_clips),
                action="move_arrangement_clip",
            )

            try:
                source_track.delete_clip(source_clip)
            except Exception as exc:
                raise RuntimeError(
                    "Arrangement clip duplication succeeded but deleting the original "
                    f"clip failed: {exc}"
                ) from exc

            final_target_clip_index = self._find_clip_index(
                target_track,
                moved_clip,
                resolved_target_track_index,
            )
            return {
                "source_track_index": resolved_source_track_index,
                "source_clip_index": source_clip_index,
                "target_track_index": resolved_target_track_index,
                "target_clip_index": final_target_clip_index,
                "start_time": float(moved_clip.start_time),
            }

        return self._run_on_main_thread(_move)

    def handle_get_length(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the song's arrangement length in beats."""

        def _read() -> dict[str, Any]:
            return {"song_length": float(self._song.song_length)}

        return self._run_on_main_thread(_read)

    def handle_set_loop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set arrangement loop start/end/enabled."""
        start_time = self._require_number(params, "start_time", minimum=0.0)
        end_time = self._require_number(params, "end_time", minimum=0.0)
        enabled = params.get("enabled", True)
        if not isinstance(enabled, bool):
            raise InvalidParamsError("'enabled' must be a boolean")
        if end_time <= start_time:
            raise InvalidParamsError("'end_time' must be greater than 'start_time'")

        def _set() -> dict[str, Any]:
            song = self._song
            song.loop_start = start_time
            song.loop_length = end_time - start_time
            song.loop = enabled
            return {
                "start_time": float(song.loop_start),
                "end_time": float(song.loop_start + song.loop_length),
                "enabled": enabled,
            }

        return self._run_on_main_thread(_set)


__all__ = ["ArrangementHandler"]
