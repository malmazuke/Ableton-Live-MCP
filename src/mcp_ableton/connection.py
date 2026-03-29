"""Async TCP client for communicating with the Ableton Live Remote Script."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from mcp_ableton.protocol import CommandRequest, CommandResponse

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
PING_TIMEOUT = 5.0
BUFFER_SIZE = 65536
STREAM_LIMIT = 8 * 1024 * 1024


class AbletonConnection:
    """Async TCP connection to the Ableton Live Remote Script.

    Sends :class:`CommandRequest` messages and receives :class:`CommandResponse`
    messages over a newline-delimited JSON TCP stream on port 9877.

    Features:
    - Request-ID correlation for safe concurrent sends
    - Exponential-backoff retry on ``connect()``
    - Transparent single-attempt reconnect on ``send_command()``
    - ``ping()`` health check via the ``system.ping`` command
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[CommandResponse]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the TCP connection is open."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open a TCP connection to the Remote Script with retry.

        Retries up to :attr:`max_retries` times with exponential backoff
        starting at :attr:`retry_delay` seconds.
        """
        last_error: OSError | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._open_connection()
                return
            except OSError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Connection attempt %d/%d failed: %s — retrying in %.1fs",
                        attempt,
                        self.max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise ConnectionError(
            f"Failed to connect to Ableton at {self.host}:{self.port} "
            f"after {self.max_retries} attempts: {last_error}"
        ) from last_error

    async def _open_connection(self) -> None:
        """Single-attempt TCP open (no retry).  Starts the background reader."""
        logger.info("Connecting to Ableton at %s:%d", self.host, self.port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.host,
                    self.port,
                    limit=STREAM_LIMIT,
                ),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Could not connect to Ableton at {self.host}:{self.port} "
                f"within {self.timeout}s"
            ) from None
        self._reader_task = asyncio.create_task(self._reader_loop())
        logger.info("Connected to Ableton at %s:%d", self.host, self.port)

    # ------------------------------------------------------------------
    # Background reader
    # ------------------------------------------------------------------

    async def _reader_loop(self) -> None:
        """Continuously read responses and resolve the matching pending future."""
        assert self._reader is not None
        try:
            while True:
                raw_line = await self._reader.readuntil(b"\n")
                try:
                    response = CommandResponse.from_line(raw_line)
                except Exception:
                    logger.warning(
                        "Failed to parse response: %s",
                        raw_line,
                        exc_info=True,
                    )
                    continue
                future = self._pending.pop(response.id, None)
                if future is not None and not future.done():
                    future.set_result(response)
                elif future is None:
                    logger.warning(
                        "No pending request for response id=%s",
                        response.id,
                    )
        except asyncio.IncompleteReadError:
            self._reject_pending(
                ConnectionError("Connection to Ableton closed"),
            )
        except ConnectionResetError:
            self._reject_pending(
                ConnectionError("Connection to Ableton reset"),
            )
        except asyncio.LimitOverrunError:
            logger.error(
                "Response exceeded stream limit (%d bytes)",
                STREAM_LIMIT,
            )
            self._reject_pending(
                RuntimeError("Response exceeded stream limit"),
            )

    def _reject_pending(self, error: Exception) -> None:
        """Reject all in-flight futures with *error* and clear the map."""
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    async def _stop_reader(self) -> None:
        """Cancel the background reader task and wait for it to finish."""
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            logger.info("Disconnecting from Ableton")
            await self._stop_reader()
            self._reject_pending(ConnectionError("Disconnected from Ableton"))
            self._writer.close()
            await self._writer.wait_closed()
            self._reader = None
            self._writer = None
            logger.info("Disconnected from Ableton")

    async def _reconnect(self) -> None:
        """Drop the current connection and open a fresh one (single attempt)."""
        logger.info("Attempting reconnect to Ableton")
        await self.disconnect()
        await self._open_connection()

    # ------------------------------------------------------------------
    # Sending commands
    # ------------------------------------------------------------------

    async def send_command(
        self,
        request: CommandRequest,
        timeout: float | None = None,
    ) -> CommandResponse:
        """Send a command and wait for the correlated response.

        If the connection has dropped, one transparent reconnect is attempted
        before raising.

        Args:
            request: The command to send.
            timeout: Response timeout override.  Falls back to
                :attr:`timeout` when ``None``.

        Raises:
            ConnectionError: If the connection cannot be established.
            TimeoutError: If no response arrives within the timeout.
        """
        try:
            return await self._send(request, timeout=timeout)
        except (ConnectionError, OSError) as exc:
            logger.warning("Send failed (%s), attempting reconnect", exc)
            try:
                await self._reconnect()
            except OSError as reconnect_exc:
                raise ConnectionError(
                    f"Reconnect to Ableton failed: {reconnect_exc}"
                ) from reconnect_exc
            return await self._send(request, timeout=timeout)

    async def _send(
        self,
        request: CommandRequest,
        timeout: float | None = None,
    ) -> CommandResponse:
        """Register a pending future, write the request, and await the response.

        Args:
            request: The command to send.
            timeout: Response timeout override.  Falls back to
                :attr:`timeout` when ``None``.
        """
        if not self.is_connected or self._writer is None:
            raise ConnectionError("Not connected to Ableton. Call connect() first.")

        effective_timeout = timeout if timeout is not None else self.timeout

        loop = asyncio.get_running_loop()
        future: asyncio.Future[CommandResponse] = loop.create_future()
        self._pending[request.id] = future

        try:
            async with self._write_lock:
                self._writer.write(request.to_line())
                await self._writer.drain()
        except Exception:
            self._pending.pop(request.id, None)
            raise

        try:
            return await asyncio.wait_for(future, timeout=effective_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request.id, None)
            raise TimeoutError(
                f"No response from Ableton within {effective_timeout}s"
            ) from None

    async def ping(self) -> bool:
        """Send a ``system.ping`` and return ``True`` if the Remote Script responds.

        Uses a short timeout (:data:`PING_TIMEOUT`) independent of the default.
        Returns ``False`` on any failure rather than raising.
        """
        req = CommandRequest(command="system.ping")
        try:
            resp = await self.send_command(req, timeout=PING_TIMEOUT)
            return resp.status == "ok"
        except (ConnectionError, TimeoutError, OSError):
            return False


__all__ = [
    "AbletonConnection",
    "DEFAULT_HOST",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_PORT",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_TIMEOUT",
    "BUFFER_SIZE",
    "PING_TIMEOUT",
    "STREAM_LIMIT",
]
