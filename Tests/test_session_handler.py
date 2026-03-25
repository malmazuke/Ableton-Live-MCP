"""Tests for the Remote Script SessionHandler.

Tests run against the handler directly with a fake ControlSurface and
mock Song object, following the pattern established in test_dispatcher.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError
from AbletonLiveMCP.handlers.session import SessionHandler


class _FakeSong:
    """Mock Song providing controllable LOM properties."""

    def __init__(
        self,
        tempo: float = 120.0,
        signature_numerator: int = 4,
        signature_denominator: int = 4,
        is_playing: bool = False,
        record_mode: bool = False,
        song_length: float = 64.0,
        current_song_time: float = 0.0,
    ):
        self.tempo = tempo
        self.signature_numerator = signature_numerator
        self.signature_denominator = signature_denominator
        self.is_playing = is_playing
        self.record_mode = record_mode
        self.song_length = song_length
        self.current_song_time = current_song_time
        self.tracks = [MagicMock() for _ in range(3)]

        self.start_playing = MagicMock()
        self.stop_playing = MagicMock()


class _FakeControlSurface:
    """Minimal stand-in for a ControlSurface in tests."""

    def __init__(self, song: _FakeSong | None = None):
        self._song = song or _FakeSong()

    def song(self):
        return self._song

    def log_message(self, msg):
        pass

    def show_message(self, msg):
        pass

    def schedule_message(self, delay, callback):
        callback()


@pytest.fixture
def song() -> _FakeSong:
    return _FakeSong()


@pytest.fixture
def handler(song: _FakeSong) -> SessionHandler:
    cs = _FakeControlSurface(song)
    return SessionHandler(cs)


# ===================================================================
# handle_get_info
# ===================================================================
class TestGetInfo:
    def test_returns_all_fields(self, handler: SessionHandler, song: _FakeSong) -> None:
        result = handler.handle_get_info({})

        assert result["tempo"] == 120.0
        assert result["signature_numerator"] == 4
        assert result["signature_denominator"] == 4
        assert result["track_count"] == 3
        assert result["is_playing"] is False
        assert result["is_recording"] is False
        assert result["song_length"] == 64.0

    def test_reflects_current_state(self, handler: SessionHandler) -> None:
        handler._song.tempo = 140.0
        handler._song.is_playing = True
        handler._song.record_mode = True

        result = handler.handle_get_info({})

        assert result["tempo"] == 140.0
        assert result["is_playing"] is True
        assert result["is_recording"] is True


# ===================================================================
# handle_set_tempo
# ===================================================================
class TestSetTempo:
    def test_sets_tempo(self, handler: SessionHandler, song: _FakeSong) -> None:
        result = handler.handle_set_tempo({"tempo": 140.0})

        assert result["tempo"] == 140.0
        assert song.tempo == 140.0

    @pytest.mark.parametrize("tempo", [20.0, 85.5, 999.0])
    def test_accepts_boundary_values(
        self, handler: SessionHandler, song: _FakeSong, tempo: float
    ) -> None:
        result = handler.handle_set_tempo({"tempo": tempo})
        assert result["tempo"] == tempo
        assert song.tempo == tempo

    @pytest.mark.parametrize("tempo", [19.9, 0, -1, 999.1, 1000])
    def test_rejects_out_of_range(self, handler: SessionHandler, tempo: float) -> None:
        with pytest.raises(InvalidParamsError, match="between 20 and 999"):
            handler.handle_set_tempo({"tempo": tempo})

    def test_rejects_missing_param(self, handler: SessionHandler) -> None:
        with pytest.raises(InvalidParamsError, match="required"):
            handler.handle_set_tempo({})

    def test_rejects_non_numeric(self, handler: SessionHandler) -> None:
        with pytest.raises(InvalidParamsError, match="must be a number"):
            handler.handle_set_tempo({"tempo": "fast"})

    def test_accepts_integer(self, handler: SessionHandler, song: _FakeSong) -> None:
        result = handler.handle_set_tempo({"tempo": 120})
        assert result["tempo"] == 120.0
        assert song.tempo == 120.0


# ===================================================================
# handle_set_time_signature
# ===================================================================
class TestSetTimeSignature:
    @pytest.mark.parametrize(
        "numerator,denominator",
        [(3, 4), (4, 4), (6, 8), (7, 8), (1, 1), (32, 32)],
    )
    def test_sets_valid_signatures(
        self,
        handler: SessionHandler,
        song: _FakeSong,
        numerator: int,
        denominator: int,
    ) -> None:
        result = handler.handle_set_time_signature(
            {"numerator": numerator, "denominator": denominator}
        )

        assert result["numerator"] == numerator
        assert result["denominator"] == denominator
        assert song.signature_numerator == numerator
        assert song.signature_denominator == denominator

    @pytest.mark.parametrize("denominator", [3, 5, 6, 7, 9, 10, 15])
    def test_rejects_non_power_of_2_denominator(
        self, handler: SessionHandler, denominator: int
    ) -> None:
        with pytest.raises(InvalidParamsError, match="power of 2"):
            handler.handle_set_time_signature(
                {"numerator": 4, "denominator": denominator}
            )

    @pytest.mark.parametrize("denominator", [1, 2, 4, 8, 16, 32])
    def test_accepts_power_of_2_denominators(
        self, handler: SessionHandler, song: _FakeSong, denominator: int
    ) -> None:
        handler.handle_set_time_signature({"numerator": 4, "denominator": denominator})
        assert song.signature_denominator == denominator

    @pytest.mark.parametrize("numerator", [0, -1, 33])
    def test_rejects_bad_numerator(
        self, handler: SessionHandler, numerator: int
    ) -> None:
        with pytest.raises(InvalidParamsError):
            handler.handle_set_time_signature(
                {"numerator": numerator, "denominator": 4}
            )

    def test_rejects_missing_params(self, handler: SessionHandler) -> None:
        with pytest.raises(InvalidParamsError, match="required"):
            handler.handle_set_time_signature({})

    def test_rejects_non_integer(self, handler: SessionHandler) -> None:
        with pytest.raises(InvalidParamsError, match="must be integers"):
            handler.handle_set_time_signature({"numerator": 4.5, "denominator": 4})


# ===================================================================
# handle_start_playback / handle_stop_playback
# ===================================================================
class TestStartPlayback:
    def test_calls_start_playing(
        self, handler: SessionHandler, song: _FakeSong
    ) -> None:
        result = handler.handle_start_playback({})

        assert result["action"] == "start"
        assert result["is_playing"] is True
        song.start_playing.assert_called_once()

    def test_does_not_call_stop(self, handler: SessionHandler, song: _FakeSong) -> None:
        handler.handle_start_playback({})
        song.stop_playing.assert_not_called()


class TestStopPlayback:
    def test_calls_stop_playing(self, handler: SessionHandler, song: _FakeSong) -> None:
        result = handler.handle_stop_playback({})

        assert result["action"] == "stop"
        assert result["is_playing"] is False
        song.stop_playing.assert_called_once()

    def test_does_not_call_start(
        self, handler: SessionHandler, song: _FakeSong
    ) -> None:
        handler.handle_stop_playback({})
        song.start_playing.assert_not_called()


# ===================================================================
# handle_get_playback_position
# ===================================================================
class TestGetPlaybackPosition:
    def test_returns_position_at_start(self, handler: SessionHandler) -> None:
        result = handler.handle_get_playback_position({})

        assert result["beats"] == 0.0
        assert result["bar"] == 1
        assert result["beat_in_bar"] == 1.0
        assert result["time_seconds"] == 0.0
        assert result["is_playing"] is False

    def test_computes_bar_and_beat(self, handler: SessionHandler) -> None:
        handler._song.current_song_time = 10.0
        handler._song.signature_numerator = 4
        handler._song.tempo = 120.0

        result = handler.handle_get_playback_position({})

        assert result["beats"] == 10.0
        assert result["bar"] == 3
        assert result["beat_in_bar"] == pytest.approx(3.0)
        assert result["time_seconds"] == pytest.approx(5.0)

    def test_time_seconds_with_different_tempo(self, handler: SessionHandler) -> None:
        handler._song.current_song_time = 4.0
        handler._song.tempo = 60.0

        result = handler.handle_get_playback_position({})

        assert result["time_seconds"] == pytest.approx(4.0)

    def test_3_4_time_signature(self, handler: SessionHandler) -> None:
        handler._song.current_song_time = 9.0
        handler._song.signature_numerator = 3
        handler._song.tempo = 120.0

        result = handler.handle_get_playback_position({})

        assert result["bar"] == 4
        assert result["beat_in_bar"] == pytest.approx(1.0)

    def test_reflects_playing_state(self, handler: SessionHandler) -> None:
        handler._song.is_playing = True

        result = handler.handle_get_playback_position({})

        assert result["is_playing"] is True


# ===================================================================
# Dispatcher integration (InvalidParamsError routing)
# ===================================================================
class TestInvalidParamsErrorRouting:
    """Verify that InvalidParamsError results in INVALID_PARAMS, not INTERNAL_ERROR."""

    def test_dispatcher_routes_invalid_params(self, song: _FakeSong) -> None:
        cs = _FakeControlSurface(song)
        dispatcher = Dispatcher(cs)
        dispatcher.register("session", SessionHandler(cs))

        resp = dispatcher.dispatch("session.set_tempo", {"tempo": 5.0}, "val-1")

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "INVALID_PARAMS"
        assert "between 20 and 999" in resp["error"]["message"]

    def test_dispatcher_routes_internal_error(self, song: _FakeSong) -> None:
        cs = _FakeControlSurface(song)
        dispatcher = Dispatcher(cs)
        handler = SessionHandler(cs)
        dispatcher.register("session", handler)

        handler._song.start_playing.side_effect = RuntimeError("LOM crash")
        resp = dispatcher.dispatch("session.start_playback", {}, "err-1")

        assert resp["status"] == "error"
        assert resp["error"]["code"] == "INTERNAL_ERROR"
        assert "LOM crash" in resp["error"]["message"]
