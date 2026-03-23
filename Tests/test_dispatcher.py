"""Tests for the Remote Script command dispatcher.

The dispatcher is pure Python with no Ableton imports, so we can test
it directly in the standard pytest suite.  The _Framework stub and
remote_script sys.path setup live in conftest.py.
"""

import pytest
from AbletonLiveMCP import create_instance
from AbletonLiveMCP.dispatcher import (
    INTERNAL_ERROR,
    UNKNOWN_COMMAND,
    Dispatcher,
)


class _FakeControlSurface:
    """Minimal stand-in for a ControlSurface in tests."""

    def log_message(self, msg):
        pass

    def show_message(self, msg):
        pass

    def song(self):
        return None

    def schedule_message(self, delay, callback):
        callback()


class _SampleHandler:
    """A handler with a few actions for testing dispatch."""

    def handle_get_info(self, params):
        return {"tempo": 120.0}

    def handle_set_tempo(self, params):
        tempo = params.get("tempo")
        if tempo is None:
            raise ValueError("tempo is required")
        return {"tempo": tempo}

    def handle_explode(self, params):
        raise RuntimeError("boom")


@pytest.fixture
def dispatcher():
    cs = _FakeControlSurface()
    d = Dispatcher(cs)
    d.register("session", _SampleHandler())
    return d


class TestSystemPing:
    def test_ping_returns_pong(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("system.ping", {}, "ping-1")
        assert resp["status"] == "ok"
        assert resp["result"] == {"message": "pong"}
        assert resp["id"] == "ping-1"


class TestCommandRouting:
    def test_routes_to_handler(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("session.get_info", {}, "r-1")
        assert resp["status"] == "ok"
        assert resp["result"] == {"tempo": 120.0}
        assert resp["id"] == "r-1"

    def test_passes_params(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("session.set_tempo", {"tempo": 140.0}, "r-2")
        assert resp["status"] == "ok"
        assert resp["result"] == {"tempo": 140.0}

    def test_handler_exception_returns_internal_error(
        self, dispatcher: Dispatcher
    ) -> None:
        resp = dispatcher.dispatch("session.explode", {}, "r-3")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == INTERNAL_ERROR
        assert "boom" in resp["error"]["message"]

    def test_handler_value_error_returns_internal_error(
        self, dispatcher: Dispatcher
    ) -> None:
        resp = dispatcher.dispatch("session.set_tempo", {}, "r-4")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == INTERNAL_ERROR
        assert "tempo is required" in resp["error"]["message"]


class TestUnknownCommands:
    def test_unknown_category(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("bogus.action", {}, "u-1")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == UNKNOWN_COMMAND
        assert "bogus" in resp["error"]["message"]

    def test_unknown_action(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("session.nonexistent", {}, "u-2")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == UNKNOWN_COMMAND
        assert "nonexistent" in resp["error"]["message"]

    def test_no_dot_in_command(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("nodot", {}, "u-3")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == UNKNOWN_COMMAND
        assert "category.action" in resp["error"]["message"]


class TestResponseShape:
    """Every response must have all four keys."""

    def test_ok_shape(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("system.ping", {}, "s-1")
        assert set(resp.keys()) == {"status", "result", "id", "error"}
        assert resp["error"] is None

    def test_error_shape(self, dispatcher: Dispatcher) -> None:
        resp = dispatcher.dispatch("bogus.action", {}, "s-2")
        assert set(resp.keys()) == {"status", "result", "id", "error"}
        assert resp["result"] is None
        assert set(resp["error"].keys()) == {"code", "message"}


class TestCreateInstance:
    """Ableton calls create_instance(c_instance) to load a Remote Script."""

    def test_returns_control_surface(self, monkeypatch) -> None:
        import AbletonLiveMCP as alm_pkg
        from AbletonLiveMCP import AbletonLiveMCP

        monkeypatch.setattr(alm_pkg, "TCP_PORT", 0)

        instance = create_instance(_FakeControlSurface())
        assert isinstance(instance, AbletonLiveMCP)

        instance._tcp_server.shutdown()
        instance._server_thread.join(timeout=3)
