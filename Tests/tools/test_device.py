"""Tests for device and parameter MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.device import (
    DeviceParametersResult,
    EffectLoadedResult,
    InstrumentLoadedResult,
    ParameterSetResult,
    get_device_parameters,
    load_effect,
    load_instrument,
    set_device_parameter,
)

TOOL_NAMES = [
    "get_device_parameters",
    "set_device_parameter",
    "load_instrument",
    "load_effect",
]

DEVICE_PARAMETERS_RESULT = {
    "track_index": 1,
    "device_index": 2,
    "device_name": "Analog",
    "parameters": [
        {
            "parameter_index": 1,
            "name": "Device On",
            "value": 1.0,
            "min": 0.0,
            "max": 1.0,
            "is_quantized": True,
        },
        {
            "parameter_index": 2,
            "name": "Filter Freq",
            "value": 5500.0,
            "min": 20.0,
            "max": 20000.0,
            "is_quantized": False,
        },
    ],
}

PARAMETER_SET_RESULT = {
    "track_index": 1,
    "device_index": 2,
    "parameter_index": 2,
    "value": 1200.0,
}

INSTRUMENT_LOADED_RESULT = {
    "track_index": 1,
    "device_index": 2,
    "name": "Analog",
    "uri": "browser:instruments/synths/analog",
}

EFFECT_LOADED_RESULT = {
    "track_index": 1,
    "device_index": 3,
    "name": "Auto Filter",
    "uri": "browser:audio_effects/filters/auto-filter",
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

    def test_get_device_parameters_schema(self) -> None:
        tool = self._get_tool("get_device_parameters")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["device_index"]["minimum"] == 1

    def test_set_device_parameter_schema(self) -> None:
        tool = self._get_tool("set_device_parameter")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["device_index"]["minimum"] == 1
        assert props["parameter_index"]["minimum"] == 1

    def test_load_instrument_schema(self) -> None:
        tool = self._get_tool("load_instrument")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["uri"]["minLength"] == 1

    def test_load_effect_schema(self) -> None:
        tool = self._get_tool("load_effect")
        props = tool.parameters["properties"]
        assert props["track_index"]["minimum"] == 1
        assert props["uri"]["minLength"] == 1
        assert props["position"]["default"] == -1


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_get_device_parameters_rejects_non_positive_indices(self) -> None:
        model = self._arg_model("get_device_parameters")
        with pytest.raises(ValidationError):
            model(track_index=0, device_index=1)
        with pytest.raises(ValidationError):
            model(track_index=1, device_index=0)

    def test_set_device_parameter_rejects_non_positive_parameter_index(self) -> None:
        model = self._arg_model("set_device_parameter")
        with pytest.raises(ValidationError):
            model(
                track_index=1,
                device_index=1,
                parameter_index=0,
                value=1.0,
            )

    def test_load_instrument_rejects_empty_uri(self) -> None:
        model = self._arg_model("load_instrument")
        with pytest.raises(ValidationError):
            model(track_index=1, uri="")

    def test_load_effect_defaults_position_to_minus_one(self) -> None:
        model = self._arg_model("load_effect")
        args = model(track_index=1, uri="browser:audio_effects/filters/auto-filter")
        assert args.position == -1


class TestGetDeviceParameters:
    async def test_returns_parameters(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            DEVICE_PARAMETERS_RESULT
        )

        result = await get_device_parameters(
            ctx=mock_context,
            track_index=1,
            device_index=2,
        )

        assert isinstance(result, DeviceParametersResult)
        assert result.device_name == "Analog"
        assert result.parameters[1].parameter_index == 2
        assert result.parameters[1].value == 5500.0

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            DEVICE_PARAMETERS_RESULT
        )

        await get_device_parameters(
            ctx=mock_context,
            track_index=3,
            device_index=4,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "device.get_parameters"
        assert req.params == {"track_index": 3, "device_index": 4}

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Device 9 does not exist on track 1",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_device_parameters(
                ctx=mock_context,
                track_index=1,
                device_index=9,
            )


class TestSetDeviceParameter:
    async def test_returns_parameter_set_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(PARAMETER_SET_RESULT)

        result = await set_device_parameter(
            ctx=mock_context,
            track_index=1,
            device_index=2,
            parameter_index=2,
            value=1200.0,
        )

        assert isinstance(result, ParameterSetResult)
        assert result.parameter_index == 2
        assert result.value == 1200.0

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(PARAMETER_SET_RESULT)

        await set_device_parameter(
            ctx=mock_context,
            track_index=5,
            device_index=2,
            parameter_index=7,
            value=0.5,
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "device.set_parameter"
        assert req.params == {
            "track_index": 5,
            "device_index": 2,
            "parameter_index": 7,
            "value": 0.5,
        }

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message="'value' must be between 0.0 and 1.0, got 2.0",
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await set_device_parameter(
                ctx=mock_context,
                track_index=1,
                device_index=1,
                parameter_index=1,
                value=2.0,
            )


class TestLoadInstrument:
    async def test_returns_instrument_load_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            INSTRUMENT_LOADED_RESULT
        )

        result = await load_instrument(
            ctx=mock_context,
            track_index=1,
            uri="browser:instruments/synths/analog",
        )

        assert isinstance(result, InstrumentLoadedResult)
        assert result.device_index == 2
        assert result.name == "Analog"

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            INSTRUMENT_LOADED_RESULT
        )

        await load_instrument(
            ctx=mock_context,
            track_index=2,
            uri="browser:instruments/synths/operator",
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "browser.load_instrument"
        assert req.params == {
            "track_index": 2,
            "uri": "browser:instruments/synths/operator",
        }


class TestLoadEffect:
    async def test_returns_effect_load_result(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(EFFECT_LOADED_RESULT)

        result = await load_effect(
            ctx=mock_context,
            track_index=1,
            uri="browser:audio_effects/filters/auto-filter",
        )

        assert isinstance(result, EffectLoadedResult)
        assert result.device_index == 3
        assert result.name == "Auto Filter"

    async def test_sends_correct_command_with_default_position(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(EFFECT_LOADED_RESULT)

        await load_effect(
            ctx=mock_context,
            track_index=4,
            uri="browser:midi_effects/pitch/chord",
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "browser.load_effect"
        assert req.params == {
            "track_index": 4,
            "uri": "browser:midi_effects/pitch/chord",
            "position": -1,
        }

    async def test_raises_on_error(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="INVALID_PARAMS",
            message=(
                "Arbitrary effect insertion is unsupported on the Live 12.2.5 "
                "runtime; use position=-1"
            ),
        )

        with pytest.raises(CommandError, match="INVALID_PARAMS"):
            await load_effect(
                ctx=mock_context,
                track_index=1,
                uri="browser:audio_effects/filters/auto-filter",
                position=0,
            )
