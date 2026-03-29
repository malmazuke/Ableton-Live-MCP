"""Tests for the async TCP connection client."""

from __future__ import annotations

import asyncio

import pytest

from mcp_ableton.connection import STREAM_LIMIT, AbletonConnection
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

    async def test_open_connection_uses_large_stream_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, int] = {}

        class _FakeWriter:
            def is_closing(self) -> bool:
                return False

            def close(self) -> None:
                pass

            async def wait_closed(self) -> None:
                return None

        async def fake_open_connection(host: str, port: int, *, limit: int):
            captured["limit"] = limit
            return asyncio.StreamReader(), _FakeWriter()

        monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

        conn = AbletonConnection(host="127.0.0.1", port=9877, max_retries=1)
        await conn.connect()

        assert captured["limit"] == STREAM_LIMIT

        await conn.disconnect()


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

        if conn._writer:
            conn._writer.close()
            await conn._writer.wait_closed()

        server.close()
        await server.wait_closed()

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


class TestConcurrency:
    """Tests for concurrent send_command calls with ID correlation."""

    async def test_concurrent_sends_correct_correlation(self, echo_server) -> None:
        """Multiple concurrent sends each receive their own response."""
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()

            requests = [
                CommandRequest(command=f"test.concurrent_{i}", id=f"cc-{i}")
                for i in range(10)
            ]
            responses = await asyncio.gather(
                *(conn.send_command(req) for req in requests)
            )

            for i, resp in enumerate(responses):
                assert resp.status == "ok"
                assert resp.id == f"cc-{i}"
                assert resp.result == {"echo": f"test.concurrent_{i}"}

            await conn.disconnect()

    async def test_out_of_order_responses(self) -> None:
        """Responses arriving in reverse order are correctly correlated."""
        request_count = 3

        async def reverse_handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            try:
                lines: list[bytes] = []
                for _ in range(request_count):
                    line = await reader.readuntil(b"\n")
                    lines.append(line)
                for line in reversed(lines):
                    req = CommandRequest.from_line(line)
                    resp = CommandResponse(
                        status="ok",
                        result={"echo": req.command},
                        id=req.id,
                    )
                    writer.write(resp.to_line())
                await writer.drain()
                await reader.read()
            except (asyncio.IncompleteReadError, ConnectionError):
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(reverse_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()

            requests = [
                CommandRequest(command=f"test.rev_{i}", id=f"rev-{i}")
                for i in range(request_count)
            ]
            responses = await asyncio.gather(
                *(conn.send_command(req) for req in requests)
            )

            for i, resp in enumerate(responses):
                assert resp.id == f"rev-{i}"
                assert resp.result == {"echo": f"test.rev_{i}"}

            await conn.disconnect()


class TestTimeoutCleanup:
    """Verify that timed-out requests are cleaned out of _pending."""

    async def test_pending_cleaned_on_timeout(self) -> None:
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

            req = CommandRequest(command="hang", id="pending-cleanup")
            with pytest.raises(TimeoutError):
                await conn.send_command(req)

            assert "pending-cleanup" not in conn._pending
            assert len(conn._pending) == 0

            await conn.disconnect()


class TestReaderLifecycle:
    """Tests for the background reader task lifecycle."""

    async def test_reader_task_started_on_connect(self, echo_server) -> None:
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            assert conn._reader_task is None
            await conn.connect()
            assert conn._reader_task is not None
            assert not conn._reader_task.done()
            await conn.disconnect()

    async def test_reader_task_stopped_on_disconnect(self, echo_server) -> None:
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()
            reader_task = conn._reader_task
            assert reader_task is not None

            await conn.disconnect()
            assert conn._reader_task is None
            assert reader_task.done()

    async def test_reader_handles_connection_close(self) -> None:
        """When the server closes, pending futures get ConnectionError."""
        gate = asyncio.Event()

        async def close_on_signal(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await gate.wait()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(close_on_signal, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port, timeout=5.0)
            await conn.connect()

            loop = asyncio.get_running_loop()
            future: asyncio.Future[CommandResponse] = loop.create_future()
            conn._pending["orphan-1"] = future

            gate.set()
            with pytest.raises(ConnectionError):
                await asyncio.wait_for(future, timeout=2.0)

            assert len(conn._pending) == 0
            await conn.disconnect()

    async def test_new_reader_task_after_reconnect(self, echo_server) -> None:
        """Reconnecting starts a fresh reader task."""
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
            await conn.connect()
            old_task = conn._reader_task

            await conn._reconnect()
            new_task = conn._reader_task

            assert new_task is not None
            assert new_task is not old_task
            assert old_task is not None and old_task.done()
            assert not new_task.done()

            await conn.disconnect()

    async def test_pending_rejected_on_disconnect(self, echo_server) -> None:
        """Outstanding futures are rejected with ConnectionError on disconnect."""
        server, port = await echo_server()
        async with server:
            conn = AbletonConnection(host="127.0.0.1", port=port)
            await conn.connect()

            loop = asyncio.get_running_loop()
            f1: asyncio.Future[CommandResponse] = loop.create_future()
            f2: asyncio.Future[CommandResponse] = loop.create_future()
            conn._pending["d-1"] = f1
            conn._pending["d-2"] = f2

            await conn.disconnect()

            assert f1.done()
            assert f2.done()
            with pytest.raises(ConnectionError):
                f1.result()
            with pytest.raises(ConnectionError):
                f2.result()
