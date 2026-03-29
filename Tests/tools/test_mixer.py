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
    ReturnPanSetResult,
    ReturnTrackInfo,
    ReturnTracksResult,
    ReturnVolumeSetResult,
    SendLevelSetResult,
    TrackPanSetResult,
    TrackVolumeSetResult,
    get_master_info,
    get_return_tracks,
    set_master_volume,
    set_return_pan,
    set_return_volume,
    set_send_level,
    set_track_pan,
    set_track_volume,
)

TOOL_NAMES = [
    "set_track_volume",
    "set_track_pan",
    "get_return_tracks",
    "set_send_level",
    "get_master_info",
    "set_master_volume",
    "set_return_volume",
    "set_return_pan",
]

MASTER_INFO_RESULT = {
    "name": "Master",
    "volume": 0.74,
    "pan": 0.0,
}

RETURN_TRACKS_RESULT = {
    "return_tracks": [
        {
            "return_index": 1,
            "name": "A Return",
            "volume": 0.61,
            "pan": -0.2,
        },
        {
            "return_index": 2,
            "name": "B Return",
            "volume": 0.49,
            "pan": 0.15,
        },
    ]
}

TRACK_VOLUME_RESULT = {
    "track_index": 2,
    "volume": 0.5,
}

TRACK_PAN_RESULT = {
    "track_index": 2,
    "pan": -0.25,
}

SEND_LEVEL_RESULT = {
    "track_index": 2,
    "send_index": 1,
    "level": 0.33,
}

MASTER_VOLUME_RESULT = {
    "volume": 0.8,
}

RETURN_VOLUME_RESULT = {
    "return_index": 1,
    "volume": 0.64,
}

RETURN_PAN_RESULT = {
    "return_index": 1,
    "pan": -0.45,
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

    def test_get_return_tracks_schema(self) -> None:
        tool = self._get_tool("get_return_tracks")
        assert tool.parameters["properties"] == {}
        assert "required" not in tool.parameters

    def test_set_send_level_schema(self) -> None:
        tool = self._get_tool("set_send_level")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["send_index"]["minimum"] == 1
        assert props["level"]["minimum"] == 0.0
        assert props["level"]["maximum"] == 1.0

    def test_set_master_volume_schema(self) -> None:
        tool = self._get_tool("set_master_volume")
        props = tool.parameters["properties"]
        assert props["volume"]["minimum"] == 0.0
        assert props["volume"]["maximum"] == 1.0

    def test_set_return_volume_schema(self) -> None:
        tool = self._get_tool("set_return_volume")
        props = tool.parameters["properties"]
        assert props["return_index"]["minimum"] == 1
        assert props["volume"]["minimum"] == 0.0
        assert props["volume"]["maximum"] == 1.0

    def test_set_return_pan_schema(self) -> None:
        tool = self._get_tool("set_return_pan")
        props = tool.parameters["properties"]
        assert props["return_index"]["minimum"] == 1
        assert props["pan"]["minimum"] == -1.0
        assert props["pan"]["maximum"] == 1.0


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

    def test_set_send_level_rejects_non_positive_send_index(self) -> None:
        model = self._arg_model("set_send_level")
        with pytest.raises(ValidationError):
            model(track_index=1, send_index=0, level=0.5)

    @pytest.mark.parametrize("level", [-0.1, 1.1])
    def test_set_send_level_rejects_out_of_range_level(self, level: float) -> None:
        model = self._arg_model("set_send_level")
        with pytest.raises(ValidationError):
            model(track_index=1, send_index=1, level=level)

    def test_set_master_volume_accepts_upper_bound(self) -> None:
        model = self._arg_model("set_master_volume")
        args = model(volume=1.0)
        assert args.volume == 1.0

    def test_set_return_volume_rejects_non_positive_return_index(self) -> None:
        model = self._arg_model("set_return_volume")
        with pytest.raises(ValidationError):
            model(return_index=0, volume=0.5)

    @pytest.mark.parametrize("volume", [-0.1, 1.1])
    def test_set_return_volume_rejects_out_of_range_volume(self, volume: float) -> None:
        model = self._arg_model("set_return_volume")
        with pytest.raises(ValidationError):
            model(return_index=1, volume=volume)

    @pytest.mark.parametrize("pan", [-1.1, 1.1])
    def test_set_return_pan_rejects_out_of_range_pan(self, pan: float) -> None:
        model = self._arg_model("set_return_pan")
        with pytest.raises(ValidationError):
            model(return_index=1, pan=pan)


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


class TestGetReturnTracks:
    async def test_returns_return_tracks(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_TRACKS_RESULT)

        result = await get_return_tracks(ctx=mock_context)

        assert isinstance(result, ReturnTracksResult)
        assert result.return_tracks == [
            ReturnTrackInfo(
                return_index=1,
                name="A Return",
                volume=0.61,
                pan=-0.2,
            ),
            ReturnTrackInfo(
                return_index=2,
                name="B Return",
                volume=0.49,
                pan=0.15,
            ),
        ]

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_TRACKS_RESULT)

        await get_return_tracks(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.get_return_tracks"
        assert req.params == {}


class TestSetSendLevel:
    async def test_returns_send_level_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(SEND_LEVEL_RESULT)

        result = await set_send_level(
            ctx=mock_context,
            track_index=2,
            send_index=1,
            level=0.33,
        )

        assert isinstance(result, SendLevelSetResult)
        assert result.track_index == 2
        assert result.send_index == 1
        assert result.level == 0.33

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(SEND_LEVEL_RESULT)

        await set_send_level(
            ctx=mock_context,
            track_index=3,
            send_index=2,
            level=0.75,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_send_level"
        assert req.params == {"track_index": 3, "send_index": 2, "level": 0.75}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Send 4 does not exist for track 1",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await set_send_level(
                ctx=mock_context,
                track_index=1,
                send_index=4,
                level=0.5,
            )


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


class TestSetReturnVolume:
    async def test_returns_return_volume_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_VOLUME_RESULT)

        result = await set_return_volume(ctx=mock_context, return_index=1, volume=0.64)

        assert isinstance(result, ReturnVolumeSetResult)
        assert result.return_index == 1
        assert result.volume == 0.64

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_VOLUME_RESULT)

        await set_return_volume(ctx=mock_context, return_index=2, volume=0.27)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_return_volume"
        assert req.params == {"return_index": 2, "volume": 0.27}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Return track 9 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await set_return_volume(ctx=mock_context, return_index=9, volume=0.5)


class TestSetReturnPan:
    async def test_returns_return_pan_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_PAN_RESULT)

        result = await set_return_pan(ctx=mock_context, return_index=1, pan=-0.45)

        assert isinstance(result, ReturnPanSetResult)
        assert result.return_index == 1
        assert result.pan == -0.45

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(RETURN_PAN_RESULT)

        await set_return_pan(ctx=mock_context, return_index=2, pan=0.35)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "mixer.set_return_pan"
        assert req.params == {"return_index": 2, "pan": 0.35}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="'pan' must be between -1.0 and 1.0, got 1.5",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_return_pan(ctx=mock_context, return_index=1, pan=0.5)
