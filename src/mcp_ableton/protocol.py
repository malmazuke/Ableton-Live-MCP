"""Typed request/response models for the MCP server <-> Remote Script TCP protocol.

All messages are newline-delimited JSON (each message is a single line terminated
by ``\\n``).  Use :meth:`CommandRequest.to_line` / :meth:`CommandRequest.from_line`
and the corresponding :class:`CommandResponse` helpers for framing.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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

    def to_line(self) -> bytes:
        """Serialize to a newline-terminated UTF-8 byte string."""
        return self.model_dump_json().encode("utf-8") + b"\n"

    @classmethod
    def from_line(cls, line: bytes) -> CommandResponse:
        """Deserialize from a newline-delimited UTF-8 byte string."""
        return cls.model_validate_json(line.strip())


__all__ = [
    "CommandRequest",
    "CommandResponse",
    "ErrorDetail",
]
