"""Routes 'category.action' commands to the appropriate handler method.

The dispatcher is pure Python with no Ableton imports, making it testable
outside of Live's runtime.
"""

# Error codes mirrored from the MCP server's protocol.ErrorCode.
# Duplicated here because the Remote Script cannot import Pydantic-based modules.
UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
INVALID_PARAMS = "INVALID_PARAMS"
INTERNAL_ERROR = "INTERNAL_ERROR"


class Dispatcher:
    """Map ``category.action`` command strings to handler methods.

    Handlers are registered by category name and must expose
    ``handle_<action>(params)`` methods.  The built-in ``system.ping``
    command is handled directly without an external handler.
    """

    def __init__(self, control_surface):
        self._handlers = {}
        self._control_surface = control_surface

    def register(self, category, handler):
        """Register a handler instance for a command category."""
        self._handlers[category] = handler

    def dispatch(self, command, params, request_id):
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
        except Exception as exc:
            return _error(INTERNAL_ERROR, str(exc), request_id)


def _ok(result, request_id):
    return {
        "status": "ok",
        "result": result,
        "id": request_id,
        "error": None,
    }


def _error(code, message, request_id):
    return {
        "status": "error",
        "result": None,
        "id": request_id,
        "error": {"code": code, "message": message},
    }
