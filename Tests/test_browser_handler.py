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
        self.sounds = _BrowserItem("Sounds", uri="browser:sounds", children=[])
        self.drums = _BrowserItem("Drums", uri="browser:drums", children=[])
        self.audio_effects = _BrowserItem(
            "Audio Effects",
            uri="browser:audio-effects",
            children=[],
        )
        self.midi_effects = _BrowserItem(
            "MIDI Effects",
            uri="browser:midi-effects",
            children=[],
        )


class _Application:
    def __init__(self) -> None:
        self.browser = _Browser()


class _FakeControlSurface:
    def __init__(self) -> None:
        self._application = _Application()

    def application(self):
        return self._application

    def song(self):
        return None

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
