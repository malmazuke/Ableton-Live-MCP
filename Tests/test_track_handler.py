"""Tests for the Remote Script TrackHandler."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.track import TrackHandler


class _Mixer:
    def __init__(self, volume: float = 0.8, pan: float = 0.1) -> None:
        self.volume = MagicMock(value=volume)
        self.panning = MagicMock(value=pan)


class _Slot:
    def __init__(self, has_clip: bool = False) -> None:
        self.has_clip = has_clip


class _Device:
    def __init__(self, name: str) -> None:
        self.name = name


class _Track:
    def __init__(
        self,
        name: str,
        *,
        midi: bool = True,
        audio: bool = False,
        can_be_armed: bool = True,
    ) -> None:
        self.name = name
        self.has_audio_input = audio
        self.has_midi_input = midi
        self.mute = False
        self.solo = False
        self.arm = False
        self.can_be_armed = can_be_armed
        self.mixer_device = _Mixer()
        self.devices = [_Device("Device A")]
        self.clip_slots = [_Slot(False), _Slot(True)]


class _FakeSong:
    def __init__(self) -> None:
        self.tracks = [_Track("One"), _Track("Two")]

    def create_midi_track(self, index: int) -> None:
        t = _Track("New MIDI", midi=True)
        if index == -1:
            self.tracks.append(t)
        else:
            self.tracks.insert(index, t)

    def create_audio_track(self, index: int) -> None:
        t = _Track("New Audio", midi=False, audio=True)
        if index == -1:
            self.tracks.append(t)
        else:
            self.tracks.insert(index, t)

    def delete_track(self, index: int) -> None:
        del self.tracks[index]

    def duplicate_track(self, index: int) -> None:
        src = self.tracks[index]
        dup = copy.copy(src)
        dup.mixer_device = _Mixer(
            volume=src.mixer_device.volume.value,
            pan=src.mixer_device.panning.value,
        )
        self.tracks.insert(index + 1, dup)


class _FakeControlSurface:
    def __init__(self, song: _FakeSong | None = None) -> None:
        self._song = song or _FakeSong()

    def song(self):
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def show_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay, callback):
        callback()


@pytest.fixture
def song() -> _FakeSong:
    return _FakeSong()


@pytest.fixture
def handler(song: _FakeSong) -> TrackHandler:
    return TrackHandler(_FakeControlSurface(song))


class TestGetInfo:
    def test_returns_expected_shape(self, handler: TrackHandler) -> None:
        result = handler.handle_get_info({"track_index": 1})

        assert result["name"] == "One"
        assert result["track_index"] == 1
        assert result["is_midi_track"] is True
        assert result["device_names"] == ["Device A"]
        assert result["clip_slot_has_clip"] == [False, True]

    def test_raises_not_found(self, handler: TrackHandler) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            handler.handle_get_info({"track_index": 99})

    def test_missing_track_index(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="track_index"):
            handler.handle_get_info({})


class TestCreateMidi:
    def test_append(self, handler: TrackHandler, song: _FakeSong) -> None:
        n_before = len(song.tracks)
        result = handler.handle_create_midi({"index": -1})

        assert result["track_index"] == n_before + 1
        assert len(song.tracks) == n_before + 1

    def test_insert_at_zero(self, handler: TrackHandler, song: _FakeSong) -> None:
        handler.handle_create_midi({"index": 0})

        assert song.tracks[0].name == "New MIDI"

    def test_invalid_index(self, handler: TrackHandler, song: _FakeSong) -> None:
        with pytest.raises(InvalidParamsError, match="index"):
            handler.handle_create_midi({"index": 50})


class TestDeleteDuplicate:
    def test_delete(self, handler: TrackHandler, song: _FakeSong) -> None:
        result = handler.handle_delete({"track_index": 2})

        assert result["track_index"] == 2
        assert len(song.tracks) == 1

    def test_duplicate(self, handler: TrackHandler, song: _FakeSong) -> None:
        result = handler.handle_duplicate({"track_index": 1})

        assert result == {"source_track_index": 1, "new_track_index": 2}
        assert len(song.tracks) == 3


class TestSetters:
    def test_set_name(self, handler: TrackHandler, song: _FakeSong) -> None:
        handler.handle_set_name({"track_index": 1, "name": "Renamed"})

        assert song.tracks[0].name == "Renamed"

    def test_set_mute(self, handler: TrackHandler, song: _FakeSong) -> None:
        handler.handle_set_mute({"track_index": 1, "mute": True})

        assert song.tracks[0].mute is True

    def test_set_mute_requires_bool(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="mute"):
            handler.handle_set_mute({"track_index": 1, "mute": "yes"})

    def test_set_arm_unarmable(self, handler: TrackHandler, song: _FakeSong) -> None:
        song.tracks[0].can_be_armed = False

        with pytest.raises(InvalidParamsError, match="cannot be armed"):
            handler.handle_set_arm({"track_index": 1, "arm": True})


class TestDispatcherNotFoundIntegration:
    def test_track_get_info_not_found_via_dispatcher(self, song: _FakeSong) -> None:
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch("track.get_info", {"track_index": 10}, "r1")

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "NOT_FOUND"
        assert "10" in resp["error"]["message"]
