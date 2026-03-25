"""Tests for session clip MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.clip import (
    ClipCreatedResult,
    ClipDuplicatedResult,
    ClipInfo,
    ClipRenamedResult,
    ClipSlotResult,
    create_clip,
    delete_clip,
    duplicate_clip,
    fire_clip,
    get_clip_info,
    set_clip_name,
    stop_clip,
)

TOOL_NAMES = [
    "create_clip",
    "delete_clip",
    "duplicate_clip",
    "set_clip_name",
    "fire_clip",
    "stop_clip",
    "get_clip_info",
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


CLIP_INFO_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "name": "Kick",
    "length": 4.0,
    "is_audio_clip": False,
    "is_midi_clip": True,
    "is_playing": True,
    "is_recording": False,
}


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

    def test_create_clip_schema(self) -> None:
        tool = self._get_tool("create_clip")
        props = tool.parameters["properties"]
        assert props["length"]["default"] == 4.0
        assert props["clip_slot_index"]["minimum"] == 1


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    @pytest.mark.parametrize("clip_slot_index", [0, -1])
    def test_create_clip_rejects_bad_slot(
        self,
        clip_slot_index: int,
    ) -> None:
        model = self._arg_model("create_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=clip_slot_index)

    def test_create_clip_rejects_non_positive_length(self) -> None:
        model = self._arg_model("create_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, length=0.0)


class TestCreateClip:
    async def test_sends_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 1, "clip_slot_index": 2, "length": 8.0},
        )

        result = await create_clip(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            length=8.0,
        )

        assert isinstance(result, ClipCreatedResult)
        assert result.length == 8.0
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.create"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "length": 8.0,
        }


class TestGetClipInfo:
    async def test_returns_clip_info(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_INFO_RESULT)

        result = await get_clip_info(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
        )

        assert isinstance(result, ClipInfo)
        assert result.name == "Kick"
        assert result.is_playing is True

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="No clip in slot",
        )
        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_clip_info(ctx=mock_context, track_index=1, clip_slot_index=1)


class TestDeleteDuplicateFireStop:
    async def test_delete_clip(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 1, "clip_slot_index": 3},
        )

        result = await delete_clip(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=3,
        )

        assert isinstance(result, ClipSlotResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.delete"

    async def test_duplicate_clip(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "source_clip_slot_index": 1,
                "new_clip_slot_index": 2,
            },
        )

        result = await duplicate_clip(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=1,
        )

        assert isinstance(result, ClipDuplicatedResult)
        assert result.new_clip_slot_index == 2
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.duplicate"

    async def test_set_clip_name(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "name": "Snare",
            },
        )

        result = await set_clip_name(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            name="Snare",
        )

        assert isinstance(result, ClipRenamedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.set_name"

    async def test_fire_and_stop(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 1, "clip_slot_index": 1},
        )

        await fire_clip(ctx=mock_context, track_index=1, clip_slot_index=1)
        assert mock_connection.send_command.call_args[0][0].command == "clip.fire"

        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 1, "clip_slot_index": 1},
        )
        await stop_clip(ctx=mock_context, track_index=1, clip_slot_index=1)
        assert mock_connection.send_command.call_args[0][0].command == "clip.stop"


class TestResponseModels:
    def test_clip_info_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            ClipInfo.model_validate({"track_index": 1})

    def test_clip_info_accepts_valid(self) -> None:
        c = ClipInfo.model_validate(CLIP_INFO_RESULT)
        assert c.name == "Kick"
