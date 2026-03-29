"""Tests for scene management MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.scene import (
    SceneActionResult,
    SceneCreatedResult,
    SceneDeletedResult,
    SceneDuplicatedResult,
    SceneInfo,
    SceneRenamedResult,
    ScenesResult,
    create_scene,
    delete_scene,
    duplicate_scene,
    fire_scene,
    get_scenes,
    set_scene_name,
    stop_scene,
)

TOOL_NAMES = [
    "get_scenes",
    "create_scene",
    "delete_scene",
    "duplicate_scene",
    "fire_scene",
    "stop_scene",
    "set_scene_name",
]

SCENES_RESULT = {
    "scenes": [
        {
            "scene_index": 1,
            "name": "Intro",
            "is_empty": False,
            "is_triggered": False,
            "tempo_enabled": True,
            "tempo": 120.0,
            "time_signature_enabled": True,
            "time_signature_numerator": 4,
            "time_signature_denominator": 4,
        },
        {
            "scene_index": 2,
            "name": "Breakdown",
            "is_empty": True,
            "is_triggered": True,
            "tempo_enabled": False,
            "tempo": None,
            "time_signature_enabled": False,
            "time_signature_numerator": None,
            "time_signature_denominator": None,
        },
    ]
}


def _ok_response(result: dict[str, Any], request_id: str = "test") -> CommandResponse:
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

    def test_create_scene_schema_defaults(self) -> None:
        tool = self._get_tool("create_scene")
        props = tool.parameters["properties"]
        assert props["index"]["default"] == -1
        assert props["index"]["minimum"] == -1

    def test_scene_index_minimums(self) -> None:
        tool = self._get_tool("delete_scene")
        props = tool.parameters["properties"]
        assert props["scene_index"]["minimum"] == 1

    def test_set_scene_name_schema(self) -> None:
        tool = self._get_tool("set_scene_name")
        props = tool.parameters["properties"]
        assert props["name"]["minLength"] == 1


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_create_scene_accepts_default_values(self) -> None:
        model = self._arg_model("create_scene")
        args = model()
        assert args.index == -1
        assert args.name is None

    def test_create_scene_rejects_index_below_append_sentinel(self) -> None:
        model = self._arg_model("create_scene")
        with pytest.raises(ValidationError):
            model(index=-2)

    @pytest.mark.parametrize("scene_index", [0, -1])
    def test_scene_actions_reject_non_positive_index(self, scene_index: int) -> None:
        model = self._arg_model("fire_scene")
        with pytest.raises(ValidationError):
            model(scene_index=scene_index)

    def test_set_scene_name_rejects_empty_name(self) -> None:
        model = self._arg_model("set_scene_name")
        with pytest.raises(ValidationError):
            model(scene_index=1, name="")


class TestGetScenes:
    async def test_returns_scene_models(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(SCENES_RESULT)

        result = await get_scenes(ctx=mock_context)

        assert isinstance(result, ScenesResult)
        assert len(result.scenes) == 2
        assert isinstance(result.scenes[0], SceneInfo)
        assert result.scenes[1].tempo is None
        assert result.scenes[1].time_signature_numerator is None

    async def test_sends_scene_get_all_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(SCENES_RESULT)

        await get_scenes(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.get_all"
        assert req.params == {}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INTERNAL_ERROR",
            message="scene listing failed",
        )

        with pytest.raises(CommandError, match="INTERNAL_ERROR"):
            await get_scenes(ctx=mock_context)


class TestCreateScene:
    async def test_default_append_without_name(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"scene_index": 3, "name": "Scene 3"}
        )

        result = await create_scene(ctx=mock_context)

        assert isinstance(result, SceneCreatedResult)
        assert result.scene_index == 3
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.create"
        assert req.params == {"index": -1}

    async def test_explicit_insert_and_name(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"scene_index": 2, "name": "Bridge"}
        )

        await create_scene(ctx=mock_context, index=1, name="Bridge")

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"index": 1, "name": "Bridge"}


class TestSceneActions:
    async def test_delete_scene(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"scene_index": 2})

        result = await delete_scene(ctx=mock_context, scene_index=2)

        assert isinstance(result, SceneDeletedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.delete"
        assert req.params == {"scene_index": 2}

    async def test_duplicate_scene(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"source_scene_index": 1, "new_scene_index": 2}
        )

        result = await duplicate_scene(ctx=mock_context, scene_index=1)

        assert isinstance(result, SceneDuplicatedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.duplicate"
        assert req.params == {"scene_index": 1}

    async def test_fire_scene(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"scene_index": 1})

        result = await fire_scene(ctx=mock_context, scene_index=1)

        assert isinstance(result, SceneActionResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.fire"
        assert req.params == {"scene_index": 1}

    async def test_stop_scene(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"scene_index": 2})

        result = await stop_scene(ctx=mock_context, scene_index=2)

        assert isinstance(result, SceneActionResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.stop"
        assert req.params == {"scene_index": 2}

    async def test_set_scene_name(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"scene_index": 1, "name": "Outro"}
        )

        result = await set_scene_name(ctx=mock_context, scene_index=1, name="Outro")

        assert isinstance(result, SceneRenamedResult)
        assert result.name == "Outro"
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "scene.set_name"
        assert req.params == {"scene_index": 1, "name": "Outro"}

    async def test_action_raises_remote_not_found(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Scene 9 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await delete_scene(ctx=mock_context, scene_index=9)
