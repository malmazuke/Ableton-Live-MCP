# Browser Reference

The Browser provides access to Live's content library for loading instruments, effects, samples, and presets.

## Table of Contents
- [Accessing the Browser](#accessing-the-browser)
- [Browser Categories](#browser-categories)
- [BrowserItem Class](#browseritem-class)
- [Loading Content](#loading-content)
- [Common Patterns](#common-patterns)

---

## Accessing the Browser

Access via `self.application().browser`.

```python
app = self.application()
browser = app.browser
```

---

## Browser Categories

The browser exposes content through category properties:

| Property | Type | Description |
|----------|------|-------------|
| `instruments` | BrowserItem | All instruments (Ableton, plugins, racks) |
| `sounds` | BrowserItem | Sound presets (organized by category) |
| `drums` | BrowserItem | Drum kits and one-shots |
| `audio_effects` | BrowserItem | Audio effect devices and racks |
| `midi_effects` | BrowserItem | MIDI effect devices and racks |
| `max_for_live` | BrowserItem | Max for Live devices |
| `plugins` | BrowserItem | VST/AU plugins |
| `clips` | BrowserItem | Audio and MIDI clips |
| `samples` | BrowserItem | Audio samples |
| `packs` | BrowserItem | Installed Packs content |
| `user_library` | BrowserItem | User library content |
| `current_project` | BrowserItem | Current project's content |
| `user_folders` | list[BrowserItem] | User-defined folders |

### Example: Access Categories
```python
browser = app.browser

# Get instruments category
instruments = browser.instruments
print(f"Instruments folder: {instruments.name}")

# List top-level items in sounds
for item in browser.sounds.children:
    print(f"Sound category: {item.name}")
```

---

## BrowserItem Class

Represents an item in the browser hierarchy (folder, device, preset, sample, etc.).

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R | No | Display name |
| `uri` | symbol | R | No | Unique identifier URI |
| `is_folder` | bool | R | No | Contains children |
| `is_device` | bool | R | No | Is a device (instrument/effect) |
| `is_loadable` | bool | R | No | Can be loaded into Live |
| `children` | list[BrowserItem] | R | No | Child items (if folder) |
| `source` | symbol | R | No | Source location |

### Example: Navigate Browser Hierarchy
```python
def list_browser_item(item, depth=0):
    """Recursively list browser items."""
    indent = "  " * depth
    print(f"{indent}{item.name} (loadable: {item.is_loadable})")

    if hasattr(item, 'children') and item.children:
        for child in item.children:
            list_browser_item(child, depth + 1)

# List instruments
list_browser_item(browser.instruments)
```

---

## Loading Content

### `browser.load_item(browser_item)`
Load a browser item onto the selected track.

```python
def load_instrument(self, track_index, item_uri):
    """Load an instrument by URI."""
    track = self._song.tracks[track_index]

    # Select the track first
    self._song.view.selected_track = track

    # Find the item
    item = self.find_browser_item_by_uri(browser, item_uri)

    if item and item.is_loadable:
        browser.load_item(item)
        return True
    return False
```

### Hot-Swap Mode

```python
def enter_hotswap(app, device):
    """Enter Hot-Swap mode for a device."""
    # Select the device
    song.view.select_device(device)

    # Toggle browse mode
    app.view.toggle_browse()

    # Now user can browse and swap the device
```

---

## Common Patterns

### Find Item by URI
```python
def find_browser_item_by_uri(browser_or_item, uri, max_depth=10, current_depth=0):
    """Recursively find a browser item by its URI."""
    # Check if this is the item
    if hasattr(browser_or_item, 'uri') and browser_or_item.uri == uri:
        return browser_or_item

    # Stop at max depth
    if current_depth >= max_depth:
        return None

    # Check root categories if this is the browser
    if hasattr(browser_or_item, 'instruments'):
        categories = [
            browser_or_item.instruments,
            browser_or_item.sounds,
            browser_or_item.drums,
            browser_or_item.audio_effects,
            browser_or_item.midi_effects
        ]
        for category in categories:
            result = find_browser_item_by_uri(category, uri, max_depth, current_depth + 1)
            if result:
                return result

    # Check children
    if hasattr(browser_or_item, 'children') and browser_or_item.children:
        for child in browser_or_item.children:
            result = find_browser_item_by_uri(child, uri, max_depth, current_depth + 1)
            if result:
                return result

    return None
```

### Find Item by Path
```python
def find_browser_item_by_path(browser, path):
    """Navigate to item using path like 'instruments/Analog/Bass'."""
    parts = path.split("/")

    # Determine root category
    root_name = parts[0].lower()
    if root_name == "instruments":
        current = browser.instruments
    elif root_name == "sounds":
        current = browser.sounds
    elif root_name == "drums":
        current = browser.drums
    elif root_name == "audio_effects":
        current = browser.audio_effects
    elif root_name == "midi_effects":
        current = browser.midi_effects
    else:
        return None

    # Navigate through path
    for part in parts[1:]:
        if not part:
            continue
        found = False
        for child in current.children:
            if child.name.lower() == part.lower():
                current = child
                found = True
                break
        if not found:
            return None

    return current
```

### List Available Devices
```python
def list_loadable_devices(category, device_list=None, prefix=""):
    """Get all loadable devices in a category."""
    if device_list is None:
        device_list = []

    if category.is_loadable:
        device_list.append({
            "name": category.name,
            "path": prefix + category.name,
            "uri": category.uri,
            "is_device": category.is_device
        })

    if hasattr(category, 'children') and category.children:
        for child in category.children:
            new_prefix = prefix + category.name + "/" if prefix else category.name + "/"
            list_loadable_devices(child, device_list, new_prefix)

    return device_list

# Usage
devices = list_loadable_devices(browser.instruments)
for d in devices[:10]:  # First 10
    print(f"{d['path']}: {d['uri']}")
```

### Get Browser Tree Structure
```python
def get_browser_tree(browser, category_type="all", max_depth=2):
    """Get a simplified browser tree."""
    def process_item(item, depth=0):
        if depth > max_depth:
            return None

        result = {
            "name": item.name,
            "uri": item.uri if hasattr(item, 'uri') else None,
            "is_folder": hasattr(item, 'children') and bool(item.children),
            "is_loadable": item.is_loadable if hasattr(item, 'is_loadable') else False,
            "children": []
        }

        if depth < max_depth and hasattr(item, 'children') and item.children:
            for child in item.children:
                child_result = process_item(child, depth + 1)
                if child_result:
                    result["children"].append(child_result)

        return result

    tree = {"categories": []}

    categories = []
    if category_type == "all" or category_type == "instruments":
        categories.append(("Instruments", browser.instruments))
    if category_type == "all" or category_type == "sounds":
        categories.append(("Sounds", browser.sounds))
    if category_type == "all" or category_type == "drums":
        categories.append(("Drums", browser.drums))
    if category_type == "all" or category_type == "audio_effects":
        categories.append(("Audio Effects", browser.audio_effects))
    if category_type == "all" or category_type == "midi_effects":
        categories.append(("MIDI Effects", browser.midi_effects))

    for name, category in categories:
        cat_tree = process_item(category)
        cat_tree["name"] = name
        tree["categories"].append(cat_tree)

    return tree
```

### Load Device onto Track
```python
def load_device_by_path(self, track_index, path):
    """Load a device using a path string."""
    browser = self.application().browser
    item = find_browser_item_by_path(browser, path)

    if not item:
        raise ValueError(f"Device not found: {path}")

    if not item.is_loadable:
        raise ValueError(f"Item not loadable: {path}")

    # Select target track
    track = self._song.tracks[track_index]
    self._song.view.selected_track = track

    # Load the device
    browser.load_item(item)

    return {
        "loaded": True,
        "name": item.name,
        "track": track.name
    }
```

### Search Browser Content
```python
def search_browser(browser, query, category=None, max_results=50):
    """Search for items matching a query string."""
    results = []
    query_lower = query.lower()

    def search_item(item, path=""):
        if len(results) >= max_results:
            return

        current_path = path + "/" + item.name if path else item.name

        # Check if name matches
        if query_lower in item.name.lower():
            if item.is_loadable:
                results.append({
                    "name": item.name,
                    "path": current_path,
                    "uri": item.uri,
                    "is_device": item.is_device
                })

        # Search children
        if hasattr(item, 'children') and item.children:
            for child in item.children:
                search_item(child, current_path)

    # Search in specified category or all
    if category:
        categories = [getattr(browser, category)]
    else:
        categories = [
            browser.instruments,
            browser.sounds,
            browser.drums,
            browser.audio_effects,
            browser.midi_effects
        ]

    for cat in categories:
        search_item(cat)

    return results

# Usage
results = search_browser(browser, "compressor")
for r in results:
    print(f"{r['path']}")
```

### Cache Browser URIs
```python
class BrowserCache:
    """Cache browser URIs for faster lookups."""

    def __init__(self, browser):
        self.browser = browser
        self.uri_cache = {}
        self.path_cache = {}

    def build_cache(self, categories=None, max_depth=5):
        """Build cache of all loadable items."""
        if categories is None:
            categories = ['instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects']

        for cat_name in categories:
            category = getattr(self.browser, cat_name, None)
            if category:
                self._cache_item(category, cat_name, 0, max_depth)

    def _cache_item(self, item, path, depth, max_depth):
        if depth > max_depth:
            return

        if hasattr(item, 'uri') and item.uri:
            self.uri_cache[item.uri] = item
            self.path_cache[path] = item

        if hasattr(item, 'children') and item.children:
            for child in item.children:
                child_path = f"{path}/{child.name}"
                self._cache_item(child, child_path, depth + 1, max_depth)

    def get_by_uri(self, uri):
        return self.uri_cache.get(uri)

    def get_by_path(self, path):
        return self.path_cache.get(path)
```
