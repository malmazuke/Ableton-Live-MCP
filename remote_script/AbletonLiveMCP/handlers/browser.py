"""Browser command handlers for Ableton Live's content Browser."""

from __future__ import annotations

from typing import Any

from ..dispatcher import InvalidParamsError, NotFoundError
from .base import BaseHandler

BROWSER_TREE_DEPTH = 2
SUPPORTED_BROWSER_CATEGORIES = (
    "instruments",
    "sounds",
    "drums",
    "audio_effects",
    "midi_effects",
)


class BrowserHandler(BaseHandler):
    """Handle Browser navigation and search commands."""

    def _browser(self) -> Any:
        """Return Ableton's Browser object."""
        application = self._control_surface.application()
        browser = getattr(application, "browser", None)
        if browser is None:
            raise RuntimeError("Ableton Browser is not available")
        return browser

    def _normalize_category(
        self,
        raw_value: Any,
        *,
        allow_all: bool = False,
    ) -> str:
        """Validate and normalize a category name."""
        if raw_value is None:
            return "all" if allow_all else ""
        if not isinstance(raw_value, str):
            raise InvalidParamsError("'category' must be a string")

        category = raw_value.strip().lower()
        if not category:
            raise InvalidParamsError("'category' must not be empty")
        if category == "all":
            if allow_all:
                return category
            raise InvalidParamsError("'category' must not be 'all' in this context")
        if category not in SUPPORTED_BROWSER_CATEGORIES:
            supported = ", ".join(SUPPORTED_BROWSER_CATEGORIES)
            raise InvalidParamsError(
                f"'category' must be one of: all, {supported}"
                if allow_all
                else f"'category' must be one of: {supported}"
            )
        return category

    def _require_non_empty_string(self, raw_value: Any, name: str) -> str:
        """Validate a required non-empty string parameter."""
        if raw_value is None:
            raise InvalidParamsError(f"'{name}' parameter is required")
        if not isinstance(raw_value, str):
            raise InvalidParamsError(f"'{name}' must be a string")

        value = raw_value.strip()
        if not value:
            raise InvalidParamsError(f"'{name}' must not be empty")
        return value

    def _root_categories(
        self,
        browser: Any,
        category: str,
    ) -> list[tuple[str, Any]]:
        """Return the Browser root categories to inspect."""
        if category == "all":
            return [
                (category_name, self._root_item(browser, category_name))
                for category_name in SUPPORTED_BROWSER_CATEGORIES
            ]
        return [(category, self._root_item(browser, category))]

    def _root_item(self, browser: Any, category: str) -> Any:
        """Return one top-level Browser category object."""
        normalized_category = self._normalize_category(category)
        item = getattr(browser, normalized_category, None)
        if item is None:
            raise NotFoundError(
                f"Browser category '{normalized_category}' is not available"
            )
        return item

    def _children(self, item: Any) -> list[Any]:
        """Return a materialized child list for a Browser item."""
        raw_children = getattr(item, "children", [])
        if raw_children is None:
            return []
        return list(raw_children)

    def _serialize_tree_item(self, item: Any, depth: int) -> dict[str, Any]:
        """Serialize a Browser item for tree output."""
        children = self._children(item)
        payload = {
            "name": str(getattr(item, "name", "")),
            "uri": self._item_uri(item),
            "is_folder": bool(getattr(item, "is_folder", False) or children),
            "is_loadable": bool(getattr(item, "is_loadable", False)),
            "children": [],
        }

        if depth < BROWSER_TREE_DEPTH:
            payload["children"] = [
                self._serialize_tree_item(child, depth + 1) for child in children
            ]

        return payload

    def _serialize_browser_item(self, item: Any) -> dict[str, Any]:
        """Serialize a Browser item for flat list output."""
        return {
            "name": str(getattr(item, "name", "")),
            "uri": self._item_uri(item),
            "is_loadable": bool(getattr(item, "is_loadable", False)),
        }

    def _item_uri(self, item: Any) -> str | None:
        """Return a string URI when available."""
        uri = getattr(item, "uri", None)
        if uri is None:
            return None
        return str(uri)

    def _resolve_path(self, browser: Any, path: str) -> tuple[Any, str]:
        """Resolve a slash-separated Browser path."""
        parts = [part.strip() for part in path.split("/") if part.strip()]
        if not parts:
            raise InvalidParamsError("'path' must not be empty")

        root_name = parts[0].lower()
        current = self._root_item(browser, root_name)
        normalized_parts = [root_name]

        for raw_part in parts[1:]:
            match = next(
                (
                    child
                    for child in self._children(current)
                    if str(getattr(child, "name", "")).lower() == raw_part.lower()
                ),
                None,
            )
            if match is None:
                raise NotFoundError(f"Browser path not found: {path}")
            current = match
            normalized_parts.append(str(getattr(match, "name", "")))

        return current, "/".join(normalized_parts)

    def _search_item(
        self,
        item: Any,
        *,
        query: str,
        path: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Recursively collect Browser items whose names match the query."""
        name = str(getattr(item, "name", ""))
        if query in name.lower():
            results.append(
                {
                    "name": name,
                    "path": path,
                    "uri": self._item_uri(item),
                    "is_loadable": bool(getattr(item, "is_loadable", False)),
                }
            )

        for child in self._children(item):
            child_name = str(getattr(child, "name", ""))
            child_path = f"{path}/{child_name}"
            self._search_item(child, query=query, path=child_path, results=results)

    def handle_get_tree(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a fixed-depth Browser tree."""
        category = self._normalize_category(
            params.get("category", "all"),
            allow_all=True,
        )

        def _read() -> dict[str, Any]:
            browser = self._browser()
            categories = [
                self._serialize_tree_item(item, depth=0)
                for _slug, item in self._root_categories(browser, category)
            ]
            return {"categories": categories}

        return self._run_on_main_thread(_read)

    def handle_get_items(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the immediate children at a Browser path."""
        path = self._require_non_empty_string(params.get("path"), "path")

        def _read() -> dict[str, Any]:
            browser = self._browser()
            item, normalized_path = self._resolve_path(browser, path)
            return {
                "path": normalized_path,
                "items": [
                    self._serialize_browser_item(child)
                    for child in self._children(item)
                ],
            }

        return self._run_on_main_thread(_read)

    def handle_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search Browser items recursively by name."""
        query = self._require_non_empty_string(params.get("query"), "query")
        category = self._normalize_category(
            params.get("category", "all"),
            allow_all=True,
        )

        def _read() -> dict[str, Any]:
            browser = self._browser()
            results: list[dict[str, Any]] = []
            for root_name, root_item in self._root_categories(browser, category):
                self._search_item(
                    root_item,
                    query=query.lower(),
                    path=root_name,
                    results=results,
                )
            return {
                "query": query,
                "category": category,
                "items": results,
            }

        return self._run_on_main_thread(_read)


__all__ = ["BrowserHandler"]
