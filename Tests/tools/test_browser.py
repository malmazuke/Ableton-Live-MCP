"""Tests for Browser MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from unittest.mock import AsyncMock, MagicMock

from mcp_ableton._app import mcp
from mcp_ableton.protocol import CommandError, CommandResponse, ErrorDetail
from mcp_ableton.tools.browser import (
    BrowserItemsResult,
    BrowserSearchResult,
    BrowserTree,
    get_browser_items,
    get_browser_tree,
    search_browser,
)

TOOL_NAMES = [
    "get_browser_tree",
    "get_browser_items",
    "search_browser",
]

BROWSER_TREE_RESULT = {
    "categories": [
        {
            "name": "Instruments",
            "uri": "browser:instruments",
            "is_folder": True,
            "is_loadable": False,
            "children": [
                {
                    "name": "Synths",
                    "uri": "browser:instruments/synths",
                    "is_folder": True,
                    "is_loadable": False,
                    "children": [
                        {
                            "name": "Analog",
                            "uri": "browser:instruments/synths/analog",
                            "is_folder": False,
                            "is_loadable": True,
                            "children": [],
                        }
                    ],
                }
            ],
        }
    ]
}

BROWSER_ITEMS_RESULT = {
    "path": "instruments/Synths",
    "items": [
        {
            "name": "Analog",
            "uri": "browser:instruments/synths/analog",
            "is_loadable": True,
        },
        {
            "name": "Operator",
            "uri": "browser:instruments/synths/operator",
            "is_loadable": True,
        },
    ],
}

BROWSER_SEARCH_RESULT = {
    "query": "Analog",
    "category": "instruments",
    "items": [
        {
            "name": "Analog",
            "path": "instruments/Synths/Analog",
            "uri": "browser:instruments/synths/analog",
            "is_loadable": True,
        }
    ],
}


def _ok_response(result: dict, request_id: str = "test") -> CommandResponse:
    return CommandResponse(status="ok", result=result, id=request_id)


def _error_response(
    code: str = "INTERNAL_ERROR",
    message: str = "something broke",
    request_id: str = "test",
) -> CommandResponse:
    return CommandResponse(
        status="error",
        id=request_id,
        error=ErrorDetail(code=code, message=message),
    )


class TestToolContracts:
    def _get_tool(self, name: str):
        tools = mcp._tool_manager._tools
        assert name in tools, f"Tool '{name}' not registered"
        return tools[name]

    @pytest.mark.parametrize("name", TOOL_NAMES)
    def test_tool_is_registered(self, name: str) -> None:
        self._get_tool(name)

    @pytest.mark.parametrize("name", TOOL_NAMES)
    def test_tool_has_description(self, name: str) -> None:
        tool = self._get_tool(name)
        assert tool.description, f"Tool '{name}' is missing a description"

    def test_get_browser_tree_schema(self) -> None:
        tool = self._get_tool("get_browser_tree")
        props = tool.parameters["properties"]
        assert props["category"]["default"] == "all"
        assert props["category"]["enum"] == [
            "all",
            "instruments",
            "sounds",
            "drums",
            "audio_effects",
            "midi_effects",
        ]

    def test_get_browser_items_schema(self) -> None:
        tool = self._get_tool("get_browser_items")
        props = tool.parameters["properties"]
        assert props["path"]["minLength"] == 1

    def test_search_browser_schema(self) -> None:
        tool = self._get_tool("search_browser")
        props = tool.parameters["properties"]
        assert props["query"]["minLength"] == 1
        assert props["category"]["default"] == "all"


class TestInputValidation:
    def _arg_model(self, tool_name: str):
        return mcp._tool_manager._tools[tool_name].fn_metadata.arg_model

    def test_get_browser_tree_rejects_unknown_category(self) -> None:
        model = self._arg_model("get_browser_tree")
        with pytest.raises(ValidationError):
            model(category="plugins")

    def test_get_browser_items_rejects_empty_path(self) -> None:
        model = self._arg_model("get_browser_items")
        with pytest.raises(ValidationError):
            model(path="")

    def test_search_browser_rejects_empty_query(self) -> None:
        model = self._arg_model("search_browser")
        with pytest.raises(ValidationError):
            model(query="")


class TestGetBrowserTree:
    async def test_returns_tree(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(BROWSER_TREE_RESULT)

        result = await get_browser_tree(ctx=mock_context)

        assert isinstance(result, BrowserTree)
        assert result.categories[0].name == "Instruments"
        assert result.categories[0].children[0].children[0].name == "Analog"

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(BROWSER_TREE_RESULT)

        await get_browser_tree(ctx=mock_context, category="drums")

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "browser.get_tree"
        assert req.params == {"category": "drums"}


class TestGetBrowserItems:
    async def test_returns_items(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(BROWSER_ITEMS_RESULT)

        result = await get_browser_items(ctx=mock_context, path="instruments/Synths")

        assert isinstance(result, BrowserItemsResult)
        assert result.path == "instruments/Synths"
        assert result.items[0].name == "Analog"
        assert result.items[1].is_loadable is True

    async def test_raises_on_not_found(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _error_response(
            code="NOT_FOUND",
            message="Browser path not found: instruments/Missing",
        )

        with pytest.raises(CommandError, match="NOT_FOUND"):
            await get_browser_items(ctx=mock_context, path="instruments/Missing")


class TestSearchBrowser:
    async def test_returns_results(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(BROWSER_SEARCH_RESULT)

        result = await search_browser(
            ctx=mock_context,
            query="Analog",
            category="instruments",
        )

        assert isinstance(result, BrowserSearchResult)
        assert result.query == "Analog"
        assert result.category == "instruments"
        assert result.items[0].path == "instruments/Synths/Analog"

    async def test_sends_correct_command(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(BROWSER_SEARCH_RESULT)

        await search_browser(
            ctx=mock_context,
            query="Analog",
            category="instruments",
        )

        req = mock_connection.send_command.call_args[0][0]
        assert req.command == "browser.search"
        assert req.params == {"query": "Analog", "category": "instruments"}

    async def test_empty_results_are_allowed(
        self,
        mock_context: MagicMock,
        mock_connection: AsyncMock,
    ) -> None:
        mock_connection.send_command.return_value = _ok_response(
            {"query": "zzz", "category": "all", "items": []},
        )

        result = await search_browser(ctx=mock_context, query="zzz")

        assert result.items == []
