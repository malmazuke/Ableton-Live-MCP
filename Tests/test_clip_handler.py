"""Tests for the Remote Script ClipHandler."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from AbletonLiveMCP.dispatcher import InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.clip import ClipHandler

from Tests.test_track_handler import _FakeControlSurface, _FakeSong, _Track


def _note(
    note_id: int,
    pitch: int,
    start_time: float,
    duration: float,
    velocity: float = 100.0,
    *,
    mute: bool = False,
    probability: float | None = None,
    velocity_deviation: float | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "note_id": note_id,
        "pitch": pitch,
        "start_time": start_time,
        "duration": duration,
        "velocity": velocity,
        "mute": mute,
    }
    if probability is not None:
        result["probability"] = probability
    if velocity_deviation is not None:
        result["velocity_deviation"] = velocity_deviation
    return result


class _Clip:
    def __init__(
        self,
        name: str = "Clip",
        length: float = 4.0,
        *,
        audio: bool = False,
        gain: float = 1.0,
        pitch_coarse: int = 0,
        warp_mode: int = 0,
        warping: bool = True,
        available_warp_modes: list[int] | None = None,
        notes: list[dict[str, object]] | None = None,
    ) -> None:
        self.name = name
        self.length = length
        self.is_audio_clip = audio
        self.is_midi_clip = not audio
        self.loop_start = 0.0
        self.loop_end = length
        self.looping = True
        self.color_index = 0
        self.is_playing = False
        self.is_recording = False
        self._gain = float(gain)
        self.pitch_coarse = pitch_coarse
        self.warp_mode = warp_mode
        self.warping = warping
        self.available_warp_modes = list(available_warp_modes or [0, 1, 2, 6])
        self._notes: list[dict[str, object]] = []
        self._next_note_id = 1
        self._automation_envelopes: dict[int, _AutomationEnvelope] = {}

        for note in notes or []:
            self._notes.append(dict(note))
            self._next_note_id = max(self._next_note_id, int(note["note_id"]) + 1)

    @property
    def notes(self) -> list[dict[str, object]]:
        return [dict(note) for note in self._notes]

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, value: float) -> None:
        self._gain = float(value)

    @property
    def gain_display_string(self) -> str:
        if self._gain <= 0.0:
            return "-inf dB"
        return f"{20.0 * math.log10(self._gain):.1f} dB"

    def get_all_notes_extended(self):
        return tuple(self.notes)

    def add_new_notes(self, payload) -> tuple[int, ...]:
        assert isinstance(payload, tuple)

        note_ids: list[int] = []
        for note in payload:
            assert isinstance(note, dict)
            note_id = self._next_note_id
            self._next_note_id += 1
            stored: dict[str, object] = {
                "note_id": note_id,
                "pitch": int(note["pitch"]),
                "start_time": float(note["start_time"]),
                "duration": float(note["duration"]),
                "velocity": float(note["velocity"]),
                "mute": bool(note.get("mute", False)),
            }
            if "probability" in note:
                stored["probability"] = float(note["probability"])
            if "velocity_deviation" in note:
                stored["velocity_deviation"] = float(note["velocity_deviation"])
            self._notes.append(stored)
            note_ids.append(note_id)

        self._notes.sort(
            key=lambda item: (
                float(item["start_time"]),
                int(item["pitch"]),
                int(item["note_id"]),
            )
        )
        return tuple(note_ids)

    def remove_notes_by_id(self, note_ids: list[int]) -> None:
        note_id_set = set(note_ids)
        self._notes = [
            note for note in self._notes if int(note["note_id"]) not in note_id_set
        ]

    @property
    def has_envelopes(self) -> bool:
        return bool(self._automation_envelopes)

    def automation_envelope(self, parameter) -> _AutomationEnvelope | None:
        return self._automation_envelopes.get(id(parameter))

    def create_automation_envelope(self, parameter) -> _AutomationEnvelope:
        envelope = _AutomationEnvelope()
        self._automation_envelopes[id(parameter)] = envelope
        return envelope

    def clear_envelope(self, parameter) -> None:
        self._automation_envelopes.pop(id(parameter), None)


class _AutomationEvent:
    def __init__(
        self,
        time: float,
        value: float | None,
        step_length: float = 0.0,
    ) -> None:
        self.time = time
        self.value = value
        self.step_length = step_length


class _AutomationEnvelope:
    def __init__(self, events: list[_AutomationEvent] | None = None) -> None:
        self.events = list(events or [])

    def events_in_range(self, start: float, end: float):
        stop = end if end >= start else start
        return tuple(event for event in self.events if start <= event.time <= stop)

    def insert_step(self, time: float, step_length: float, value: float) -> None:
        self.events.append(_AutomationEvent(time, value, step_length))
        self.events.sort(key=lambda event: event.time)


class _UnreadableAutomationEnvelope:
    def __init__(self, events: list[_AutomationEvent] | None = None) -> None:
        self.events = list(events or [])

    def insert_step(self, time: float, step_length: float, value: float) -> None:
        self.events.append(_AutomationEvent(time, value, step_length))


class _Parameter:
    def __init__(
        self,
        name: str,
        value: float,
        minimum: float,
        maximum: float,
    ) -> None:
        self.name = name
        self.value = value
        self.min = minimum
        self.max = maximum


class _Device:
    def __init__(self, name: str, parameters: list[_Parameter]) -> None:
        self.name = name
        self.parameters = parameters


class _Slot:
    def __init__(self, clip: _Clip | None = None) -> None:
        self._clip = clip
        self.has_clip = clip is not None

    @property
    def clip(self) -> _Clip:
        assert self._clip is not None
        return self._clip

    def create_clip(self, length: float) -> None:
        if self.has_clip:
            raise RuntimeError("already has clip")
        self._clip = _Clip(name="MIDI Clip", length=length, audio=False)
        self.has_clip = True

    def create_audio_clip(self, file_path: str) -> None:
        if self.has_clip:
            raise RuntimeError("already has clip")
        self._clip = _Clip(name=Path(file_path).stem, length=6.5, audio=True)
        self.has_clip = True

    def delete_clip(self) -> None:
        self._clip = None
        self.has_clip = False

    def fire(self, *args: object, **kwargs: object) -> None:
        pass

    def stop(self) -> None:
        pass


def _track_with_slots(
    *slots: _Slot,
    midi: bool = True,
    audio: bool = False,
    devices: list[_Device] | None = None,
) -> _Track:
    track = _Track("Track", midi=midi, audio=audio)
    track.clip_slots = list(slots)
    if devices is not None:
        track.devices = devices
    return track


class _SongWithClipTracks(_FakeSong):
    def __init__(self) -> None:
        self.tracks = [
            _track_with_slots(
                _Slot(),
                _Slot(
                    _Clip(
                        "Hi",
                        2.0,
                        notes=[
                            _note(1, 60, 0.0, 0.5, 100.0),
                            _note(
                                2,
                                64,
                                1.0,
                                0.25,
                                96.0,
                                probability=0.5,
                            ),
                            _note(
                                3,
                                67,
                                2.0,
                                0.75,
                                110.0,
                                mute=True,
                                velocity_deviation=4.0,
                            ),
                        ],
                    )
                ),
                _Slot(),
                devices=[
                    _Device(
                        "Utility",
                        [
                            _Parameter("Gain", 0.0, -35.0, 35.0),
                            _Parameter("Mute", 0.0, 0.0, 1.0),
                        ],
                    ),
                    _Device(
                        "Auto Filter",
                        [
                            _Parameter("Device On", 1.0, 0.0, 1.0),
                            _Parameter("Frequency", 5000.0, 20.0, 20000.0),
                        ],
                    ),
                ],
            ),
            _track_with_slots(
                _Slot(
                    _Clip(
                        "Drums",
                        6.5,
                        audio=True,
                        gain=0.5,
                        pitch_coarse=0,
                        warp_mode=0,
                        available_warp_modes=[0, 1, 2, 6],
                    )
                ),
                _Slot(),
                midi=False,
                audio=True,
            ),
        ]


class _TrackDup(_Track):
    def duplicate_clip_slot(self, index: int) -> None:
        src_slot = self.clip_slots[index]
        if not src_slot.has_clip:
            raise RuntimeError("no clip")
        for slot_index in range(index + 1, len(self.clip_slots)):
            if not self.clip_slots[slot_index].has_clip:
                clip = src_slot.clip
                self.clip_slots[slot_index]._clip = _Clip(
                    name=clip.name + " 2",
                    length=clip.length,
                    audio=clip.is_audio_clip,
                    gain=clip.gain,
                    pitch_coarse=clip.pitch_coarse,
                    warp_mode=clip.warp_mode,
                    warping=clip.warping,
                    available_warp_modes=list(clip.available_warp_modes),
                    notes=clip.notes,
                )
                self.clip_slots[slot_index].has_clip = True
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
        song.tracks = [_track_with_slots(_Slot(), midi=False, audio=True)]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(InvalidParamsError, match="MIDI"):
            handler.handle_create({"track_index": 1, "clip_slot_index": 1})

    def test_delete(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_delete({"track_index": 1, "clip_slot_index": 2})
        assert result == {"track_index": 1, "clip_slot_index": 2}
        assert not song_clip.tracks[0].clip_slots[1].has_clip


class TestImportAudio:
    def test_success_on_audio_track(self, tmp_path) -> None:
        file_path = tmp_path / "drums.wav"
        file_path.write_bytes(b"RIFF")
        song = _FakeSong()
        song.tracks = [_track_with_slots(_Slot(), _Slot(), midi=False, audio=True)]
        handler = ClipHandler(_FakeControlSurface(song))

        result = handler.handle_import_audio(
            {
                "track_index": 1,
                "clip_slot_index": 1,
                "file_path": str(file_path),
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 1,
            "name": "drums",
            "file_path": str(file_path),
            "length": 6.5,
            "is_audio_clip": True,
        }
        slot = song.tracks[0].clip_slots[0]
        assert slot.has_clip
        assert slot.clip.is_audio_clip is True

    def test_rejects_midi_only_track(self, tmp_path) -> None:
        file_path = tmp_path / "drums.wav"
        file_path.write_bytes(b"RIFF")
        song = _FakeSong()
        song.tracks = [_track_with_slots(_Slot(), _Slot(), midi=True, audio=False)]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(InvalidParamsError, match="does not accept audio clips"):
            handler.handle_import_audio(
                {
                    "track_index": 1,
                    "clip_slot_index": 1,
                    "file_path": str(file_path),
                }
            )

    def test_rejects_occupied_slot(self, tmp_path) -> None:
        file_path = tmp_path / "drums.wav"
        file_path.write_bytes(b"RIFF")
        song = _FakeSong()
        song.tracks = [
            _track_with_slots(
                _Slot(_Clip("Existing", audio=True)),
                midi=False,
                audio=True,
            )
        ]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(InvalidParamsError, match="already has a clip"):
            handler.handle_import_audio(
                {
                    "track_index": 1,
                    "clip_slot_index": 1,
                    "file_path": str(file_path),
                }
            )

    def test_rejects_missing_file(self, tmp_path) -> None:
        file_path = tmp_path / "missing.wav"
        song = _FakeSong()
        song.tracks = [_track_with_slots(_Slot(), midi=False, audio=True)]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(NotFoundError, match="File does not exist"):
            handler.handle_import_audio(
                {
                    "track_index": 1,
                    "clip_slot_index": 1,
                    "file_path": str(file_path),
                }
            )

    def test_rejects_malformed_file_path(self) -> None:
        song = _FakeSong()
        song.tracks = [_track_with_slots(_Slot(), midi=False, audio=True)]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(
            InvalidParamsError,
            match="absolute local filesystem path",
        ):
            handler.handle_import_audio(
                {
                    "track_index": 1,
                    "clip_slot_index": 1,
                    "file_path": "samples/drums.wav",
                }
            )


class TestDuplicate:
    def test_duplicate_finds_new_slot(self) -> None:
        song = _FakeSong()
        song.tracks = [_TrackDup("T", midi=True)]
        song.tracks[0].clip_slots = [
            _Slot(_Clip("a", 1.0)),
            _Slot(),
            _Slot(),
        ]
        handler = ClipHandler(_FakeControlSurface(song))

        result = handler.handle_duplicate({"track_index": 1, "clip_slot_index": 1})

        assert result["new_clip_slot_index"] == 2
        assert song.tracks[0].clip_slots[1].has_clip


class TestSetNameFireStopGetInfo:
    def test_set_name(self, handler_clip: ClipHandler) -> None:
        result = handler_clip.handle_set_name(
            {"track_index": 1, "clip_slot_index": 2, "name": "Renamed"},
        )
        assert result == {
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
        result = handler_clip.handle_get_info({"track_index": 1, "clip_slot_index": 2})
        assert result["name"] == "Hi"
        assert result["length"] == 2.0
        assert result["is_midi_clip"] is True
        assert result["is_audio_clip"] is False

    def test_get_info_empty_raises(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(NotFoundError, match="No clip"):
            handler_clip.handle_get_info({"track_index": 1, "clip_slot_index": 1})


class TestLoopAndColor:
    def test_set_loop_success(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_set_loop(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "loop_start": 0.5,
                "loop_end": 1.5,
                "looping": True,
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "loop_start": 0.5,
            "loop_end": 1.5,
            "looping": True,
        }
        clip = song_clip.tracks[0].clip_slots[1].clip
        assert clip.loop_start == 0.5
        assert clip.loop_end == 1.5
        assert clip.looping is True

    def test_set_loop_rejects_invalid_range(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(InvalidParamsError, match="loop_end"):
            handler_clip.handle_set_loop(
                {
                    "track_index": 1,
                    "clip_slot_index": 2,
                    "loop_start": 2.0,
                    "loop_end": 2.0,
                }
            )

    def test_set_color_success(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_set_color(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "color_index": 11,
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "color_index": 11,
        }
        assert song_clip.tracks[0].clip_slots[1].clip.color_index == 11

    def test_set_color_missing_clip_raises_not_found(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="No clip"):
            handler_clip.handle_set_color(
                {
                    "track_index": 1,
                    "clip_slot_index": 1,
                    "color_index": 3,
                }
            )


class TestAudioClipOperations:
    def test_set_clip_pitch_success_on_audio_clip(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_set_pitch(
            {"track_index": 2, "clip_slot_index": 1, "semitones": -7},
        )

        assert result == {
            "track_index": 2,
            "clip_slot_index": 1,
            "semitones": -7,
        }
        assert song_clip.tracks[1].clip_slots[0].clip.pitch_coarse == -7

    def test_set_clip_pitch_rejects_midi_clip(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="not an audio clip"):
            handler_clip.handle_set_pitch(
                {"track_index": 1, "clip_slot_index": 2, "semitones": 3},
            )

    def test_set_clip_warp_mode_success_on_audio_clip(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        song_clip.tracks[1].clip_slots[0].clip.warping = False

        result = handler_clip.handle_set_warp_mode(
            {"track_index": 2, "clip_slot_index": 1, "warp_mode": 2},
        )

        assert result == {
            "track_index": 2,
            "clip_slot_index": 1,
            "warp_mode": 2,
        }
        clip = song_clip.tracks[1].clip_slots[0].clip
        assert clip.warping is True
        assert clip.warp_mode == 2

    def test_set_clip_warp_mode_rejects_invalid_mode(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        with pytest.raises(
            InvalidParamsError, match="available modes: \\[0, 1, 2, 6\\]"
        ):
            handler_clip.handle_set_warp_mode(
                {"track_index": 2, "clip_slot_index": 1, "warp_mode": 99},
            )

    def test_set_clip_gain_success(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        result = handler_clip.handle_set_gain(
            {"track_index": 2, "clip_slot_index": 1, "gain": 0.25},
        )

        assert result == {
            "track_index": 2,
            "clip_slot_index": 1,
            "gain": 0.25,
            "gain_display_string": "-12.0 dB",
        }

    def test_set_clip_gain_missing_clip_returns_not_found(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="No clip in slot 2 on track 2"):
            handler_clip.handle_set_gain(
                {"track_index": 2, "clip_slot_index": 2, "gain": 0.5},
            )


class TestGetNotes:
    def test_returns_all_notes(self, handler_clip: ClipHandler) -> None:
        result = handler_clip.handle_get_notes({"track_index": 1, "clip_slot_index": 2})

        assert result["track_index"] == 1
        assert result["clip_slot_index"] == 2
        assert len(result["notes"]) == 3
        assert result["notes"][0]["note_id"] == 1
        assert result["notes"][1]["probability"] == 0.5
        assert result["notes"][2]["velocity_deviation"] == 4.0

    def test_empty_slot_raises_not_found(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(NotFoundError, match="No clip"):
            handler_clip.handle_get_notes({"track_index": 1, "clip_slot_index": 1})

    def test_audio_clip_rejected(self) -> None:
        song = _FakeSong()
        song.tracks = [
            _track_with_slots(
                _Slot(_Clip("Audio", audio=True)),
                midi=False,
                audio=True,
            ),
        ]
        handler = ClipHandler(_FakeControlSurface(song))

        with pytest.raises(InvalidParamsError, match="not a MIDI clip"):
            handler.handle_get_notes({"track_index": 1, "clip_slot_index": 1})


class TestAddNotes:
    def test_add_notes_returns_ids_and_count(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_add_notes(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "notes": [
                    {
                        "pitch": 72,
                        "start_time": 3.0,
                        "duration": 0.5,
                        "velocity": 90.0,
                        "mute": False,
                        "probability": 0.9,
                    }
                ],
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "added_count": 1,
            "note_ids": [4],
        }
        notes = song_clip.tracks[0].clip_slots[1].clip.notes
        assert len(notes) == 4
        assert notes[-1]["note_id"] == 4
        assert notes[-1]["probability"] == 0.9

    def test_rejects_malformed_note_payload(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(InvalidParamsError, match="unexpected keys"):
            handler_clip.handle_add_notes(
                {
                    "track_index": 1,
                    "clip_slot_index": 2,
                    "notes": [
                        {
                            "pitch": 60,
                            "start_time": 0.0,
                            "duration": 0.5,
                            "velocity": 100.0,
                            "note_id": 99,
                        }
                    ],
                }
            )


class TestRemoveNotes:
    def test_remove_notes_with_time_span(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_remove_notes(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "from_pitch": 60,
                "pitch_span": 8,
                "from_time": 0.5,
                "time_span": 1.0,
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "removed_count": 1,
        }
        remaining_ids = [
            int(note["note_id"])
            for note in song_clip.tracks[0].clip_slots[1].clip.notes
        ]
        assert remaining_ids == [1, 3]

    def test_remove_notes_without_time_span_removes_from_time_onward(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_remove_notes(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "from_pitch": 67,
                "pitch_span": 1,
                "from_time": 1.0,
            }
        )

        assert result["removed_count"] == 1
        remaining_pitches = [
            int(note["pitch"]) for note in song_clip.tracks[0].clip_slots[1].clip.notes
        ]
        assert remaining_pitches == [60, 64]


class TestSetNotes:
    def test_replaces_all_notes(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_set_notes(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "notes": [
                    {
                        "pitch": 72,
                        "start_time": 0.0,
                        "duration": 1.0,
                        "velocity": 80.0,
                        "mute": False,
                    },
                    {
                        "pitch": 76,
                        "start_time": 1.0,
                        "duration": 0.5,
                        "velocity": 90.0,
                        "mute": True,
                    },
                ],
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "removed_count": 3,
            "added_count": 2,
            "note_ids": [4, 5],
        }
        notes = song_clip.tracks[0].clip_slots[1].clip.notes
        assert [int(note["pitch"]) for note in notes] == [72, 76]
        assert [int(note["note_id"]) for note in notes] == [4, 5]

    def test_empty_note_list_clears_clip(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        result = handler_clip.handle_set_notes(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "notes": [],
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "removed_count": 3,
            "added_count": 0,
            "note_ids": [],
        }
        assert song_clip.tracks[0].clip_slots[1].clip.notes == []

    def test_rejects_bad_region_params(self, handler_clip: ClipHandler) -> None:
        with pytest.raises(InvalidParamsError, match="must not exceed 128"):
            handler_clip.handle_remove_notes(
                {
                    "track_index": 1,
                    "clip_slot_index": 2,
                    "from_pitch": 120,
                    "pitch_span": 16,
                }
            )


class TestAutomation:
    def test_get_automation_resolves_device_and_parameter(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        clip = song_clip.tracks[0].clip_slots[1].clip
        parameter = song_clip.tracks[0].devices[1].parameters[1]
        clip._automation_envelopes[id(parameter)] = _AutomationEnvelope(
            [
                _AutomationEvent(0.0, 250.0),
                _AutomationEvent(1.0, 5000.0, 0.5),
            ]
        )

        result = handler_clip.handle_get_automation(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "device_index": 2,
                "parameter_index": 2,
            }
        )

        assert result["device_name"] == "Auto Filter"
        assert result["parameter_name"] == "Frequency"
        assert result["points"] == [
            {"time": 0.0, "value": 250.0, "step_length": 0.0},
            {"time": 1.0, "value": 5000.0, "step_length": 0.5},
        ]

    def test_get_automation_skips_events_without_numeric_value(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        clip = song_clip.tracks[0].clip_slots[1].clip
        parameter = song_clip.tracks[0].devices[1].parameters[1]
        clip._automation_envelopes[id(parameter)] = _AutomationEnvelope(
            [
                _AutomationEvent(0.0, 250.0),
                _AutomationEvent(0.5, None),
            ]
        )

        result = handler_clip.handle_get_automation(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "device_index": 2,
                "parameter_index": 2,
            }
        )

        assert result["points"] == [{"time": 0.0, "value": 250.0, "step_length": 0.0}]

    def test_get_automation_skips_non_finite_values(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        clip = song_clip.tracks[0].clip_slots[1].clip
        parameter = song_clip.tracks[0].devices[1].parameters[1]
        clip._automation_envelopes[id(parameter)] = _AutomationEnvelope(
            [
                _AutomationEvent(0.0, 250.0),
                _AutomationEvent(0.5, float("nan")),
            ]
        )

        result = handler_clip.handle_get_automation(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "device_index": 2,
                "parameter_index": 2,
            }
        )

        assert result["points"] == [{"time": 0.0, "value": 250.0, "step_length": 0.0}]

    def test_set_automation_replaces_existing_envelope(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        clip = song_clip.tracks[0].clip_slots[1].clip
        parameter = song_clip.tracks[0].devices[1].parameters[1]
        clip._automation_envelopes[id(parameter)] = _AutomationEnvelope(
            [_AutomationEvent(0.0, 1000.0, 0.25)]
        )

        result = handler_clip.handle_set_automation(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "device_index": 2,
                "parameter_index": 2,
                "points": [
                    {"time": 0.0, "value": 250.0, "step_length": 0.25},
                    {"time": 1.0, "value": 5000.0, "step_length": 0.5},
                ],
            }
        )

        assert result == {
            "track_index": 1,
            "clip_slot_index": 2,
            "device_index": 2,
            "parameter_index": 2,
            "device_name": "Auto Filter",
            "parameter_name": "Frequency",
            "point_count": 2,
        }
        envelope = clip.automation_envelope(parameter)
        assert envelope is not None
        assert [(event.time, event.value) for event in envelope.events] == [
            (0.0, 250.0),
            (1.0, 5000.0),
        ]

    def test_set_automation_rejects_non_numeric_value(
        self,
        handler_clip: ClipHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="'points\\[1\\]'\\.value"):
            handler_clip.handle_set_automation(
                {
                    "track_index": 1,
                    "clip_slot_index": 2,
                    "device_index": 2,
                    "parameter_index": 2,
                    "points": [{"time": 0.0, "value": "loud"}],
                }
            )

    def test_get_automation_raises_when_events_are_unreadable(
        self,
        handler_clip: ClipHandler,
        song_clip: _SongWithClipTracks,
    ) -> None:
        clip = song_clip.tracks[0].clip_slots[1].clip
        parameter = song_clip.tracks[0].devices[1].parameters[1]
        clip._automation_envelopes[id(parameter)] = _UnreadableAutomationEnvelope(
            [_AutomationEvent(0.0, 250.0)]
        )

        with pytest.raises(RuntimeError, match="readable envelope events"):
            handler_clip.handle_get_automation(
                {
                    "track_index": 1,
                    "clip_slot_index": 2,
                    "device_index": 2,
                    "parameter_index": 2,
                }
            )
