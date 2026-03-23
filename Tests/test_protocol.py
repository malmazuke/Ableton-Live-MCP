"""Tests for the MCP <-> Remote Script protocol models."""

import json

import pytest
from pydantic import ValidationError

from mcp_ableton.protocol import CommandRequest, CommandResponse, ErrorDetail


class TestCommandRequest:
    def test_defaults(self) -> None:
        req = CommandRequest(command="session.get_info")
        assert req.command == "session.get_info"
        assert req.params == {}
        assert len(req.id) > 0

    def test_explicit_params(self) -> None:
        req = CommandRequest(
            command="session.set_tempo",
            params={"tempo": 120.0},
            id="abc123",
        )
        assert req.command == "session.set_tempo"
        assert req.params == {"tempo": 120.0}
        assert req.id == "abc123"

    def test_serialization_round_trip(self) -> None:
        req = CommandRequest(
            command="track.create_midi",
            params={"index": 0},
            id="roundtrip-1",
        )
        json_str = req.model_dump_json()
        restored = CommandRequest.model_validate_json(json_str)
        assert restored == req

    def test_to_line_format(self) -> None:
        req = CommandRequest(command="session.get_info", params={}, id="line-1")
        line = req.to_line()
        assert line.endswith(b"\n")
        payload = json.loads(line)
        assert payload["command"] == "session.get_info"
        assert payload["id"] == "line-1"

    def test_from_line(self) -> None:
        raw = b'{"command":"clip.create","params":{"track_index":1},"id":"fl-1"}\n'
        req = CommandRequest.from_line(raw)
        assert req.command == "clip.create"
        assert req.params == {"track_index": 1}
        assert req.id == "fl-1"

    def test_from_line_strips_whitespace(self) -> None:
        raw = b'  {"command":"x","params":{},"id":"ws"}  \n'
        req = CommandRequest.from_line(raw)
        assert req.command == "x"

    def test_to_line_from_line_round_trip(self) -> None:
        original = CommandRequest(
            command="device.get_params",
            params={"track_index": 2, "device_index": 0},
            id="rt-2",
        )
        restored = CommandRequest.from_line(original.to_line())
        assert restored == original

    def test_missing_command_raises(self) -> None:
        with pytest.raises(ValidationError):
            CommandRequest.model_validate({"params": {}, "id": "bad"})


class TestErrorDetail:
    def test_fields(self) -> None:
        err = ErrorDetail(code="NOT_FOUND", message="Track 99 does not exist")
        assert err.code == "NOT_FOUND"
        assert err.message == "Track 99 does not exist"


class TestCommandResponse:
    def test_ok_response(self) -> None:
        resp = CommandResponse(
            status="ok",
            result={"tempo": 120.0},
            id="ok-1",
        )
        assert resp.status == "ok"
        assert resp.result == {"tempo": 120.0}
        assert resp.error is None

    def test_error_response(self) -> None:
        resp = CommandResponse(
            status="error",
            id="err-1",
            error=ErrorDetail(code="INVALID_PARAM", message="Tempo out of range"),
        )
        assert resp.status == "error"
        assert resp.result is None
        assert resp.error is not None
        assert resp.error.code == "INVALID_PARAM"

    def test_serialization_round_trip(self) -> None:
        resp = CommandResponse(
            status="ok",
            result={"tracks": [{"name": "Bass"}]},
            id="rt-resp",
        )
        json_str = resp.model_dump_json()
        restored = CommandResponse.model_validate_json(json_str)
        assert restored == resp

    def test_to_line_format(self) -> None:
        resp = CommandResponse(status="ok", result={}, id="line-r")
        line = resp.to_line()
        assert line.endswith(b"\n")
        payload = json.loads(line)
        assert payload["status"] == "ok"

    def test_from_line(self) -> None:
        raw = b'{"status":"ok","result":{"bpm":140},"id":"fl-r","error":null}\n'
        resp = CommandResponse.from_line(raw)
        assert resp.status == "ok"
        assert resp.result == {"bpm": 140}
        assert resp.id == "fl-r"

    def test_to_line_from_line_round_trip(self) -> None:
        original = CommandResponse(
            status="error",
            id="rt-err",
            error=ErrorDetail(code="TIMEOUT", message="Command timed out"),
        )
        restored = CommandResponse.from_line(original.to_line())
        assert restored == original

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            CommandResponse(status="unknown", id="bad")  # type: ignore[arg-type]

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            CommandResponse.model_validate({"status": "ok"})
