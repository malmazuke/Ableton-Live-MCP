"""Ableton Live MCP Remote Script.

A ControlSurface that exposes Ableton Live's API over TCP for the
MCP server to consume.  The TCP server, dispatcher, and handlers
are started during ``__init__`` and torn down in ``disconnect()``.
"""

import threading
from typing import Any

from _Framework.ControlSurface import ControlSurface

from .dispatcher import Dispatcher
from .tcp_server import TcpServer

TCP_HOST = "127.0.0.1"
TCP_PORT = 9877


def create_instance(c_instance: Any) -> "AbletonLiveMCP":
    """Entry point called by Ableton Live to instantiate the Remote Script."""
    return AbletonLiveMCP(c_instance)


class AbletonLiveMCP(ControlSurface):
    """MCP Remote Script entry point loaded by Ableton Live."""

    def __init__(self, c_instance: Any) -> None:
        ControlSurface.__init__(self, c_instance)

        self.log_message("AbletonLiveMCP: initialising")

        self._dispatcher = Dispatcher(self)
        self._register_handlers()

        self._tcp_server = TcpServer(
            dispatcher=self._dispatcher,
            log_fn=self.log_message,
            host=TCP_HOST,
            port=TCP_PORT,
        )
        self._server_thread = threading.Thread(
            target=self._tcp_server.serve_forever,
            daemon=True,
        )
        self._server_thread.start()

        self.log_message("AbletonLiveMCP: ready")
        self.show_message(f"AbletonLiveMCP: listening on port {TCP_PORT}")

    def _register_handlers(self) -> None:
        """Register command handlers with the dispatcher."""
        from .handlers.browser import BrowserHandler
        from .handlers.clip import ClipHandler
        from .handlers.device import DeviceHandler
        from .handlers.mixer import MixerHandler
        from .handlers.session import SessionHandler
        from .handlers.track import TrackHandler

        self._dispatcher.register("session", SessionHandler(self))
        self._dispatcher.register("track", TrackHandler(self))
        self._dispatcher.register("device", DeviceHandler(self))
        self._dispatcher.register("clip", ClipHandler(self))
        self._dispatcher.register("browser", BrowserHandler(self))
        self._dispatcher.register("mixer", MixerHandler(self))

    def disconnect(self) -> None:
        """Ableton lifecycle hook -- shut down the TCP server."""
        self.log_message("AbletonLiveMCP: shutting down")
        self._tcp_server.shutdown()
        ControlSurface.disconnect(self)


__all__ = ["AbletonLiveMCP", "TCP_HOST", "TCP_PORT", "create_instance"]
