"""Scene command handlers for the Ableton Live MCP Remote Script."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class SceneHandler(BaseHandler):
    """Handle scene list, CRUD, and launch/stop commands."""

    def _require_scene_index(self, params: dict[str, Any]) -> int:
        raw = params.get("scene_index")
        if raw is None:
            raise InvalidParamsError("'scene_index' parameter is required")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidParamsError("'scene_index' must be an integer")
        if raw < 1:
            raise InvalidParamsError("'scene_index' must be at least 1")
        return raw

    def _resolve_scene(self, params: dict[str, Any]) -> tuple[Any, int, int]:
        scene_index = self._require_scene_index(params)
        scenes = self._song.scenes
        scene_count = len(scenes)
        if scene_index > scene_count:
            raise NotFoundError(
                f"Scene {scene_index} does not exist (song has {scene_count} scene(s))"
            )
        lo_index = scene_index - 1
        return scenes[lo_index], scene_index, lo_index

    def _require_name(
        self,
        params: dict[str, Any],
        *,
        required: bool,
    ) -> str | None:
        name = params.get("name")
        if name is None:
            if required:
                raise InvalidParamsError("'name' parameter is required")
            return None
        if not isinstance(name, str):
            raise InvalidParamsError("'name' must be a string")
        if not name.strip():
            raise InvalidParamsError("'name' must not be empty")
        return name

    def _serialize_scene(self, scene: Any, *, scene_index: int) -> dict[str, Any]:
        tempo_enabled = bool(scene.tempo_enabled)
        raw_tempo = float(scene.tempo)
        tempo = raw_tempo if tempo_enabled and raw_tempo >= 0.0 else None

        time_signature_enabled = bool(scene.time_signature_enabled)
        raw_numerator = int(scene.time_signature_numerator)
        raw_denominator = int(scene.time_signature_denominator)
        numerator = (
            raw_numerator if time_signature_enabled and raw_numerator >= 0 else None
        )
        denominator = (
            raw_denominator if time_signature_enabled and raw_denominator >= 0 else None
        )

        return {
            "scene_index": scene_index,
            "name": str(scene.name),
            "is_empty": bool(scene.is_empty),
            "is_triggered": bool(scene.is_triggered),
            "tempo_enabled": tempo_enabled,
            "tempo": tempo,
            "time_signature_enabled": time_signature_enabled,
            "time_signature_numerator": numerator,
            "time_signature_denominator": denominator,
        }

    def handle_get_all(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all scenes with their outward API shape."""

        def _read() -> dict[str, Any]:
            scenes = [
                self._serialize_scene(scene, scene_index=scene_index)
                for scene_index, scene in enumerate(self._song.scenes, start=1)
            ]
            return {"scenes": scenes}

        return self._run_on_main_thread(_read)

    def handle_create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a scene at the requested Live insertion index."""
        index = params.get("index", -1)
        if isinstance(index, bool) or not isinstance(index, int):
            raise InvalidParamsError("'index' must be an integer")
        name = self._require_name(params, required=False)

        def _create() -> dict[str, Any]:
            song = self._song
            scenes = song.scenes
            scene_count = len(scenes)
            if index < -1 or (index != -1 and (index < 0 or index > scene_count - 1)):
                raise InvalidParamsError(
                    f"'index' must be -1 (append) or 0..{scene_count - 1}, got {index}"
                )

            created_scene = song.create_scene(index)
            new_lo_index = len(song.scenes) - 1 if index == -1 else index
            new_scene = song.scenes[new_lo_index]

            if created_scene is not None:
                for candidate_lo_index, candidate_scene in enumerate(song.scenes):
                    if candidate_scene is created_scene:
                        new_scene = candidate_scene
                        new_lo_index = candidate_lo_index
                        break

            if name is not None:
                new_scene.name = name

            return {
                "scene_index": new_lo_index + 1,
                "name": str(new_scene.name),
            }

        return self._run_on_main_thread(_create)

    def handle_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Delete a scene by its 1-based index."""

        def _delete() -> dict[str, Any]:
            _scene, scene_index, lo_index = self._resolve_scene(params)
            self._song.delete_scene(lo_index)
            return {"scene_index": scene_index}

        return self._run_on_main_thread(_delete)

    def handle_duplicate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Duplicate a scene; the copy is inserted immediately after the source."""

        def _duplicate() -> dict[str, Any]:
            _scene, scene_index, lo_index = self._resolve_scene(params)
            self._song.duplicate_scene(lo_index)
            return {
                "source_scene_index": scene_index,
                "new_scene_index": scene_index + 1,
            }

        return self._run_on_main_thread(_duplicate)

    def handle_fire(self, params: dict[str, Any]) -> dict[str, Any]:
        """Launch a scene."""

        def _fire() -> dict[str, Any]:
            scene, scene_index, _lo_index = self._resolve_scene(params)
            scene.fire()
            return {"scene_index": scene_index}

        return self._run_on_main_thread(_fire)

    def handle_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stop clip slots in the targeted scene row only."""

        def _stop() -> dict[str, Any]:
            _scene, scene_index, lo_index = self._resolve_scene(params)
            for track in self._song.tracks:
                clip_slots = getattr(track, "clip_slots", ())
                if lo_index < len(clip_slots):
                    clip_slots[lo_index].stop()
            return {"scene_index": scene_index}

        return self._run_on_main_thread(_stop)

    def handle_set_name(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rename a scene."""
        name = self._require_name(params, required=True)
        assert name is not None

        def _set_name() -> dict[str, Any]:
            scene, scene_index, _lo_index = self._resolve_scene(params)
            scene.name = name
            return {"scene_index": scene_index, "name": str(scene.name)}

        return self._run_on_main_thread(_set_name)


__all__ = ["SceneHandler"]
