# View Classes Reference

View classes provide access to UI state and navigation within Live.

## Table of Contents
- [Application Class](#application-class)
- [Application.View Class](#applicationview-class)
- [Song.View Class](#songview-class)
- [Track.View Class](#trackview-class)
- [Clip.View Class](#clipview-class)
- [Device.View Class](#deviceview-class)
- [Common Patterns](#common-patterns)

---

## Application Class

Access via `self.application()` in a ControlSurface.

**Canonical Path:** `live_app`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `current_dialog_button_count` | int | R | No | Number of buttons in current message box |
| `current_dialog_message` | symbol | R | No | Text of current message box (empty if none) |
| `open_dialog_count` | int | R | Yes | Number of dialog boxes shown |
| `average_process_usage` | float | R | Yes | Average CPU load |
| `peak_process_usage` | float | R | Yes | Peak CPU load |

### Methods

#### `get_document()` → Song
Returns the current Live Set.
```python
song = app.get_document()
```

#### Version Methods
```python
app.get_major_version()     # e.g., 12
app.get_minor_version()     # e.g., 3
app.get_bugfix_version()    # e.g., 0
app.get_version_string()    # e.g., "12.3.0"
```

#### `press_current_dialog_button(index)`
Press a button in the current dialog box.
```python
if app.open_dialog_count > 0:
    app.press_current_dialog_button(0)  # Press first button
```

### Children

| Property | Type | Description |
|----------|------|-------------|
| `browser` | Browser | Access to Live's browser |
| `view` | Application.View | View aspects of application |

---

## Application.View Class

Access via `self.application().view`.

**Canonical Path:** `live_app view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `browse_mode` | bool | R | Yes | 1 if Hot-Swap Mode is active |
| `focused_document_view` | unicode | R | Yes | "Session" or "Arranger" |

### Methods

#### `available_main_views()` → list[symbol]
Returns valid view names.
```python
views = app.view.available_main_views()
# ['Browser', 'Arranger', 'Session', 'Detail', 'Detail/Clip', 'Detail/DeviceChain']
```

#### `show_view(view_name)`
Display a view.
```python
app.view.show_view("Session")
app.view.show_view("Arranger")
app.view.show_view("Browser")
app.view.show_view("Detail/Clip")
app.view.show_view("Detail/DeviceChain")
```

#### `hide_view(view_name)`
Hide a view. Empty string hides current main view.
```python
app.view.hide_view("Browser")
app.view.hide_view("")  # Hide current main view
```

#### `focus_view(view_name)`
Display view and bring focus to it.
```python
app.view.focus_view("Session")
```

#### `is_view_visible(view_name)` → bool
Check if view is displayed.
```python
if app.view.is_view_visible("Browser"):
    app.view.hide_view("Browser")
```

#### `toggle_browse()`
Display device chain and browser, activate Hot-Swap Mode.
```python
app.view.toggle_browse()
```

#### `scroll_view(direction, view_name, modifier_pressed)`
Scroll a view. Direction: 0=up, 1=down, 2=left, 3=right.
Works with: Arranger, Browser, Session, Detail/DeviceChain.
```python
app.view.scroll_view(1, "Session", False)  # Scroll down
app.view.scroll_view(3, "Arranger", False)  # Scroll right
```

#### `zoom_view(direction, view_name, modifier_pressed)`
Zoom a view. Direction: 0=up, 1=down, 2=left, 3=right.
Works with: Arranger, Session.
```python
app.view.zoom_view(0, "Arranger", False)  # Zoom in vertical
app.view.zoom_view(2, "Session", False)   # Zoom in horizontal
```

---

## Song.View Class

Access via `self.song().view` or `self._song.view`.

**Canonical Path:** `live_set view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `draw_mode` | bool | R/W | Yes | 0=breakpoint editing, 1=drawing mode (Cmd/Ctrl-B) |
| `follow_song` | bool | R/W | Yes | Follow playback position (Cmd/Ctrl-F) |
| `detail_clip` | Clip | R/W | Yes | Clip in Detail View |
| `highlighted_clip_slot` | ClipSlot | R/W | No | Highlighted slot in Session View |
| `selected_chain` | Chain | R/W | Yes | Selected chain (or id 0) |
| `selected_parameter` | DeviceParameter | R | Yes | Selected parameter (or id 0) |
| `selected_scene` | Scene | R/W | Yes | Selected scene |
| `selected_track` | Track | R/W | Yes | Selected track |

### Methods

#### `select_device(device)`
Select a device in its track.
```python
device = track.devices[0]
song.view.select_device(device)
```

### Example: Navigate to Clip
```python
def show_clip_in_detail(song, track_idx, slot_idx):
    """Show a specific clip in Detail View."""
    track = song.tracks[track_idx]
    slot = track.clip_slots[slot_idx]

    if slot.has_clip:
        song.view.detail_clip = slot.clip
        # Optionally show the clip view
        app = self.application()
        app.view.show_view("Detail/Clip")
```

### Example: Select Track and Scene
```python
def select_cell(song, track_idx, scene_idx):
    """Select a specific cell in Session View."""
    song.view.selected_track = song.tracks[track_idx]
    song.view.selected_scene = song.scenes[scene_idx]
    song.view.highlighted_clip_slot = song.tracks[track_idx].clip_slots[scene_idx]
```

---

## Track.View Class

Access via `track.view`.

**Canonical Path:** `live_set tracks N view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `selected_device` | Device | R | Yes | Selected device (first if multi-selection) |
| `device_insert_mode` | int | R/W | Yes | 0=end, 1=left of selected, 2=right of selected |
| `is_collapsed` | bool | R/W | Yes | Arrangement View: 1=collapsed, 0=opened |

### Methods

#### `select_instrument()` → bool
Select track's instrument or first device, make visible and focus.
Returns 0 if no devices.
```python
if track.view.select_instrument():
    self.log_message("Instrument selected")
else:
    self.log_message("No instrument on track")
```

---

## Clip.View Class

Access via `clip.view`.

**Canonical Path:** `live_set tracks N clip_slots M clip view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `grid_quantization` | int | R/W | No | Grid quantization setting |
| `grid_is_triplet` | bool | R/W | No | Display with triplet grid |

### Methods

#### `show_envelope()`
Show the Envelopes box in clip view.

#### `hide_envelope()`
Hide the Envelopes box.

#### `select_envelope_parameter(device_parameter)`
Select parameter in the Envelopes box.
```python
clip.view.select_envelope_parameter(device.parameters[0])
```

#### `show_loop()`
Make current loop visible in Detail View.
```python
if clip == song.view.detail_clip:
    clip.view.show_loop()
```

---

## Device.View Class

Access via `device.view`.

**Canonical Path:** `live_set tracks N devices M view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `is_collapsed` | bool | R/W | Yes | 1=device collapsed in chain |

```python
device.view.is_collapsed = True   # Collapse
device.view.is_collapsed = False  # Expand
```

---

## RackDevice.View Class

Access via `rack_device.view`.

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `is_showing_chains` | bool | R/W | Yes | Chains visible in Session View |

---

## Eq8Device.View Class

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `selected_band` | int | R/W | Yes | Currently selected EQ band |

---

## SimplerDevice.View Class

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `selected_slice` | int | R/W | Yes | Currently selected slice |

---

## Common Patterns

### Toggle Session/Arrangement View
```python
def toggle_main_view(app):
    """Switch between Session and Arrangement views."""
    if app.view.focused_document_view == "Session":
        app.view.focus_view("Arranger")
    else:
        app.view.focus_view("Session")
```

### Show Device and Parameter
```python
def show_device_parameter(song, app, device, param_index):
    """Navigate to a specific device parameter."""
    # Select the device
    song.view.select_device(device)

    # Show device chain
    app.view.show_view("Detail/DeviceChain")

    # Expand device if collapsed
    device.view.is_collapsed = False
```

### Follow Selection
```python
def get_current_selection(song):
    """Get the current selection state."""
    return {
        "track": song.view.selected_track.name if song.view.selected_track else None,
        "scene": song.view.selected_scene.name if song.view.selected_scene else None,
        "device": song.view.selected_track.view.selected_device.name if song.view.selected_track and song.view.selected_track.view.selected_device else None,
        "clip": song.view.detail_clip.name if song.view.detail_clip else None
    }
```

### Session View Grid Navigation
```python
class SessionNavigator:
    """Navigate Session View grid."""

    def __init__(self, song, app):
        self.song = song
        self.app = app
        self.track_offset = 0
        self.scene_offset = 0

    def move_right(self):
        max_track = len(self.song.tracks) - 1
        if self.track_offset < max_track:
            self.track_offset += 1
            self._update_selection()

    def move_left(self):
        if self.track_offset > 0:
            self.track_offset -= 1
            self._update_selection()

    def move_down(self):
        max_scene = len(self.song.scenes) - 1
        if self.scene_offset < max_scene:
            self.scene_offset += 1
            self._update_selection()

    def move_up(self):
        if self.scene_offset > 0:
            self.scene_offset -= 1
            self._update_selection()

    def _update_selection(self):
        self.song.view.selected_track = self.song.tracks[self.track_offset]
        self.song.view.selected_scene = self.song.scenes[self.scene_offset]

    def launch_selected(self):
        track = self.song.tracks[self.track_offset]
        slot = track.clip_slots[self.scene_offset]
        slot.fire()
```

### View State Snapshot
```python
def save_view_state(song, app):
    """Save current view state for later restoration."""
    return {
        "focused_view": app.view.focused_document_view,
        "selected_track_idx": list(song.tracks).index(song.view.selected_track) if song.view.selected_track in song.tracks else None,
        "selected_scene_idx": list(song.scenes).index(song.view.selected_scene) if song.view.selected_scene else None,
        "detail_clip": song.view.detail_clip,
        "follow_song": song.view.follow_song,
        "draw_mode": song.view.draw_mode
    }

def restore_view_state(song, app, state):
    """Restore a previously saved view state."""
    if state["selected_track_idx"] is not None:
        song.view.selected_track = song.tracks[state["selected_track_idx"]]
    if state["selected_scene_idx"] is not None:
        song.view.selected_scene = song.scenes[state["selected_scene_idx"]]
    if state["detail_clip"]:
        song.view.detail_clip = state["detail_clip"]
    song.view.follow_song = state["follow_song"]
    song.view.draw_mode = state["draw_mode"]
    app.view.focus_view(state["focused_view"])
```
