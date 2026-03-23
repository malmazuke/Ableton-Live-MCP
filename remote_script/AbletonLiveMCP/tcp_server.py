"""Synchronous TCP server for the Ableton Live MCP Remote Script.

Runs inside Ableton's embedded Python runtime -- no asyncio, no pip
packages.  Each connected client is handled in its own daemon thread.
Messages use the newline-delimited JSON protocol defined in
``mcp_ableton.protocol`` (reimplemented here with plain ``json``).
"""

import contextlib
import json
import socket
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877
BUFFER_SIZE = 65536


class TcpServer:
    """A threaded TCP server that dispatches JSON commands via a :class:`Dispatcher`.

    Call :meth:`serve_forever` from a daemon thread, and :meth:`shutdown`
    when the ControlSurface disconnects.
    """

    def __init__(self, dispatcher, log_fn, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self._dispatcher = dispatcher
        self._log = log_fn
        self._host = host
        self._port = port
        self._server_socket = None
        self._running = False
        self._client_threads = []

    def serve_forever(self):
        """Accept connections in a loop until :meth:`shutdown` is called."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(5)
        self._running = True
        self._log(f"AbletonLiveMCP TCP server listening on {self._host}:{self._port}")

        while self._running:
            try:
                client_socket, address = self._server_socket.accept()
                self._log(f"Client connected from {address[0]}:{address[1]}")
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                self._client_threads = [t for t in self._client_threads if t.is_alive()]
                self._client_threads.append(thread)
                thread.start()
            except TimeoutError:
                continue
            except OSError:
                if self._running:
                    self._log("Server socket error during accept")
                break

        self._cleanup()

    def shutdown(self):
        """Signal the server to stop accepting connections."""
        self._running = False
        if self._server_socket:
            with contextlib.suppress(OSError):
                self._server_socket.close()

    def _cleanup(self):
        if self._server_socket:
            with contextlib.suppress(OSError):
                self._server_socket.close()
        self._log("AbletonLiveMCP TCP server stopped")

    def _handle_client(self, client_socket, address):
        """Read newline-delimited JSON commands from a single client."""
        buf = ""
        try:
            while self._running:
                try:
                    data = client_socket.recv(BUFFER_SIZE)
                except OSError:
                    break
                if not data:
                    break

                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    response = self._process_line(line)
                    try:
                        client_socket.sendall(
                            (json.dumps(response) + "\n").encode("utf-8")
                        )
                    except OSError:
                        self._log(
                            f"Failed to send response to {address[0]}:{address[1]}"
                        )
                        return
        except Exception as exc:
            self._log(f"Unhandled error for client {address[0]}:{address[1]}: {exc}")
        finally:
            with contextlib.suppress(OSError):
                client_socket.close()
            self._log(f"Client disconnected: {address[0]}:{address[1]}")

    def _process_line(self, line):
        """Parse a JSON line into a command and dispatch it."""
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            return {
                "status": "error",
                "result": None,
                "id": None,
                "error": {
                    "code": "INVALID_PARAMS",
                    "message": f"Malformed JSON: {exc}",
                },
            }

        command = message.get("command")
        params = message.get("params", {})
        request_id = message.get("id")

        if not command or not isinstance(command, str):
            return {
                "status": "error",
                "result": None,
                "id": request_id,
                "error": {
                    "code": "INVALID_PARAMS",
                    "message": "Missing or invalid 'command' field",
                },
            }

        return self._dispatcher.dispatch(command, params, request_id)
