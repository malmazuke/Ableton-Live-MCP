"""Async TCP client for communicating with the Ableton Live Remote Script."""

from __future__ import annotations

import asyncio
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
        """Single-attempt TCP open (no retry)."""
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
        logger.info("Connected to Ableton at %s:%d", self.host, self.port)

    async def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            logger.info("Disconnecting from Ableton")
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
        """Write a request and read the response (no retry).

        Args:
            request: The command to send.
            timeout: Response timeout override.  Falls back to
                :attr:`timeout` when ``None``.
        """
        if not self.is_connected or self._writer is None or self._reader is None:
            raise ConnectionError("Not connected to Ableton. Call connect() first.")

        effective_timeout = timeout if timeout is not None else self.timeout

        self._writer.write(request.to_line())
        await self._writer.drain()

        try:
            raw_line = await asyncio.wait_for(
                self._reader.readuntil(b"\n"),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"No response from Ableton within {effective_timeout}s"
            ) from None
        except asyncio.LimitOverrunError:
            raise RuntimeError(
                "Response from Ableton exceeded the configured stream limit "
                f"({STREAM_LIMIT} bytes)"
            ) from None
        return CommandResponse.from_line(raw_line)

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
