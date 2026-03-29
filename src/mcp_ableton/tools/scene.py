"""MCP tools for Ableton Live scene management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import Context  # noqa: TCH002
from pydantic import BaseModel, Field

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandRequest

if TYPE_CHECKING:
    from mcp_ableton.connection import AbletonConnection


SceneIndex = Annotated[
    int,
    Field(
        description="1-based scene index (the first scene is 1).",
        ge=1,
    ),
]


class SceneInfo(BaseModel):
    """Per-scene snapshot returned by ``get_scenes``."""

    scene_index: int
    name: str
    is_empty: bool
    is_triggered: bool
    tempo_enabled: bool
    tempo: float | None
    time_signature_enabled: bool
    time_signature_numerator: int | None
    time_signature_denominator: int | None


class ScenesResult(BaseModel):
    """All scenes currently in the song."""

    scenes: list[SceneInfo]


class SceneCreatedResult(BaseModel):
    """Result of ``create_scene``."""

    scene_index: int
    name: str


class SceneDeletedResult(BaseModel):
    """Result of ``delete_scene``."""

    scene_index: int


class SceneDuplicatedResult(BaseModel):
    """Result of ``duplicate_scene``."""

    source_scene_index: int
    new_scene_index: int


class SceneActionResult(BaseModel):
    """Result of ``fire_scene`` or ``stop_scene``."""

    scene_index: int


class SceneRenamedResult(BaseModel):
    """Result of ``set_scene_name``."""

    scene_index: int
    name: str


def _get_connection(ctx: Context) -> AbletonConnection:
    connection: AbletonConnection = ctx.request_context.lifespan_context.connection
    return connection


@mcp.tool()
async def get_scenes(ctx: Context) -> ScenesResult:
    """Get all scenes with launch and tempo/time-signature metadata."""
    connection = _get_connection(ctx)
    request = CommandRequest(command="scene.get_all")
    response = await connection.send_command(request)
    response.raise_on_error()
    return ScenesResult.model_validate(response.result)


@mcp.tool()
async def create_scene(
    ctx: Context,
    index: Annotated[
        int,
        Field(
            description=(
                "Insert position using Live's API: -1 appends at the end; "
                "0..N-1 inserts before that 0-based slot."
            ),
            ge=-1,
        ),
    ] = -1,
    name: Annotated[
        str | None,
        Field(
            description=(
                "Optional scene name applied after creation (non-empty if set)."
            ),
            min_length=1,
        ),
    ] = None,
) -> SceneCreatedResult:
    """Create a new scene."""
    connection = _get_connection(ctx)
    params: dict[str, int | str] = {"index": index}
    if name is not None:
        params["name"] = name
    request = CommandRequest(command="scene.create", params=params)
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneCreatedResult.model_validate(response.result)


@mcp.tool()
async def delete_scene(
    ctx: Context,
    scene_index: SceneIndex,
) -> SceneDeletedResult:
    """Delete a scene from the song."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="scene.delete",
        params={"scene_index": scene_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneDeletedResult.model_validate(response.result)


@mcp.tool()
async def duplicate_scene(
    ctx: Context,
    scene_index: SceneIndex,
) -> SceneDuplicatedResult:
    """Duplicate a scene; the copy is inserted after the source scene."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="scene.duplicate",
        params={"scene_index": scene_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneDuplicatedResult.model_validate(response.result)


@mcp.tool()
async def fire_scene(
    ctx: Context,
    scene_index: SceneIndex,
) -> SceneActionResult:
    """Launch every clip slot in the scene."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="scene.fire",
        params={"scene_index": scene_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneActionResult.model_validate(response.result)


@mcp.tool()
async def stop_scene(
    ctx: Context,
    scene_index: SceneIndex,
) -> SceneActionResult:
    """Stop playback or recording for the targeted scene row only."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="scene.stop",
        params={"scene_index": scene_index},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneActionResult.model_validate(response.result)


@mcp.tool()
async def set_scene_name(
    ctx: Context,
    scene_index: SceneIndex,
    name: Annotated[str, Field(description="New scene name.", min_length=1)],
) -> SceneRenamedResult:
    """Rename a scene."""
    connection = _get_connection(ctx)
    request = CommandRequest(
        command="scene.set_name",
        params={"scene_index": scene_index, "name": name},
    )
    response = await connection.send_command(request)
    response.raise_on_error()
    return SceneRenamedResult.model_validate(response.result)


__all__ = [
    "SceneActionResult",
    "SceneCreatedResult",
    "SceneDeletedResult",
    "SceneDuplicatedResult",
    "SceneInfo",
    "SceneRenamedResult",
    "ScenesResult",
    "create_scene",
    "delete_scene",
    "duplicate_scene",
    "fire_scene",
    "get_scenes",
    "set_scene_name",
    "stop_scene",
]
