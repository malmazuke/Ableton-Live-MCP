"""Tests for track management MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from mcp_ableton._app import mcp
from mcp_ableton.protocol import (
    CommandError,
    CommandRequest,
    CommandResponse,
    ErrorDetail,
)
from mcp_ableton.tools.track import (
    AvailableRoutingResult,
    RoutingOption,
    TrackCreatedResult,
    TrackDeletedResult,
    TrackDuplicatedResult,
    TrackFoldResult,
    TrackInfo,
    TrackInputRoutingResult,
    TrackOutputRoutingResult,
    TrackRoutingInfo,
    TrackUpdatedResult,
    create_audio_track,
    create_midi_track,
    delete_track,
    duplicate_track,
    fold_group,
    get_available_routing,
    get_track_info,
    get_track_routing,
    set_track_arm,
    set_track_input_routing,
    set_track_mute,
    set_track_name,
    set_track_output_routing,
    set_track_solo,
)

TOOL_NAMES = [
    "get_track_info",
    "get_track_routing",
    "get_available_routing",
    "set_track_input_routing",
    "set_track_output_routing",
    "create_midi_track",
    "create_audio_track",
    "delete_track",
    "duplicate_track",
    "fold_group",
    "set_track_name",
    "set_track_mute",
    "set_track_solo",
    "set_track_arm",
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


TRACK_INFO_RESULT = {
    "name": "Midi 1",
    "track_scope": "main",
    "track_index": 1,
    "is_audio_track": False,
    "is_midi_track": True,
    "mute": False,
    "solo": False,
    "arm": False,
    "volume": 0.85,
    "pan": 0.0,
    "device_names": ["Instrument Rack"],
    "clip_slot_has_clip": [False, True],
    "is_foldable": False,
    "fold_state": None,
    "is_grouped": False,
    "group_track_index": None,
}

RETURN_TRACK_INFO_RESULT = {
    "name": "Return A",
    "track_scope": "return",
    "track_index": 1,
    "is_audio_track": False,
    "is_midi_track": False,
    "mute": True,
    "solo": False,
    "arm": False,
    "volume": 0.72,
    "pan": -0.1,
    "device_names": [],
    "clip_slot_has_clip": [],
    "is_foldable": False,
    "fold_state": None,
    "is_grouped": False,
    "group_track_index": None,
}

MASTER_TRACK_INFO_RESULT = {
    "name": "Master",
    "track_scope": "master",
    "track_index": None,
    "is_audio_track": False,
    "is_midi_track": False,
    "mute": False,
    "solo": False,
    "arm": False,
    "volume": 0.88,
    "pan": 0.0,
    "device_names": [],
    "clip_slot_has_clip": [],
    "is_foldable": False,
    "fold_state": None,
    "is_grouped": False,
    "group_track_index": None,
}

GROUPED_TRACK_INFO_RESULT = {
    "name": "Bass",
    "track_scope": "main",
    "track_index": 2,
    "is_audio_track": False,
    "is_midi_track": True,
    "mute": False,
    "solo": False,
    "arm": False,
    "volume": 0.8,
    "pan": 0.0,
    "device_names": [],
    "clip_slot_has_clip": [False, False],
    "is_foldable": False,
    "fold_state": None,
    "is_grouped": True,
    "group_track_index": 1,
}

ROUTING_OPTION_RESULT = {
    "identifier": "ExtIns",
    "display_name": "Ext. In",
}

TRACK_ROUTING_RESULT = {
    "track_index": 1,
    "input_routing_type": {
        "identifier": "ExtIns",
        "display_name": "Ext. In",
    },
    "input_routing_channel": {
        "identifier": "ExtIns/1",
        "display_name": "1",
    },
    "output_routing_type": {
        "identifier": "Master",
        "display_name": "Master",
    },
    "output_routing_channel": {
        "identifier": "Master/Stereo",
        "display_name": "Stereo",
    },
}

AVAILABLE_ROUTING_RESULT = {
    "track_index": 1,
    "available_input_routing_types": [
        {
            "identifier": "ExtIns",
            "display_name": "Ext. In",
        },
        {
            "identifier": "Resampling",
            "display_name": "Resampling",
        },
    ],
    "available_input_routing_channels": [
        {
            "identifier": "ExtIns/1",
            "display_name": "1",
        },
        {
            "identifier": "ExtIns/2",
            "display_name": "2",
        },
    ],
    "available_output_routing_types": [
        {
            "identifier": "Master",
            "display_name": "Master",
        },
        {
            "identifier": "SendsOnly",
            "display_name": "Sends Only",
        },
    ],
    "available_output_routing_channels": [
        {
            "identifier": "Master/Stereo",
            "display_name": "Stereo",
        }
    ],
}

TRACK_INPUT_ROUTING_RESULT = {
    "track_index": 1,
    "input_routing_type": {
        "identifier": "Resampling",
        "display_name": "Resampling",
    },
    "input_routing_channel": {
        "identifier": "Resampling/PostMixer",
        "display_name": "Post Mixer",
    },
}

TRACK_OUTPUT_ROUTING_RESULT = {
    "track_index": 1,
    "output_routing_type": {
        "identifier": "SendsOnly",
        "display_name": "Sends Only",
    },
    "output_routing_channel": {
        "identifier": "SendsOnly/PostFX",
        "display_name": "Post FX",
    },
}

TRACK_UPDATED_RESULT = {
    "track_scope": "main",
    "track_index": 1,
}

MASTER_TRACK_UPDATED_RESULT = {
    "track_scope": "master",
    "track_index": None,
}

TRACK_FOLD_RESULT = {
    "track_index": 3,
    "folded": True,
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

    def test_get_track_info_schema(self) -> None:
        tool = self._get_tool("get_track_info")
        props = tool.parameters["properties"]
        assert props["track_scope"]["default"] == "main"
        assert props["track_scope"]["enum"] == ["main", "return", "master"]
        assert "track_index" in props
        assert props["track_index"]["anyOf"][0]["minimum"] == 1
        assert props["track_index"]["default"] is None

    def test_get_track_routing_schema(self) -> None:
        tool = self._get_tool("get_track_routing")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1

    def test_get_available_routing_schema(self) -> None:
        tool = self._get_tool("get_available_routing")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1

    def test_set_track_input_routing_schema(self) -> None:
        tool = self._get_tool("set_track_input_routing")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["routing_type_identifier"]["minLength"] == 1
        assert props["routing_channel_identifier"]["minLength"] == 1

    def test_set_track_output_routing_schema(self) -> None:
        tool = self._get_tool("set_track_output_routing")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["routing_type_identifier"]["minLength"] == 1
        assert props["routing_channel_identifier"]["minLength"] == 1

    def test_create_midi_track_index_default(self) -> None:
        tool = self._get_tool("create_midi_track")
        props = tool.parameters["properties"]
        assert props["index"]["default"] == -1

    def test_create_audio_track_index_default(self) -> None:
        tool = self._get_tool("create_audio_track")
        props = tool.parameters["properties"]
        assert props["index"]["default"] == -1

    def test_fold_group_schema(self) -> None:
        tool = self._get_tool("fold_group")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["folded"]["type"] == "boolean"

    @pytest.mark.parametrize(
        "tool_name",
        [
            "get_track_info",
            "set_track_name",
            "set_track_mute",
            "set_track_solo",
            "set_track_arm",
        ],
    )
    def test_scoped_track_tools_have_track_scope_default(self, tool_name: str) -> None:
        tool = self._get_tool(tool_name)
        props = tool.parameters["properties"]
        assert props["track_scope"]["default"] == "main"


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    @pytest.mark.parametrize("track_index", [0, -1, -5])
    def test_get_track_info_rejects_non_positive_index(self, track_index: int) -> None:
        model = self._arg_model("get_track_info")
        with pytest.raises(ValidationError):
            model(track_index=track_index)

    def test_get_track_info_accepts_positive_index(self) -> None:
        model = self._arg_model("get_track_info")
        args = model(track_index=3)
        assert args.track_index == 3

    def test_set_track_input_routing_rejects_empty_identifiers(self) -> None:
        model = self._arg_model("set_track_input_routing")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                routing_type_identifier="",
                routing_channel_identifier="ExtIns/1",
            )
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                routing_type_identifier="ExtIns",
                routing_channel_identifier="",
            )

    def test_set_track_output_routing_rejects_empty_identifiers(self) -> None:
        model = self._arg_model("set_track_output_routing")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                routing_type_identifier="",
                routing_channel_identifier="Master/Stereo",
            )
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                routing_type_identifier="Master",
                routing_channel_identifier="",
            )

    def test_set_track_name_rejects_empty_name(self) -> None:
        model = self._arg_model("set_track_name")
        with pytest.raises(ValidationError):
            model(track_index=1, name="")

    def test_get_track_info_accepts_main_without_index(self) -> None:
        model = self._arg_model("get_track_info")
        args = model(track_scope="main")
        assert args.track_scope == "main"
        assert args.track_index is None

    def test_get_track_info_accepts_return_without_index(self) -> None:
        model = self._arg_model("get_track_info")
        args = model(track_scope="return")
        assert args.track_scope == "return"
        assert args.track_index is None

    def test_get_track_info_accepts_master_without_index(self) -> None:
        model = self._arg_model("get_track_info")
        args = model(track_scope="master")
        assert args.track_scope == "master"
        assert args.track_index is None

    def test_fold_group_accepts_valid_input(self) -> None:
        model = self._arg_model("fold_group")
        args = model(track_index=2, folded=True)
        assert args.track_index == 2
        assert args.folded is True

    @pytest.mark.parametrize("track_index", [0, -1])
    def test_fold_group_rejects_non_positive_index(self, track_index: int) -> None:
        model = self._arg_model("fold_group")
        with pytest.raises(ValidationError):
            model(track_index=track_index, folded=True)


class TestGetTrackInfo:
    async def test_returns_track_info(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_INFO_RESULT)

        result = await get_track_info(ctx=mock_context, track_index=1)

        assert isinstance(result, TrackInfo)
        assert result.name == "Midi 1"
        assert result.track_index == 1
        assert result.is_midi_track is True
        assert result.clip_slot_has_clip == [False, True]
        assert result.is_foldable is False
        assert result.fold_state is None
        assert result.is_grouped is False
        assert result.group_track_index is None

    async def test_returns_scoped_return_track_info(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            RETURN_TRACK_INFO_RESULT
        )

        result = await get_track_info(
            ctx=mock_context,
            track_scope="return",
            track_index=1,
        )

        assert isinstance(result, TrackInfo)
        assert result.track_scope == "return"
        assert result.track_index == 1
        assert result.clip_slot_has_clip == []
        assert result.is_foldable is False
        assert result.fold_state is None

    async def test_returns_master_track_info(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            MASTER_TRACK_INFO_RESULT
        )

        result = await get_track_info(ctx=mock_context, track_scope="master")

        assert isinstance(result, TrackInfo)
        assert result.track_scope == "master"
        assert result.track_index is None
        assert result.clip_slot_has_clip == []
        assert result.group_track_index is None

    async def test_returns_group_metadata(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            GROUPED_TRACK_INFO_RESULT
        )

        result = await get_track_info(ctx=mock_context, track_index=2)

        assert result.is_grouped is True
        assert result.group_track_index == 1
        assert result.is_foldable is False
        assert result.fold_state is None

    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_INFO_RESULT)

        await get_track_info(ctx=mock_context, track_index=2)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.get_info"
        assert req.params == {"track_scope": "main", "track_index": 2}

    async def test_sends_scoped_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            RETURN_TRACK_INFO_RESULT
        )

        await get_track_info(
            ctx=mock_context,
            track_scope="return",
            track_index=1,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.get_info"
        assert req.params == {"track_scope": "return", "track_index": 1}

    async def test_sends_master_command_without_track_index(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            MASTER_TRACK_INFO_RESULT
        )

        await get_track_info(ctx=mock_context, track_scope="master")

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.get_info"
        assert req.params == {"track_scope": "master"}

    async def test_raises_on_error(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND", message="Track 9 does not exist"
        )
        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_track_info(ctx=mock_context, track_index=9)

    async def test_rejects_master_track_index_before_sending(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        with pytest.raises(ValueError, match="track_index"):
            await get_track_info(
                ctx=mock_context,
                track_scope="master",
                track_index=1,
            )

        mock_connection.send_command.assert_not_called()

    async def test_requires_track_index_for_main_and_return(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        with pytest.raises(ValueError, match="track_index"):
            await get_track_info(ctx=mock_context, track_scope="main")

        with pytest.raises(ValueError, match="track_index"):
            await get_track_info(ctx=mock_context, track_scope="return")

        mock_connection.send_command.assert_not_called()


class TestRoutingTools:
    async def test_get_track_routing_returns_typed_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_ROUTING_RESULT)

        result = await get_track_routing(ctx=mock_context, track_index=1)

        assert isinstance(result, TrackRoutingInfo)
        assert result.input_routing_type.identifier == "ExtIns"
        assert result.output_routing_channel.display_name == "Stereo"

    async def test_get_track_routing_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_ROUTING_RESULT)

        await get_track_routing(ctx=mock_context, track_index=2)

        req = mock_connection.send_command.call_args[0][0]
        assert isinstance(req, CommandRequest)
        assert req.command == "track.get_routing"
        assert req.params == {"track_index": 2}

    async def test_get_available_routing_returns_typed_result(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            AVAILABLE_ROUTING_RESULT
        )

        result = await get_available_routing(ctx=mock_context, track_index=1)

        assert isinstance(result, AvailableRoutingResult)
        assert result.available_input_routing_types[0].identifier == "ExtIns"
        assert result.available_output_routing_channels[0].display_name == "Stereo"

    async def test_get_available_routing_raises_on_error(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="Track 1 has no available input routing types",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await get_available_routing(ctx=mock_context, track_index=1)

    async def test_set_track_input_routing_sends_identifiers(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TRACK_INPUT_ROUTING_RESULT
        )

        result = await set_track_input_routing(
            ctx=mock_context,
            track_index=1,
            routing_type_identifier="Resampling",
            routing_channel_identifier="Resampling/PostMixer",
        )

        assert isinstance(result, TrackInputRoutingResult)
        req = mock_connection.send_command.call_args[0][0]
        assert isinstance(req, CommandRequest)
        assert req.command == "track.set_input_routing"
        assert req.params == {
            "track_index": 1,
            "routing_type_identifier": "Resampling",
            "routing_channel_identifier": "Resampling/PostMixer",
        }

    async def test_set_track_output_routing_sends_identifiers(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            TRACK_OUTPUT_ROUTING_RESULT
        )

        result = await set_track_output_routing(
            ctx=mock_context,
            track_index=2,
            routing_type_identifier="SendsOnly",
            routing_channel_identifier="SendsOnly/PostFX",
        )

        assert isinstance(result, TrackOutputRoutingResult)
        req = mock_connection.send_command.call_args[0][0]
        assert isinstance(req, CommandRequest)
        assert req.command == "track.set_output_routing"
        assert req.params == {
            "track_index": 2,
            "routing_type_identifier": "SendsOnly",
            "routing_channel_identifier": "SendsOnly/PostFX",
        }

    async def test_set_track_input_routing_raises_on_not_found(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Track 1 has no input routing type with identifier 'Bogus'",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await set_track_input_routing(
                ctx=mock_context,
                track_index=1,
                routing_type_identifier="Bogus",
                routing_channel_identifier="ExtIns/1",
            )

    async def test_set_track_output_routing_raises_on_invalid_params(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="Track 1 does not support available output routing types",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_track_output_routing(
                ctx=mock_context,
                track_index=1,
                routing_type_identifier="Master",
                routing_channel_identifier="Master/Stereo",
            )


class TestFoldGroup:
    async def test_sends_correct_command(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_FOLD_RESULT)

        result = await fold_group(ctx=mock_context, track_index=3, folded=True)

        assert isinstance(result, TrackFoldResult)
        assert result.track_index == 3
        assert result.folded is True
        req = mock_connection.send_command.call_args[0][0]
        assert isinstance(req, CommandRequest)
        assert req.command == "track.fold_group"
        assert req.params == {"track_index": 3, "folded": True}

    async def test_raises_invalid_params(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="Track 2 is not a foldable group track",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await fold_group(ctx=mock_context, track_index=2, folded=False)


class TestCreateMidiTrack:
    async def test_default_index_and_no_name(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 2, "name": None}
        )

        result = await create_midi_track(ctx=mock_context)

        assert isinstance(result, TrackCreatedResult)
        assert result.track_index == 2
        assert result.name is None
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.create_midi"
        assert req.params == {"index": -1}

    async def test_with_name(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 1, "name": "Bass"}
        )

        await create_midi_track(
            ctx=mock_context,
            index=0,
            name="Bass",
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"index": 0, "name": "Bass"}


class TestCreateAudioTrack:
    async def test_sends_create_audio(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"track_index": 3, "name": None}
        )

        await create_audio_track(ctx=mock_context, index=-1)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.create_audio"
        assert req.params == {"index": -1}


class TestDeleteDuplicateSetters:
    async def test_delete_track(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response({"track_index": 2})

        result = await delete_track(ctx=mock_context, track_index=2)

        assert isinstance(result, TrackDeletedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.delete"
        assert req.params == {"track_index": 2}

    async def test_duplicate_track(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"source_track_index": 1, "new_track_index": 2}
        )

        result = await duplicate_track(ctx=mock_context, track_index=1)

        assert isinstance(result, TrackDuplicatedResult)
        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.duplicate"

    async def test_set_track_name(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_UPDATED_RESULT)

        await set_track_name(ctx=mock_context, track_index=1, name="Lead")

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.set_name"
        assert req.params == {
            "track_scope": "main",
            "track_index": 1,
            "name": "Lead",
        }

    async def test_set_track_name_scoped_master(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            MASTER_TRACK_UPDATED_RESULT
        )

        await set_track_name(ctx=mock_context, track_scope="master", name="Main")

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.set_name"
        assert req.params == {"track_scope": "master", "name": "Main"}

    async def test_set_track_mute(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_UPDATED_RESULT)

        await set_track_mute(ctx=mock_context, track_index=1, mute=True)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.set_mute"
        assert req.params == {
            "track_scope": "main",
            "track_index": 1,
            "mute": True,
        }

    async def test_set_track_mute_scoped_return(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            RETURN_TRACK_INFO_RESULT
        )

        await set_track_mute(
            ctx=mock_context,
            track_scope="return",
            track_index=1,
            mute=True,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {
            "track_scope": "return",
            "track_index": 1,
            "mute": True,
        }

    async def test_set_track_mute_raises_on_invalid_params(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="Master track does not support mute",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_track_mute(ctx=mock_context, track_scope="master", mute=True)

    async def test_set_track_solo(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_UPDATED_RESULT)

        await set_track_solo(ctx=mock_context, track_index=2, solo=False)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.set_solo"
        assert req.params == {
            "track_scope": "main",
            "track_index": 2,
            "solo": False,
        }

    async def test_set_track_solo_scoped_master(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            MASTER_TRACK_UPDATED_RESULT
        )

        await set_track_solo(ctx=mock_context, track_scope="master", solo=False)

        req = mock_connection.send_command.call_args[0][0]
        assert req.params == {"track_scope": "master", "solo": False}

    async def test_set_track_arm(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(TRACK_UPDATED_RESULT)

        await set_track_arm(ctx=mock_context, track_index=1, arm=True)

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "track.set_arm"
        assert req.params == {
            "track_scope": "main",
            "track_index": 1,
            "arm": True,
        }

    async def test_set_track_arm_rejects_master_before_sending(
        self, mock_context: MagicMock, mock_connection: AsyncMock
    ) -> None:
        with pytest.raises(ValueError, match="track_index"):
            await set_track_arm(
                ctx=mock_context,
                track_scope="master",
                track_index=1,
                arm=True,
            )

        mock_connection.send_command.assert_not_called()


class TestResponseModels:
    def test_track_info_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            TrackInfo.model_validate({"name": "x"})

    def test_track_info_accepts_valid(self) -> None:
        t = TrackInfo.model_validate(TRACK_INFO_RESULT)
        assert t.device_names == ["Instrument Rack"]
        assert t.track_scope == "main"
        assert t.track_index == 1

    def test_track_info_accepts_master(self) -> None:
        t = TrackInfo.model_validate(MASTER_TRACK_INFO_RESULT)
        assert t.track_scope == "master"
        assert t.track_index is None

    def test_track_updated_result_accepts_valid(self) -> None:
        result = TrackUpdatedResult.model_validate(TRACK_UPDATED_RESULT)
        assert result.track_scope == "main"
        assert result.track_index == 1

    def test_track_updated_result_accepts_master(self) -> None:
        result = TrackUpdatedResult.model_validate(MASTER_TRACK_UPDATED_RESULT)
        assert result.track_scope == "master"
        assert result.track_index is None

    def test_routing_option_accepts_valid(self) -> None:
        option = RoutingOption.model_validate(ROUTING_OPTION_RESULT)
        assert option.identifier == "ExtIns"

    def test_track_routing_info_accepts_valid(self) -> None:
        result = TrackRoutingInfo.model_validate(TRACK_ROUTING_RESULT)
        assert result.output_routing_type.identifier == "Master"

    def test_available_routing_result_accepts_valid(self) -> None:
        result = AvailableRoutingResult.model_validate(AVAILABLE_ROUTING_RESULT)
        assert len(result.available_input_routing_types) == 2

    def test_track_input_routing_result_accepts_valid(self) -> None:
        result = TrackInputRoutingResult.model_validate(TRACK_INPUT_ROUTING_RESULT)
        assert result.input_routing_channel.display_name == "Post Mixer"

    def test_track_output_routing_result_accepts_valid(self) -> None:
        result = TrackOutputRoutingResult.model_validate(TRACK_OUTPUT_ROUTING_RESULT)
        assert result.output_routing_channel.identifier == "SendsOnly/PostFX"
