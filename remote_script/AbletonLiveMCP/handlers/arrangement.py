"""Arrangement command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

import queue
from collections import Counter
from typing import TYPE_CHECKING, Any, TypeVar

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import MAIN_THREAD_TIMEOUT, BaseHandler
from .note_mixin import NoteMixin

T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable


class ArrangementHandler(NoteMixin, BaseHandler):
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

    def _require_take_lane_index(self, params: dict[str, Any]) -> int:
        raw = params.get("take_lane_index")
        if raw is None:
            raise InvalidParamsError("'take_lane_index' parameter is required")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidParamsError("'take_lane_index' must be an integer")
        if raw < 1:
            raise InvalidParamsError("'take_lane_index' must be at least 1")
        return raw

    def _require_locator_index(self, params: dict[str, Any]) -> int:
        raw = params.get("locator_index")
        if raw is None:
            raise InvalidParamsError("'locator_index' parameter is required")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidParamsError("'locator_index' must be an integer")
        if raw < 1:
            raise InvalidParamsError("'locator_index' must be at least 1")
        return raw

    def _require_arrangement_number(
        self,
        params: dict[str, Any],
        key: str,
        *,
        minimum: float | None = None,
        exclusive_minimum: bool = False,
    ) -> float:
        """Validate a required number param for arrangement commands."""
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

    def _require_locator_name(
        self,
        params: dict[str, Any],
        *,
        required: bool = True,
    ) -> str | None:
        raw = params.get("name")
        if raw is None:
            if required:
                raise InvalidParamsError("'name' parameter is required")
            return None
        if not isinstance(raw, str):
            raise InvalidParamsError("'name' must be a string")
        name = raw.strip()
        if not name:
            raise InvalidParamsError("'name' must be a non-empty string")
        return name

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

    def _resolve_take_lane(
        self,
        track: Any,
        *,
        track_index: int,
        take_lane_index: int,
    ) -> Any:
        take_lanes = track.take_lanes
        take_lane_count = len(take_lanes)
        if take_lane_index > take_lane_count:
            raise NotFoundError(
                "Take lane "
                f"{take_lane_index} does not exist on track {track_index} "
                f"(track has {take_lane_count} take lane(s))"
            )
        return take_lanes[take_lane_index - 1]

    def _serialize_take_lane_clip(
        self,
        clip: Any,
        *,
        clip_index: int,
    ) -> dict[str, Any]:
        start_time = float(clip.start_time)
        end_time = float(clip.end_time)
        return {
            "clip_index": clip_index,
            "name": str(clip.name),
            "start_time": start_time,
            "end_time": end_time,
            "length": float(clip.length),
            "is_audio_clip": bool(clip.is_audio_clip),
            "is_midi_clip": bool(clip.is_midi_clip),
        }

    def _serialize_take_lane(
        self,
        take_lane: Any,
        *,
        take_lane_index: int,
    ) -> dict[str, Any]:
        clips = [
            self._serialize_take_lane_clip(clip, clip_index=clip_index)
            for clip_index, clip in enumerate(take_lane.arrangement_clips, start=1)
        ]
        return {
            "take_lane_index": take_lane_index,
            "name": str(take_lane.name),
            "clips": clips,
        }

    def _take_lane_signature(
        self,
        take_lane: Any,
    ) -> tuple[str, tuple[tuple[str, float, float, float, bool, bool], ...]]:
        return (
            str(take_lane.name),
            tuple(self._clip_signature(clip) for clip in take_lane.arrangement_clips),
        )

    def _find_new_take_lane(
        self,
        before: list[Any],
        after: list[Any],
        *,
        action: str,
    ) -> tuple[int, Any]:
        before_counts = Counter(id(take_lane) for take_lane in before)
        seen_counts: Counter[int] = Counter()
        candidates: list[tuple[int, Any]] = []

        for take_lane_index, take_lane in enumerate(after, start=1):
            take_lane_id = id(take_lane)
            seen_counts[take_lane_id] += 1
            if seen_counts[take_lane_id] > before_counts[take_lane_id]:
                candidates.append((take_lane_index, take_lane))

        if len(candidates) == 1:
            return candidates[0]

        signature_before_counts = Counter(
            self._take_lane_signature(take_lane) for take_lane in before
        )
        signature_seen_counts: Counter[
            tuple[str, tuple[tuple[str, float, float, float, bool, bool], ...]]
        ] = Counter()
        signature_candidates: list[tuple[int, Any]] = []

        for take_lane_index, take_lane in enumerate(after, start=1):
            signature = self._take_lane_signature(take_lane)
            signature_seen_counts[signature] += 1
            if signature_seen_counts[signature] > signature_before_counts[signature]:
                signature_candidates.append((take_lane_index, take_lane))

        if not signature_candidates:
            raise RuntimeError(f"No new take lane appeared after {action} completed")
        if len(signature_candidates) > 1:
            raise RuntimeError(
                f"Could not uniquely identify the take lane after {action}"
            )
        return signature_candidates[0]

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

    def _resolve_midi_arrangement_clip(
        self,
        params: dict[str, Any],
    ) -> tuple[Any, int, int]:
        """Return ``(clip, track_index, clip_index)`` for a MIDI arrangement clip."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        clip_index = self._require_clip_index(params)
        track, resolved_track_index, _ = self._resolve_track(track_index)

        if not bool(track.has_midi_input):
            raise InvalidParamsError(
                f"Track {resolved_track_index} does not accept MIDI clips"
            )

        clip = self._resolve_arrangement_clip(
            track,
            track_index=resolved_track_index,
            clip_index=clip_index,
        )

        if not bool(clip.is_midi_clip):
            raise InvalidParamsError(
                f"Arrangement clip {clip_index} on track {resolved_track_index} "
                "is not a MIDI clip"
            )

        return clip, resolved_track_index, clip_index

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

    def _serialize_cue_point(
        self,
        cue_point: Any,
        *,
        locator_index: int,
    ) -> dict[str, Any]:
        return {
            "locator_index": locator_index,
            "name": str(cue_point.name),
            "time": float(cue_point.time),
        }

    def _get_cue_points(self) -> list[Any]:
        return list(self._song.cue_points)

    def _find_cue_points_at_time(self, time: float) -> list[Any]:
        return [
            cue_point
            for cue_point in self._song.cue_points
            if float(cue_point.time) == time
        ]

    def _resolve_locator(
        self,
        locator_index: int,
    ) -> tuple[Any, int]:
        cue_points = self._get_cue_points()
        cue_count = len(cue_points)
        if locator_index > cue_count:
            raise NotFoundError(
                "Locator "
                f"{locator_index} does not exist (song has {cue_count} locator(s))"
            )
        return cue_points[locator_index - 1], locator_index

    def _cue_point_index(self, cue_point: Any) -> int:
        for locator_index, candidate in enumerate(self._song.cue_points, start=1):
            if candidate is cue_point:
                return locator_index
        raise RuntimeError("Could not locate locator after creation")

    def _locator_index_at_time(self, time: float) -> int:
        for locator_index, cue_point in enumerate(self._song.cue_points, start=1):
            if float(cue_point.time) == time:
                return locator_index
        raise RuntimeError(f"Could not locate locator at time {time}")

    def _run_on_main_thread_after_settle(
        self,
        setup: Callable[[], Any],
        action: Callable[[], T],
    ) -> T:
        """Run *setup* on one tick, then *action* on the next tick."""
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _action_wrapper() -> None:
            try:
                result_queue.put(("ok", action()))
            except Exception as exc:
                result_queue.put(("error", exc))

        def _setup_wrapper() -> None:
            try:
                setup()
                self._control_surface.schedule_message(0, _action_wrapper)
            except Exception as exc:
                result_queue.put(("error", exc))

        self._control_surface.schedule_message(0, _setup_wrapper)

        status, value = result_queue.get(timeout=MAIN_THREAD_TIMEOUT)
        if status == "error":
            raise value
        return value

    def _set_current_song_time_and_wait(self, target_time: float) -> None:
        """Move the playhead and wait for Live to settle the new time."""
        self._run_on_main_thread_after_settle(
            lambda: setattr(self._song, "current_song_time", target_time),
            lambda: None,
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

    # ------------------------------------------------------------------
    # Existing arrangement handlers
    # ------------------------------------------------------------------

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
        start_time = self._require_arrangement_number(params, "start_time", minimum=0.0)
        length = self._require_arrangement_number(
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

    def handle_import_audio(self, params: dict[str, Any]) -> dict[str, Any]:
        """Import an audio file into arrangement view on an audio track."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        file_path = self._require_absolute_file_path(params, "file_path")
        self._require_existing_file(file_path)
        start_time = self._require_arrangement_number(params, "start_time", minimum=0.0)

        def _import() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            if not bool(track.has_audio_input):
                raise InvalidParamsError(
                    f"Track {resolved_track_index} does not accept audio clips"
                )

            before = list(track.arrangement_clips)
            try:
                track.create_audio_clip(file_path, start_time)
            except Exception as exc:
                raise InvalidParamsError(
                    "Unable to import audio clip to arrangement track "
                    f"{resolved_track_index}: {exc}"
                ) from exc

            clip_index, clip = self._find_new_clip(
                before,
                list(track.arrangement_clips),
                action="import_audio_to_arrangement",
            )
            return {
                "track_index": resolved_track_index,
                "clip_index": clip_index,
                "name": str(clip.name),
                "file_path": file_path,
                "start_time": float(clip.start_time),
                "length": float(clip.length),
                "is_audio_clip": bool(clip.is_audio_clip),
            }

        return self._run_on_main_thread(_import)

    def handle_get_take_lanes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all take lanes for one track."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None

        def _read() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            take_lanes = [
                self._serialize_take_lane(take_lane, take_lane_index=take_lane_index)
                for take_lane_index, take_lane in enumerate(track.take_lanes, start=1)
            ]
            return {
                "track_index": resolved_track_index,
                "take_lanes": take_lanes,
            }

        return self._run_on_main_thread(_read)

    def handle_create_take_lane(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a take lane on a track and optionally name it."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        name = self._require_locator_name(params, required=False)

        def _create() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            before = list(track.take_lanes)
            track.create_take_lane()
            take_lane_index, take_lane = self._find_new_take_lane(
                before,
                list(track.take_lanes),
                action="create_take_lane",
            )
            if name is not None:
                take_lane.name = name
            return {
                "track_index": resolved_track_index,
                "take_lane_index": take_lane_index,
                "name": str(take_lane.name),
            }

        return self._run_on_main_thread(_create)

    def handle_set_take_lane_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename an existing take lane."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        take_lane_index = self._require_take_lane_index(params)
        name = self._require_locator_name(params)
        assert name is not None

        def _rename() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            take_lane = self._resolve_take_lane(
                track,
                track_index=resolved_track_index,
                take_lane_index=take_lane_index,
            )
            take_lane.name = name
            return {
                "track_index": resolved_track_index,
                "take_lane_index": take_lane_index,
                "name": str(take_lane.name),
            }

        return self._run_on_main_thread(_rename)

    def handle_create_take_lane_midi_clip(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an empty MIDI clip inside a take lane on a MIDI track."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        take_lane_index = self._require_take_lane_index(params)
        start_time = self._require_arrangement_number(params, "start_time", minimum=0.0)
        length = self._require_arrangement_number(
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
            take_lane = self._resolve_take_lane(
                track,
                track_index=resolved_track_index,
                take_lane_index=take_lane_index,
            )
            before = list(take_lane.arrangement_clips)
            try:
                take_lane.create_midi_clip(start_time, length)
            except Exception as exc:
                raise InvalidParamsError(
                    "Unable to create MIDI clip in take lane "
                    f"{take_lane_index} on track {resolved_track_index}: {exc}"
                ) from exc

            clip_index, clip = self._find_new_clip(
                before,
                list(take_lane.arrangement_clips),
                action="create_take_lane_midi_clip",
            )
            return {
                "track_index": resolved_track_index,
                "take_lane_index": take_lane_index,
                "clip_index": clip_index,
                "start_time": start_time,
                "length": length,
                "name": str(clip.name),
            }

        return self._run_on_main_thread(_create)

    def handle_import_audio_to_take_lane(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Import an audio file into a take lane on an audio track."""
        track_index = self._require_track_index(params, "track_index")
        assert track_index is not None
        take_lane_index = self._require_take_lane_index(params)
        file_path = self._require_absolute_file_path(params, "file_path")
        self._require_existing_file(file_path)
        start_time = self._require_arrangement_number(params, "start_time", minimum=0.0)

        def _import() -> dict[str, Any]:
            track, resolved_track_index, _ = self._resolve_track(track_index)
            if not bool(track.has_audio_input):
                raise InvalidParamsError(
                    f"Track {resolved_track_index} does not accept audio clips"
                )
            take_lane = self._resolve_take_lane(
                track,
                track_index=resolved_track_index,
                take_lane_index=take_lane_index,
            )
            before = list(take_lane.arrangement_clips)
            try:
                take_lane.create_audio_clip(file_path, start_time)
            except Exception as exc:
                raise InvalidParamsError(
                    "Unable to import audio clip to take lane "
                    f"{take_lane_index} on track {resolved_track_index}: {exc}"
                ) from exc

            clip_index, clip = self._find_new_clip(
                before,
                list(take_lane.arrangement_clips),
                action="import_audio_to_take_lane",
            )
            return {
                "track_index": resolved_track_index,
                "take_lane_index": take_lane_index,
                "clip_index": clip_index,
                "name": str(clip.name),
                "file_path": file_path,
                "start_time": float(clip.start_time),
                "length": float(clip.length),
                "is_audio_clip": bool(clip.is_audio_clip),
            }

        return self._run_on_main_thread(_import)

    def handle_move_clip(self, params: dict[str, Any]) -> dict[str, Any]:
        """Move an arrangement clip to a new track/time by duplicate-then-delete."""
        source_track_index = self._require_track_index(params, "track_index")
        assert source_track_index is not None
        source_clip_index = self._require_clip_index(params)
        new_start_time = self._require_arrangement_number(
            params, "new_start_time", minimum=0.0
        )
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
        start_time = self._require_arrangement_number(params, "start_time", minimum=0.0)
        end_time = self._require_arrangement_number(params, "end_time", minimum=0.0)
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

    def handle_get_locators(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all cue points in the song."""

        def _read() -> dict[str, Any]:
            locators = [
                self._serialize_cue_point(cue_point, locator_index=locator_index)
                for locator_index, cue_point in enumerate(
                    self._song.cue_points, start=1
                )
            ]
            return {"locators": locators}

        return self._run_on_main_thread(_read)

    def handle_create_locator(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a locator at the requested beat time."""
        target_time = self._require_arrangement_number(params, "time", minimum=0.0)
        name = self._require_locator_name(params, required=False)

        original_time = self._run_on_main_thread(
            lambda: float(self._song.current_song_time)
        )
        existing = self._run_on_main_thread(
            lambda: self._find_cue_points_at_time(target_time)
        )
        if existing:
            raise InvalidParamsError(f"A locator already exists at time {target_time}")

        before_count = self._run_on_main_thread(lambda: len(self._song.cue_points))
        try:
            self._set_current_song_time_and_wait(target_time)

            def _create() -> dict[str, Any]:
                song = self._song
                song.set_or_delete_cue()
                after_count = len(song.cue_points)
                if after_count != before_count + 1:
                    raise RuntimeError(
                        "Locator creation did not change cue-point count by +1"
                    )

                created_candidates = [
                    cue_point
                    for cue_point in song.cue_points
                    if float(cue_point.time) == target_time
                ]
                if len(created_candidates) != 1:
                    raise RuntimeError(
                        "Could not uniquely identify locator at time "
                        f"{target_time} after creation"
                    )
                created = created_candidates[0]
                if name is not None:
                    created.name = name
                locator_index = self._locator_index_at_time(target_time)
                return self._serialize_cue_point(
                    created,
                    locator_index=locator_index,
                )

            result = self._run_on_main_thread_after_settle(lambda: None, _create)
            return result
        finally:
            self._set_current_song_time_and_wait(original_time)
            self._run_on_main_thread_after_settle(
                lambda: None,
                lambda: None,
            )

    def handle_delete_locator(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete a locator by 1-based index."""
        locator_index = self._require_locator_index(params)
        original_time = self._run_on_main_thread(
            lambda: float(self._song.current_song_time)
        )
        cue_point, resolved_locator_index = self._run_on_main_thread(
            lambda: self._resolve_locator(locator_index)
        )
        cue_time = float(cue_point.time)
        cue_name = str(cue_point.name)
        try:
            self._set_current_song_time_and_wait(cue_time)

            def _delete() -> dict[str, Any]:
                song = self._song
                matched = [
                    cue_point
                    for cue_point in song.cue_points
                    if float(cue_point.time) == cue_time
                ]
                if not matched:
                    raise NotFoundError(
                        "Locator "
                        f"{resolved_locator_index} no longer exists at time {cue_time}"
                    )

                before_count = len(song.cue_points)
                song.set_or_delete_cue()
                after_count = len(song.cue_points)
                if after_count != before_count - 1:
                    raise RuntimeError(
                        "Locator deletion did not change cue-point count by -1"
                    )
                remaining = [
                    cue_point
                    for cue_point in song.cue_points
                    if float(cue_point.time) == cue_time
                ]
                if remaining:
                    raise RuntimeError(
                        f"Locator deletion left a cue point at time {cue_time}"
                    )
                return {
                    "locator_index": resolved_locator_index,
                    "name": cue_name,
                    "time": cue_time,
                }

            result = self._run_on_main_thread_after_settle(lambda: None, _delete)
            return result
        finally:
            self._set_current_song_time_and_wait(original_time)
            self._run_on_main_thread_after_settle(
                lambda: None,
                lambda: None,
            )

    def handle_set_locator_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename a locator."""
        locator_index = self._require_locator_index(params)
        name = self._require_locator_name(params)
        assert name is not None

        def _rename() -> dict[str, Any]:
            cue_point, resolved_locator_index = self._resolve_locator(locator_index)
            cue_point.name = name
            return self._serialize_cue_point(
                cue_point,
                locator_index=resolved_locator_index,
            )

        return self._run_on_main_thread(_rename)

    def handle_jump_to_time(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set the current arrangement playhead position."""
        target_time = self._require_arrangement_number(params, "time", minimum=0.0)

        def _jump() -> dict[str, Any]:
            return {"time": float(self._song.current_song_time)}

        self._set_current_song_time_and_wait(target_time)
        return self._run_on_main_thread(_jump)

    # ------------------------------------------------------------------
    # Note editing handlers for arrangement clips
    # ------------------------------------------------------------------

    def handle_get_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all MIDI notes in an arrangement clip."""

        def _do() -> dict[str, Any]:
            clip, track_index, clip_index = self._resolve_midi_arrangement_clip(params)
            notes = [self._serialize_note(note) for note in self._get_clip_notes(clip)]
            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "notes": notes,
                "count": len(notes),
            }

        return self._run_on_main_thread(_do)

    def handle_add_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add MIDI notes to an arrangement clip."""
        normalized_notes = self._normalize_input_notes(params)

        def _do() -> dict[str, Any]:
            clip, track_index, clip_index = self._resolve_midi_arrangement_clip(params)
            before_notes = [
                self._serialize_note(note) for note in self._get_clip_notes(clip)
            ]
            note_ids = self._write_notes(
                clip,
                normalized_notes,
                log_prefix="AbletonLiveMCP arrangement.add_notes",
                before_notes=before_notes,
            )
            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "added_count": len(note_ids),
                "note_ids": note_ids,
            }

        return self._run_on_main_thread(_do)

    def handle_set_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Replace all MIDI notes in an arrangement clip."""
        normalized_notes = self._normalize_input_notes(params)

        def _do() -> dict[str, Any]:
            clip, track_index, clip_index = self._resolve_midi_arrangement_clip(params)
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
                    log_prefix="AbletonLiveMCP arrangement.set_notes",
                )

            return {
                "track_index": track_index,
                "clip_index": clip_index,
                "removed_count": len(existing_note_ids),
                "added_count": len(added_note_ids),
                "note_ids": added_note_ids,
            }

        return self._run_on_main_thread(_do)

    def handle_remove_notes(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove notes by pitch/time region from an arrangement clip."""
        from_pitch, pitch_span, from_time, time_span = self._get_remove_region(params)

        def _do() -> dict[str, Any]:
            clip, track_index, clip_index = self._resolve_midi_arrangement_clip(params)
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
                "clip_index": clip_index,
                "removed_count": len(note_ids),
            }

        return self._run_on_main_thread(_do)


__all__ = ["ArrangementHandler"]
