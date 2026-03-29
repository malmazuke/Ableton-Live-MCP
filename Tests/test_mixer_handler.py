"""Tests for the Remote Script MixerHandler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError
from AbletonLiveMCP.handlers.mixer import MixerHandler


class _MixerDevice:
    def __init__(self, volume: float = 0.8, pan: float = 0.1) -> None:
        self.volume = MagicMock(value=volume)
        self.panning = MagicMock(value=pan)


class _Track:
    def __init__(self, name: str, *, volume: float = 0.8, pan: float = 0.1) -> None:
        self.name = name
        self.mixer_device = _MixerDevice(volume=volume, pan=pan)


class _Song:
    def __init__(self) -> None:
        self.tracks = [
            _Track("Track 1", volume=0.82, pan=0.15),
            _Track("Track 2", volume=0.63, pan=-0.35),
        ]
        self.master_track = _Track("Master", volume=0.9, pan=0.0)


class _FakeControlSurface:
    def __init__(self, song: _Song | None = None) -> None:
        self._song = song or _Song()

    def song(self) -> _Song:
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay: int, callback) -> None:
        callback()


@pytest.fixture
def song() -> _Song:
    return _Song()


@pytest.fixture
def handler(song: _Song) -> MixerHandler:
    return MixerHandler(_FakeControlSurface(song))


class TestSetTrackVolume:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_track_volume({"track_index": 2, "volume": 0.45})

        assert result == {"track_index": 2, "volume": 0.45}
        assert song.tracks[1].mixer_device.volume.value == 0.45

    def test_missing_track_returns_not_found(self, handler: MixerHandler) -> None:
        dispatcher = Dispatcher(_FakeControlSurface())
        dispatcher.register("mixer", handler)

        response = dispatcher.dispatch(
            "mixer.set_track_volume",
            {"track_index": 99, "volume": 0.5},
            "mix-1",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "Track 99" in response["error"]["message"]

    def test_out_of_range_volume(self, handler: MixerHandler) -> None:
        with pytest.raises(InvalidParamsError, match="volume"):
            handler.handle_set_track_volume({"track_index": 1, "volume": 1.1})


class TestSetTrackPan:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_track_pan({"track_index": 1, "pan": -0.5})

        assert result == {"track_index": 1, "pan": -0.5}
        assert song.tracks[0].mixer_device.panning.value == -0.5

    def test_out_of_range_pan(self, handler: MixerHandler) -> None:
        with pytest.raises(InvalidParamsError, match="pan"):
            handler.handle_set_track_pan({"track_index": 1, "pan": -1.5})


class TestGetMasterInfo:
    def test_serialization_shape(self, handler: MixerHandler) -> None:
        result = handler.handle_get_master_info({})

        assert result == {
            "name": "Master",
            "volume": 0.9,
            "pan": 0.0,
        }


class TestSetMasterVolume:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_master_volume({"volume": 0.72})

        assert result == {"volume": 0.72}
        assert song.master_track.mixer_device.volume.value == 0.72


class TestDispatcherRegistration:
    def test_dispatcher_routes_mixer_commands(self, song: _Song) -> None:
        dispatcher = Dispatcher(_FakeControlSurface(song))
        dispatcher.register("mixer", MixerHandler(_FakeControlSurface(song)))

        response = dispatcher.dispatch("mixer.get_master_info", {}, "mix-2")

        assert response["status"] == "ok"
        assert response["result"] == {
            "name": "Master",
            "volume": 0.9,
            "pan": 0.0,
        }
