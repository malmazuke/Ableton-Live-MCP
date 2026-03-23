"""Async TCP client for communicating with the Ableton Live Remote Script."""

from __future__ import annotations

import asyncio
import logging

from mcp_ableton.protocol import CommandRequest, CommandResponse

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT = 30.0
BUFFER_SIZE = 65536


class AbletonConnection:
    """Async TCP connection to the Ableton Live Remote Script.

    Sends :class:`CommandRequest` messages and receives :class:`CommandResponse`
    messages over a newline-delimited JSON TCP stream on port 9877.

    Retry logic, health-check, and reconnection are deferred to Issue #5.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the TCP connection is open."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open a TCP connection to the Remote Script."""
        logger.info("Connecting to Ableton at %s:%d", self.host, self.port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
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

    async def send_command(self, request: CommandRequest) -> CommandResponse:
        """Send a command and wait for the correlated response.

        Raises:
            ConnectionError: If the connection is not open.
            TimeoutError: If no response arrives within :attr:`timeout` seconds.
        """
        if not self.is_connected or self._writer is None or self._reader is None:
            raise ConnectionError("Not connected to Ableton. Call connect() first.")

        self._writer.write(request.to_line())
        await self._writer.drain()

        try:
            raw_line = await asyncio.wait_for(
                self._reader.readuntil(b"\n"),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            # Python 3.10: asyncio.TimeoutError != builtins.TimeoutError
            raise TimeoutError(
                f"No response from Ableton within {self.timeout}s"
            ) from None
        return CommandResponse.from_line(raw_line)


__all__ = [
    "AbletonConnection",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT",
    "BUFFER_SIZE",
]
