"""Typed request/response models for the MCP server <-> Remote Script TCP protocol.

All messages are newline-delimited JSON (each message is a single line terminated
by ``\\n``).  Use :meth:`CommandRequest.to_line` / :meth:`CommandRequest.from_line`
and the corresponding :class:`CommandResponse` helpers for framing.

Protocol shape::

    Request:  {"command": "category.action", "params": {...}, "id": "uuid"}
    Response: {"status": "ok"|"error", "result": {...}, "id": "uuid", "error": {...}}

Error codes are standardized via :class:`ErrorCode` constants, shared between
the MCP server and the Remote Script (which reimplements parsing in plain Python).
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(str, Enum):
    """Standardized error codes used by both the MCP server and Remote Script."""

    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    INVALID_PARAMS = "INVALID_PARAMS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    NOT_CONNECTED = "NOT_CONNECTED"


class CommandError(Exception):
    """Raised when the Remote Script returns an error response."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class CommandRequest(BaseModel):
    """A command sent from the MCP server to the Remote Script.

    ``command`` uses ``category.action`` dot notation (e.g. ``session.get_info``).
    ``id`` correlates requests with responses and defaults to a new UUID.
    """

    model_config = ConfigDict(strict=True)

    command: str
    params: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    def to_line(self) -> bytes:
        """Serialize to a newline-terminated UTF-8 byte string."""
        return self.model_dump_json().encode("utf-8") + b"\n"

    @classmethod
    def from_line(cls, line: bytes) -> CommandRequest:
        """Deserialize from a newline-delimited UTF-8 byte string."""
        return cls.model_validate_json(line.strip())


class ErrorDetail(BaseModel):
    """Structured error information returned by the Remote Script."""

    model_config = ConfigDict(strict=True)

    code: str
    message: str


class CommandResponse(BaseModel):
    """A response sent from the Remote Script back to the MCP server."""

    model_config = ConfigDict(strict=True)

    status: Literal["ok", "error"]
    result: dict[str, Any] | None = None
    id: str
    error: ErrorDetail | None = None

    def raise_on_error(self) -> None:
        """Raise :class:`CommandError` if this response indicates failure."""
        if self.status == "error":
            error = self.error
            code = error.code if error else ErrorCode.INTERNAL_ERROR
            message = error.message if error else "Unknown error"
            raise CommandError(code, message)

    def to_line(self) -> bytes:
        """Serialize to a newline-terminated UTF-8 byte string."""
        return self.model_dump_json().encode("utf-8") + b"\n"

    @classmethod
    def from_line(cls, line: bytes) -> CommandResponse:
        """Deserialize from a newline-delimited UTF-8 byte string."""
        return cls.model_validate_json(line.strip())


__all__ = [
    "CommandError",
    "CommandRequest",
    "CommandResponse",
    "ErrorCode",
    "ErrorDetail",
]
