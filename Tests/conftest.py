"""Shared test fixtures and configuration."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from mcp_ableton.protocol import CommandRequest, CommandResponse

# ---------------------------------------------------------------------------
# Stub out Ableton's _Framework so Remote Script modules can be imported
# in the test suite without Ableton's embedded runtime.
# ---------------------------------------------------------------------------
_framework_stub = types.ModuleType("_Framework")
_cs_stub = types.ModuleType("_Framework.ControlSurface")
_noop = lambda *a, **k: None  # noqa: E731
_cs_stub.ControlSurface = type(  # type: ignore[attr-defined]
    "ControlSurface",
    (),
    {
        "__init__": _noop,
        "log_message": _noop,
        "show_message": _noop,
        "song": lambda self: None,
        "application": lambda self: None,
        "schedule_message": lambda self, delay, cb: cb(),
    },
)
sys.modules.setdefault("_Framework", _framework_stub)
sys.modules.setdefault("_Framework.ControlSurface", _cs_stub)

_remote_script_root = str(Path(__file__).resolve().parent.parent / "remote_script")
if _remote_script_root not in sys.path:
    sys.path.insert(0, _remote_script_root)


# ---------------------------------------------------------------------------
# Shared async echo server fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def echo_server():
    """Factory fixture that starts an in-process async TCP echo server.

    Returns an async callable that creates a server and returns (server, port).
    The server echoes every CommandRequest back as a CommandResponse with
    ``result={"echo": command}``.
    """

    async def _create() -> tuple[asyncio.Server, int]:
        async def _handle_client(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                while True:
                    line = await reader.readuntil(b"\n")
                    req = CommandRequest.from_line(line)
                    resp = CommandResponse(
                        status="ok",
                        result={"echo": req.command},
                        id=req.id,
                    )
                    writer.write(resp.to_line())
                    await writer.drain()
            except (asyncio.IncompleteReadError, ConnectionError):
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        return server, port

    return _create
