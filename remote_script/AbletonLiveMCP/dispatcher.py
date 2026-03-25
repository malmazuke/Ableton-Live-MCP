"""Routes 'category.action' commands to the appropriate handler method.

The dispatcher is pure Python with no Ableton imports, making it testable
outside of Live's runtime.
"""

from typing import Any

# Error codes mirrored from the MCP server's protocol.ErrorCode.
# Duplicated here because the Remote Script cannot import Pydantic-based modules.
UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
INVALID_PARAMS = "INVALID_PARAMS"
INTERNAL_ERROR = "INTERNAL_ERROR"
NOT_FOUND = "NOT_FOUND"


class InvalidParamsError(Exception):
    """Raised by handlers when parameters fail semantic validation."""


class NotFoundError(Exception):
    """Raised when a requested resource (e.g. track index) does not exist."""


class Dispatcher:
    """Map ``category.action`` command strings to handler methods.

    Handlers are registered by category name and must expose
    ``handle_<action>(params)`` methods.  The built-in ``system.ping``
    command is handled directly without an external handler.
    """

    def __init__(self, control_surface: Any) -> None:
        self._handlers: dict[str, Any] = {}
        self._control_surface = control_surface

    def register(self, category: str, handler: Any) -> None:
        """Register a handler instance for a command category."""
        self._handlers[category] = handler

    def dispatch(
        self,
        command: str,
        params: dict[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        """Route a command to its handler and return a response dict.

        Returns a dict matching the protocol response shape::

            {"status": "ok"|"error", "result": ..., "id": ..., "error": ...}
        """
        if command == "system.ping":
            return _ok({"message": "pong"}, request_id)

        category, sep, action = command.partition(".")
        if not sep or not action:
            return _error(
                UNKNOWN_COMMAND,
                f"Command must use 'category.action' format, got: {command}",
                request_id,
            )

        handler = self._handlers.get(category)
        if handler is None:
            return _error(
                UNKNOWN_COMMAND,
                f"Unknown category: {category}",
                request_id,
            )

        method = getattr(handler, f"handle_{action}", None)
        if method is None:
            return _error(
                UNKNOWN_COMMAND,
                f"Unknown action '{action}' for category '{category}'",
                request_id,
            )

        try:
            result = method(params)
            return _ok(result, request_id)
        except InvalidParamsError as exc:
            return _error(INVALID_PARAMS, str(exc), request_id)
        except NotFoundError as exc:
            return _error(NOT_FOUND, str(exc), request_id)
        except Exception as exc:
            return _error(INTERNAL_ERROR, str(exc), request_id)


def _ok(result: Any, request_id: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "result": result,
        "id": request_id,
        "error": None,
    }


def _error(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {
        "status": "error",
        "result": None,
        "id": request_id,
        "error": {"code": code, "message": message},
    }
