"""Tests for session and transport MCP tools.

Establishes reusable testing patterns for all tool modules:
- Tool contract tests (registration, schema, description)
- Input validation tests with parameterization
- Tool unit tests (correct commands, response parsing, error handling)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.session import (
    PlaybackPosition,
    SessionInfo,
    TempoResult,
    TimeSignatureResult,
    TransportResult,
    get_playback_position,
    get_session_info,
    set_tempo,
    set_time_signature,
    start_playback,
    stop_playback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TOOL_NAMES = [
    "get_session_info",
    "set_tempo",
    "set_time_signature",
    "start_playback",
    "stop_playback",
    "get_playback_position",
]


def _ok_response(result: dict, request_id: str = "test") -> CommandResponse:
    return CommandResponse(status="ok", result=result, id=request_id)


def _error_response(
    code: str = "INTERNAL_ERROR",
    message: str = "something broke",
    request_id: str = "test",
) -> CommandResponse:
    return CommandResponse(
        status="error",
        id=request_id,
        error=ErrorDetail(code=code, message=message),
    )


# ===================================================================
# 1. Tool contract tests
# ===================================================================
class TestToolContracts:
    """Verify each tool is registered with the correct name, schema, and description."""

    def _get_tool(self, name: str):
        tools = mcp._tool_manager._tools
        assert name in tools, f"Tool '{name}' not registered"
        return tools[name]

    @pytest.mark.parametrize("name", TOOL_NAMES)
    def test_tool_is_registered(self, name: str) -> None:
        self._get_tool(name)

    @pytest.mark.parametrize("name", TOOL_NAMES)
    def test_tool_has_description(self, name: str) -> None:
        tool = self._get_tool(name)
        assert tool.description, f"Tool '{name}' is missing a description"

    def test_set_tempo_schema(self) -> None:
        tool = self._get_tool("set_tempo")
        props = tool.parameters["properties"]
        assert "tempo" in props
        assert props["tempo"]["minimum"] == 20.0
        assert props["tempo"]["maximum"] == 999.0

    def test_set_time_signature_schema(self) -> None:
        tool = self._get_tool("set_time_signature")
        props = tool.parameters["properties"]
        assert "numerator" in props
        assert "denominator" in props
        assert props["numerator"]["minimum"] == 1
        assert props["numerator"]["maximum"] == 32
        assert props["denominator"]["enum"] == [1, 2, 4, 8, 16, 32]

    def test_get_session_info_has_no_required_params(self) -> None:
        tool = self._get_tool("get_session_info")
        required = tool.parameters.get("required", [])
        assert required == []

    def test_start_playback_has_no_required_params(self) -> None:
        tool = self._get_tool("start_playback")
        required = tool.parameters.get("required", [])
        assert required == []

    def test_stop_playback_has_no_required_params(self) -> None:
        tool = self._get_tool("stop_playback")
        required = tool.parameters.get("required", [])
        assert required == []

    def test_get_playback_position_has_no_required_params(self) -> None:
        tool = self._get_tool("get_playback_position")
        required = tool.parameters.get("required", [])
        assert required == []


# ===================================================================
# 2. Input validation tests (schema-level, via arg_model)
# ===================================================================
class TestInputValidation:
    """Verify Pydantic Field constraints reject bad inputs at the schema level."""

    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    @pytest.mark.parametrize("tempo", [19.9, 0, -1, 999.1, 1000, 10000])
    def test_set_tempo_rejects_out_of_range(self, tempo: float) -> None:
        model = self._arg_model("set_tempo")
        with pytest.raises(ValidationError):
            model(tempo=tempo)

    @pytest.mark.parametrize("tempo", [20.0, 120.0, 85.5, 999.0, 440.0])
    def test_set_tempo_accepts_valid_values(self, tempo: float) -> None:
        model = self._arg_model("set_tempo")
        args = model(tempo=tempo)
        assert args.tempo == tempo

    @pytest.mark.parametrize("numerator", [0, -1, 33, 100])
    def test_set_time_signature_rejects_bad_numerator(self, numerator: int) -> None:
        model = self._arg_model("set_time_signature")
        with pytest.raises(ValidationError):
            model(numerator=numerator, denominator=4)

    @pytest.mark.parametrize("denominator", [0, -1, 3, 5, 7, 33, 100])
    def test_set_time_signature_rejects_bad_denominator(self, denominator: int) -> None:
        model = self._arg_model("set_time_signature")
        with pytest.raises(ValidationError):
            model(numerator=4, denominator=denominator)

    @pytest.mark.parametrize(
        "numerator,denominator",
        [(1, 4), (3, 4), (4, 4), (6, 8), (7, 8), (12, 16), (32, 32)],
    )
    def test_set_time_signature_accepts_valid_values(
        self, numerator: int, denominator: int
    ) -> None:
        model = self._arg_model("set_time_signature")
        args = model(numerator=numerator, denominator=denominator)
        assert args.numerator == numerator
        assert args.denominator == denominator


# ===================================================================
# 3. Tool unit tests
# ===================================================================
class TestGetSessionInfo:
    SESSION_RESULT = {
        "tempo": 120.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
        "track_count": 3,
        "is_playing": False,
        "is_recording": False,
        "song_length": 32.0,
    }

    async def test_returns_session_info(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(self.SESSION_RESULT)

        result = await get_session_info(ctx=mock_context)

        assert isinstance(result, SessionInfo)
        assert result.tempo == 120.0
        assert result.track_count == 3
        assert result.is_playing is False
        assert result.is_recording is False
        assert result.song_length == 32.0

    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(self.SESSION_RESULT)

        await get_session_info(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.get_info"
        assert req.params == {}

    async def test_raises_on_error_response(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response()

        with pytest.raises(CommandError):
            await get_session_info(ctx=mock_context)


class TestSetTempo:
    async def test_returns_tempo_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"tempo": 140.0})

        result = await set_tempo(ctx=mock_context, tempo=140.0)

        assert isinstance(result, TempoResult)
        assert result.tempo == 140.0

    async def test_sends_correct_command_and_params(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"tempo": 85.5})

        await set_tempo(ctx=mock_context, tempo=85.5)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.set_tempo"
        assert req.params == {"tempo": 85.5}

    async def test_raises_on_error_response(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS", message="Tempo out of range"
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_tempo(ctx=mock_context, tempo=120.0)


class TestSetTimeSignature:
    async def test_returns_time_signature_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"numerator": 3, "denominator": 4}
        )

        result = await set_time_signature(ctx=mock_context, numerator=3, denominator=4)

        assert isinstance(result, TimeSignatureResult)
        assert result.numerator == 3
        assert result.denominator == 4

    async def test_sends_correct_command_and_params(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"numerator": 6, "denominator": 8}
        )

        await set_time_signature(ctx=mock_context, numerator=6, denominator=8)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.set_time_signature"
        assert req.params == {"numerator": 6, "denominator": 8}

    async def test_raises_on_error_response(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS", message="not a power of 2"
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_time_signature(ctx=mock_context, numerator=4, denominator=5)


class TestStartPlayback:
    async def test_returns_transport_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"action": "start", "is_playing": True}
        )

        result = await start_playback(ctx=mock_context)

        assert isinstance(result, TransportResult)
        assert result.action == "start"
        assert result.is_playing is True

    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"action": "start", "is_playing": True}
        )

        await start_playback(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.start_playback"
        assert req.params == {}


class TestStopPlayback:
    async def test_returns_transport_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"action": "stop", "is_playing": False}
        )

        result = await stop_playback(ctx=mock_context)

        assert isinstance(result, TransportResult)
        assert result.action == "stop"
        assert result.is_playing is False

    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"action": "stop", "is_playing": False}
        )

        await stop_playback(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.stop_playback"
        assert req.params == {}


class TestGetPlaybackPosition:
    POSITION_RESULT = {
        "beats": 8.5,
        "bar": 3,
        "beat_in_bar": 1.5,
        "time_seconds": 4.25,
        "is_playing": True,
    }

    async def test_returns_playback_position(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(self.POSITION_RESULT)

        result = await get_playback_position(ctx=mock_context)

        assert isinstance(result, PlaybackPosition)
        assert result.beats == 8.5
        assert result.bar == 3
        assert result.beat_in_bar == 1.5
        assert result.time_seconds == 4.25
        assert result.is_playing is True

    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(self.POSITION_RESULT)

        await get_playback_position(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "session.get_playback_position"
        assert req.params == {}

    async def test_raises_on_error_response(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response()

        with pytest.raises(CommandError):
            await get_playback_position(ctx=mock_context)


# ===================================================================
# 4. Response model validation
# ===================================================================
class TestResponseModels:
    """Ensure response models reject malformed data from the Remote Script."""

    def test_session_info_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            SessionInfo.model_validate({"tempo": 120.0})

    def test_tempo_result_rejects_missing_tempo(self) -> None:
        with pytest.raises(ValidationError):
            TempoResult.model_validate({})

    def test_playback_position_accepts_valid_data(self) -> None:
        pos = PlaybackPosition.model_validate(
            {
                "beats": 0.0,
                "bar": 1,
                "beat_in_bar": 1.0,
                "time_seconds": 0.0,
                "is_playing": False,
            }
        )
        assert pos.bar == 1
