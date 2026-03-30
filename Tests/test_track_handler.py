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


class _RoutingOption:
    def __init__(self, identifier: int, display_name: str) -> None:
        self._identifier = identifier
        self.display_name = display_name

    def __hash__(self) -> int:
        return self._identifier


class _Track:
    def __init__(
        self,
        name: str,
        *,
        midi: bool = True,
        audio: bool = False,
        can_be_armed: bool = True,
        routing_supported: bool = True,
        clip_slots: list[_Slot] | None = None,
        device_names: list[str] | None = None,
        supports_mute: bool = True,
        supports_solo: bool = True,
        supports_arm: bool = True,
        is_foldable: bool = False,
        fold_state: bool = False,
        group_track: _Track | None = None,
    ) -> None:
        self.name = name
        self.has_audio_input = audio
        self.has_midi_input = midi
        self.is_foldable = is_foldable
        self.is_grouped = group_track is not None
        if is_foldable:
            self.fold_state = fold_state
        if group_track is not None:
            self.group_track = group_track
        if supports_mute:
            self.mute = False
        if supports_solo:
            self.solo = False
        if supports_arm:
            self.arm = False
        if can_be_armed:
            self.can_be_armed = can_be_armed
        self.mixer_device = _Mixer()
        names = device_names if device_names is not None else ["Device A"]
        self.devices = [_Device(name) for name in names]
        if clip_slots is None:
            self.clip_slots = [_Slot(False), _Slot(True)]
        else:
            self.clip_slots = clip_slots

        if routing_supported:
            self._available_input_routing_types = [
                _RoutingOption(101, "Ext. In"),
                _RoutingOption(102, "Resampling"),
            ]
            self._input_channels_by_type = {
                "101": [
                    _RoutingOption(201, "1"),
                    _RoutingOption(202, "2"),
                ],
                "102": [
                    _RoutingOption(211, "Post Mixer"),
                    _RoutingOption(212, "Pre FX"),
                ],
            }
            self._available_output_routing_types = [
                _RoutingOption(301, "Master"),
                _RoutingOption(302, "Sends Only"),
            ]
            self._output_channels_by_type = {
                "301": [
                    _RoutingOption(401, "Stereo"),
                    _RoutingOption(402, "1"),
                ],
                "302": [
                    _RoutingOption(411, "Post FX"),
                    _RoutingOption(412, "Pre FX"),
                ],
            }
            self._input_routing_type = self._available_input_routing_types[0]
            self._input_routing_channel = self._input_channels_by_type[
                str(hash(self._input_routing_type))
            ][0]
            self._output_routing_type = self._available_output_routing_types[0]
            self._output_routing_channel = self._output_channels_by_type[
                str(hash(self._output_routing_type))
            ][0]
        else:
            self._available_input_routing_types = []
            self._input_channels_by_type = {}
            self._available_output_routing_types = []
            self._output_channels_by_type = {}
            self._input_routing_type = None
            self._input_routing_channel = None
            self._output_routing_type = None
            self._output_routing_channel = None

    @property
    def input_routing_type(self) -> _RoutingOption | None:
        return self._input_routing_type

    @input_routing_type.setter
    def input_routing_type(self, option: _RoutingOption) -> None:
        self._input_routing_type = option
        channels = self.available_input_routing_channels
        if channels:
            self._input_routing_channel = channels[0]

    @property
    def input_routing_channel(self) -> _RoutingOption | None:
        return self._input_routing_channel

    @input_routing_channel.setter
    def input_routing_channel(self, option: _RoutingOption) -> None:
        self._input_routing_channel = option

    @property
    def output_routing_type(self) -> _RoutingOption | None:
        return self._output_routing_type

    @output_routing_type.setter
    def output_routing_type(self, option: _RoutingOption) -> None:
        self._output_routing_type = option
        channels = self.available_output_routing_channels
        if channels:
            self._output_routing_channel = channels[0]

    @property
    def output_routing_channel(self) -> _RoutingOption | None:
        return self._output_routing_channel

    @output_routing_channel.setter
    def output_routing_channel(self, option: _RoutingOption) -> None:
        self._output_routing_channel = option

    @property
    def available_input_routing_types(self) -> list[_RoutingOption]:
        return list(self._available_input_routing_types)

    @property
    def available_input_routing_channels(self) -> list[_RoutingOption]:
        if self._input_routing_type is None:
            return []
        return list(self._input_channels_by_type[str(hash(self._input_routing_type))])

    @property
    def available_output_routing_types(self) -> list[_RoutingOption]:
        return list(self._available_output_routing_types)

    @property
    def available_output_routing_channels(self) -> list[_RoutingOption]:
        if self._output_routing_type is None:
            return []
        return list(self._output_channels_by_type[str(hash(self._output_routing_type))])


class _FakeSong:
    def __init__(self, tracks: list[_Track] | None = None) -> None:
        self.tracks = tracks or [_Track("One"), _Track("Two")]
        self.return_tracks = [
            _Track(
                "Return A",
                midi=False,
                audio=False,
                can_be_armed=False,
                clip_slots=[],
                device_names=[],
            )
        ]
        self.master_track = _Track(
            "Master",
            midi=False,
            audio=False,
            can_be_armed=False,
            clip_slots=[],
            device_names=[],
            supports_mute=False,
            supports_solo=False,
            supports_arm=False,
        )

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
        assert result["track_scope"] == "main"
        assert result["track_index"] == 1
        assert result["is_midi_track"] is True
        assert result["device_names"] == ["Device A"]
        assert result["clip_slot_has_clip"] == [False, True]
        assert result["is_foldable"] is False
        assert result["fold_state"] is None
        assert result["is_grouped"] is False
        assert result["group_track_index"] is None

    def test_returns_return_track_info(self, handler: TrackHandler) -> None:
        result = handler.handle_get_info({"track_scope": "return", "track_index": 1})

        assert result["track_scope"] == "return"
        assert result["track_index"] == 1
        assert result["device_names"] == []
        assert result["clip_slot_has_clip"] == []
        assert result["is_foldable"] is False
        assert result["fold_state"] is None

    def test_returns_master_track_info(self, handler: TrackHandler) -> None:
        result = handler.handle_get_info({"track_scope": "master"})

        assert result["track_scope"] == "master"
        assert result["track_index"] is None
        assert result["device_names"] == []
        assert result["clip_slot_has_clip"] == []
        assert result["group_track_index"] is None

    def test_returns_group_metadata_for_child_track(self) -> None:
        group_track = _Track("Drums", is_foldable=True, fold_state=True)
        child_track = _Track("Kick", group_track=group_track)
        handler = TrackHandler(
            _FakeControlSurface(_FakeSong([group_track, child_track]))
        )

        result = handler.handle_get_info({"track_index": 2})

        assert result["is_foldable"] is False
        assert result["fold_state"] is None
        assert result["is_grouped"] is True
        assert result["group_track_index"] == 1

    def test_raises_not_found(self, handler: TrackHandler) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            handler.handle_get_info({"track_index": 99})

    def test_returns_not_found_for_missing_return_track(
        self, handler: TrackHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="Return track 99"):
            handler.handle_get_info({"track_scope": "return", "track_index": 99})

    def test_missing_track_index(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="track_index"):
            handler.handle_get_info({})

    def test_master_rejects_track_index(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="track_index"):
            handler.handle_get_info({"track_scope": "master", "track_index": 1})


class TestRouting:
    def test_get_track_routing_serializes_selected_options(
        self, handler: TrackHandler
    ) -> None:
        result = handler.handle_get_routing({"track_index": 1})

        assert result == {
            "track_index": 1,
            "input_routing_type": {
                "identifier": "101",
                "display_name": "Ext. In",
            },
            "input_routing_channel": {
                "identifier": "201",
                "display_name": "1",
            },
            "output_routing_type": {
                "identifier": "301",
                "display_name": "Master",
            },
            "output_routing_channel": {
                "identifier": "401",
                "display_name": "Stereo",
            },
        }

    def test_get_available_routing_serializes_available_options(
        self, handler: TrackHandler
    ) -> None:
        result = handler.handle_get_available_routing({"track_index": 1})

        assert result["track_index"] == 1
        assert result["available_input_routing_types"][1] == {
            "identifier": "102",
            "display_name": "Resampling",
        }
        assert result["available_input_routing_channels"] == [
            {
                "identifier": "201",
                "display_name": "1",
            },
            {
                "identifier": "202",
                "display_name": "2",
            },
        ]
        assert result["available_output_routing_channels"][0] == {
            "identifier": "401",
            "display_name": "Stereo",
        }

    def test_set_input_routing_uses_identifiers(
        self, handler: TrackHandler, song: _FakeSong
    ) -> None:
        result = handler.handle_set_input_routing(
            {
                "track_index": 1,
                "routing_type_identifier": "102",
                "routing_channel_identifier": "211",
            }
        )

        assert result == {
            "track_index": 1,
            "input_routing_type": {
                "identifier": "102",
                "display_name": "Resampling",
            },
            "input_routing_channel": {
                "identifier": "211",
                "display_name": "Post Mixer",
            },
        }
        assert str(hash(song.tracks[0].input_routing_type)) == "102"
        assert str(hash(song.tracks[0].input_routing_channel)) == "211"

    def test_set_output_routing_uses_identifiers(
        self, handler: TrackHandler, song: _FakeSong
    ) -> None:
        result = handler.handle_set_output_routing(
            {
                "track_index": 1,
                "routing_type_identifier": "302",
                "routing_channel_identifier": "412",
            }
        )

        assert result == {
            "track_index": 1,
            "output_routing_type": {
                "identifier": "302",
                "display_name": "Sends Only",
            },
            "output_routing_channel": {
                "identifier": "412",
                "display_name": "Pre FX",
            },
        }
        assert str(hash(song.tracks[0].output_routing_type)) == "302"
        assert str(hash(song.tracks[0].output_routing_channel)) == "412"

    def test_missing_track_raises_not_found(self, handler: TrackHandler) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            handler.handle_get_routing({"track_index": 99})

    def test_unknown_type_identifier_raises_not_found(
        self, handler: TrackHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="identifier 'BogusType'"):
            handler.handle_set_input_routing(
                {
                    "track_index": 1,
                    "routing_type_identifier": "BogusType",
                    "routing_channel_identifier": "201",
                }
            )

    def test_unknown_channel_identifier_raises_not_found(
        self, handler: TrackHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="identifier 'BogusChannel'"):
            handler.handle_set_output_routing(
                {
                    "track_index": 1,
                    "routing_type_identifier": "301",
                    "routing_channel_identifier": "BogusChannel",
                }
            )

    def test_missing_routing_options_raise_invalid_params(self) -> None:
        handler = TrackHandler(
            _FakeControlSurface(
                _FakeSong([_Track("No Routing", routing_supported=False)])
            )
        )

        with pytest.raises(
            InvalidParamsError,
            match="has no available input routing types",
        ):
            handler.handle_get_available_routing({"track_index": 1})

    def test_track_index_is_still_one_based_for_routing_setters(self) -> None:
        song = _FakeSong([_Track("One"), _Track("Two")])
        handler = TrackHandler(_FakeControlSurface(song))

        handler.handle_set_input_routing(
            {
                "track_index": 2,
                "routing_type_identifier": "102",
                "routing_channel_identifier": "212",
            }
        )

        assert str(hash(song.tracks[0].input_routing_type)) == "101"
        assert str(hash(song.tracks[1].input_routing_type)) == "102"
        assert str(hash(song.tracks[1].input_routing_channel)) == "212"


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
        result = handler.handle_set_name({"track_index": 1, "name": "Renamed"})

        assert result == {"track_scope": "main", "track_index": 1}
        assert song.tracks[0].name == "Renamed"

    def test_set_mute(self, handler: TrackHandler, song: _FakeSong) -> None:
        result = handler.handle_set_mute({"track_index": 1, "mute": True})

        assert result == {"track_scope": "main", "track_index": 1}
        assert song.tracks[0].mute is True

    def test_set_mute_supports_return_track(self, handler: TrackHandler) -> None:
        song = handler._song
        result = handler.handle_set_mute(
            {"track_scope": "return", "track_index": 1, "mute": True}
        )

        assert result == {"track_scope": "return", "track_index": 1}
        assert song.return_tracks[0].mute is True

    def test_set_mute_requires_bool(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="mute"):
            handler.handle_set_mute({"track_index": 1, "mute": "yes"})

    def test_set_mute_requires_track_index_for_return(
        self, handler: TrackHandler
    ) -> None:
        with pytest.raises(InvalidParamsError, match="track_index"):
            handler.handle_set_mute({"track_scope": "return", "mute": True})

    def test_set_mute_rejects_master(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="does not support mute"):
            handler.handle_set_mute({"track_scope": "master", "mute": True})

    def test_set_solo(self, handler: TrackHandler, song: _FakeSong) -> None:
        result = handler.handle_set_solo({"track_index": 2, "solo": True})

        assert result == {"track_scope": "main", "track_index": 2}
        assert song.tracks[1].solo is True

    def test_set_arm_unarmable(self, handler: TrackHandler, song: _FakeSong) -> None:
        song.tracks[0].can_be_armed = False

        with pytest.raises(InvalidParamsError, match="cannot be armed"):
            handler.handle_set_arm({"track_index": 1, "arm": True})

    def test_set_arm_rejects_return_and_master(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="cannot be armed"):
            handler.handle_set_arm(
                {"track_scope": "return", "track_index": 1, "arm": True}
            )

        with pytest.raises(InvalidParamsError, match="cannot be armed"):
            handler.handle_set_arm({"track_scope": "master", "arm": True})

    def test_set_solo_rejects_master(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="does not support solo"):
            handler.handle_set_solo({"track_scope": "master", "solo": True})

    def test_fold_group_sets_fold_state(self) -> None:
        group_track = _Track("Group", is_foldable=True, fold_state=False)
        song = _FakeSong([group_track, _Track("Child", group_track=group_track)])
        handler = TrackHandler(_FakeControlSurface(song))

        result = handler.handle_fold_group({"track_index": 1, "folded": True})

        assert result == {"track_index": 1, "folded": True}
        assert song.tracks[0].fold_state is True

    def test_fold_group_rejects_non_foldable_track(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="foldable group track"):
            handler.handle_fold_group({"track_index": 1, "folded": True})

    def test_fold_group_rejects_non_main_scope(self, handler: TrackHandler) -> None:
        with pytest.raises(InvalidParamsError, match="only supports main tracks"):
            handler.handle_fold_group(
                {"track_scope": "return", "track_index": 1, "folded": True}
            )


class TestDispatcherNotFoundIntegration:
    def test_track_get_info_not_found_via_dispatcher(self, song: _FakeSong) -> None:
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch("track.get_info", {"track_index": 10}, "r1")

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "NOT_FOUND"
        assert "10" in resp["error"]["message"]

    def test_track_get_info_master_via_dispatcher(self, song: _FakeSong) -> None:
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch("track.get_info", {"track_scope": "master"}, "r1m")

        assert resp["status"] == "ok"
        assert resp["result"]["track_scope"] == "master"
        assert resp["result"]["track_index"] is None

    def test_track_get_available_routing_invalid_params_via_dispatcher(self) -> None:
        song = _FakeSong([_Track("No Routing", routing_supported=False)])
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch("track.get_available_routing", {"track_index": 1}, "r2")

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "INVALID_PARAMS"
        assert "available input routing types" in resp["error"]["message"]

    def test_track_set_mute_master_rejected_via_dispatcher(self) -> None:
        song = _FakeSong()
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch(
            "track.set_mute", {"track_scope": "master", "mute": True}, "r3"
        )

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "INVALID_PARAMS"
        assert "does not support mute" in resp["error"]["message"]

    def test_track_fold_group_success_via_dispatcher(self) -> None:
        group_track = _Track("Group", is_foldable=True, fold_state=False)
        song = _FakeSong([group_track, _Track("Child", group_track=group_track)])
        d = Dispatcher(_FakeControlSurface(song))
        d.register("track", TrackHandler(_FakeControlSurface(song)))

        resp = d.dispatch("track.fold_group", {"track_index": 1, "folded": True}, "r4")

        assert resp["status"] == "ok"
        assert resp["result"] == {"track_index": 1, "folded": True}
