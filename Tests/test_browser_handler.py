"""Tests for the Remote Script BrowserHandler."""

from __future__ import annotations

import pytest
from AbletonLiveMCP.dispatcher import InvalidParamsError, NotFoundError
from AbletonLiveMCP.handlers.browser import BrowserHandler


class _BrowserItem:
    def __init__(
        self,
        name: str,
        *,
        uri: str | None = None,
        is_loadable: bool = False,
        children: list[_BrowserItem] | None = None,
    ) -> None:
        self.name = name
        self.uri = uri
        self.is_loadable = is_loadable
        self.children = children or []
        self.is_folder = bool(self.children)


class _FakeDevice:
    def __init__(self, name: str, class_name: str = "PluginDevice") -> None:
        self.name = name
        self.class_name = class_name


class _FakeTrack:
    def __init__(
        self,
        *,
        has_midi_input: bool = True,
        devices: list[_FakeDevice] | None = None,
    ) -> None:
        self.has_midi_input = has_midi_input
        self.devices = list(devices or [])


class _FakeView:
    def __init__(self) -> None:
        self.selected_track = None


class _FakeSong:
    def __init__(self, tracks: list[_FakeTrack] | None = None) -> None:
        self.tracks = list(tracks or [])
        self.view = _FakeView()


class _Browser:
    def __init__(self) -> None:
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
                        ),
                        _BrowserItem(
                            "Deep Folder",
                            uri="browser:instruments/synths/deep-folder",
                            children=[
                                _BrowserItem(
                                    "Hidden Child",
                                    uri=(
                                        "browser:instruments/synths/"
                                        "deep-folder/hidden-child"
                                    ),
                                    is_loadable=True,
                                )
                            ],
                        ),
                    ],
                ),
                _BrowserItem(
                    "Keys",
                    uri="browser:instruments/keys",
                    children=[],
                ),
            ],
        )
        self.sounds = _BrowserItem(
            "Sounds",
            uri="browser:sounds",
            children=[
                _BrowserItem(
                    "Analog Bass.adv",
                    uri="query:Sounds#FileId_999",
                    is_loadable=True,
                ),
            ],
        )
        self.drums = _BrowserItem(
            "Drums",
            uri="browser:drums",
            children=[
                _BrowserItem(
                    "Akustichord Kit.adg",
                    uri="query:Drums#FileId_13686",
                    is_loadable=True,
                ),
            ],
        )
        self.audio_effects = _BrowserItem(
            "Audio Effects",
            uri="browser:audio-effects",
            children=[
                _BrowserItem(
                    "Reverb.adv",
                    uri="query:AudioEffects#FileId_100",
                    is_loadable=True,
                ),
            ],
        )
        self.midi_effects = _BrowserItem(
            "MIDI Effects",
            uri="browser:midi-effects",
            children=[],
        )

        self._load_item_callback: object = None

    def load_item(self, item: _BrowserItem) -> None:
        if callable(self._load_item_callback):
            self._load_item_callback(item)


class _Application:
    def __init__(self) -> None:
        self.browser = _Browser()


class _FakeControlSurface:
    def __init__(
        self,
        song: _FakeSong | None = None,
    ) -> None:
        self._application = _Application()
        self._song = song or _FakeSong()

    def application(self):
        return self._application

    def song(self):
        return self._song

    def log_message(self, msg: str) -> None:
        pass

    def schedule_message(self, delay, callback) -> None:
        callback()


@pytest.fixture
def handler() -> BrowserHandler:
    return BrowserHandler(_FakeControlSurface())


class TestGetTree:
    def test_supported_category_lookup(self, handler: BrowserHandler) -> None:
        result = handler.handle_get_tree({"category": "instruments"})

        assert len(result["categories"]) == 1
        assert result["categories"][0]["name"] == "Instruments"

    def test_tree_depth_is_limited(self, handler: BrowserHandler) -> None:
        result = handler.handle_get_tree({"category": "instruments"})

        deep_folder = result["categories"][0]["children"][0]["children"][1]
        assert deep_folder["name"] == "Deep Folder"
        assert deep_folder["children"] == []

    def test_invalid_category_raises(self, handler: BrowserHandler) -> None:
        with pytest.raises(InvalidParamsError, match="category"):
            handler.handle_get_tree({"category": "plugins"})


class TestGetItems:
    def test_nested_path_traversal_is_case_insensitive(
        self,
        handler: BrowserHandler,
    ) -> None:
        result = handler.handle_get_items({"path": "Instruments/sYnThS"})

        assert result["path"] == "instruments/Synths"
        assert [item["name"] for item in result["items"]] == ["Analog", "Deep Folder"]

    def test_valid_leaf_returns_empty_items(self, handler: BrowserHandler) -> None:
        result = handler.handle_get_items({"path": "instruments/keys"})

        assert result == {"path": "instruments/Keys", "items": []}

    def test_invalid_path_raises_not_found(self, handler: BrowserHandler) -> None:
        with pytest.raises(NotFoundError, match="Browser path not found"):
            handler.handle_get_items({"path": "instruments/missing"})

    def test_blank_path_is_invalid(self, handler: BrowserHandler) -> None:
        with pytest.raises(InvalidParamsError, match="path"):
            handler.handle_get_items({"path": "   "})


class TestSearch:
    def test_search_matches_nested_items(self, handler: BrowserHandler) -> None:
        result = handler.handle_search({"query": "analog", "category": "instruments"})

        assert result["query"] == "analog"
        assert result["category"] == "instruments"
        assert result["items"] == [
            {
                "name": "Analog",
                "path": "instruments/Synths/Analog",
                "uri": "browser:instruments/synths/analog",
                "is_loadable": True,
            }
        ]

    def test_search_misses_return_empty_list(self, handler: BrowserHandler) -> None:
        result = handler.handle_search({"query": "zzz", "category": "all"})

        assert result["items"] == []

    def test_search_includes_nested_hidden_child(self, handler: BrowserHandler) -> None:
        result = handler.handle_search({"query": "hidden", "category": "instruments"})

        assert result["items"][0]["path"] == (
            "instruments/Synths/Deep Folder/Hidden Child"
        )

    def test_blank_query_is_invalid(self, handler: BrowserHandler) -> None:
        with pytest.raises(InvalidParamsError, match="query"):
            handler.handle_search({"query": "   "})


def _make_load_handler(
    *,
    track: _FakeTrack | None = None,
    load_adds_device: _FakeDevice | None = None,
    load_adds_device_after_ticks: int = 0,
) -> BrowserHandler:
    """Build a BrowserHandler wired for load_instrument / load_effect tests.

    When ``load_adds_device_after_ticks > 0``, the device won't appear in
    ``track.devices`` until that many retry ticks have elapsed, simulating
    the async nature of ``browser.load_item`` in Ableton.
    """
    t = track or _FakeTrack()
    song = _FakeSong(tracks=[t])
    cs = _FakeControlSurface(song=song)

    if load_adds_device is not None:
        if load_adds_device_after_ticks == 0:
            cs.application().browser._load_item_callback = lambda _item: (
                t.devices.append(load_adds_device)
            )
        else:
            ticks_elapsed = [0]

            def _schedule_with_delayed_device(delay, callback):
                if delay >= 1:
                    ticks_elapsed[0] += 1
                    if ticks_elapsed[0] >= load_adds_device_after_ticks:
                        t.devices.append(load_adds_device)
                callback()

            cs.schedule_message = _schedule_with_delayed_device

    return BrowserHandler(cs)


class TestLoadInstrument:
    def test_loads_from_instruments_category(self) -> None:
        device = _FakeDevice("Analog", "OriginalSimpler")
        handler = _make_load_handler(load_adds_device=device)

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "browser:instruments/synths/analog",
            }
        )

        assert result["name"] == "Analog"
        assert result["device_index"] == 1
        assert result["track_index"] == 1

    def test_loads_from_drums_category(self) -> None:
        device = _FakeDevice("Akustichord Kit", "DrumGroupDevice")
        handler = _make_load_handler(load_adds_device=device)

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "query:Drums#FileId_13686",
            }
        )

        assert result["name"] == "Akustichord Kit"

    def test_loads_from_sounds_category(self) -> None:
        device = _FakeDevice("Analog Bass", "OriginalSimpler")
        handler = _make_load_handler(load_adds_device=device)

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "query:Sounds#FileId_999",
            }
        )

        assert result["name"] == "Analog Bass"

    def test_rejects_audio_track(self) -> None:
        track = _FakeTrack(has_midi_input=False)
        handler = _make_load_handler(
            track=track,
            load_adds_device=_FakeDevice("X"),
        )

        with pytest.raises(InvalidParamsError, match="MIDI track"):
            handler.handle_load_instrument(
                {
                    "track_index": 1,
                    "uri": "browser:instruments/synths/analog",
                }
            )

    def test_unknown_uri_raises_not_found(self) -> None:
        handler = _make_load_handler(
            load_adds_device=_FakeDevice("X"),
        )

        with pytest.raises(NotFoundError, match="not found"):
            handler.handle_load_instrument(
                {
                    "track_index": 1,
                    "uri": "browser:nonexistent",
                }
            )

    def test_detects_device_after_async_delay(self) -> None:
        """Simulates browser.load_item being async — device appears after
        several main-thread ticks, not immediately."""
        device = _FakeDevice("Akustichord Kit", "DrumGroupDevice")
        handler = _make_load_handler(
            load_adds_device=device,
            load_adds_device_after_ticks=3,
        )

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "query:Drums#FileId_13686",
            }
        )

        assert result["name"] == "Akustichord Kit"

    def test_timeout_when_device_never_appears(self) -> None:
        handler = _make_load_handler()

        with pytest.raises(RuntimeError, match="timed out"):
            handler.handle_load_instrument(
                {
                    "track_index": 1,
                    "uri": "browser:instruments/synths/analog",
                }
            )


class TestLoadEffect:
    def test_loads_audio_effect(self) -> None:
        device = _FakeDevice("Reverb", "Reverb")
        handler = _make_load_handler(load_adds_device=device)

        result = handler.handle_load_effect(
            {
                "track_index": 1,
                "uri": "query:AudioEffects#FileId_100",
            }
        )

        assert result["name"] == "Reverb"
        assert result["device_index"] == 1

    def test_detects_effect_after_async_delay(self) -> None:
        device = _FakeDevice("Reverb", "Reverb")
        handler = _make_load_handler(
            load_adds_device=device,
            load_adds_device_after_ticks=5,
        )

        result = handler.handle_load_effect(
            {
                "track_index": 1,
                "uri": "query:AudioEffects#FileId_100",
            }
        )

        assert result["name"] == "Reverb"

    def test_rejects_invalid_position(self) -> None:
        handler = _make_load_handler(
            load_adds_device=_FakeDevice("X"),
        )

        with pytest.raises(InvalidParamsError, match="position"):
            handler.handle_load_effect(
                {
                    "track_index": 1,
                    "uri": "query:AudioEffects#FileId_100",
                    "position": 2,
                }
            )


class TestDeviceReplacement:
    """When loading onto a track that already has a device, Ableton
    replaces it — the device count stays the same but the signature
    changes."""

    def test_detects_replaced_instrument(self) -> None:
        existing_device = _FakeDevice("Old Synth", "OriginalSimpler")
        track = _FakeTrack(devices=[existing_device])
        new_device = _FakeDevice("Analog", "OriginalSimpler")

        def _replace(_item):
            track.devices[0] = new_device

        song = _FakeSong(tracks=[track])
        cs = _FakeControlSurface(song=song)
        cs.application().browser._load_item_callback = _replace
        handler = BrowserHandler(cs)

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "browser:instruments/synths/analog",
            }
        )

        assert result["name"] == "Analog"
        assert result["device_index"] == 1

    def test_detects_replaced_instrument_after_delay(self) -> None:
        existing_device = _FakeDevice("Old Synth", "OriginalSimpler")
        track = _FakeTrack(devices=[existing_device])
        new_device = _FakeDevice("Analog", "OriginalSimpler")

        song = _FakeSong(tracks=[track])
        cs = _FakeControlSurface(song=song)

        ticks_elapsed = [0]

        def _delayed_schedule(delay, callback):
            if delay >= 1:
                ticks_elapsed[0] += 1
                if ticks_elapsed[0] >= 2:
                    track.devices[0] = new_device
            callback()

        cs.schedule_message = _delayed_schedule
        handler = BrowserHandler(cs)

        result = handler.handle_load_instrument(
            {
                "track_index": 1,
                "uri": "browser:instruments/synths/analog",
            }
        )

        assert result["name"] == "Analog"
