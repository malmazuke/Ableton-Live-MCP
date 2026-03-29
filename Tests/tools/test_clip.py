"""Tests for session clip MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.clip import (
    ClipAutomationPoint,
    ClipAutomationResult,
    ClipAutomationSetResult,
    ClipColorResult,
    ClipCreatedResult,
    ClipDuplicatedResult,
    ClipInfo,
    ClipLoopResult,
    ClipNote,
    ClipNotesResult,
    ClipRenamedResult,
    ClipSlotResult,
    NotesAddedResult,
    NotesRemovedResult,
    NotesSetResult,
    SessionAudioImportResult,
    add_notes_to_clip,
    create_clip,
    delete_clip,
    duplicate_clip,
    fire_clip,
    get_clip_automation,
    get_clip_info,
    get_clip_notes,
    import_audio_to_session,
    remove_notes,
    set_clip_automation,
    set_clip_color,
    set_clip_loop,
    set_clip_name,
    set_clip_notes,
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
    "import_audio_to_session",
    "set_clip_loop",
    "set_clip_color",
    "get_clip_notes",
    "get_clip_automation",
    "add_notes_to_clip",
    "set_clip_automation",
    "remove_notes",
    "set_clip_notes",
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

CLIP_NOTES_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "notes": [
        {
            "note_id": 11,
            "pitch": 60,
            "start_time": 0.0,
            "duration": 0.5,
            "velocity": 100.0,
            "mute": False,
            "probability": 0.75,
        },
        {
            "note_id": 12,
            "pitch": 67,
            "start_time": 1.0,
            "duration": 0.25,
            "velocity": 96.0,
            "mute": True,
            "velocity_deviation": 4.0,
        },
    ],
}

CLIP_LOOP_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "loop_start": 0.0,
    "loop_end": 4.0,
    "looping": True,
}

CLIP_COLOR_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "color_index": 17,
}

SESSION_AUDIO_IMPORT_RESULT = {
    "track_index": 2,
    "clip_slot_index": 3,
    "name": "beat",
    "file_path": "/tmp/beat.wav",
    "length": 7.5,
    "is_audio_clip": True,
}

CLIP_AUTOMATION_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "device_index": 1,
    "parameter_index": 2,
    "device_name": "Auto Filter",
    "parameter_name": "Frequency",
    "points": [
        {"time": 0.0, "value": 250.0},
        {"time": 1.0, "value": 5000.0, "step_length": 0.5},
    ],
}

CLIP_AUTOMATION_SET_RESULT = {
    "track_index": 1,
    "clip_slot_index": 2,
    "device_index": 1,
    "parameter_index": 2,
    "device_name": "Auto Filter",
    "parameter_name": "Frequency",
    "point_count": 2,
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

    def test_add_notes_to_clip_schema(self) -> None:
        tool = self._get_tool("add_notes_to_clip")
        props = tool.parameters["properties"]
        assert props["notes"]["minItems"] == 1

    def test_set_clip_loop_schema(self) -> None:
        tool = self._get_tool("set_clip_loop")
        props = tool.parameters["properties"]
        assert props["loop_start"]["minimum"] == 0.0
        assert props["looping"]["default"] is True

    def test_set_clip_color_schema(self) -> None:
        tool = self._get_tool("set_clip_color")
        props = tool.parameters["properties"]
        assert props["color_index"]["minimum"] == 0

    def test_import_audio_to_session_schema(self) -> None:
        tool = self._get_tool("import_audio_to_session")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["clip_slot_index"]["minimum"] == 1
        assert props["file_path"]["type"] == "string"

    def test_set_clip_automation_schema(self) -> None:
        tool = self._get_tool("set_clip_automation")
        props = tool.parameters["properties"]
        assert props["points"]["minItems"] == 1

    def test_remove_notes_schema(self) -> None:
        tool = self._get_tool("remove_notes")
        props = tool.parameters["properties"]
        assert props["from_pitch"]["minimum"] == 0
        assert props["from_pitch"]["maximum"] == 127
        assert props["pitch_span"]["minimum"] == 1
        assert props["pitch_span"]["maximum"] == 128


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

    def test_set_clip_loop_rejects_negative_start(self) -> None:
        model = self._arg_model("set_clip_loop")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                clip_slot_index=1,
                loop_start=-0.1,
                loop_end=4.0,
            )

    def test_set_clip_color_rejects_negative_index(self) -> None:
        model = self._arg_model("set_clip_color")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, color_index=-1)

    def test_import_audio_to_session_rejects_relative_file_path(self) -> None:
        model = self._arg_model("import_audio_to_session")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, file_path="samples/beat.wav")

    def test_set_clip_automation_rejects_empty_point_list(self) -> None:
        model = self._arg_model("set_clip_automation")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                clip_slot_index=1,
                device_index=1,
                parameter_index=1,
                points=[],
            )

    def test_set_clip_automation_rejects_negative_point_time(self) -> None:
        model = self._arg_model("set_clip_automation")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                clip_slot_index=1,
                device_index=1,
                parameter_index=1,
                points=[{"time": -0.1, "value": 0.5}],
            )

    def test_add_notes_accepts_lean_note_arrays(self) -> None:
        model = self._arg_model("add_notes_to_clip")
        args = model(track_index=1, clip_slot_index=1, notes=[[60, 0.0, 0.5, 100]])
        assert len(args.notes) == 1

    def test_add_notes_accepts_object_notes(self) -> None:
        model = self._arg_model("add_notes_to_clip")
        args = model(
            track_index=1,
            clip_slot_index=1,
            notes=[
                {
                    "pitch": 60,
                    "start_time": 0.0,
                    "duration": 0.5,
                    "velocity": 100.0,
                    "mute": True,
                    "probability": 0.5,
                    "velocity_deviation": 6.0,
                }
            ],
        )
        assert len(args.notes) == 1

    def test_add_notes_rejects_empty_list(self) -> None:
        model = self._arg_model("add_notes_to_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, notes=[])

    @pytest.mark.parametrize("pitch", [-1, 128])
    def test_add_notes_rejects_out_of_range_pitch(self, pitch: int) -> None:
        model = self._arg_model("add_notes_to_clip")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                clip_slot_index=1,
                notes=[[pitch, 0.0, 0.5, 100]],
            )

    def test_set_clip_notes_accepts_empty_list(self) -> None:
        model = self._arg_model("set_clip_notes")
        args = model(track_index=1, clip_slot_index=1, notes=[])
        assert args.notes == []

    @pytest.mark.parametrize("time_span", [0.0, -1.0])
    def test_remove_notes_rejects_non_positive_time_span(
        self,
        time_span: float,
    ) -> None:
        model = self._arg_model("remove_notes")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_slot_index=1, time_span=time_span)


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


class TestGetClipNotes:
    async def test_returns_clip_notes(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_NOTES_RESULT)

        result = await get_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
        )

        assert isinstance(result, ClipNotesResult)
        assert len(result.notes) == 2
        assert isinstance(result.notes[0], ClipNote)
        assert result.notes[0].note_id == 11
        assert result.notes[1].mute is True

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_NOTES_RESULT)

        await get_clip_notes(ctx=mock_context, track_index=1, clip_slot_index=2)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.get_notes"
        assert req.params == {"track_index": 1, "clip_slot_index": 2}


class TestSetClipLoop:
    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_LOOP_RESULT)

        result = await set_clip_loop(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            loop_start=0.0,
            loop_end=4.0,
        )

        assert isinstance(result, ClipLoopResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.set_loop"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "loop_start": 0.0,
            "loop_end": 4.0,
            "looping": True,
        }

    async def test_rejects_invalid_range_before_send(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        with pytest.raises(ValueError, match="loop_end"):
            await set_clip_loop(
                ctx=mock_context,
                track_index=1,
                clip_slot_index=2,
                loop_start=4.0,
                loop_end=4.0,
            )

        mock_connection.send_command.assert_not_called()


class TestSetClipColor:
    async def test_returns_color_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_COLOR_RESULT)

        result = await set_clip_color(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            color_index=17,
        )

        assert isinstance(result, ClipColorResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.set_color"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "color_index": 17,
        }


class TestClipAutomation:
    async def test_get_clip_automation_returns_points(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(CLIP_AUTOMATION_RESULT)

        result = await get_clip_automation(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            device_index=1,
            parameter_index=2,
        )

        assert isinstance(result, ClipAutomationResult)
        assert isinstance(result.points[0], ClipAutomationPoint)
        assert result.points[0].step_length == 0.0
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.get_automation"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "device_index": 1,
            "parameter_index": 2,
        }

    async def test_set_clip_automation_sends_points(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            CLIP_AUTOMATION_SET_RESULT
        )

        result = await set_clip_automation(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            device_index=1,
            parameter_index=2,
            points=[
                {"time": 0.0, "value": 250.0},
                {"time": 1.0, "value": 5000.0, "step_length": 0.5},
            ],
        )

        assert isinstance(result, ClipAutomationSetResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.set_automation"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "device_index": 1,
            "parameter_index": 2,
            "points": [
                {"time": 0.0, "value": 250.0, "step_length": 0.0},
                {"time": 1.0, "value": 5000.0, "step_length": 0.5},
            ],
        }

    async def test_get_clip_automation_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Parameter 2 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_clip_automation(
                ctx=mock_context,
                track_index=1,
                clip_slot_index=2,
                device_index=1,
                parameter_index=2,
            )


class TestAddNotesToClip:
    async def test_normalizes_lean_note_arrays(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "added_count": 1,
                "note_ids": [42],
            }
        )

        result = await add_notes_to_clip(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            notes=[[60, 0.0, 0.5, 100]],
        )

        assert isinstance(result, NotesAddedResult)
        assert result.note_ids == [42]
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.add_notes"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "notes": [
                {
                    "pitch": 60,
                    "start_time": 0.0,
                    "duration": 0.5,
                    "velocity": 100.0,
                    "mute": False,
                }
            ],
        }

    async def test_normalizes_object_notes(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "added_count": 1,
                "note_ids": [99],
            }
        )

        await add_notes_to_clip(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            notes=[
                {
                    "pitch": 67,
                    "start_time": 1.0,
                    "duration": 0.25,
                    "velocity": 96.0,
                    "mute": True,
                    "probability": 0.5,
                    "velocity_deviation": 8.0,
                }
            ],
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params["notes"] == [
            {
                "pitch": 67,
                "start_time": 1.0,
                "duration": 0.25,
                "velocity": 96.0,
                "mute": True,
                "probability": 0.5,
                "velocity_deviation": 8.0,
            }
        ]

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="bad note payload",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await add_notes_to_clip(
                ctx=mock_context,
                track_index=1,
                clip_slot_index=2,
                notes=[[60, 0.0, 0.5, 100]],
            )


class TestRemoveNotes:
    async def test_sends_default_region(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "removed_count": 3,
            }
        )

        result = await remove_notes(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
        )

        assert isinstance(result, NotesRemovedResult)
        assert result.removed_count == 3
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.remove_notes"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "from_pitch": 0,
            "pitch_span": 128,
            "from_time": 0.0,
        }

    async def test_includes_time_span_when_provided(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "removed_count": 1,
            }
        )

        await remove_notes(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            from_pitch=60,
            pitch_span=4,
            from_time=1.0,
            time_span=2.0,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "from_pitch": 60,
            "pitch_span": 4,
            "from_time": 1.0,
            "time_span": 2.0,
        }


class TestSetClipNotes:
    async def test_accepts_empty_notes_for_clear(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_slot_index": 2,
                "removed_count": 2,
                "added_count": 0,
                "note_ids": [],
            }
        )

        result = await set_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_slot_index=2,
            notes=[],
        )

        assert isinstance(result, NotesSetResult)
        assert result.added_count == 0
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.set_notes"
        assert req.params == {
            "track_index": 1,
            "clip_slot_index": 2,
            "notes": [],
        }


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


class TestImportAudioToSession:
    async def test_import_audio_to_session(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
        tmp_path,
    ) -> None:
        file_path = tmp_path / "beat.wav"
        file_path.write_bytes(b"RIFF")
        response_result = dict(SESSION_AUDIO_IMPORT_RESULT)
        response_result["file_path"] = str(file_path)
        mock_connection.send_command.return_value = _ok_response(response_result)

        result = await import_audio_to_session(
            ctx=mock_context,
            track_index=2,
            clip_slot_index=3,
            file_path=str(file_path),
        )

        assert isinstance(result, SessionAudioImportResult)
        assert result.clip_slot_index == 3
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "clip.import_audio"
        assert req.params == {
            "track_index": 2,
            "clip_slot_index": 3,
            "file_path": str(file_path),
        }

    async def test_import_audio_to_session_raises_on_error(
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
            await import_audio_to_session(
                ctx=mock_context,
                track_index=1,
                clip_slot_index=1,
                file_path=str(file_path),
            )


class TestResponseModels:
    def test_clip_automation_accepts_valid(self) -> None:
        automation = ClipAutomationResult.model_validate(CLIP_AUTOMATION_RESULT)
        assert automation.parameter_name == "Frequency"
        assert automation.points[1].step_length == 0.5

    def test_clip_info_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            ClipInfo.model_validate({"track_index": 1})

    def test_clip_notes_accepts_valid(self) -> None:
        notes = ClipNotesResult.model_validate(CLIP_NOTES_RESULT)
        assert notes.track_index == 1
        assert len(notes.notes) == 2

    def test_clip_info_accepts_valid(self) -> None:
        c = ClipInfo.model_validate(CLIP_INFO_RESULT)
        assert c.name == "Kick"

    def test_session_audio_import_result_accepts_valid(self) -> None:
        result = SessionAudioImportResult.model_validate(SESSION_AUDIO_IMPORT_RESULT)
        assert result.is_audio_clip is True
