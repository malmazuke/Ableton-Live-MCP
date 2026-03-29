"""Tests for mixer MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.mixer import (
    MasterTrackInfo,
    MasterVolumeSetResult,
    TrackPanSetResult,
    TrackVolumeSetResult,
    get_master_info,
    set_master_volume,
    set_track_pan,
    set_track_volume,
)

TOOL_NAMES = [
    "set_track_volume",
    "set_track_pan",
    "get_master_info",
    "set_master_volume",
]

MASTER_INFO_RESULT = {
    "name": "Master",
    "volume": 0.74,
    "pan": 0.0,
}

TRACK_VOLUME_RESULT = {
    "track_index": 2,
    "volume": 0.5,
}

TRACK_PAN_RESULT = {
    "track_index": 2,
    "pan": -0.25,
}

MASTER_VOLUME_RESULT = {
    "volume": 0.8,
}


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


class TestToolContracts:
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

    def test_set_track_volume_schema(self) -> None:
        tool = self._get_tool("set_track_volume")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["volume"]["minimum"] == 0.0
        assert props["volume"]["maximum"] == 1.0

    def test_set_track_pan_schema(self) -> None:
        tool = self._get_tool("set_track_pan")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["pan"]["minimum"] == -1.0
        assert props["pan"]["maximum"] == 1.0

    def test_set_master_volume_schema(self) -> None:
        tool = self._get_tool("set_master_volume")
        props = tool.parameters["properties"]
        assert props["volume"]["minimum"] == 0.0
        assert props["volume"]["maximum"] == 1.0


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_set_track_volume_rejects_non_positive_track_index(self) -> None:
        model = self._arg_model("set_track_volume")
        with pytest.raises(ValidationError):
            model(track_index=0, volume=0.5)

    @pytest.mark.parametrize("volume", [-0.1, 1.1])
    def test_set_track_volume_rejects_out_of_range_volume(self, volume: float) -> None:
        model = self._arg_model("set_track_volume")
        with pytest.raises(ValidationError):
            model(track_index=1, volume=volume)

    @pytest.mark.parametrize("pan", [-1.1, 1.1])
    def test_set_track_pan_rejects_out_of_range_pan(self, pan: float) -> None:
        model = self._arg_model("set_track_pan")
        with pytest.raises(ValidationError):
            model(track_index=1, pan=pan)

    def test_set_master_volume_accepts_upper_bound(self) -> None:
        model = self._arg_model("set_master_volume")
        args = model(volume=1.0)
        assert args.volume == 1.0


class TestSetTrackVolume:
    async def test_returns_track_volume_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_VOLUME_RESULT)

        result = await set_track_volume(ctx=mock_context, track_index=2, volume=0.5)

        assert isinstance(result, TrackVolumeSetResult)
        assert result.track_index == 2
        assert result.volume == 0.5

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_VOLUME_RESULT)

        await set_track_volume(ctx=mock_context, track_index=3, volume=0.25)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_track_volume"
        assert req.params == {"track_index": 3, "volume": 0.25}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Track 9 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await set_track_volume(ctx=mock_context, track_index=9, volume=0.4)


class TestSetTrackPan:
    async def test_returns_track_pan_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_PAN_RESULT)

        result = await set_track_pan(ctx=mock_context, track_index=2, pan=-0.25)

        assert isinstance(result, TrackPanSetResult)
        assert result.track_index == 2
        assert result.pan == -0.25

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_PAN_RESULT)

        await set_track_pan(ctx=mock_context, track_index=1, pan=0.75)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_track_pan"
        assert req.params == {"track_index": 1, "pan": 0.75}


class TestGetMasterInfo:
    async def test_returns_master_info(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(MASTER_INFO_RESULT)

        result = await get_master_info(ctx=mock_context)

        assert isinstance(result, MasterTrackInfo)
        assert result.name == "Master"
        assert result.volume == 0.74
        assert result.pan == 0.0

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(MASTER_INFO_RESULT)

        await get_master_info(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.get_master_info"
        assert req.params == {}


class TestSetMasterVolume:
    async def test_returns_master_volume_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(MASTER_VOLUME_RESULT)

        result = await set_master_volume(ctx=mock_context, volume=0.8)

        assert isinstance(result, MasterVolumeSetResult)
        assert result.volume == 0.8

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(MASTER_VOLUME_RESULT)

        await set_master_volume(ctx=mock_context, volume=0.35)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_master_volume"
        assert req.params == {"volume": 0.35}

    async def test_raises_on_invalid_params(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="'volume' must be between 0.0 and 1.0, got 1.5",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_master_volume(ctx=mock_context, volume=0.9)
