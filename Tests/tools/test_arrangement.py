"""Tests for arrangement MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.arrangement import (
    ArrangementAudioImportResult,
    ArrangementClipCreatedResult,
    ArrangementClipInfo,
    ArrangementClipMovedResult,
    ArrangementClipsResult,
    ArrangementLengthResult,
    ArrangementLoopResult,
    JumpToTimeResult,
    LocatorCreatedResult,
    LocatorDeletedResult,
    LocatorInfo,
    LocatorRenamedResult,
    LocatorsResult,
    TakeLaneAudioImportResult,
    TakeLaneClipInfo,
    TakeLaneCreatedResult,
    TakeLaneInfo,
    TakeLaneMidiClipCreatedResult,
    TakeLaneRenamedResult,
    TakeLanesResult,
    create_arrangement_clip,
    create_locator,
    create_take_lane,
    create_take_lane_midi_clip,
    delete_locator,
    get_arrangement_clips,
    get_arrangement_length,
    get_locators,
    get_take_lanes,
    import_audio_to_arrangement,
    import_audio_to_take_lane,
    jump_to_time,
    move_arrangement_clip,
    set_arrangement_loop,
    set_locator_name,
    set_take_lane_name,
)

TOOL_NAMES = [
    "get_arrangement_clips",
    "create_arrangement_clip",
    "move_arrangement_clip",
    "get_arrangement_length",
    "set_arrangement_loop",
    "import_audio_to_arrangement",
    "get_take_lanes",
    "create_take_lane",
    "set_take_lane_name",
    "create_take_lane_midi_clip",
    "import_audio_to_take_lane",
    "get_locators",
    "create_locator",
    "delete_locator",
    "set_locator_name",
    "jump_to_time",
]

ARRANGEMENT_CLIPS_RESULT = {
    "track_index": None,
    "clips": [
        {
            "track_index": 1,
            "clip_index": 1,
            "name": "Verse",
            "start_time": 0.0,
            "end_time": 8.0,
            "length": 8.0,
            "is_audio_clip": False,
            "is_midi_clip": True,
        },
        {
            "track_index": 2,
            "clip_index": 1,
            "name": "Vocal",
            "start_time": 4.0,
            "end_time": 12.0,
            "length": 8.0,
            "is_audio_clip": True,
            "is_midi_clip": False,
        },
    ],
}

ARRANGEMENT_AUDIO_IMPORT_RESULT = {
    "track_index": 2,
    "clip_index": 2,
    "name": "vocal",
    "file_path": "/tmp/vocal.wav",
    "start_time": 12.0,
    "length": 8.5,
    "is_audio_clip": True,
}

TAKE_LANES_RESULT = {
    "track_index": 1,
    "take_lanes": [
        {
            "take_lane_index": 1,
            "name": "Comp A",
            "clips": [
                {
                    "clip_index": 1,
                    "name": "Verse Take",
                    "start_time": 8.0,
                    "end_time": 12.0,
                    "length": 4.0,
                    "is_audio_clip": False,
                    "is_midi_clip": True,
                }
            ],
        }
    ],
}

TAKE_LANE_CREATED_RESULT = {
    "track_index": 1,
    "take_lane_index": 2,
    "name": "MCP Take Lane",
}

TAKE_LANE_RENAMED_RESULT = {
    "track_index": 1,
    "take_lane_index": 2,
    "name": "Renamed Lane",
}

TAKE_LANE_MIDI_CLIP_CREATED_RESULT = {
    "track_index": 1,
    "take_lane_index": 2,
    "clip_index": 1,
    "start_time": 16.0,
    "length": 4.0,
    "name": "New MIDI Clip",
}

TAKE_LANE_AUDIO_IMPORT_RESULT = {
    "track_index": 2,
    "take_lane_index": 1,
    "clip_index": 2,
    "name": "vox",
    "file_path": "/tmp/vox.wav",
    "start_time": 24.0,
    "length": 8.5,
    "is_audio_clip": True,
}

LOCATORS_RESULT = {
    "locators": [
        {"locator_index": 1, "name": "Intro", "time": 0.0},
        {"locator_index": 2, "name": "Breakdown", "time": 16.0},
    ]
}

LOCATOR_CREATED_RESULT = {
    "locator_index": 3,
    "name": "MCP Locator",
    "time": 24.0,
}

LOCATOR_DELETED_RESULT = {
    "locator_index": 2,
    "name": "Breakdown",
    "time": 16.0,
}

LOCATOR_RENAMED_RESULT = {
    "locator_index": 1,
    "name": "MCP Renamed",
    "time": 0.0,
}

JUMP_TO_TIME_RESULT = {"time": 16.0}


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


def _schema_minimum(schema: dict[str, Any]) -> int | float | None:
    if "minimum" in schema:
        return schema["minimum"]
    for option in schema.get("anyOf", []):
        if "minimum" in option:
            return option["minimum"]
    return None


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

    def test_get_arrangement_clips_schema(self) -> None:
        tool = self._get_tool("get_arrangement_clips")
        props = tool.parameters["properties"]
        assert "track_index" in props
        assert _schema_minimum(props["track_index"]) == 1

    def test_move_arrangement_clip_schema(self) -> None:
        tool = self._get_tool("move_arrangement_clip")
        props = tool.parameters["properties"]
        assert props["clip_index"]["minimum"] == 1
        assert props["new_start_time"]["minimum"] == 0.0
        assert _schema_minimum(props["new_track_index"]) == 1

    def test_set_arrangement_loop_schema_defaults(self) -> None:
        tool = self._get_tool("set_arrangement_loop")
        props = tool.parameters["properties"]
        assert props["start_time"]["minimum"] == 0.0
        assert props["end_time"]["minimum"] == 0.0
        assert props["enabled"]["default"] is True

    def test_import_audio_to_arrangement_schema(self) -> None:
        tool = self._get_tool("import_audio_to_arrangement")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["start_time"]["minimum"] == 0.0
        assert props["file_path"]["type"] == "string"

    def test_get_take_lanes_schema(self) -> None:
        tool = self._get_tool("get_take_lanes")
        assert tool.parameters["properties"]["track_index"]["minimum"] == 1

    def test_create_take_lane_schema_defaults(self) -> None:
        tool = self._get_tool("create_take_lane")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["name"]["default"] is None

    def test_set_take_lane_name_schema(self) -> None:
        tool = self._get_tool("set_take_lane_name")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["take_lane_index"]["minimum"] == 1
        assert props["name"]["type"] == "string"

    def test_create_take_lane_midi_clip_schema(self) -> None:
        tool = self._get_tool("create_take_lane_midi_clip")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["take_lane_index"]["minimum"] == 1
        assert props["start_time"]["minimum"] == 0.0
        assert props["length"]["exclusiveMinimum"] == 0.0

    def test_import_audio_to_take_lane_schema(self) -> None:
        tool = self._get_tool("import_audio_to_take_lane")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["take_lane_index"]["minimum"] == 1
        assert props["start_time"]["minimum"] == 0.0
        assert props["file_path"]["type"] == "string"

    def test_get_locators_schema(self) -> None:
        tool = self._get_tool("get_locators")
        assert tool.parameters["properties"] == {}

    def test_create_locator_schema_defaults(self) -> None:
        tool = self._get_tool("create_locator")
        props = tool.parameters["properties"]
        assert props["time"]["minimum"] == 0.0
        assert props["name"]["default"] is None

    def test_delete_locator_schema(self) -> None:
        tool = self._get_tool("delete_locator")
        assert _schema_minimum(tool.parameters["properties"]["locator_index"]) == 1

    def test_set_locator_name_schema(self) -> None:
        tool = self._get_tool("set_locator_name")
        props = tool.parameters["properties"]
        assert _schema_minimum(props["locator_index"]) == 1
        assert props["name"]["type"] == "string"

    def test_jump_to_time_schema(self) -> None:
        tool = self._get_tool("jump_to_time")
        assert tool.parameters["properties"]["time"]["minimum"] == 0.0


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_get_arrangement_clips_accepts_omitted_track_index(self) -> None:
        model = self._arg_model("get_arrangement_clips")
        args = model()
        assert args.track_index is None

    @pytest.mark.parametrize("track_index", [0, -1])
    def test_create_arrangement_clip_rejects_bad_track_index(
        self,
        track_index: int,
    ) -> None:
        model = self._arg_model("create_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=track_index, start_time=0.0, length=4.0)

    def test_create_arrangement_clip_rejects_negative_start_time(self) -> None:
        model = self._arg_model("create_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, start_time=-1.0, length=4.0)

    def test_create_arrangement_clip_rejects_non_positive_length(self) -> None:
        model = self._arg_model("create_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, start_time=0.0, length=0.0)

    def test_move_arrangement_clip_rejects_non_positive_clip_index(self) -> None:
        model = self._arg_model("move_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_index=0, new_start_time=4.0)

    def test_move_arrangement_clip_rejects_negative_start_time(self) -> None:
        model = self._arg_model("move_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_index=1, new_start_time=-0.5)

    def test_set_arrangement_loop_rejects_negative_end_time(self) -> None:
        model = self._arg_model("set_arrangement_loop")
        with pytest.raises(ValidationError):
            model(start_time=0.0, end_time=-1.0)

    def test_import_audio_to_arrangement_rejects_relative_file_path(self) -> None:
        model = self._arg_model("import_audio_to_arrangement")
        with pytest.raises(ValidationError):
            model(track_index=2, file_path="audio/vocal.wav", start_time=4.0)

    def test_create_take_lane_accepts_omitted_name(self) -> None:
        model = self._arg_model("create_take_lane")
        args = model(track_index=1)
        assert args.name is None

    def test_create_take_lane_rejects_blank_name(self) -> None:
        model = self._arg_model("create_take_lane")
        with pytest.raises(ValidationError):
            model(track_index=1, name="   ")

    @pytest.mark.parametrize(
        "tool_name",
        ["set_take_lane_name", "create_take_lane_midi_clip"],
    )
    def test_take_lane_tools_reject_non_positive_take_lane_index(
        self,
        tool_name: str,
    ) -> None:
        model = self._arg_model(tool_name)
        with pytest.raises(ValidationError):
            if tool_name == "set_take_lane_name":
                model(track_index=1, take_lane_index=0, name="Lane")
            else:
                model(
                    track_index=1,
                    take_lane_index=0,
                    start_time=0.0,
                    length=4.0,
                )

    def test_set_take_lane_name_rejects_blank_name(self) -> None:
        model = self._arg_model("set_take_lane_name")
        with pytest.raises(ValidationError):
            model(track_index=1, take_lane_index=1, name="   ")

    def test_create_take_lane_midi_clip_rejects_non_positive_length(self) -> None:
        model = self._arg_model("create_take_lane_midi_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, take_lane_index=1, start_time=0.0, length=0.0)

    def test_import_audio_to_take_lane_rejects_relative_file_path(self) -> None:
        model = self._arg_model("import_audio_to_take_lane")
        with pytest.raises(ValidationError):
            model(
                track_index=2,
                take_lane_index=1,
                file_path="audio/vox.wav",
                start_time=8.0,
            )

    def test_create_locator_accepts_omitted_name(self) -> None:
        model = self._arg_model("create_locator")
        args = model(time=8.0)
        assert args.name is None

    def test_create_locator_rejects_blank_name(self) -> None:
        model = self._arg_model("create_locator")
        with pytest.raises(ValidationError):
            model(time=8.0, name="   ")

    def test_set_locator_name_rejects_blank_name(self) -> None:
        model = self._arg_model("set_locator_name")
        with pytest.raises(ValidationError):
            model(locator_index=1, name="   ")

    @pytest.mark.parametrize("time", [-1.0, -0.5])
    def test_jump_to_time_rejects_negative_time(self, time: float) -> None:
        model = self._arg_model("jump_to_time")
        with pytest.raises(ValidationError):
            model(time=time)


class TestGetArrangementClips:
    async def test_returns_arrangement_clips(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            ARRANGEMENT_CLIPS_RESULT
        )

        result = await get_arrangement_clips(ctx=mock_context)

        assert isinstance(result, ArrangementClipsResult)
        assert result.track_index is None
        assert len(result.clips) == 2
        assert isinstance(result.clips[0], ArrangementClipInfo)
        assert result.clips[1].is_audio_clip is True

    async def test_sends_empty_params_when_track_index_omitted(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            ARRANGEMENT_CLIPS_RESULT
        )

        await get_arrangement_clips(ctx=mock_context)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.get_clips"
        assert req.params == {}

    async def test_sends_track_index_when_provided(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 2,
                "clips": [ARRANGEMENT_CLIPS_RESULT["clips"][1]],
            }
        )

        await get_arrangement_clips(ctx=mock_context, track_index=2)

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"track_index": 2}

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
            await get_arrangement_clips(ctx=mock_context, track_index=9)


class TestLocators:
    async def test_get_locators_returns_nested_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(LOCATORS_RESULT)

        result = await get_locators(ctx=mock_context)

        assert isinstance(result, LocatorsResult)
        assert isinstance(result.locators[0], LocatorInfo)
        assert result.locators[1].name == "Breakdown"

    async def test_create_locator_sends_name_when_provided(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(LOCATOR_CREATED_RESULT)

        result = await create_locator(
            ctx=mock_context,
            time=24.0,
            name="MCP Locator",
        )

        assert isinstance(result, LocatorCreatedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.create_locator"
        assert req.params == {"time": 24.0, "name": "MCP Locator"}

    async def test_create_locator_omits_name_when_missing(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(LOCATOR_CREATED_RESULT)

        await create_locator(ctx=mock_context, time=24.0)

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"time": 24.0}

    async def test_delete_locator_sends_locator_index(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(LOCATOR_DELETED_RESULT)

        result = await delete_locator(ctx=mock_context, locator_index=2)

        assert isinstance(result, LocatorDeletedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.delete_locator"
        assert req.params == {"locator_index": 2}

    async def test_set_locator_name_sends_trimmed_name(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(LOCATOR_RENAMED_RESULT)

        result = await set_locator_name(
            ctx=mock_context,
            locator_index=1,
            name="MCP Renamed",
        )

        assert isinstance(result, LocatorRenamedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.set_locator_name"
        assert req.params == {"locator_index": 1, "name": "MCP Renamed"}

    async def test_jump_to_time_sends_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(JUMP_TO_TIME_RESULT)

        result = await jump_to_time(ctx=mock_context, time=16.0)

        assert isinstance(result, JumpToTimeResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.jump_to_time"
        assert req.params == {"time": 16.0}

    async def test_create_locator_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="A locator already exists at time 16.0",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await create_locator(ctx=mock_context, time=16.0)


class TestTakeLanes:
    async def test_get_take_lanes_returns_nested_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TAKE_LANES_RESULT)

        result = await get_take_lanes(ctx=mock_context, track_index=1)

        assert isinstance(result, TakeLanesResult)
        assert isinstance(result.take_lanes[0], TakeLaneInfo)
        assert isinstance(result.take_lanes[0].clips[0], TakeLaneClipInfo)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.get_take_lanes"
        assert req.params == {"track_index": 1}

    async def test_create_take_lane_sends_name_when_provided(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TAKE_LANE_CREATED_RESULT
        )

        result = await create_take_lane(
            ctx=mock_context,
            track_index=1,
            name="MCP Take Lane",
        )

        assert isinstance(result, TakeLaneCreatedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.create_take_lane"
        assert req.params == {"track_index": 1, "name": "MCP Take Lane"}

    async def test_create_take_lane_omits_name_when_missing(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TAKE_LANE_CREATED_RESULT
        )

        await create_take_lane(ctx=mock_context, track_index=1)

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"track_index": 1}

    async def test_set_take_lane_name_sends_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TAKE_LANE_RENAMED_RESULT
        )

        result = await set_take_lane_name(
            ctx=mock_context,
            track_index=1,
            take_lane_index=2,
            name="Renamed Lane",
        )

        assert isinstance(result, TakeLaneRenamedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.set_take_lane_name"
        assert req.params == {
            "track_index": 1,
            "take_lane_index": 2,
            "name": "Renamed Lane",
        }

    async def test_create_take_lane_midi_clip_sends_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TAKE_LANE_MIDI_CLIP_CREATED_RESULT
        )

        result = await create_take_lane_midi_clip(
            ctx=mock_context,
            track_index=1,
            take_lane_index=2,
            start_time=16.0,
            length=4.0,
        )

        assert isinstance(result, TakeLaneMidiClipCreatedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.create_take_lane_midi_clip"
        assert req.params == {
            "track_index": 1,
            "take_lane_index": 2,
            "start_time": 16.0,
            "length": 4.0,
        }

    async def test_import_audio_to_take_lane_sends_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vox.wav"
        file_path.write_bytes(b"RIFF")
        response_result = dict(TAKE_LANE_AUDIO_IMPORT_RESULT)
        response_result["file_path"] = str(file_path)
        mock_connection.send_command.return_value = _ok_response(response_result)

        result = await import_audio_to_take_lane(
            ctx=mock_context,
            track_index=2,
            take_lane_index=1,
            file_path=str(file_path),
            start_time=24.0,
        )

        assert isinstance(result, TakeLaneAudioImportResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.import_audio_to_take_lane"
        assert req.params == {
            "track_index": 2,
            "take_lane_index": 1,
            "file_path": str(file_path),
            "start_time": 24.0,
        }

    async def test_get_take_lanes_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Track 9 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_take_lanes(ctx=mock_context, track_index=9)


class TestCreateArrangementClip:
    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_index": 2,
                "start_time": 16.0,
                "length": 8.0,
                "name": "New MIDI Clip",
            }
        )

        result = await create_arrangement_clip(
            ctx=mock_context,
            track_index=1,
            start_time=16.0,
            length=8.0,
        )

        assert isinstance(result, ArrangementClipCreatedResult)
        assert result.clip_index == 2
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.create_clip"
        assert req.params == {
            "track_index": 1,
            "start_time": 16.0,
            "length": 8.0,
        }


class TestMoveArrangementClip:
    async def test_sends_correct_command_with_optional_track(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "source_track_index": 1,
                "source_clip_index": 1,
                "target_track_index": 2,
                "target_clip_index": 1,
                "start_time": 24.0,
            }
        )

        result = await move_arrangement_clip(
            ctx=mock_context,
            track_index=1,
            clip_index=1,
            new_start_time=24.0,
            new_track_index=2,
        )

        assert isinstance(result, ArrangementClipMovedResult)
        assert result.target_track_index == 2
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.move_clip"
        assert req.params == {
            "track_index": 1,
            "clip_index": 1,
            "new_start_time": 24.0,
            "new_track_index": 2,
        }

    async def test_omits_optional_target_track_when_missing(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "source_track_index": 1,
                "source_clip_index": 1,
                "target_track_index": 1,
                "target_clip_index": 1,
                "start_time": 12.0,
            }
        )

        await move_arrangement_clip(
            ctx=mock_context,
            track_index=1,
            clip_index=1,
            new_start_time=12.0,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {
            "track_index": 1,
            "clip_index": 1,
            "new_start_time": 12.0,
        }


class TestArrangementLengthAndLoop:
    async def test_get_arrangement_length(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"song_length": 128.0})

        result = await get_arrangement_length(ctx=mock_context)

        assert isinstance(result, ArrangementLengthResult)
        assert result.song_length == 128.0
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.get_length"
        assert req.params == {}

    async def test_set_arrangement_loop(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"start_time": 8.0, "end_time": 16.0, "enabled": False}
        )

        result = await set_arrangement_loop(
            ctx=mock_context,
            start_time=8.0,
            end_time=16.0,
            enabled=False,
        )

        assert isinstance(result, ArrangementLoopResult)
        assert result.enabled is False
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.set_loop"
        assert req.params == {
            "start_time": 8.0,
            "end_time": 16.0,
            "enabled": False,
        }

    async def test_set_arrangement_loop_rejects_invalid_range(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        with pytest.raises(ValueError, match="end_time"):
            await set_arrangement_loop(
                ctx=mock_context,
                start_time=8.0,
                end_time=8.0,
            )

        mock_connection.send_command.assert_not_called()


class TestImportAudioToArrangement:
    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "vocal.wav"
        file_path.write_bytes(b"RIFF")
        response_result = dict(ARRANGEMENT_AUDIO_IMPORT_RESULT)
        response_result["file_path"] = str(file_path)
        mock_connection.send_command.return_value = _ok_response(response_result)

        result = await import_audio_to_arrangement(
            ctx=mock_context,
            track_index=2,
            file_path=str(file_path),
            start_time=12.0,
        )

        assert isinstance(result, ArrangementAudioImportResult)
        assert result.clip_index == 2
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.import_audio"
        assert req.params == {
            "track_index": 2,
            "file_path": str(file_path),
            "start_time": 12.0,
        }

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "missing.wav"
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message=f"File does not exist: {file_path}",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await import_audio_to_arrangement(
                ctx=mock_context,
                track_index=2,
                file_path=str(file_path),
                start_time=4.0,
            )


class TestResponseModels:
    def test_arrangement_audio_import_accepts_valid(self) -> None:
        result = ArrangementAudioImportResult.model_validate(
            ARRANGEMENT_AUDIO_IMPORT_RESULT
        )
        assert result.is_audio_clip is True

    def test_take_lane_models_accept_valid(self) -> None:
        take_lanes = TakeLanesResult.model_validate(TAKE_LANES_RESULT)
        assert take_lanes.take_lanes[0].take_lane_index == 1
        assert take_lanes.take_lanes[0].clips[0].is_midi_clip is True
        assert TakeLaneCreatedResult.model_validate(TAKE_LANE_CREATED_RESULT).name == (
            "MCP Take Lane"
        )
        assert (
            TakeLaneRenamedResult.model_validate(TAKE_LANE_RENAMED_RESULT).name
            == "Renamed Lane"
        )
        assert (
            TakeLaneMidiClipCreatedResult.model_validate(
                TAKE_LANE_MIDI_CLIP_CREATED_RESULT
            ).clip_index
            == 1
        )
        assert (
            TakeLaneAudioImportResult.model_validate(
                TAKE_LANE_AUDIO_IMPORT_RESULT
            ).is_audio_clip
            is True
        )

    def test_locator_models_accept_valid(self) -> None:
        locators = LocatorsResult.model_validate(LOCATORS_RESULT)
        assert locators.locators[0].locator_index == 1
        assert LocatorCreatedResult.model_validate(LOCATOR_CREATED_RESULT).name == (
            "MCP Locator"
        )
        assert LocatorDeletedResult.model_validate(LOCATOR_DELETED_RESULT).time == 16.0
        assert LocatorRenamedResult.model_validate(LOCATOR_RENAMED_RESULT).name == (
            "MCP Renamed"
        )
        assert JumpToTimeResult.model_validate(JUMP_TO_TIME_RESULT).time == 16.0
