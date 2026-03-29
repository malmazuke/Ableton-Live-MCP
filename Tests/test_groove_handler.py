"""Tests for the Remote Script GrooveHandler."""

from __future__ import annotations

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.groove import GrooveHandler


class _Groove:
    def __init__(
        self,
        name: str,
        *,
        base: int = 2,
        quantization_amount: float = 0.0,
        timing_amount: float = 0.5,
        random_amount: float = 0.0,
        velocity_amount: float = 0.25,
    ) -> None:
        self.name = name
        self.base = base
        self.quantization_amount = quantization_amount
        self.timing_amount = timing_amount
        self.random_amount = random_amount
        self.velocity_amount = velocity_amount


class _Clip:
    def __init__(self, name: str = "Clip", audio: bool = False) -> None:
        self.name = name
        self.is_audio_clip = audio
        self.is_midi_clip = not audio
        self.groove: _Groove | None = None


class _ClipSlot:
    def __init__(self, clip: _Clip | None = None) -> None:
        self._clip = clip
        self.has_clip = clip is not None

    @property
    def clip(self) -> _Clip:
        assert self._clip is not None
        return self._clip


class _Track:
    def __init__(self, clip_slots: list[_ClipSlot]) -> None:
        self.clip_slots = clip_slots


class _GroovePool:
    def __init__(self, grooves: list[_Groove]) -> None:
        self.grooves = grooves


class _GrooveSong:
    def __init__(self, grooves: list[_Groove] | None = None) -> None:
        self.groove_pool = _GroovePool(grooves or [])
        self.tracks = [
            _Track([_ClipSlot(), _ClipSlot()]),
            _Track([_ClipSlot(_Clip("Audio Clip", audio=True)), _ClipSlot()]),
        ]


class _FakeControlSurface:
    def __init__(self, song: _GrooveSong | None = None) -> None:
        self._song = song or _GrooveSong()

    def song(self) -> _GrooveSong:
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def show_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay, callback) -> None:
        callback()


@pytest.fixture
def groove_song() -> _GrooveSong:
    return _GrooveSong([_Groove("MPC 16 Swing 57"), _Groove("Swing 16")])


@pytest.fixture
def groove_handler(groove_song: _GrooveSong) -> GrooveHandler:
    return GrooveHandler(_FakeControlSurface(groove_song))


class TestGetGroovePool:
    def test_serializes_pool_shape(self, groove_handler: GrooveHandler) -> None:
        result = groove_handler.handle_get_pool({})

        assert result == {
            "grooves": [
                {
                    "groove_index": 1,
                    "name": "MPC 16 Swing 57",
                    "base": 2,
                    "quantization_amount": 0.0,
                    "timing_amount": 0.5,
                    "random_amount": 0.0,
                    "velocity_amount": 0.25,
                },
                {
                    "groove_index": 2,
                    "name": "Swing 16",
                    "base": 2,
                    "quantization_amount": 0.0,
                    "timing_amount": 0.5,
                    "random_amount": 0.0,
                    "velocity_amount": 0.25,
                },
            ]
        }

    def test_empty_pool_returns_empty_list(self) -> None:
        handler = GrooveHandler(_FakeControlSurface(_GrooveSong([])))

        result = handler.handle_get_pool({})

        assert result == {"grooves": []}


class TestApplyGroove:
    def test_applies_groove_to_session_clip(
        self,
        groove_handler: GrooveHandler,
        groove_song: _GrooveSong,
    ) -> None:
        result = groove_handler.handle_apply(
            {
                "track_index": 2,
                "clip_slot_index": 1,
                "groove_index": 1,
            }
        )

        assert result == {
            "track_index": 2,
            "clip_slot_index": 1,
            "groove_index": 1,
            "groove_name": "MPC 16 Swing 57",
        }
        assert (
            groove_song.tracks[1].clip_slots[0].clip.groove
            is groove_song.groove_pool.grooves[0]
        )

    def test_missing_track_raises_not_found(
        self, groove_handler: GrooveHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="Track 99"):
            groove_handler.handle_apply(
                {
                    "track_index": 99,
                    "clip_slot_index": 1,
                    "groove_index": 1,
                }
            )

    def test_missing_clip_slot_raises_not_found(
        self, groove_handler: GrooveHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="Clip slot 99"):
            groove_handler.handle_apply(
                {
                    "track_index": 1,
                    "clip_slot_index": 99,
                    "groove_index": 1,
                }
            )

    def test_empty_slot_raises_not_found(self, groove_handler: GrooveHandler) -> None:
        with pytest.raises(NotFoundError, match="No clip in slot 2"):
            groove_handler.handle_apply(
                {
                    "track_index": 2,
                    "clip_slot_index": 2,
                    "groove_index": 1,
                }
            )

    def test_missing_groove_raises_not_found(
        self, groove_handler: GrooveHandler
    ) -> None:
        with pytest.raises(NotFoundError, match="Groove 99"):
            groove_handler.handle_apply(
                {
                    "track_index": 2,
                    "clip_slot_index": 1,
                    "groove_index": 99,
                }
            )

    @pytest.mark.parametrize(
        "params, expected",
        [
            ({}, "'track_index' parameter is required"),
            ({"track_index": "1", "clip_slot_index": 1, "groove_index": 1}, "integer"),
            ({"track_index": 1, "clip_slot_index": 0, "groove_index": 1}, "at least 1"),
            ({"track_index": 2, "clip_slot_index": 1}, "parameter is required"),
        ],
    )
    def test_invalid_params_raise_invalid_params(
        self,
        groove_handler: GrooveHandler,
        params: dict[str, object],
        expected: str,
    ) -> None:
        with pytest.raises(InvalidParamsError, match=expected):
            groove_handler.handle_apply(params)


class TestDispatcherRouting:
    def test_dispatch_routes_groove_commands(self) -> None:
        cs = _FakeControlSurface(_GrooveSong([_Groove("MPC")]))
        dispatcher = Dispatcher(cs)
        dispatcher.register("groove", GrooveHandler(cs))

        get_resp = dispatcher.dispatch("groove.get_pool", {}, "g-1")
        apply_resp = dispatcher.dispatch(
            "groove.apply",
            {"track_index": 2, "clip_slot_index": 1, "groove_index": 1},
            "g-2",
        )

        assert get_resp["status"] == "ok"
        assert get_resp["result"]["grooves"][0]["groove_index"] == 1
        assert apply_resp["status"] == "ok"
        assert apply_resp["result"]["groove_name"] == "MPC"
