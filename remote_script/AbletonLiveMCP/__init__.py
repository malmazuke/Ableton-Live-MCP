"""Ableton Live MCP Remote Script.

A ControlSurface that exposes Ableton Live's API over TCP for the
MCP server to consume.  The TCP server, dispatcher, and handlers
are started during ``__init__`` and torn down in ``disconnect()``.
"""

import threading

from _Framework.ControlSurface import ControlSurface

from .dispatcher import Dispatcher
from .tcp_server import TcpServer

TCP_HOST = "127.0.0.1"
TCP_PORT = 9877


def create_instance(c_instance):
    """Entry point called by Ableton Live to instantiate the Remote Script."""
    return AbletonLiveMCP(c_instance)


class AbletonLiveMCP(ControlSurface):
    """MCP Remote Script entry point loaded by Ableton Live."""

    def __init__(self, c_instance):
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

    def _register_handlers(self):
        """Register command handlers with the dispatcher.

        Add new handlers here as they are implemented in subsequent issues
        (session, track, clip, device, etc.).
        """
        pass

    def disconnect(self):
        """Ableton lifecycle hook -- shut down the TCP server."""
        self.log_message("AbletonLiveMCP: shutting down")
        self._tcp_server.shutdown()
        ControlSurface.disconnect(self)
