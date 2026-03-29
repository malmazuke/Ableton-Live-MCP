"""Tests for the Remote Script MixerHandler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError
from AbletonLiveMCP.handlers.mixer import MixerHandler


class _MixerDevice:
    def __init__(
        self,
        volume: float = 0.8,
        pan: float = 0.1,
        sends: list[float] | None = None,
    ) -> None:
        self.volume = MagicMock(value=volume)
        self.panning = MagicMock(value=pan)
        self.sends = [MagicMock(value=value) for value in sends or []]


class _Track:
    def __init__(
        self,
        name: str,
        *,
        volume: float = 0.8,
        pan: float = 0.1,
        sends: list[float] | None = None,
    ) -> None:
        self.name = name
        self.mixer_device = _MixerDevice(volume=volume, pan=pan, sends=sends)


class _Song:
    def __init__(self) -> None:
        self.tracks = [
            _Track("Track 1", volume=0.82, pan=0.15, sends=[0.2, 0.4]),
            _Track("Track 2", volume=0.63, pan=-0.35, sends=[0.1, 0.3]),
        ]
        self.return_tracks = [
            _Track("A Return", volume=0.55, pan=-0.2),
            _Track("B Return", volume=0.48, pan=0.25),
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


class TestGetReturnTracks:
    def test_serialization_shape(self, handler: MixerHandler) -> None:
        result = handler.handle_get_return_tracks({})

        assert result == {
            "return_tracks": [
                {
                    "return_index": 1,
                    "name": "A Return",
                    "volume": 0.55,
                    "pan": -0.2,
                },
                {
                    "return_index": 2,
                    "name": "B Return",
                    "volume": 0.48,
                    "pan": 0.25,
                },
            ]
        }


class TestSetSendLevel:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_send_level(
            {"track_index": 2, "send_index": 1, "level": 0.45}
        )

        assert result == {"track_index": 2, "send_index": 1, "level": 0.45}
        assert song.tracks[1].mixer_device.sends[0].value == 0.45

    def test_missing_send_returns_not_found(self, handler: MixerHandler) -> None:
        dispatcher = Dispatcher(_FakeControlSurface())
        dispatcher.register("mixer", handler)

        response = dispatcher.dispatch(
            "mixer.set_send_level",
            {"track_index": 1, "send_index": 9, "level": 0.5},
            "mix-send-missing",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "Send 9" in response["error"]["message"]

    def test_out_of_range_level(self, handler: MixerHandler) -> None:
        with pytest.raises(InvalidParamsError, match="level"):
            handler.handle_set_send_level(
                {"track_index": 1, "send_index": 1, "level": 1.1}
            )


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


class TestSetReturnVolume:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_return_volume({"return_index": 1, "volume": 0.67})

        assert result == {"return_index": 1, "volume": 0.67}
        assert song.return_tracks[0].mixer_device.volume.value == 0.67

    def test_missing_return_track_returns_not_found(self, song: _Song) -> None:
        dispatcher = Dispatcher(_FakeControlSurface(song))
        dispatcher.register("mixer", MixerHandler(_FakeControlSurface(song)))

        response = dispatcher.dispatch(
            "mixer.set_return_volume",
            {"return_index": 99, "volume": 0.5},
            "mix-return-missing",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "Return track 99" in response["error"]["message"]

    def test_out_of_range_volume(self, handler: MixerHandler) -> None:
        with pytest.raises(InvalidParamsError, match="volume"):
            handler.handle_set_return_volume({"return_index": 1, "volume": -0.1})


class TestSetReturnPan:
    def test_success(self, handler: MixerHandler, song: _Song) -> None:
        result = handler.handle_set_return_pan({"return_index": 2, "pan": -0.6})

        assert result == {"return_index": 2, "pan": -0.6}
        assert song.return_tracks[1].mixer_device.panning.value == -0.6

    def test_out_of_range_pan(self, handler: MixerHandler) -> None:
        with pytest.raises(InvalidParamsError, match="pan"):
            handler.handle_set_return_pan({"return_index": 1, "pan": 1.2})


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

    def test_dispatcher_routes_invalid_params_for_send_level(self, song: _Song) -> None:
        dispatcher = Dispatcher(_FakeControlSurface(song))
        dispatcher.register("mixer", MixerHandler(_FakeControlSurface(song)))

        response = dispatcher.dispatch(
            "mixer.set_send_level",
            {"track_index": 1, "send_index": "bad", "level": 0.4},
            "mix-invalid-send",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "INVALID_PARAMS"
        assert "send_index" in response["error"]["message"]
