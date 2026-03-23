"""Tests for the async TCP connection client."""

from __future__ import annotations

import asyncio

import pytest

from mcp_ableton.connection import AbletonConnection
from mcp_ableton.protocol import CommandRequest


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
    async def test_send_raises_when_disconnected(self) -> None:
        conn = AbletonConnection(host="127.0.0.1", port=1, timeout=0.1, max_retries=1)
        req = CommandRequest(command="session.get_info", id="no-conn")
        with pytest.raises(ConnectionError, match="Reconnect.*failed"):
            await conn.send_command(req)


class TestWithMockServer:
    """Integration tests using the shared echo_server fixture."""

    async def test_connect_send_disconnect(self, echo_server) -> None:
        server, port = await echo_server()
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

    async def test_multiple_commands(self, echo_server) -> None:
        server, port = await echo_server()
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

    async def test_disconnect_is_idempotent(self, echo_server) -> None:
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()
            await conn.disconnect()
            await conn.disconnect()
            assert conn.is_connected is False

    async def test_connect_failure_raises(self) -> None:
        conn = AbletonConnection(host="127.0.0.1", port=1, timeout=0.5, max_retries=1)
        with pytest.raises(ConnectionError):
            await conn.connect()

    async def test_timeout_on_no_response(self) -> None:
        """Server accepts but never responds -- should time out."""

        async def silent_handler(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await reader.read()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(silent_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port, timeout=0.3)
            await conn.connect()
            req = CommandRequest(command="hang", id="timeout-test")
            with pytest.raises(TimeoutError):
                await conn.send_command(req)
            await conn.disconnect()


class TestRetryLogic:
    """Tests for connect() retry with exponential backoff."""

    async def test_retry_exhaustion(self) -> None:
        """All retries fail -> ConnectionError with attempt count."""
        conn = AbletonConnection(
            host="127.0.0.1",
            port=1,
            timeout=0.1,
            max_retries=2,
            retry_delay=0.05,
        )
        with pytest.raises(ConnectionError, match="after 2 attempts"):
            await conn.connect()

    async def test_succeeds_on_first_available_attempt(self, echo_server) -> None:
        """Connection succeeds when the server is available."""
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(
                host="127.0.0.1",
                port=port,
                max_retries=3,
                retry_delay=0.05,
            )
            await conn.connect()
            assert conn.is_connected is True
            await conn.disconnect()

    async def test_max_retries_default(self) -> None:
        conn = AbletonConnection()
        assert conn.max_retries == 3
        assert conn.retry_delay == 1.0


class TestAutoReconnect:
    """Tests for transparent reconnect on send_command()."""

    async def test_reconnects_after_server_drop(self, echo_server) -> None:
        """If the server drops the connection, send_command reconnects."""
        server, port = await echo_server()
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="test.first", id="rc-1")
        resp = await conn.send_command(req)
        assert resp.status == "ok"

        # Simulate a dropped connection by closing the writer
        if conn._writer:
            conn._writer.close()
            await conn._writer.wait_closed()

        # Next send should reconnect transparently
        async with server:
            req2 = CommandRequest(command="test.after_drop", id="rc-2")
            resp2 = await conn.send_command(req2)
            assert resp2.status == "ok"
            assert resp2.result == {"echo": "test.after_drop"}

        await conn.disconnect()

    async def test_reconnect_failure_raises(self, echo_server) -> None:
        """If reconnect also fails, ConnectionError is raised."""
        server, port = await echo_server()
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()
        server.close()
        await server.wait_closed()

        if conn._writer:
            conn._writer.close()
            await conn._writer.wait_closed()

        req = CommandRequest(command="test.fail", id="rc-fail")
        with pytest.raises(ConnectionError, match="Reconnect.*failed"):
            await conn.send_command(req)


class TestPing:
    """Tests for the ping() health check."""

    async def test_ping_success(self, echo_server) -> None:
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()
            assert await conn.ping() is True
            await conn.disconnect()

    async def test_ping_returns_false_when_disconnected(self) -> None:
        conn = AbletonConnection(host="127.0.0.1", port=1, max_retries=1)
        assert await conn.ping() is False

    async def test_ping_returns_false_on_timeout(self) -> None:
        async def silent_handler(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await reader.read()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(silent_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port, timeout=0.2)
            await conn.connect()
            assert await conn.ping() is False
            await conn.disconnect()
