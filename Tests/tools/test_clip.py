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
    ClipCreatedResult,
    ClipDuplicatedResult,
    ClipInfo,
    ClipNote,
    ClipNotesResult,
    ClipRenamedResult,
    ClipSlotResult,
    NotesAddedResult,
    NotesRemovedResult,
    NotesSetResult,
    add_notes_to_clip,
    create_clip,
    delete_clip,
    duplicate_clip,
    fire_clip,
    get_clip_info,
    get_clip_notes,
    remove_notes,
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
    "get_clip_notes",
    "add_notes_to_clip",
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


class TestResponseModels:
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
