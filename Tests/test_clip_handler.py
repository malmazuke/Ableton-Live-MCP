"""Tests for the Remote Script ClipHandler."""

from __future__ import annotations

import pytest
from AbletonLiveMCP.dispatcher import InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.clip import ClipHandler

from Tests.test_track_handler import _FakeControlSurface, _FakeSong, _Track


class _Clip:
    def __init__(
        self,
        name: str = "Clip",
        length: float = 4.0,
        *,
        audio: bool = False,
    ) -> None:
        self.name = name
        self.length = length
        self.is_audio_clip = audio
        self.is_midi_clip = not audio
        self.is_playing = False
        self.is_recording = False


class _Slot:
    def __init__(self, clip: _Clip | None = None) -> None:
        self._clip = clip
        self.has_clip = clip is not None

    @property
    def clip(self) -> _Clip:
        return self._clip

    def create_clip(self, length: float) -> None:
        if self.has_clip:
            raise RuntimeError("already has clip")
        self._clip = _Clip(name="MIDI Clip", length=length, audio=False)
        self.has_clip = True

    def delete_clip(self) -> None:
        self._clip = None
        self.has_clip = False

    def fire(self, *args: object, **kwargs: object) -> None:
        pass

    def stop(self) -> None:
        pass


def _track_with_slots(*slots: _Slot) -> _Track:
    t = _Track("Midi", midi=True)
    t.clip_slots = list(slots)
    return t


class _SongWithClipTracks(_FakeSong):
    def __init__(self) -> None:
        self.tracks = [
            _track_with_slots(_Slot(), _Slot(_Clip("Hi", 2.0)), _Slot()),
        ]


class _TrackDup(_Track):
    def duplicate_clip_slot(self, index: int) -> None:
        src_slot = self.clip_slots[index]
        if not src_slot.has_clip:
            raise RuntimeError("no clip")
        for i in range(index + 1, len(self.clip_slots)):
            if not self.clip_slots[i].has_clip:
                c = src_slot.clip
                self.clip_slots[i]._clip = _Clip(
                    name=c.name + " 2",
                    length=c.length,
                    audio=c.is_audio_clip,
                )
                self.clip_slots[i].has_clip = True
                return
        raise RuntimeError("no empty slot")


@pytest.fixture
def song_clip() -> _SongWithClipTracks:
    return _SongWithClipTracks()


@pytest.fixture
def handler_clip(song_clip: _SongWithClipTracks) -> ClipHandler:
    return ClipHandler(_FakeControlSurface(song_clip))


class TestCreateDelete:
    def test_create_empty_slot(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_create(
            {"track_index": 1, "clip_slot_index": 1, "length": 8.0},
        )
        assert result == {
            "track_index": 1,
            "clip_slot_index": 1,
            "length": 8.0,
        }
        slot = song_clip.tracks[0].clip_slots[0]
        assert slot.has_clip
        assert slot.clip.length == 8.0

    def test_create_rejects_audio_track(self) -> None:
        song = _FakeSong()
        song.tracks = [_Track("A", midi=False, audio=True)]
        song.tracks[0].clip_slots = [_Slot()]
        h = ClipHandler(_FakeControlSurface(song))
        with pytest.raises(InvalidParamsError, match="MIDI"):
            h.handle_create({"track_index": 1, "clip_slot_index": 1})

    def test_delete(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_delete({"track_index": 1, "clip_slot_index": 2})
        assert result == {"track_index": 1, "clip_slot_index": 2}
        assert not song_clip.tracks[0].clip_slots[1].has_clip


class TestDuplicate:
    def test_duplicate_finds_new_slot(self) -> None:
        song = _FakeSong()
        song.tracks = [
            _TrackDup(
                "T",
                midi=True,
            ),
        ]
        song.tracks[0].clip_slots = [
            _Slot(_Clip("a", 1.0)),
            _Slot(),
            _Slot(),
        ]
        h = ClipHandler(_FakeControlSurface(song))
        result = h.handle_duplicate({"track_index": 1, "clip_slot_index": 1})
        assert result["new_clip_slot_index"] == 2
        assert song.tracks[0].clip_slots[1].has_clip


class TestSetNameFireStopGetInfo:
    def test_set_name(self, handler_clip: ClipHandler) -> None:
        r = handler_clip.handle_set_name(
            {"track_index": 1, "clip_slot_index": 2, "name": "Renamed"},
        )
        assert r == {
            "track_index": 1,
            "clip_slot_index": 2,
            "name": "Renamed",
        }

    def test_fire_stop(self, handler_clip: ClipHandler) -> None:
        assert handler_clip.handle_fire(
            {"track_index": 1, "clip_slot_index": 2},
        ) == {"track_index": 1, "clip_slot_index": 2}
        assert handler_clip.handle_stop(
            {"track_index": 1, "clip_slot_index": 2},
        ) == {"track_index": 1, "clip_slot_index": 2}

    def test_get_info(self, handler_clip: ClipHandler) -> None:
        r = handler_clip.handle_get_info({"track_index": 1, "clip_slot_index": 2})
        assert r["name"] == "Hi"
        assert r["length"] == 2.0
        assert r["is_midi_clip"] is True
        assert r["is_audio_clip"] is False

    def test_get_info_empty_raises(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(NotFoundError, match="No clip"):
            handler_clip.handle_get_info({"track_index": 1, "clip_slot_index": 1})
