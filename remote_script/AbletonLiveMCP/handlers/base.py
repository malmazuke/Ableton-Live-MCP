"""Base handler providing shared helpers for all command handlers.

Subclass this for each command category (session, track, clip, etc.).
The handler runs on a client-socket thread; use ``_run_on_main_thread``
for any operation that mutates Ableton's state.
"""

import os
import queue
from collections.abc import Callable
from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError

MAIN_THREAD_TIMEOUT = 30


class BaseHandler:
    """Shared base for all Remote Script command handlers.

    Provides access to the ControlSurface (and thus the Song) and a
    helper for scheduling work on Ableton's main thread.
    """

    def __init__(self, control_surface: Any) -> None:
        self._control_surface = control_surface

    @property
    def _song(self) -> Any:
        return self._control_surface.song()

    def _log(self, message: str) -> None:
        self._control_surface.log_message(message)

    def _require_absolute_file_path(
        self,
        params: dict[str, Any],
        name: str = "file_path",
    ) -> str:
        """Validate and return an absolute local filesystem path parameter."""
        raw_value = params.get(name)
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if not isinstance(raw_value, str) or not raw_value:
            raise InvalidParamsError(f"'{name}' must be a string")
        if "://" in raw_value or not os.path.isabs(raw_value):
            raise InvalidParamsError(
                f"'{name}' must be an absolute local filesystem path"
            )
        return raw_value

    def _require_existing_file(self, file_path: str) -> None:
        """Ensure the referenced local file exists before touching Live."""
        if not os.path.isfile(file_path):
            raise NotFoundError(f"File does not exist: {file_path}")

    def _run_on_main_thread(self, fn: Callable[[], Any]) -> Any:
        """Schedule *fn* on Ableton's main thread and block until it completes.

        Uses ``schedule_message(0, callback)`` to run on the next tick of
        Ableton's main thread, and a ``queue.Queue`` to synchronise the
        result back to the calling (client-socket) thread.

        Returns the value produced by *fn* or re-raises any exception.
        """
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _wrapper() -> None:
            try:
                result_queue.put(("ok", fn()))
            except Exception as exc:
                result_queue.put(("error", exc))

        self._control_surface.schedule_message(0, _wrapper)

        status, value = result_queue.get(timeout=MAIN_THREAD_TIMEOUT)
        if status == "error":
            raise value
        return value
