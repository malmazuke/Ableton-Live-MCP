# Session View Reference

This document covers Scene and ClipSlot classes for Session View control.

## Table of Contents
- [Scene Class](#scene-class)
- [ClipSlot Class](#clipslot-class)
- [Common Patterns](#common-patterns)

---

## Scene Class

The Scene class represents a row in Session View (a series of clip slots across all tracks).

**Canonical Path:** `live_set scenes N`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Scene display name |
| `color` | int | R/W | Yes | RGB value (0x00rrggbb) |
| `color_index` | long | R/W | Yes | Scene's color index |
| `is_empty` | bool | R | No | 1 when no slots contain clips |
| `is_triggered` | bool | R | Yes | 1 when scene is blinking |
| `tempo` | float | R/W | Yes | Scene tempo (-1 if disabled) |
| `tempo_enabled` | bool | R/W | Yes | Use scene tempo vs song tempo |
| `time_signature_numerator` | int | R/W | Yes | Time sig numerator (-1 if disabled) |
| `time_signature_denominator` | int | R/W | Yes | Time sig denominator (-1 if disabled) |
| `time_signature_enabled` | bool | R/W | Yes | Use scene time sig vs song's |

### Children

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `clip_slots` | list[ClipSlot] | R | Yes | Clip slots in this scene |

### Methods

#### `fire(force_legato=False, can_select_scene_on_launch=True)`
Launch all clip slots in the scene.
```python
scene.fire()  # Normal launch
scene.fire(True)  # Force legato mode
scene.fire(False, False)  # Don't select scene after launch
```

#### `fire_as_selected(force_legato=False)`
Fire the scene and advance selection to next scene.
```python
scene.fire_as_selected()
```

#### `set_fire_button_state(state)`
Simulate holding the scene launch button.
```python
scene.set_fire_button_state(1)  # Press
# ... time passes
scene.set_fire_button_state(0)  # Release
```

### Example: Scene with Tempo Change
```python
scene = song.scenes[0]
scene.name = "Verse - 120 BPM"
scene.tempo_enabled = True
scene.tempo = 120.0
```

### Example: Scene with Time Signature
```python
scene = song.scenes[4]
scene.name = "Bridge - 6/8"
scene.time_signature_enabled = True
scene.time_signature_numerator = 6
scene.time_signature_denominator = 8
```

---

## ClipSlot Class

The ClipSlot class represents an entry in Session View's matrix (intersection of track and scene).

**Canonical Path:** `live_set tracks N clip_slots M`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `has_clip` | bool | R | Yes | 1 if clip exists in this slot |
| `clip` | Clip | R | No | The clip (if has_clip is true) |
| `has_stop_button` | bool | R/W | Yes | 1 if slot has stop button |
| `is_playing` | bool | R | No | 1 if playing_status != 0 |
| `is_recording` | bool | R | No | 1 if playing_status == 2 |
| `is_triggered` | bool | R | Yes | 1 if launch/stop button blinking |
| `playing_status` | int | R | Yes | 0=stopped/empty, 1=playing, 2=recording |
| `will_record_on_start` | bool | R | No | 1 if slot will record when started |
| `is_group_slot` | bool | R | No | 1 if this is a Group Track slot |
| `controls_other_clips` | bool | R | Yes | 1 if Group slot contains active clips |
| `color` | long | R | Yes | RGB of first clip in Group (Group slots) |
| `color_index` | long | R | Yes | Color index (Group slots) |

### Methods

#### `fire(record_length=None, launch_quantization=None)`
Launch the clip or trigger stop button. Optionally start recording.
```python
clip_slot.fire()  # Launch clip or stop button
clip_slot.fire(4.0)  # Record for 4 beats
clip_slot.fire(4.0, 4)  # Record 4 beats with 1/4 quantization
```

#### `stop()`
Stop playback or recording in this track (or nested group tracks).
```python
clip_slot.stop()
```

#### `set_fire_button_state(state)`
Simulate holding the clip launch button.
```python
clip_slot.set_fire_button_state(1)  # Press
# ... time passes
clip_slot.set_fire_button_state(0)  # Release
```

#### `create_clip(length)`
Create a MIDI clip of specified beat length in empty MIDI track slots.
```python
clip_slot.create_clip(4.0)  # 4-beat clip
```

#### `create_audio_clip(path)`
Create an audio clip from an absolute file path.
```python
clip_slot.create_audio_clip("/path/to/audio.wav")
```

#### `delete_clip()`
Remove the contained clip.
```python
if clip_slot.has_clip:
    clip_slot.delete_clip()
```

#### `duplicate_clip_to(target_clip_slot)`
Copy this slot's clip to another ClipSlot.
```python
source_slot = track.clip_slots[0]
target_slot = track.clip_slots[1]
source_slot.duplicate_clip_to(target_slot)
```

---

## Common Patterns

### Launch a Scene
```python
def launch_scene_by_name(song, name):
    """Find and launch a scene by name."""
    for scene in song.scenes:
        if scene.name == name:
            scene.fire()
            return True
    return False

launch_scene_by_name(song, "Chorus")
```

### Get All Playing Clips
```python
def get_playing_clips(song):
    """Return list of all currently playing clips."""
    playing = []
    for track in song.tracks:
        for slot in track.clip_slots:
            if slot.has_clip and slot.clip.is_playing:
                playing.append({
                    "track": track.name,
                    "clip": slot.clip.name,
                    "position": slot.clip.playing_position
                })
    return playing
```

### Create Clips Across a Scene
```python
def create_scene_clips(song, scene_index, length=4.0):
    """Create clips in all MIDI tracks for a scene."""
    scene = song.scenes[scene_index]
    for track in song.tracks:
        if track.has_midi_input:
            slot = track.clip_slots[scene_index]
            if not slot.has_clip:
                slot.create_clip(length)
```

### Stop All and Launch Scene
```python
def transition_to_scene(song, scene_index, quantized=True):
    """Stop all clips and launch a specific scene."""
    song.stop_all_clips(1 if quantized else 0)
    song.scenes[scene_index].fire()
```

### Monitor Clip Slot Changes
```python
def setup_clip_slot_listeners(self, track):
    """Add listeners to track clip slot changes."""
    for i, slot in enumerate(track.clip_slots):
        def on_has_clip_changed(index=i):
            slot = track.clip_slots[index]
            if slot.has_clip:
                self.log_message(f"Clip added to slot {index}")
            else:
                self.log_message(f"Clip removed from slot {index}")

        slot.add_has_clip_listener(on_has_clip_changed)
```

### Record into Empty Slot
```python
def record_into_first_empty_slot(track, length=4.0):
    """Find first empty slot and start recording."""
    for slot in track.clip_slots:
        if not slot.has_clip:
            slot.fire(length)  # Fire with record length
            return True
    return False
```

### Navigate Session View
```python
def get_session_grid(song, start_track=0, start_scene=0, width=8, height=8):
    """Get a grid of clip slot info for Session View display."""
    grid = []
    tracks = song.tracks[start_track:start_track + width]

    for scene_offset in range(height):
        scene_idx = start_scene + scene_offset
        if scene_idx >= len(song.scenes):
            break

        row = {
            "scene_index": scene_idx,
            "scene_name": song.scenes[scene_idx].name,
            "slots": []
        }

        for track in tracks:
            if scene_idx < len(track.clip_slots):
                slot = track.clip_slots[scene_idx]
                slot_info = {
                    "has_clip": slot.has_clip,
                    "is_playing": slot.is_playing,
                    "is_triggered": slot.is_triggered,
                    "is_recording": slot.is_recording
                }
                if slot.has_clip:
                    slot_info["clip_name"] = slot.clip.name
                    slot_info["clip_color"] = slot.clip.color
                row["slots"].append(slot_info)

        grid.append(row)

    return grid
```

### Scene Launch Queue
```python
class SceneLauncher:
    """Queue scenes to launch in sequence."""

    def __init__(self, song):
        self.song = song
        self.queue = []
        self.current_index = 0

    def add_to_queue(self, scene_index):
        self.queue.append(scene_index)

    def launch_next(self):
        if self.current_index < len(self.queue):
            scene_idx = self.queue[self.current_index]
            self.song.scenes[scene_idx].fire()
            self.current_index += 1
            return True
        return False

    def reset(self):
        self.current_index = 0
```

### Group Track Slot Handling
```python
def get_group_slot_clips(slot):
    """Get info about clips controlled by a group slot."""
    if not slot.is_group_slot:
        return None

    return {
        "controls_clips": slot.controls_other_clips,
        "is_triggered": slot.is_triggered,
        "playing_status": slot.playing_status
    }
```
