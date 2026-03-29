"""Tests for arrangement clip note-editing MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.arrangement import (
    ArrangementClipNotesResult,
    ArrangementNotesAddedResult,
    ArrangementNotesRemovedResult,
    ArrangementNotesSetResult,
    add_notes_to_arrangement_clip,
    get_arrangement_clip_notes,
    remove_arrangement_clip_notes,
    set_arrangement_clip_notes,
)

TOOL_NAMES = [
    "get_arrangement_clip_notes",
    "add_notes_to_arrangement_clip",
    "set_arrangement_clip_notes",
    "remove_arrangement_clip_notes",
]

ARRANGEMENT_NOTES_RESULT = {
    "track_index": 1,
    "clip_index": 2,
    "notes": [
        {
            "note_id": 101,
            "pitch": 60,
            "start_time": 0.0,
            "duration": 0.5,
            "velocity": 100.0,
            "mute": False,
            "probability": 0.8,
        },
        {
            "note_id": 102,
            "pitch": 64,
            "start_time": 1.0,
            "duration": 0.25,
            "velocity": 90.0,
            "mute": True,
            "velocity_deviation": 3.0,
        },
    ],
    "count": 2,
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


# ------------------------------------------------------------------
# Tool registration and schema contracts
# ------------------------------------------------------------------
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

    def test_get_arrangement_clip_notes_schema(self) -> None:
        tool = self._get_tool("get_arrangement_clip_notes")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["clip_index"]["minimum"] == 1

    def test_add_notes_to_arrangement_clip_schema(self) -> None:
        tool = self._get_tool("add_notes_to_arrangement_clip")
        props = tool.parameters["properties"]
        assert props["notes"]["minItems"] == 1
        assert props["track_index"]["minimum"] == 1
        assert props["clip_index"]["minimum"] == 1

    def test_remove_arrangement_clip_notes_schema(self) -> None:
        tool = self._get_tool("remove_arrangement_clip_notes")
        props = tool.parameters["properties"]
        assert props["from_pitch"]["minimum"] == 0
        assert props["from_pitch"]["maximum"] == 127
        assert props["pitch_span"]["minimum"] == 1
        assert props["pitch_span"]["maximum"] == 128
        assert props["from_time"]["minimum"] == 0.0


# ------------------------------------------------------------------
# Input validation
# ------------------------------------------------------------------
class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    @pytest.mark.parametrize("track_index", [0, -1])
    def test_get_notes_rejects_bad_track_index(self, track_index: int) -> None:
        model = self._arg_model("get_arrangement_clip_notes")
        with pytest.raises(ValidationError):
            model(track_index=track_index, clip_index=1)

    @pytest.mark.parametrize("clip_index", [0, -1])
    def test_get_notes_rejects_bad_clip_index(self, clip_index: int) -> None:
        model = self._arg_model("get_arrangement_clip_notes")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_index=clip_index)

    def test_add_notes_rejects_empty_list(self) -> None:
        model = self._arg_model("add_notes_to_arrangement_clip")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_index=1, notes=[])

    def test_add_notes_accepts_lean_arrays(self) -> None:
        model = self._arg_model("add_notes_to_arrangement_clip")
        args = model(track_index=1, clip_index=1, notes=[[60, 0.0, 0.5, 100]])
        assert len(args.notes) == 1

    def test_add_notes_accepts_object_notes(self) -> None:
        model = self._arg_model("add_notes_to_arrangement_clip")
        args = model(
            track_index=1,
            clip_index=1,
            notes=[
                {
                    "pitch": 60,
                    "start_time": 0.0,
                    "duration": 0.5,
                    "velocity": 100.0,
                    "probability": 0.5,
                }
            ],
        )
        assert len(args.notes) == 1

    def test_set_notes_accepts_empty_list(self) -> None:
        model = self._arg_model("set_arrangement_clip_notes")
        args = model(track_index=1, clip_index=1, notes=[])
        assert args.notes == []

    @pytest.mark.parametrize("time_span", [0.0, -1.0])
    def test_remove_notes_rejects_non_positive_time_span(
        self,
        time_span: float,
    ) -> None:
        model = self._arg_model("remove_arrangement_clip_notes")
        with pytest.raises(ValidationError):
            model(track_index=1, clip_index=1, time_span=time_span)

    @pytest.mark.parametrize("pitch", [-1, 128])
    def test_add_notes_rejects_out_of_range_pitch(self, pitch: int) -> None:
        model = self._arg_model("add_notes_to_arrangement_clip")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                clip_index=1,
                notes=[[pitch, 0.0, 0.5, 100]],
            )


# ------------------------------------------------------------------
# get_arrangement_clip_notes
# ------------------------------------------------------------------
class TestGetArrangementClipNotes:
    async def test_returns_notes(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            ARRANGEMENT_NOTES_RESULT
        )

        result = await get_arrangement_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_index=2,
        )

        assert isinstance(result, ArrangementClipNotesResult)
        assert result.count == 2
        assert len(result.notes) == 2
        assert result.notes[0].note_id == 101
        assert result.notes[1].mute is True

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            ARRANGEMENT_NOTES_RESULT
        )

        await get_arrangement_clip_notes(ctx=mock_context, track_index=1, clip_index=2)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.get_notes"
        assert req.params == {"track_index": 1, "clip_index": 2}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Clip 5 does not exist",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_arrangement_clip_notes(
                ctx=mock_context,
                track_index=1,
                clip_index=5,
            )


# ------------------------------------------------------------------
# add_notes_to_arrangement_clip
# ------------------------------------------------------------------
class TestAddNotesToArrangementClip:
    async def test_normalizes_lean_note_arrays(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_index": 2,
                "added_count": 1,
                "note_ids": [201],
            }
        )

        result = await add_notes_to_arrangement_clip(
            ctx=mock_context,
            track_index=1,
            clip_index=2,
            notes=[[60, 0.0, 0.5, 100]],
        )

        assert isinstance(result, ArrangementNotesAddedResult)
        assert result.note_ids == [201]
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.add_notes"
        assert req.params == {
            "track_index": 1,
            "clip_index": 2,
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
                "clip_index": 1,
                "added_count": 1,
                "note_ids": [99],
            }
        )

        await add_notes_to_arrangement_clip(
            ctx=mock_context,
            track_index=1,
            clip_index=1,
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
            await add_notes_to_arrangement_clip(
                ctx=mock_context,
                track_index=1,
                clip_index=1,
                notes=[[60, 0.0, 0.5, 100]],
            )


# ------------------------------------------------------------------
# set_arrangement_clip_notes
# ------------------------------------------------------------------
class TestSetArrangementClipNotes:
    async def test_accepts_empty_notes_for_clear(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_index": 2,
                "removed_count": 3,
                "added_count": 0,
                "note_ids": [],
            }
        )

        result = await set_arrangement_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_index=2,
            notes=[],
        )

        assert isinstance(result, ArrangementNotesSetResult)
        assert result.added_count == 0
        assert result.removed_count == 3
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.set_notes"
        assert req.params == {
            "track_index": 1,
            "clip_index": 2,
            "notes": [],
        }

    async def test_replaces_notes(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_index": 1,
                "removed_count": 2,
                "added_count": 1,
                "note_ids": [300],
            }
        )

        result = await set_arrangement_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_index=1,
            notes=[[48, 0.0, 1.0, 80]],
        )

        assert isinstance(result, ArrangementNotesSetResult)
        assert result.note_ids == [300]
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.set_notes"


# ------------------------------------------------------------------
# remove_arrangement_clip_notes
# ------------------------------------------------------------------
class TestRemoveArrangementClipNotes:
    async def test_sends_default_region(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {
                "track_index": 1,
                "clip_index": 2,
                "removed_count": 5,
            }
        )

        result = await remove_arrangement_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_index=2,
        )

        assert isinstance(result, ArrangementNotesRemovedResult)
        assert result.removed_count == 5
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "arrangement.remove_notes"
        assert req.params == {
            "track_index": 1,
            "clip_index": 2,
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
                "clip_index": 1,
                "removed_count": 2,
            }
        )

        await remove_arrangement_clip_notes(
            ctx=mock_context,
            track_index=1,
            clip_index=1,
            from_pitch=60,
            pitch_span=4,
            from_time=1.0,
            time_span=2.0,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {
            "track_index": 1,
            "clip_index": 1,
            "from_pitch": 60,
            "pitch_span": 4,
            "from_time": 1.0,
            "time_span": 2.0,
        }

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
            await remove_arrangement_clip_notes(
                ctx=mock_context,
                track_index=9,
                clip_index=1,
            )


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------
class TestResponseModels:
    def test_arrangement_clip_notes_result_accepts_valid(self) -> None:
        result = ArrangementClipNotesResult.model_validate(ARRANGEMENT_NOTES_RESULT)
        assert result.count == 2
        assert result.notes[0].pitch == 60
        assert result.notes[1].velocity_deviation == 3.0

    def test_arrangement_notes_added_result_accepts_valid(self) -> None:
        result = ArrangementNotesAddedResult.model_validate(
            {
                "track_index": 1,
                "clip_index": 2,
                "added_count": 1,
                "note_ids": [201],
            }
        )
        assert result.added_count == 1

    def test_arrangement_notes_set_result_accepts_valid(self) -> None:
        result = ArrangementNotesSetResult.model_validate(
            {
                "track_index": 1,
                "clip_index": 1,
                "removed_count": 2,
                "added_count": 3,
                "note_ids": [10, 11, 12],
            }
        )
        assert result.removed_count == 2
        assert len(result.note_ids) == 3

    def test_arrangement_notes_removed_result_accepts_valid(self) -> None:
        result = ArrangementNotesRemovedResult.model_validate(
            {
                "track_index": 2,
                "clip_index": 3,
                "removed_count": 7,
            }
        )
        assert result.removed_count == 7
