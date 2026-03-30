"""Tests for the Remote Script ArrangementHandler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.arrangement import ArrangementHandler


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


class _FakeControlSurface:
    def __init__(self, song: object) -> None:
        self._song = song

    def song(self):
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def show_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay, callback):
        callback()


class _ArrangementClip:
    def __init__(
        self,
        name: str,
        start_time: float,
        length: float,
        *,
        audio: bool = False,
    ) -> None:
        self.name = name
        self.start_time = start_time
        self.length = length
        self.end_time = start_time + length
        self.is_audio_clip = audio
        self.is_midi_clip = not audio


class _TakeLane:
    def __init__(
        self,
        name: str,
        *,
        arrangement_clips: list[_ArrangementClip] | None = None,
    ) -> None:
        self.name = name
        self.arrangement_clips = list(arrangement_clips or [])
        self._sort_arrangement_clips()

    def _sort_arrangement_clips(self) -> None:
        self.arrangement_clips.sort(
            key=lambda clip: (clip.start_time, clip.end_time, clip.name)
        )

    def create_midi_clip(self, start_time: float, length: float) -> None:
        self.arrangement_clips.append(
            _ArrangementClip("New MIDI Clip", start_time, length, audio=False)
        )
        self._sort_arrangement_clips()

    def create_audio_clip(self, file_path: str, start_time: float) -> None:
        self.arrangement_clips.append(
            _ArrangementClip(Path(file_path).stem, start_time, 9.25, audio=True)
        )
        self._sort_arrangement_clips()


class _CuePoint:
    def __init__(self, name: str, time: float) -> None:
        self.name = name
        self.time = time


class _ArrangementTrack(_Track):
    def __init__(
        self,
        name: str,
        *,
        midi: bool = True,
        audio: bool = False,
        arrangement_clips: list[_ArrangementClip] | None = None,
        take_lanes: list[_TakeLane] | None = None,
    ) -> None:
        super().__init__(name, midi=midi, audio=audio)
        self.arrangement_clips = list(arrangement_clips or [])
        self.take_lanes = list(take_lanes or [])
        self._sort_arrangement_clips()

    def _sort_arrangement_clips(self) -> None:
        self.arrangement_clips.sort(
            key=lambda clip: (clip.start_time, clip.end_time, clip.name)
        )

    def create_midi_clip(self, start_time: float, length: float) -> None:
        if not self.has_midi_input:
            raise RuntimeError("track does not accept MIDI clips")
        self.arrangement_clips.append(
            _ArrangementClip("New MIDI Clip", start_time, length, audio=False)
        )
        self._sort_arrangement_clips()

    def create_audio_clip(self, file_path: str, start_time: float) -> None:
        if not self.has_audio_input:
            raise RuntimeError("track does not accept audio clips")
        self.arrangement_clips.append(
            _ArrangementClip(Path(file_path).stem, start_time, 9.25, audio=True)
        )
        self._sort_arrangement_clips()

    def duplicate_clip_to_arrangement(
        self,
        clip: _ArrangementClip,
        destination_time: float,
    ) -> None:
        if clip.is_midi_clip and not self.has_midi_input:
            raise RuntimeError("target track does not accept MIDI clips")
        if clip.is_audio_clip and not self.has_audio_input:
            raise RuntimeError("target track does not accept audio clips")

        self.arrangement_clips.append(
            _ArrangementClip(
                f"{clip.name} Copy",
                destination_time,
                clip.length,
                audio=clip.is_audio_clip,
            )
        )
        self._sort_arrangement_clips()

    def delete_clip(self, clip: _ArrangementClip) -> None:
        self.arrangement_clips.remove(clip)

    def create_take_lane(self) -> None:
        lane_number = len(self.take_lanes) + 1
        self.take_lanes.append(_TakeLane(f"Take Lane {lane_number}"))


class _ArrangementSong:
    def __init__(self) -> None:
        self.song_length = 96.0
        self.loop = False
        self.loop_start = 0.0
        self.loop_length = 4.0
        self.current_song_time = 0.0
        self.tracks = [
            _ArrangementTrack(
                "MIDI 1",
                midi=True,
                arrangement_clips=[
                    _ArrangementClip("Verse", 0.0, 8.0),
                    _ArrangementClip("Hook", 16.0, 4.0),
                ],
                take_lanes=[
                    _TakeLane(
                        "Comp A",
                        arrangement_clips=[_ArrangementClip("Take 1", 8.0, 4.0)],
                    )
                ],
            ),
            _ArrangementTrack(
                "Audio 1",
                midi=False,
                audio=True,
                arrangement_clips=[
                    _ArrangementClip("Vocal", 4.0, 8.0, audio=True),
                ],
                take_lanes=[
                    _TakeLane(
                        "Audio Lane",
                        arrangement_clips=[
                            _ArrangementClip("vox", 12.0, 8.0, audio=True)
                        ],
                    )
                ],
            ),
            _ArrangementTrack("MIDI 2", midi=True, arrangement_clips=[], take_lanes=[]),
        ]
        self.cue_points = [
            _CuePoint("Intro", 0.0),
            _CuePoint("Breakdown", 16.0),
        ]

    def _sort_cue_points(self) -> None:
        self.cue_points.sort(key=lambda cue_point: (cue_point.time, cue_point.name))

    def set_or_delete_cue(self) -> None:
        for cue_point in list(self.cue_points):
            if cue_point.time == self.current_song_time:
                self.cue_points.remove(cue_point)
                self._sort_cue_points()
                return

        self.cue_points.append(
            _CuePoint(f"Locator {len(self.cue_points) + 1}", self.current_song_time)
        )
        self._sort_cue_points()


class _LaggyLoopSong(_ArrangementSong):
    def __init__(self) -> None:
        self._loop_current = False
        self._loop_visible = False
        super().__init__()

    @property
    def loop(self) -> bool:
        visible = self._loop_visible
        self._loop_visible = self._loop_current
        return visible

    @loop.setter
    def loop(self, value: bool) -> None:
        self._loop_current = bool(value)


@pytest.fixture
def arrangement_song() -> _ArrangementSong:
    return _ArrangementSong()


@pytest.fixture
def arrangement_handler(arrangement_song: _ArrangementSong) -> ArrangementHandler:
    return ArrangementHandler(_FakeControlSurface(arrangement_song))


class TestGetArrangementClips:
    def test_single_track(self, arrangement_handler: ArrangementHandler) -> None:
        result = arrangement_handler.handle_get_clips({"track_index": 1})

        assert result["track_index"] == 1
        assert len(result["clips"]) == 2
        assert result["clips"][0]["track_index"] == 1
        assert result["clips"][0]["clip_index"] == 1

    def test_all_tracks_when_track_omitted(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        result = arrangement_handler.handle_get_clips({})

        assert result["track_index"] is None
        assert len(result["clips"]) == 3
        assert [clip["track_index"] for clip in result["clips"]] == [1, 1, 2]

    def test_serialization_shape(self, arrangement_handler: ArrangementHandler) -> None:
        result = arrangement_handler.handle_get_clips({"track_index": 2})

        assert result["clips"] == [
            {
                "track_index": 2,
                "clip_index": 1,
                "name": "Vocal",
                "start_time": 4.0,
                "end_time": 12.0,
                "length": 8.0,
                "is_audio_clip": True,
                "is_midi_clip": False,
            }
        ]

    def test_missing_track_raises_not_found(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            arrangement_handler.handle_get_clips({"track_index": 99})


class TestCreateArrangementClip:
    def test_success_on_midi_track(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_create_clip(
            {"track_index": 1, "start_time": 24.0, "length": 8.0}
        )

        assert result == {
            "track_index": 1,
            "clip_index": 3,
            "start_time": 24.0,
            "length": 8.0,
            "name": "New MIDI Clip",
        }
        assert len(arrangement_song.tracks[0].arrangement_clips) == 3

    def test_rejects_non_midi_track(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="does not accept MIDI clips"):
            arrangement_handler.handle_create_clip(
                {"track_index": 2, "start_time": 8.0, "length": 4.0}
            )


class TestImportAudioToArrangement:
    def test_success_on_audio_track(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vocal.wav"
        file_path.write_bytes(b"RIFF")

        result = arrangement_handler.handle_import_audio(
            {
                "track_index": 2,
                "file_path": str(file_path),
                "start_time": 12.0,
            }
        )

        assert result == {
            "track_index": 2,
            "clip_index": 2,
            "name": "vocal",
            "file_path": str(file_path),
            "start_time": 12.0,
            "length": 9.25,
            "is_audio_clip": True,
        }
        assert len(arrangement_song.tracks[1].arrangement_clips) == 2

    def test_rejects_midi_only_track(
        self,
        arrangement_handler: ArrangementHandler,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vocal.wav"
        file_path.write_bytes(b"RIFF")

        with pytest.raises(InvalidParamsError, match="does not accept audio clips"):
            arrangement_handler.handle_import_audio(
                {
                    "track_index": 1,
                    "file_path": str(file_path),
                    "start_time": 8.0,
                }
            )

    def test_rejects_missing_file(
        self,
        arrangement_handler: ArrangementHandler,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "missing.wav"

        with pytest.raises(NotFoundError, match="File does not exist"):
            arrangement_handler.handle_import_audio(
                {
                    "track_index": 2,
                    "file_path": str(file_path),
                    "start_time": 8.0,
                }
            )

    def test_rejects_malformed_file_path(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(
            InvalidParamsError,
            match="absolute local filesystem path",
        ):
            arrangement_handler.handle_import_audio(
                {
                    "track_index": 2,
                    "file_path": "audio/vocal.wav",
                    "start_time": 8.0,
                }
            )


class TestTakeLanes:
    def test_list_take_lanes(self, arrangement_handler: ArrangementHandler) -> None:
        result = arrangement_handler.handle_get_take_lanes({"track_index": 1})

        assert result == {
            "track_index": 1,
            "take_lanes": [
                {
                    "take_lane_index": 1,
                    "name": "Comp A",
                    "clips": [
                        {
                            "clip_index": 1,
                            "name": "Take 1",
                            "start_time": 8.0,
                            "end_time": 12.0,
                            "length": 4.0,
                            "is_audio_clip": False,
                            "is_midi_clip": True,
                        }
                    ],
                }
            ],
        }

    def test_create_take_lane_without_name(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_create_take_lane({"track_index": 1})

        assert result == {
            "track_index": 1,
            "take_lane_index": 2,
            "name": "Take Lane 2",
        }
        assert arrangement_song.tracks[0].take_lanes[1].name == "Take Lane 2"

    def test_create_take_lane_with_name(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_create_take_lane(
            {"track_index": 1, "name": "  MCP Take Lane  "}
        )

        assert result == {
            "track_index": 1,
            "take_lane_index": 2,
            "name": "MCP Take Lane",
        }
        assert arrangement_song.tracks[0].take_lanes[1].name == "MCP Take Lane"

    def test_rename_take_lane(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_set_take_lane_name(
            {
                "track_index": 1,
                "take_lane_index": 1,
                "name": "  Renamed Lane  ",
            }
        )

        assert result == {
            "track_index": 1,
            "take_lane_index": 1,
            "name": "Renamed Lane",
        }
        assert arrangement_song.tracks[0].take_lanes[0].name == "Renamed Lane"

    def test_create_midi_clip_in_take_lane(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_create_take_lane_midi_clip(
            {
                "track_index": 1,
                "take_lane_index": 1,
                "start_time": 16.0,
                "length": 4.0,
            }
        )

        assert result == {
            "track_index": 1,
            "take_lane_index": 1,
            "clip_index": 2,
            "start_time": 16.0,
            "length": 4.0,
            "name": "New MIDI Clip",
        }
        assert len(arrangement_song.tracks[0].take_lanes[0].arrangement_clips) == 2

    def test_import_audio_to_take_lane(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vox.wav"
        file_path.write_bytes(b"RIFF")

        result = arrangement_handler.handle_import_audio_to_take_lane(
            {
                "track_index": 2,
                "take_lane_index": 1,
                "file_path": str(file_path),
                "start_time": 24.0,
            }
        )

        assert result == {
            "track_index": 2,
            "take_lane_index": 1,
            "clip_index": 2,
            "name": "vox",
            "file_path": str(file_path),
            "start_time": 24.0,
            "length": 9.25,
            "is_audio_clip": True,
        }
        assert len(arrangement_song.tracks[1].take_lanes[0].arrangement_clips) == 2

    def test_missing_track_raises_not_found(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            arrangement_handler.handle_get_take_lanes({"track_index": 99})

    def test_missing_take_lane_raises_not_found(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Take lane 99"):
            arrangement_handler.handle_set_take_lane_name(
                {"track_index": 1, "take_lane_index": 99, "name": "Lane"}
            )

    def test_blank_name_rejected(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="non-empty string"):
            arrangement_handler.handle_create_take_lane(
                {"track_index": 1, "name": "   "}
            )

    def test_create_midi_clip_rejects_audio_track(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="does not accept MIDI clips"):
            arrangement_handler.handle_create_take_lane_midi_clip(
                {
                    "track_index": 2,
                    "take_lane_index": 1,
                    "start_time": 8.0,
                    "length": 4.0,
                }
            )

    def test_import_audio_rejects_midi_track(
        self,
        arrangement_handler: ArrangementHandler,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vox.wav"
        file_path.write_bytes(b"RIFF")

        with pytest.raises(InvalidParamsError, match="does not accept audio clips"):
            arrangement_handler.handle_import_audio_to_take_lane(
                {
                    "track_index": 1,
                    "take_lane_index": 1,
                    "file_path": str(file_path),
                    "start_time": 8.0,
                }
            )


class TestMoveArrangementClip:
    def test_same_track_success(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_move_clip(
            {
                "track_index": 1,
                "clip_index": 1,
                "new_start_time": 24.0,
            }
        )

        assert result == {
            "source_track_index": 1,
            "source_clip_index": 1,
            "target_track_index": 1,
            "target_clip_index": 2,
            "start_time": 24.0,
        }
        clips = arrangement_song.tracks[0].arrangement_clips
        assert [clip.name for clip in clips] == ["Hook", "Verse Copy"]
        assert [clip.start_time for clip in clips] == [16.0, 24.0]

    def test_cross_track_success(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_move_clip(
            {
                "track_index": 1,
                "clip_index": 2,
                "new_start_time": 32.0,
                "new_track_index": 3,
            }
        )

        assert result == {
            "source_track_index": 1,
            "source_clip_index": 2,
            "target_track_index": 3,
            "target_clip_index": 1,
            "start_time": 32.0,
        }
        assert len(arrangement_song.tracks[0].arrangement_clips) == 1
        assert arrangement_song.tracks[2].arrangement_clips[0].name == "Hook Copy"

    def test_missing_clip_raises_not_found(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Arrangement clip 99"):
            arrangement_handler.handle_move_clip(
                {
                    "track_index": 1,
                    "clip_index": 99,
                    "new_start_time": 8.0,
                }
            )

    def test_cross_track_rejects_incompatible_target(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="does not accept MIDI"):
            arrangement_handler.handle_move_clip(
                {
                    "track_index": 1,
                    "clip_index": 1,
                    "new_start_time": 8.0,
                    "new_track_index": 2,
                }
            )


class TestArrangementLengthAndLoop:
    def test_get_length_reads_song_length(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        result = arrangement_handler.handle_get_length({})

        assert result == {"song_length": 96.0}

    def test_set_loop_success(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_set_loop(
            {"start_time": 8.0, "end_time": 24.0, "enabled": True}
        )

        assert result == {"start_time": 8.0, "end_time": 24.0, "enabled": True}
        assert arrangement_song.loop is True
        assert arrangement_song.loop_start == 8.0
        assert arrangement_song.loop_length == 16.0

    def test_set_loop_rejects_invalid_range(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="end_time"):
            arrangement_handler.handle_set_loop(
                {"start_time": 8.0, "end_time": 8.0, "enabled": True}
            )

    def test_set_loop_requires_boolean_enabled(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="enabled"):
            arrangement_handler.handle_set_loop(
                {"start_time": 8.0, "end_time": 16.0, "enabled": "yes"}
            )

    def test_set_loop_returns_requested_state_when_live_read_lags(self) -> None:
        laggy_song = _LaggyLoopSong()
        handler = ArrangementHandler(_FakeControlSurface(laggy_song))

        result = handler.handle_set_loop(
            {"start_time": 12.0, "end_time": 20.0, "enabled": True}
        )

        assert result == {"start_time": 12.0, "end_time": 20.0, "enabled": True}
        assert laggy_song._loop_current is True


class TestLocators:
    def test_get_locators_serializes_shape(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        result = arrangement_handler.handle_get_locators({})

        assert result == {
            "locators": [
                {"locator_index": 1, "name": "Intro", "time": 0.0},
                {"locator_index": 2, "name": "Breakdown", "time": 16.0},
            ]
        }

    def test_create_locator_without_name_preserves_playhead(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        arrangement_song.current_song_time = 4.0

        result = arrangement_handler.handle_create_locator({"time": 24.0})

        assert result == {
            "locator_index": 3,
            "name": "Locator 3",
            "time": 24.0,
        }
        assert arrangement_song.current_song_time == 4.0
        assert [cue.name for cue in arrangement_song.cue_points] == [
            "Intro",
            "Breakdown",
            "Locator 3",
        ]

    def test_create_locator_with_name_trims_input(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        arrangement_song.current_song_time = 12.0

        result = arrangement_handler.handle_create_locator(
            {"time": 12.0, "name": "  Drop  "}
        )

        assert result == {
            "locator_index": 2,
            "name": "Drop",
            "time": 12.0,
        }
        assert arrangement_song.current_song_time == 12.0

    def test_create_locator_rejects_duplicate_time(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        arrangement_song.current_song_time = 4.0

        with pytest.raises(InvalidParamsError, match="already exists"):
            arrangement_handler.handle_create_locator({"time": 16.0})

        assert arrangement_song.current_song_time == 4.0

    def test_delete_locator_preserves_playhead(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        arrangement_song.current_song_time = 4.0

        result = arrangement_handler.handle_delete_locator({"locator_index": 2})

        assert result == {
            "locator_index": 2,
            "name": "Breakdown",
            "time": 16.0,
        }
        assert arrangement_song.current_song_time == 4.0
        assert [cue.name for cue in arrangement_song.cue_points] == ["Intro"]

    def test_set_locator_name(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        result = arrangement_handler.handle_set_locator_name(
            {"locator_index": 1, "name": "  Verse  "}
        )

        assert result == {"locator_index": 1, "name": "Verse", "time": 0.0}
        assert arrangement_song.cue_points[0].name == "Verse"

    def test_jump_to_time_updates_playhead(
        self,
        arrangement_handler: ArrangementHandler,
        arrangement_song: _ArrangementSong,
    ) -> None:
        arrangement_song.current_song_time = 2.0

        result = arrangement_handler.handle_jump_to_time({"time": 32.0})

        assert result == {"time": 32.0}
        assert arrangement_song.current_song_time == 32.0

    @pytest.mark.parametrize(
        "params,match",
        [
            ({"locator_index": 0}, "at least 1"),
            ({"locator_index": -1}, "at least 1"),
            ({"time": -1.0}, "at least 0.0"),
            ({"locator_index": 1, "name": "   "}, "non-empty string"),
        ],
    )
    def test_invalid_params(
        self,
        arrangement_handler: ArrangementHandler,
        params: dict[str, object],
        match: str,
    ) -> None:
        if "time" in params:
            with pytest.raises(InvalidParamsError, match=match):
                arrangement_handler.handle_jump_to_time(params)
            return
        if "name" in params and "locator_index" in params:
            with pytest.raises(InvalidParamsError, match=match):
                arrangement_handler.handle_set_locator_name(params)
            return
        with pytest.raises(InvalidParamsError, match=match):
            arrangement_handler.handle_delete_locator(params)

    def test_missing_locator_raises_not_found(
        self,
        arrangement_handler: ArrangementHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Locator 99"):
            arrangement_handler.handle_delete_locator({"locator_index": 99})


class TestDispatcherIntegration:
    def test_arrangement_get_length_via_dispatcher(
        self,
        arrangement_song: _ArrangementSong,
    ) -> None:
        control_surface = _FakeControlSurface(arrangement_song)
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("arrangement", ArrangementHandler(control_surface))

        response = dispatcher.dispatch("arrangement.get_length", {}, "arr-1")

        assert response["status"] == "ok"
        assert response["result"] == {"song_length": 96.0}

    def test_arrangement_get_locators_via_dispatcher(
        self,
        arrangement_song: _ArrangementSong,
    ) -> None:
        control_surface = _FakeControlSurface(arrangement_song)
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("arrangement", ArrangementHandler(control_surface))

        response = dispatcher.dispatch("arrangement.get_locators", {}, "arr-2")

        assert response["status"] == "ok"
        assert response["result"]["locators"][0]["name"] == "Intro"

    def test_arrangement_take_lanes_via_dispatcher(
        self,
        arrangement_song: _ArrangementSong,
    ) -> None:
        control_surface = _FakeControlSurface(arrangement_song)
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("arrangement", ArrangementHandler(control_surface))

        response = dispatcher.dispatch(
            "arrangement.get_take_lanes",
            {"track_index": 1},
            "arr-3",
        )

        assert response["status"] == "ok"
        assert response["result"]["take_lanes"][0]["name"] == "Comp A"
