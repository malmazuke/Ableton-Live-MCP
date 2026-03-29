"""Device and parameter command handlers for the Ableton Live Remote Script."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler


class DeviceHandler(BaseHandler):
    """Handle device parameter inspection and writes."""

    def _require_index(self, params: dict[str, Any], name: str) -> int:
        """Return a validated 1-based index parameter."""
        raw_value = params.get(name)
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise InvalidParamsError(f"'{name}' must be an integer")
        if raw_value < 1:
            raise InvalidParamsError(f"'{name}' must be at least 1")
        return raw_value

    def _require_numeric_value(self, params: dict[str, Any], name: str) -> float:
        """Return a validated numeric parameter value."""
        raw_value = params.get(name)
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise InvalidParamsError(f"'{name}' must be a number")
        return float(raw_value)

    def _resolve_track(self, track_index: int) -> Any:
        """Resolve a 1-based track index to a track object."""
        tracks = self._song.tracks
        track_count = len(tracks)
        if track_index > track_count:
            raise NotFoundError(
                f"Track {track_index} does not exist (song has {track_count} track(s))"
            )
        return tracks[track_index - 1]

    def _resolve_device(self, track: Any, track_index: int, device_index: int) -> Any:
        """Resolve a 1-based device index on a track."""
        devices = list(track.devices)
        device_count = len(devices)
        if device_index > device_count:
            raise NotFoundError(
                f"Device {device_index} does not exist on track {track_index} "
                f"(track has {device_count} device(s))"
            )
        return devices[device_index - 1]

    def _resolve_parameter(
        self,
        device: Any,
        track_index: int,
        device_index: int,
        parameter_index: int,
    ) -> Any:
        """Resolve a 1-based parameter index on a device."""
        parameters = list(device.parameters)
        parameter_count = len(parameters)
        if parameter_index > parameter_count:
            raise NotFoundError(
                f"Parameter {parameter_index} does not exist on device {device_index} "
                f"of track {track_index} (device has {parameter_count} parameter(s))"
            )
        return parameters[parameter_index - 1]

    def _serialize_parameter(
        self,
        parameter: Any,
        parameter_index: int,
    ) -> dict[str, Any]:
        """Serialize a DeviceParameter into the response payload."""
        return {
            "parameter_index": parameter_index,
            "name": str(getattr(parameter, "name", "")),
            "value": float(parameter.value),
            "min": float(parameter.min),
            "max": float(parameter.max),
            "is_quantized": bool(parameter.is_quantized),
        }

    def handle_get_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return all parameters for one device on one track."""
        track_index = self._require_index(params, "track_index")
        device_index = self._require_index(params, "device_index")

        def _read() -> dict[str, Any]:
            track = self._resolve_track(track_index)
            device = self._resolve_device(track, track_index, device_index)
            parameters = list(device.parameters)
            return {
                "track_index": track_index,
                "device_index": device_index,
                "device_name": str(getattr(device, "name", "")),
                "parameters": [
                    self._serialize_parameter(parameter, parameter_index + 1)
                    for parameter_index, parameter in enumerate(parameters)
                ],
            }

        return self._run_on_main_thread(_read)

    def handle_set_parameter(self, params: dict[str, Any]) -> dict[str, Any]:
        """Set one parameter using Live's actual parameter range."""
        track_index = self._require_index(params, "track_index")
        device_index = self._require_index(params, "device_index")
        parameter_index = self._require_index(params, "parameter_index")
        value = self._require_numeric_value(params, "value")

        def _write() -> dict[str, Any]:
            track = self._resolve_track(track_index)
            device = self._resolve_device(track, track_index, device_index)
            parameter = self._resolve_parameter(
                device,
                track_index,
                device_index,
                parameter_index,
            )
            minimum = float(parameter.min)
            maximum = float(parameter.max)
            if value < minimum or value > maximum:
                raise InvalidParamsError(
                    f"'value' must be between {minimum} and {maximum}, got {value}"
                )
            parameter.value = value
            return {
                "track_index": track_index,
                "device_index": device_index,
                "parameter_index": parameter_index,
                "value": float(parameter.value),
            }

        return self._run_on_main_thread(_write)


__all__ = ["DeviceHandler"]
