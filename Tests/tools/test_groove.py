"""Tests for groove pool MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.groove import (
    GrooveAppliedResult,
    GrooveInfo,
    GroovePoolResult,
    apply_groove,
    get_groove_pool,
)

TOOL_NAMES = [
    "get_groove_pool",
    "apply_groove",
]

GROOVE_POOL_RESULT = {
    "grooves": [
        {
            "groove_index": 1,
            "name": "MPC 16 Swing 57",
            "base": 2,
            "quantization_amount": 0.0,
            "timing_amount": 0.57,
            "random_amount": 0.0,
            "velocity_amount": 0.5,
        },
        {
            "groove_index": 2,
            "name": "Swing 16",
            "base": 2,
            "quantization_amount": 0.25,
            "timing_amount": 0.5,
            "random_amount": 0.0,
            "velocity_amount": 0.25,
        },
    ]
}

GROOVE_APPLIED_RESULT = {
    "track_index": 2,
    "clip_slot_index": 1,
    "groove_index": 1,
    "groove_name": "MPC 16 Swing 57",
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

    def test_get_groove_pool_has_no_required_params(self) -> None:
        tool = self._get_tool("get_groove_pool")
        assert tool.parameters.get("required", []) == []

    def test_apply_groove_schema(self) -> None:
        tool = self._get_tool("apply_groove")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["clip_slot_index"]["minimum"] == 1
        assert props["groove_index"]["minimum"] == 1
        assert tool.parameters["required"] == [
            "track_index",
            "clip_slot_index",
            "groove_index",
        ]


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_get_groove_pool_requires_no_arguments(self) -> None:
        model = self._arg_model("get_groove_pool")
        args = model()
        assert args.model_dump() == {}

    def test_apply_groove_requires_all_arguments(self) -> None:
        model = self._arg_model("apply_groove")
        with pytest.raises(ValidationError):
            model()

    @pytest.mark.parametrize("track_index", [0, -1])
    def test_apply_groove_rejects_bad_track_index(self, track_index: int) -> None:
        model = self._arg_model("apply_groove")
        with pytest.raises(ValidationError):
            model(track_index=track_index, clip_slot_index=1, groove_index=1)

    @pytest.mark.parametrize("clip_slot_index", [0, -1])
    def test_apply_groove_rejects_bad_clip_slot_index(
        self, clip_slot_index: int
    ) -> None:
        model = self._arg_model("apply_groove")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=clip_slot_index, groove_index=1)

    @pytest.mark.parametrize("groove_index", [0, -1])
    def test_apply_groove_rejects_bad_groove_index(self, groove_index: int) -> None:
        model = self._arg_model("apply_groove")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, groove_index=groove_index)


class TestGetGroovePool:
    async def test_returns_groove_models(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(GROOVE_POOL_RESULT)

        result = await get_groove_pool(ctx=mock_context)

        assert isinstance(result, GroovePoolResult)
        assert isinstance(result.grooves[0], GrooveInfo)
        assert result.grooves[0].groove_index == 1
        assert result.grooves[0].name == "MPC 16 Swing 57"

    async def test_sends_groove_get_pool_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(GROOVE_POOL_RESULT)

        await get_groove_pool(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "groove.get_pool"
        assert req.params == {}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INTERNAL_ERROR",
            message="groove lookup failed",
        )

        with pytest.raises(CommandError, match="INTERNAL_ERROR"):
            await get_groove_pool(ctx=mock_context)


class TestApplyGroove:
    async def test_returns_applied_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(GROOVE_APPLIED_RESULT)

        result = await apply_groove(
            ctx=mock_context,
            track_index=2,
            clip_slot_index=1,
            groove_index=1,
        )

        assert isinstance(result, GrooveAppliedResult)
        assert result.groove_name == "MPC 16 Swing 57"

    async def test_sends_groove_apply_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(GROOVE_APPLIED_RESULT)

        await apply_groove(
            ctx=mock_context,
            track_index=2,
            clip_slot_index=1,
            groove_index=1,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "groove.apply"
        assert req.params == {
            "track_index": 2,
            "clip_slot_index": 1,
            "groove_index": 1,
        }

    async def test_raises_on_not_found(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Groove 99 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await apply_groove(
                ctx=mock_context,
                track_index=2,
                clip_slot_index=1,
                groove_index=99,
            )
