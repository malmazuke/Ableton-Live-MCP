"""MCP tools for Ableton Live devices, parameters, and Browser-based loading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


class DeviceParameterInfo(BaseModel):
    """One device parameter using Live's native value range."""

    parameter_index: int
    name: str
    value: float
    min: float
    max: float
    is_quantized: bool


class DeviceParametersResult(BaseModel):
    """Parameters for one device on one track."""

    track_index: int
    device_index: int
    device_name: str
    parameters: list[DeviceParameterInfo]


class ParameterSetResult(BaseModel):
    """Result of writing a parameter using its actual Live value."""

    track_index: int
    device_index: int
    parameter_index: int
    value: float


class InstrumentLoadedResult(BaseModel):
    """Result of loading an instrument onto a track."""

    track_index: int
    device_index: int
    name: str
    uri: str


class EffectLoadedResult(BaseModel):
    """Result of loading an effect onto a track."""

    track_index: int
    device_index: int
    name: str
    uri: str


def _get_connection(ctx: Context) -> AbletonConnection:
    """Extract the Ableton TCP connection from the FastMCP context."""
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_device_parameters(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    device_index: Annotated[
        int,
        Field(description="1-based device index on the track.", ge=1),
    ],
) -> DeviceParametersResult:
    """Get all parameters for a device using Live's actual parameter values."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="device.get_parameters",
        params={
            "track_index": track_index,
            "device_index": device_index,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return DeviceParametersResult.model_validate(response.result)


@mcp.tool()
async def set_device_parameter(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    device_index: Annotated[
        int,
        Field(description="1-based device index on the track.", ge=1),
    ],
    parameter_index: Annotated[
        int,
        Field(description="1-based parameter index on the device.", ge=1),
    ],
    value: Annotated[
        float,
        Field(
            description=(
                "Parameter value in the device parameter's real Live range, "
                "not a normalized 0-1 value."
            ),
        ),
    ],
) -> ParameterSetResult:
    """Set a device parameter using its native Live min/max range."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="device.set_parameter",
        params={
            "track_index": track_index,
            "device_index": device_index,
            "parameter_index": parameter_index,
            "value": value,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return ParameterSetResult.model_validate(response.result)


@mcp.tool()
async def load_instrument(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    uri: Annotated[
        str,
        Field(description="Browser item URI for an instrument.", min_length=1),
    ],
) -> InstrumentLoadedResult:
    """Load an instrument Browser item onto a MIDI track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="browser.load_instrument",
        params={"track_index": track_index, "uri": uri},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return InstrumentLoadedResult.model_validate(response.result)


@mcp.tool()
async def load_effect(
    ctx: Context,
    track_index: Annotated[
        int,
        Field(description="1-based track index.", ge=1),
    ],
    uri: Annotated[
        str,
        Field(
            description="Browser item URI for an audio or MIDI effect.",
            min_length=1,
        ),
    ],
    position: Annotated[
        int,
        Field(
            description=(
                "Requested insertion point. Live 12.2.5 only supports -1 here, "
                "which appends via the Browser load path."
            ),
        ),
    ] = -1,
) -> EffectLoadedResult:
    """Load an effect Browser item onto a track."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="browser.load_effect",
        params={
            "track_index": track_index,
            "uri": uri,
            "position": position,
        },
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return EffectLoadedResult.model_validate(response.result)


__all__ = [
    "DeviceParameterInfo",
    "DeviceParametersResult",
    "EffectLoadedResult",
    "InstrumentLoadedResult",
    "ParameterSetResult",
    "get_device_parameters",
    "load_effect",
    "load_instrument",
    "set_device_parameter",
]
