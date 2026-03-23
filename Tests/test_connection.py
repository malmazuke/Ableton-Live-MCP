"""Tests for the async TCP connection client."""

from __future__ import annotations

import asyncio

import pytest

from mcp_ableton.connection import AbletonConnection
from mcp_ableton.protocol import CommandRequest, CommandResponse


@pytest.fixture
def connection() -> AbletonConnection:
    return AbletonConnection()


class TestConnectionDefaults:
    def test_starts_disconnected(self, connection: AbletonConnection) -> None:
        assert connection.is_connected is False

    def test_default_host_and_port(self, connection: AbletonConnection) -> None:
        assert connection.host == "localhost"
        assert connection.port == 9877

    def test_custom_host_and_port(self) -> None:
        conn = AbletonConnection(host="192.168.1.10", port=1234, timeout=5.0)
        assert conn.host == "192.168.1.10"
        assert conn.port == 1234
        assert conn.timeout == 5.0


class TestSendCommandRequiresConnection:
    async def test_send_raises_when_disconnected(
        self, connection: AbletonConnection
    ) -> None:
        req = CommandRequest(command="session.get_info", id="no-conn")
        with pytest.raises(ConnectionError, match="Not connected"):
            await connection.send_command(req)


class TestWithMockServer:
    """Integration tests using a real asyncio TCP server in-process."""

    async def _start_echo_server(
        self,
    ) -> tuple[asyncio.Server, int]:
        """Start a TCP server that echoes back a valid CommandResponse."""

        async def handle_client(
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

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        return server, port

    async def test_connect_send_disconnect(self) -> None:
        server, port = await self._start_echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()
            assert conn.is_connected is True

            req = CommandRequest(command="session.get_info", id="test-1")
            resp = await conn.send_command(req)

            assert resp.status == "ok"
            assert resp.id == "test-1"
            assert resp.result == {"echo": "session.get_info"}

            await conn.disconnect()
            assert conn.is_connected is False

    async def test_multiple_commands(self) -> None:
        server, port = await self._start_echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()

            for i in range(3):
                req = CommandRequest(
                    command=f"test.cmd_{i}",
                    params={"i": i},
                    id=f"multi-{i}",
                )
                resp = await conn.send_command(req)
                assert resp.id == f"multi-{i}"
                assert resp.result == {"echo": f"test.cmd_{i}"}

            await conn.disconnect()

    async def test_disconnect_is_idempotent(self) -> None:
        server, port = await self._start_echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()
            await conn.disconnect()
            await conn.disconnect()
            assert conn.is_connected is False

    async def test_connect_failure_raises(self) -> None:
        conn = AbletonConnection(host="127.0.0.1", port=1, timeout=0.5)
        with pytest.raises(OSError):
            await conn.connect()

    async def test_timeout_on_no_response(self) -> None:
        """Server accepts but never responds — should time out."""

        async def silent_handler(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await asyncio.sleep(60)
            writer.close()

        server = await asyncio.start_server(silent_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port, timeout=0.3)
            await conn.connect()
            req = CommandRequest(command="hang", id="timeout-test")
            with pytest.raises(TimeoutError):
                await conn.send_command(req)
            await conn.disconnect()
