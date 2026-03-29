"""Tests for DeviceHandler and BrowserHandler device-loading commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher, InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.browser import BrowserHandler
from AbletonLiveMCP.handlers.device import DeviceHandler

if TYPE_CHECKING:
    from collections.abc import Callable


class _Parameter:
    def __init__(
        self,
        name: str,
        value: float,
        minimum: float,
        maximum: float,
        *,
        is_quantized: bool = False,
    ) -> None:
        self.name = name
        self.value = value
        self.min = minimum
        self.max = maximum
        self.is_quantized = is_quantized


class _Device:
    def __init__(self, name: str, parameters: list[_Parameter]) -> None:
        self.name = name
        self.parameters = parameters


class _Track:
    def __init__(
        self,
        name: str,
        *,
        midi: bool,
        audio: bool,
        devices: list[_Device] | None = None,
    ) -> None:
        self.name = name
        self.has_midi_input = midi
        self.has_audio_input = audio
        self.devices = devices or []


class _SongView:
    def __init__(self) -> None:
        self.selected_track: _Track | None = None


class _Song:
    def __init__(self, tracks: list[_Track]) -> None:
        self.tracks = tracks
        self.view = _SongView()


class _BrowserItem:
    def __init__(
        self,
        name: str,
        *,
        uri: str | None = None,
        is_loadable: bool = False,
        device_factory: Callable[[], _Device] | None = None,
        children: list[_BrowserItem] | None = None,
    ) -> None:
        self.name = name
        self.uri = uri
        self.is_loadable = is_loadable
        self.device_factory = device_factory
        self.children = children or []
        self.is_folder = bool(self.children)


class _Browser:
    def __init__(self, song: _Song) -> None:
        self._song = song
        self.instruments = _BrowserItem(
            "Instruments",
            uri="browser:instruments",
            children=[
                _BrowserItem(
                    "Synths",
                    uri="browser:instruments/synths",
                    children=[
                        _BrowserItem(
                            "Analog",
                            uri="browser:instruments/synths/analog",
                            is_loadable=True,
                            device_factory=lambda: _Device(
                                "Analog",
                                [
                                    _Parameter(
                                        "Device On",
                                        1.0,
                                        0.0,
                                        1.0,
                                        is_quantized=True,
                                    ),
                                    _Parameter("Filter Freq", 5000.0, 20.0, 20000.0),
                                ],
                            ),
                        ),
                        _BrowserItem(
                            "Broken Instrument",
                            uri="browser:instruments/synths/broken",
                            is_loadable=False,
                        ),
                    ],
                )
            ],
        )
        self.audio_effects = _BrowserItem(
            "Audio Effects",
            uri="browser:audio_effects",
            children=[
                _BrowserItem(
                    "Filters",
                    uri="browser:audio_effects/filters",
                    children=[
                        _BrowserItem(
                            "Auto Filter",
                            uri="browser:audio_effects/filters/auto-filter",
                            is_loadable=True,
                            device_factory=lambda: _Device(
                                "Auto Filter",
                                [
                                    _Parameter(
                                        "Device On",
                                        1.0,
                                        0.0,
                                        1.0,
                                        is_quantized=True,
                                    ),
                                    _Parameter("Frequency", 2500.0, 20.0, 20000.0),
                                ],
                            ),
                        ),
                        _BrowserItem(
                            "Broken Effect",
                            uri="browser:audio_effects/filters/broken",
                            is_loadable=False,
                        ),
                    ],
                )
            ],
        )
        self.midi_effects = _BrowserItem(
            "MIDI Effects",
            uri="browser:midi_effects",
            children=[
                _BrowserItem(
                    "Pitch",
                    uri="browser:midi_effects/pitch",
                    children=[],
                )
            ],
        )
        self.drums = _BrowserItem(
            "Drums",
            uri="browser:drums",
            children=[],
        )
        self.sounds = _BrowserItem(
            "Sounds",
            uri="browser:sounds",
            children=[],
        )

    def load_item(self, item: _BrowserItem) -> None:
        selected_track = self._song.view.selected_track
        if selected_track is None:
            raise RuntimeError("No selected track")
        if item.device_factory is None:
            return
        selected_track.devices.append(item.device_factory())


class _Application:
    def __init__(self, song: _Song) -> None:
        self.browser = _Browser(song)


class _FakeControlSurface:
    def __init__(self, song: _Song) -> None:
        self._song = song
        self._application = _Application(song)

    def application(self) -> _Application:
        return self._application

    def song(self) -> _Song:
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay: int, callback) -> None:
        callback()


@pytest.fixture
def song() -> _Song:
    return _Song(
        [
            _Track(
                "MIDI Track",
                midi=True,
                audio=False,
                devices=[
                    _Device(
                        "Utility",
                        [
                            _Parameter("Gain", 0.0, -35.0, 35.0),
                            _Parameter("Mute", 0.0, 0.0, 1.0, is_quantized=True),
                        ],
                    ),
                    _Device(
                        "Analog",
                        [
                            _Parameter("Device On", 1.0, 0.0, 1.0, is_quantized=True),
                            _Parameter("Filter Freq", 5000.0, 20.0, 20000.0),
                        ],
                    ),
                ],
            ),
            _Track(
                "Audio Track",
                midi=False,
                audio=True,
                devices=[
                    _Device(
                        "EQ Eight",
                        [
                            _Parameter("Device On", 1.0, 0.0, 1.0, is_quantized=True),
                            _Parameter("Gain A", 0.0, -15.0, 15.0),
                        ],
                    )
                ],
            ),
        ]
    )


@pytest.fixture
def control_surface(song: _Song) -> _FakeControlSurface:
    return _FakeControlSurface(song)


@pytest.fixture
def device_handler(control_surface: _FakeControlSurface) -> DeviceHandler:
    return DeviceHandler(control_surface)


@pytest.fixture
def browser_handler(control_surface: _FakeControlSurface) -> BrowserHandler:
    return BrowserHandler(control_surface)


class TestGetParameters:
    def test_parameter_serialization_shape(self, device_handler: DeviceHandler) -> None:
        result = device_handler.handle_get_parameters(
            {"track_index": 1, "device_index": 2}
        )

        assert result["track_index"] == 1
        assert result["device_index"] == 2
        assert result["device_name"] == "Analog"
        assert result["parameters"] == [
            {
                "parameter_index": 1,
                "name": "Device On",
                "value": 1.0,
                "min": 0.0,
                "max": 1.0,
                "is_quantized": True,
            },
            {
                "parameter_index": 2,
                "name": "Filter Freq",
                "value": 5000.0,
                "min": 20.0,
                "max": 20000.0,
                "is_quantized": False,
            },
        ]

    def test_uses_one_based_device_addressing(
        self,
        device_handler: DeviceHandler,
    ) -> None:
        result = device_handler.handle_get_parameters(
            {"track_index": 1, "device_index": 1}
        )

        assert result["device_name"] == "Utility"
        assert result["parameters"][1]["name"] == "Mute"


class TestSetParameter:
    def test_parameter_set_success(
        self,
        device_handler: DeviceHandler,
        song: _Song,
    ) -> None:
        result = device_handler.handle_set_parameter(
            {
                "track_index": 1,
                "device_index": 2,
                "parameter_index": 2,
                "value": 1200.0,
            }
        )

        assert result == {
            "track_index": 1,
            "device_index": 2,
            "parameter_index": 2,
            "value": 1200.0,
        }
        assert song.tracks[0].devices[1].parameters[1].value == 1200.0

    def test_uses_one_based_parameter_addressing(
        self,
        device_handler: DeviceHandler,
        song: _Song,
    ) -> None:
        device_handler.handle_set_parameter(
            {
                "track_index": 1,
                "device_index": 1,
                "parameter_index": 2,
                "value": 1.0,
            }
        )

        assert song.tracks[0].devices[0].parameters[1].value == 1.0
        assert song.tracks[0].devices[0].parameters[0].value == 0.0

    def test_out_of_range_value_rejected(self, device_handler: DeviceHandler) -> None:
        with pytest.raises(InvalidParamsError, match="between 20.0 and 20000.0"):
            device_handler.handle_set_parameter(
                {
                    "track_index": 1,
                    "device_index": 2,
                    "parameter_index": 2,
                    "value": 25000.0,
                }
            )

    def test_missing_device_raises_not_found(
        self,
        device_handler: DeviceHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Device 9"):
            device_handler.handle_set_parameter(
                {
                    "track_index": 1,
                    "device_index": 9,
                    "parameter_index": 1,
                    "value": 0.0,
                }
            )

    def test_missing_parameter_raises_not_found(
        self,
        device_handler: DeviceHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Parameter 9"):
            device_handler.handle_set_parameter(
                {
                    "track_index": 1,
                    "device_index": 1,
                    "parameter_index": 9,
                    "value": 0.0,
                }
            )


class TestLoadInstrument:
    def test_load_instrument_success_on_midi_track(
        self,
        browser_handler: BrowserHandler,
        song: _Song,
    ) -> None:
        before_count = len(song.tracks[0].devices)

        result = browser_handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "browser:instruments/synths/analog",
            }
        )

        assert result == {
            "track_index": 1,
            "device_index": before_count + 1,
            "name": "Analog",
            "uri": "browser:instruments/synths/analog",
        }
        assert song.view.selected_track is song.tracks[0]
        assert song.tracks[0].devices[-1].name == "Analog"

    def test_load_instrument_rejects_audio_track(
        self,
        browser_handler: BrowserHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="must be a MIDI track"):
            browser_handler.handle_load_instrument(
                {
                    "track_index": 2,
                    "uri": "browser:instruments/synths/analog",
                }
            )

    def test_load_instrument_uri_not_found(
        self,
        browser_handler: BrowserHandler,
    ) -> None:
        with pytest.raises(NotFoundError, match="Browser item not found"):
            browser_handler.handle_load_instrument(
                {
                    "track_index": 1,
                    "uri": "browser:instruments/synths/missing",
                }
            )

    def test_load_instrument_non_loadable_uri_rejected(
        self,
        browser_handler: BrowserHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="not loadable"):
            browser_handler.handle_load_instrument(
                {
                    "track_index": 1,
                    "uri": "browser:instruments/synths/broken",
                }
            )


class TestLoadEffect:
    def test_load_effect_position_minus_one_success(
        self,
        browser_handler: BrowserHandler,
        song: _Song,
    ) -> None:
        before_count = len(song.tracks[1].devices)

        result = browser_handler.handle_load_effect(
            {
                "track_index": 2,
                "uri": "browser:audio_effects/filters/auto-filter",
                "position": -1,
            }
        )

        assert result == {
            "track_index": 2,
            "device_index": before_count + 1,
            "name": "Auto Filter",
            "uri": "browser:audio_effects/filters/auto-filter",
        }
        assert song.tracks[1].devices[-1].name == "Auto Filter"

    def test_load_effect_handles_rewrapped_existing_devices(
        self,
        browser_handler: BrowserHandler,
        song: _Song,
    ) -> None:
        browser = browser_handler._browser()

        def _reload_wrapped_devices(item: _BrowserItem) -> None:
            selected_track = song.view.selected_track
            assert selected_track is not None
            rebuilt_devices = [
                _Device(
                    existing_device.name,
                    [
                        _Parameter(
                            parameter.name,
                            parameter.value,
                            parameter.min,
                            parameter.max,
                            is_quantized=parameter.is_quantized,
                        )
                        for parameter in existing_device.parameters
                    ],
                )
                for existing_device in selected_track.devices
            ]
            if item.device_factory is not None:
                rebuilt_devices.append(item.device_factory())
            selected_track.devices = rebuilt_devices

        browser.load_item = _reload_wrapped_devices

        result = browser_handler.handle_load_effect(
            {
                "track_index": 2,
                "uri": "browser:audio_effects/filters/auto-filter",
                "position": -1,
            }
        )

        assert result["device_index"] == 2
        assert result["name"] == "Auto Filter"

    def test_load_effect_uri_not_found(self, browser_handler: BrowserHandler) -> None:
        with pytest.raises(NotFoundError, match="Browser item not found"):
            browser_handler.handle_load_effect(
                {
                    "track_index": 1,
                    "uri": "browser:audio_effects/filters/missing",
                    "position": -1,
                }
            )

    def test_load_effect_non_loadable_uri_rejected(
        self,
        browser_handler: BrowserHandler,
    ) -> None:
        with pytest.raises(InvalidParamsError, match="not loadable"):
            browser_handler.handle_load_effect(
                {
                    "track_index": 1,
                    "uri": "browser:audio_effects/filters/broken",
                    "position": -1,
                }
            )


class TestDispatcherIntegration:
    def test_missing_device_maps_to_not_found(
        self,
        control_surface: _FakeControlSurface,
    ) -> None:
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("device", DeviceHandler(control_surface))

        response = dispatcher.dispatch(
            "device.get_parameters",
            {"track_index": 1, "device_index": 9},
            "device-1",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "Device 9" in response["error"]["message"]

    def test_missing_parameter_maps_to_not_found(
        self,
        control_surface: _FakeControlSurface,
    ) -> None:
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("device", DeviceHandler(control_surface))

        response = dispatcher.dispatch(
            "device.set_parameter",
            {
                "track_index": 1,
                "device_index": 1,
                "parameter_index": 99,
                "value": 0.0,
            },
            "device-2",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "NOT_FOUND"
        assert "Parameter 99" in response["error"]["message"]

    def test_load_effect_position_zero_maps_to_invalid_params(
        self,
        control_surface: _FakeControlSurface,
    ) -> None:
        dispatcher = Dispatcher(control_surface)
        dispatcher.register("browser", BrowserHandler(control_surface))

        response = dispatcher.dispatch(
            "browser.load_effect",
            {
                "track_index": 1,
                "uri": "browser:audio_effects/filters/auto-filter",
                "position": 0,
            },
            "browser-1",
        )

        assert response["status"] == "error"
        assert response["error"]["code"] == "INVALID_PARAMS"
        assert "unsupported on the Live 12.2.5 runtime" in response["error"]["message"]
