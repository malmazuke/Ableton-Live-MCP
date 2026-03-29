"""Tests for the Remote Script SceneHandler."""

from __future__ import annotations

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.scene import SceneHandler


class _ClipSlot:
    def __init__(self) -> None:
        self.stop_count = 0

    def stop(self) -> None:
        self.stop_count += 1


class _Track:
    def __init__(self, clip_slot_count: int) -> None:
        self.clip_slots = [_ClipSlot() for _ in range(clip_slot_count)]


class _Scene:
    def __init__(
        self,
        name: str,
        *,
        is_empty: bool,
        is_triggered: bool = False,
        tempo_enabled: bool = False,
        tempo: float = -1.0,
        time_signature_enabled: bool = False,
        time_signature_numerator: int = -1,
        time_signature_denominator: int = -1,
    ) -> None:
        self.name = name
        self.is_empty = is_empty
        self.is_triggered = is_triggered
        self.tempo_enabled = tempo_enabled
        self.tempo = tempo
        self.time_signature_enabled = time_signature_enabled
        self.time_signature_numerator = time_signature_numerator
        self.time_signature_denominator = time_signature_denominator
        self.fire_count = 0

    def fire(self) -> None:
        self.fire_count += 1


class _SceneSong:
    def __init__(self) -> None:
        self.scenes = [
            _Scene(
                "Intro",
                is_empty=False,
                tempo_enabled=True,
                tempo=120.0,
                time_signature_enabled=True,
                time_signature_numerator=4,
                time_signature_denominator=4,
            ),
            _Scene(
                "Breakdown",
                is_empty=True,
                is_triggered=True,
                tempo_enabled=False,
                tempo=-1.0,
                time_signature_enabled=False,
                time_signature_numerator=-1,
                time_signature_denominator=-1,
            ),
            _Scene("Outro", is_empty=False),
        ]
        self.tracks = [_Track(3), _Track(3)]

    def create_scene(self, index: int) -> _Scene:
        insert_index = len(self.scenes) if index == -1 else index
        new_scene = _Scene(f"Scene {insert_index + 1}", is_empty=True)
        self.scenes.insert(insert_index, new_scene)
        for track in self.tracks:
            track.clip_slots.insert(insert_index, _ClipSlot())
        return new_scene

    def delete_scene(self, index: int) -> None:
        del self.scenes[index]
        for track in self.tracks:
            del track.clip_slots[index]

    def duplicate_scene(self, index: int) -> None:
        source = self.scenes[index]
        duplicate = _Scene(
            f"{source.name} Copy",
            is_empty=source.is_empty,
            is_triggered=source.is_triggered,
            tempo_enabled=source.tempo_enabled,
            tempo=source.tempo,
            time_signature_enabled=source.time_signature_enabled,
            time_signature_numerator=source.time_signature_numerator,
            time_signature_denominator=source.time_signature_denominator,
        )
        self.scenes.insert(index + 1, duplicate)
        for track in self.tracks:
            track.clip_slots.insert(index + 1, _ClipSlot())


class _FakeControlSurface:
    def __init__(self, song: _SceneSong | None = None) -> None:
        self._song = song or _SceneSong()

    def song(self) -> _SceneSong:
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def show_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay, callback) -> None:
        callback()


@pytest.fixture
def scene_song() -> _SceneSong:
    return _SceneSong()


@pytest.fixture
def scene_handler(scene_song: _SceneSong) -> SceneHandler:
    return SceneHandler(_FakeControlSurface(scene_song))


class TestGetScenes:
    def test_serializes_scene_shape(self, scene_handler: SceneHandler) -> None:
        result = scene_handler.handle_get_all({})

        assert result == {
            "scenes": [
                {
                    "scene_index": 1,
                    "name": "Intro",
                    "is_empty": False,
                    "is_triggered": False,
                    "tempo_enabled": True,
                    "tempo": 120.0,
                    "time_signature_enabled": True,
                    "time_signature_numerator": 4,
                    "time_signature_denominator": 4,
                },
                {
                    "scene_index": 2,
                    "name": "Breakdown",
                    "is_empty": True,
                    "is_triggered": True,
                    "tempo_enabled": False,
                    "tempo": None,
                    "time_signature_enabled": False,
                    "time_signature_numerator": None,
                    "time_signature_denominator": None,
                },
                {
                    "scene_index": 3,
                    "name": "Outro",
                    "is_empty": False,
                    "is_triggered": False,
                    "tempo_enabled": False,
                    "tempo": None,
                    "time_signature_enabled": False,
                    "time_signature_numerator": None,
                    "time_signature_denominator": None,
                },
            ]
        }


class TestCreateScene:
    def test_append_scene_by_default(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_create({})

        assert result == {"scene_index": 4, "name": "Scene 4"}
        assert len(scene_song.scenes) == 4
        assert len(scene_song.tracks[0].clip_slots) == 4

    def test_insert_scene_with_name(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_create({"index": 1, "name": "Bridge"})

        assert result == {"scene_index": 2, "name": "Bridge"}
        assert scene_song.scenes[1].name == "Bridge"
        assert len(scene_song.tracks[1].clip_slots) == 4

    def test_rejects_invalid_create_index(self, scene_handler: SceneHandler) -> None:
        with pytest.raises(InvalidParamsError, match="index"):
            scene_handler.handle_create({"index": 99})

    def test_rejects_empty_create_name(self, scene_handler: SceneHandler) -> None:
        with pytest.raises(InvalidParamsError, match="name"):
            scene_handler.handle_create({"name": "  "})


class TestSceneActions:
    def test_duplicate_scene(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_duplicate({"scene_index": 1})

        assert result == {"source_scene_index": 1, "new_scene_index": 2}
        assert scene_song.scenes[1].name == "Intro Copy"

    def test_delete_scene(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_delete({"scene_index": 2})

        assert result == {"scene_index": 2}
        assert [scene.name for scene in scene_song.scenes] == ["Intro", "Outro"]
        assert len(scene_song.tracks[0].clip_slots) == 2

    def test_fire_scene(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_fire({"scene_index": 2})

        assert result == {"scene_index": 2}
        assert scene_song.scenes[1].fire_count == 1

    def test_stop_scene_only_targets_requested_row(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_stop({"scene_index": 2})

        assert result == {"scene_index": 2}
        for track in scene_song.tracks:
            assert [slot.stop_count for slot in track.clip_slots] == [0, 1, 0]

    def test_set_scene_name(
        self,
        scene_handler: SceneHandler,
        scene_song: _SceneSong,
    ) -> None:
        result = scene_handler.handle_set_name({"scene_index": 3, "name": "Finale"})

        assert result == {"scene_index": 3, "name": "Finale"}
        assert scene_song.scenes[2].name == "Finale"


class TestErrors:
    def test_missing_scene_is_not_found(self, scene_handler: SceneHandler) -> None:
        with pytest.raises(NotFoundError, match="Scene 99"):
            scene_handler.handle_fire({"scene_index": 99})

    def test_invalid_scene_index_is_invalid_params(
        self,
        scene_handler: SceneHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="scene_index"):
            scene_handler.handle_delete({"scene_index": 0})

    def test_invalid_name_is_invalid_params(self, scene_handler: SceneHandler) -> None:
        with pytest.raises(InvalidParamsError, match="name"):
            scene_handler.handle_set_name({"scene_index": 1, "name": ""})


class TestDispatcherIntegration:
    def test_scene_not_found_maps_via_dispatcher(self, scene_song: _SceneSong) -> None:
        dispatcher = Dispatcher(_FakeControlSurface(scene_song))
        dispatcher.register("scene", SceneHandler(_FakeControlSurface(scene_song)))

        response = dispatcher.dispatch("scene.fire", {"scene_index": 10}, "scene-1")

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"

    def test_scene_handler_is_registered_on_dispatcher_call(
        self,
        scene_song: _SceneSong,
    ) -> None:
        dispatcher = Dispatcher(_FakeControlSurface(scene_song))
        dispatcher.register("scene", SceneHandler(_FakeControlSurface(scene_song)))

        response = dispatcher.dispatch("scene.get_all", {}, "scene-2")

        assert response["status"] == "ok"
        assert len(response["result"]["scenes"]) == 3
