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
    create_arrangement_clip,
    get_arrangement_clips,
    get_arrangement_length,
    import_audio_to_arrangement,
    move_arrangement_clip,
    set_arrangement_loop,
)

TOOL_NAMES = [
    "get_arrangement_clips",
    "create_arrangement_clip",
    "move_arrangement_clip",
    "get_arrangement_length",
    "set_arrangement_loop",
    "import_audio_to_arrangement",
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
