# Clip Class Reference

The Clip class represents audio or MIDI clips in Live.

**Canonical Path:** `live_set tracks N clip_slots M clip` (Session) or `live_set tracks N arrangement_clips M` (Arrangement)

## Table of Contents
- [Basic Properties](#basic-properties)
- [Loop & Position Properties](#loop--position-properties)
- [Launch Properties](#launch-properties)
- [Audio Clip Properties](#audio-clip-properties)
- [MIDI Note Methods](#midi-note-methods)
- [Audio Warp Methods](#audio-warp-methods)
- [Playback Methods](#playback-methods)
- [Automation Methods](#automation-methods)
- [Clip.View Class](#clipview-class)

---

## Basic Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Clip name |
| `color` | int | R/W | Yes | RGB value (0x00rrggbb) |
| `color_index` | int | R/W | Yes | Clip's color index |
| `is_audio_clip` | bool | R | No | 1 for audio, 0 for MIDI |
| `is_midi_clip` | bool | R | No | Opposite of is_audio_clip |
| `is_session_clip` | bool | R | No | 1 if Session clip |
| `is_arrangement_clip` | bool | R | No | 1 if Arrangement clip |
| `is_take_lane_clip` | bool | R | No | 1 if on Take Lane |
| `muted` | bool | R/W | Yes | 1 = muted (Clip Activator off) |
| `length` | float | R | No | Loop length (looped) or clip length in beats |
| `signature_numerator` | int | R/W | Yes | Time signature numerator |
| `signature_denominator` | int | R/W | Yes | Time signature denominator |
| `has_envelopes` | bool | R | No | Whether clip contains automation |

## Loop & Position Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `looping` | bool | R/W | Yes | 1 if clip looped (unwarped audio cannot loop) |
| `loop_start` | float | R/W | Yes | Loop start (looped) or clip start (unlooped) |
| `loop_end` | float | R/W | Yes | Loop end (looped) or clip end (unlooped) |
| `position` | float | R/W | Yes | Loop position (equals loop_start) |
| `start_marker` | float | R/W | Yes | Start marker in beats (independent of loop) |
| `end_marker` | float | R/W | Yes | End marker in beats (independent of loop) |
| `start_time` | float | R | No | Start time relative to song time in beats |
| `end_time` | float | R | No | End time (loop end for looped Session clips) |
| `playing_position` | float | R | No | Current playback position in beats (or seconds for unwarped) |
| `loop_jump` | bang | - | Yes | Bangs when play position crosses loop start |

## Playback Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `is_playing` | bool | R/W | Yes | 1 if clip playing or recording |
| `is_recording` | bool | R | No | 1 if clip recording |
| `is_triggered` | bool | R | No | 1 if Clip Launch button blinking |
| `is_overdubbing` | bool | R | No | 1 if clip is overdubbing |
| `will_record_on_start` | bool | R | No | 1 for triggered MIDI clips with armed track and Arrangement Overdub on |
| `playing_status` | bang | - | Yes | Bangs when playing/trigger status changes |

## Launch Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `launch_mode` | int | R/W | Yes | 0=Trigger, 1=Gate, 2=Toggle, 3=Repeat |
| `launch_quantization` | int | R/W | Yes | Quantization index (0-14) |
| `legato` | bool | R/W | Yes | 1 = Legato Mode on |
| `velocity_amount` | float | R/W | Yes | How much triggering note velocity affects volume (0-1) |

## Groove Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `groove` | Groove | R/W | Yes | Associated groove |
| `has_groove` | bool | R | No | Returns true if groove is associated |

---

## Audio Clip Properties

These properties only apply to audio clips.

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `file_path` | symbol | R | No | Location of audio file |
| `gain` | float | R/W | Yes | Clip gain (0.0 to 1.0) |
| `gain_display_string` | symbol | R | No | Gain as string (e.g. "1.3 dB") |
| `pitch_coarse` | int | R/W | Yes | Transpose in semitones (-48 to 48) |
| `pitch_fine` | float | R/W | Yes | Detune in cents (-50 to 49) |
| `warping` | bool | R/W | Yes | 1 if Warp switch on |
| `warp_mode` | int | R/W | Yes | Warp mode (see values below) |
| `available_warp_modes` | list | R | No | Indexes of available Warp Modes |
| `warp_markers` | dict | R | Yes | Warp marker data |
| `ram_mode` | bool | R/W | Yes | 1 if RAM switch enabled |
| `sample_length` | int | R | No | Sample length in samples |
| `sample_rate` | float | R | No | Sample rate |

### Warp Mode Values
```
0 = Beats
1 = Tones
2 = Texture
3 = Re-Pitch
4 = Complex
5 = REX
6 = Complex Pro
```

---

## MIDI Note Methods

### Note Data Format

Notes are represented as dictionaries with these keys:
- `note_id`: Unique identifier (returned by add_new_notes)
- `pitch`: MIDI pitch (0-127)
- `start_time`: Position in beats
- `duration`: Length in beats
- `velocity`: Note velocity (1-127, default 100)
- `mute`: Muted state (default False)
- `probability`: Note probability (0.0-1.0)
- `velocity_deviation`: Velocity randomization
- `release_velocity`: Release velocity

### `add_new_notes(notes_dict)` → list[note_id]
Add notes to the clip. Returns list of note IDs.
```python
notes = {
    "notes": [
        {"pitch": 60, "start_time": 0.0, "duration": 0.5, "velocity": 100},
        {"pitch": 64, "start_time": 0.5, "duration": 0.5, "velocity": 100},
        {"pitch": 67, "start_time": 1.0, "duration": 0.5, "velocity": 100}
    ]
}
note_ids = clip.add_new_notes(notes)
```

### `get_all_notes_extended(options=None)` → list[dict]
Get all notes in the clip.
```python
# Get all properties
notes = clip.get_all_notes_extended()

# Get specific properties only
notes = clip.get_all_notes_extended({"return": ["pitch", "start_time", "duration"]})
```

### `get_notes_extended(from_pitch, pitch_span, from_time, time_span)` → list[dict]
Get notes within a pitch/time region.
```python
# Get all notes from C3 to C4, beats 0-4
notes = clip.get_notes_extended(48, 12, 0.0, 4.0)

# Or as dictionary
notes = clip.get_notes_extended({
    "from_pitch": 48,
    "pitch_span": 12,
    "from_time": 0.0,
    "time_span": 4.0
})
```

### `get_notes_by_id(note_ids)` → list[dict]
Get specific notes by their IDs.
```python
notes = clip.get_notes_by_id([1, 2, 3])
# Or with specific return properties
notes = clip.get_notes_by_id({"note_ids": [1, 2, 3], "return": ["pitch", "velocity"]})
```

### `get_selected_notes_extended(options=None)` → list[dict]
Get currently selected notes.
```python
selected = clip.get_selected_notes_extended()
```

### `apply_note_modifications(notes_dict)`
Modify existing notes. Replaces remove/add workflow.
```python
# Get notes, modify, and apply
notes = clip.get_notes_extended(0, 128, 0.0, 4.0)
for note in notes["notes"]:
    note["velocity"] = min(127, note["velocity"] + 10)
clip.apply_note_modifications(notes)
```

### `remove_notes_by_id(note_ids)`
Delete notes by ID.
```python
clip.remove_notes_by_id([1, 2, 3])
```

### `remove_notes_extended(from_pitch, pitch_span, from_time, time_span)`
Delete notes within pitch/time region.
```python
clip.remove_notes_extended(0, 128, 0.0, 4.0)  # Remove all notes in first 4 beats
```

### `duplicate_notes_by_id(note_ids_or_dict)`
Duplicate notes, optionally transposing.
```python
# Simple duplication
clip.duplicate_notes_by_id([1, 2, 3])

# With destination and transposition
clip.duplicate_notes_by_id({
    "note_ids": [1, 2, 3],
    "destination_time": 4.0,
    "transposition_amount": 12  # Up one octave
})
```

### `duplicate_region(start, length, destination, pitch=-1, transposition=0)`
Duplicate notes in a region.
```python
# Duplicate beats 0-4 to beat 4
clip.duplicate_region(0.0, 4.0, 4.0)

# Duplicate with transposition
clip.duplicate_region(0.0, 4.0, 4.0, -1, 12)  # -1 = all pitches
```

### Note Selection Methods

```python
clip.select_all_notes()
clip.deselect_all_notes()
clip.select_notes_by_id([1, 2, 3])
```

### Quantize Methods

```python
# Quantize all notes (uses song's swing amount)
clip.quantize(grid, amount)  # grid = quantization index, amount = 0.0-1.0

# Quantize specific pitch only
clip.quantize_pitch(60, grid, amount)  # Only C4 notes
```

### `duplicate_loop()`
Makes loop 2x longer and duplicates notes and envelopes.

---

## Audio Warp Methods

### `add_warp_marker(marker_dict)`
Add a warp marker.
```python
clip.add_warp_marker({"beat_time": 4.0})
# Or with sample time
clip.add_warp_marker({"beat_time": 4.0, "sample_time": 88200})
```

### `move_warp_marker(beat_time, beat_time_distance)`
Relocate a warp marker.
```python
clip.move_warp_marker(4.0, 0.5)  # Move marker at beat 4 by 0.5 beats
```

### `remove_warp_marker(beat_time)`
Remove warp marker at position.
```python
clip.remove_warp_marker(4.0)
```

---

## Playback Methods

### `fire()`
Same as pressing the Clip Launch button.
```python
clip.fire()
```

### `stop()`
Stop clip playback (only if clip is playing).
```python
clip.stop()
```

### `set_fire_button_state(state)`
Simulate holding launch button (1=press, 0=release).
```python
clip.set_fire_button_state(1)  # Press
# ... some time later
clip.set_fire_button_state(0)  # Release
```

### `move_playing_pos(beats)`
Jump by amount (unquantized, relative in beats).
```python
clip.move_playing_pos(4.0)  # Jump forward 4 beats
```

### `scrub(beat_time)`
Scrub to absolute time. Respects Global Quantization.
```python
clip.scrub(8.0)  # Scrub to beat 8
```

### `stop_scrub()`
Stop active scrub operation.

---

## Automation Methods

### `clear_all_envelopes()`
Remove all automation in the clip.

### `clear_envelope(device_parameter)`
Remove automation for specific parameter.
```python
clip.clear_envelope(device.parameters[0])
```

### `crop()`
If looped: remove region outside loop. Else: remove outside markers.

---

## Clip.View Class

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
Select the specified device parameter in the Envelopes box.
```python
clip.view.select_envelope_parameter(device.parameters[0])
```

#### `show_loop()`
If clip is visible in Detail View, make the current loop visible.

---

## Working with MIDI Notes - Complete Example

```python
def create_chord_clip(self, track_index, slot_index):
    """Create a clip with a simple chord progression."""
    track = self._song.tracks[track_index]
    slot = track.clip_slots[slot_index]

    # Create empty clip if needed
    if not slot.has_clip:
        slot.create_clip(4.0)  # 4 beats

    clip = slot.clip
    clip.name = "Chord Progression"

    # Clear existing notes
    clip.remove_notes_extended(0, 128, 0.0, clip.length)

    # C major chord at beat 0
    c_major = [
        {"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100},
        {"pitch": 64, "start_time": 0.0, "duration": 1.0, "velocity": 90},
        {"pitch": 67, "start_time": 0.0, "duration": 1.0, "velocity": 80}
    ]

    # G major chord at beat 2
    g_major = [
        {"pitch": 55, "start_time": 2.0, "duration": 1.0, "velocity": 100},
        {"pitch": 59, "start_time": 2.0, "duration": 1.0, "velocity": 90},
        {"pitch": 62, "start_time": 2.0, "duration": 1.0, "velocity": 80}
    ]

    # Add all notes
    all_notes = {"notes": c_major + g_major}
    note_ids = clip.add_new_notes(all_notes)

    return {"clip_name": clip.name, "note_count": len(note_ids)}
```
