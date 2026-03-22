# Track Class Reference

The Track class represents audio, MIDI, return, group, or master tracks in Live.

**Canonical Path:** `live_set tracks N` or `live_set return_tracks N` or `live_set master_track`

## Table of Contents
- [Basic Properties](#basic-properties)
- [Routing Properties](#routing-properties)
- [Meter Properties](#meter-properties)
- [Group Track Properties](#group-track-properties)
- [Child Collections](#child-collections)
- [Methods](#methods)
- [MixerDevice Class](#mixerdevice-class)
- [Track.View Class](#trackview-class)

---

## Basic Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Track name as shown in header |
| `color` | int | R/W | Yes | RGB color value (0x00rrggbb format) |
| `color_index` | long | R/W | Yes | Track color index reference |
| `arm` | bool | R/W | Yes | Track armed for recording (not on return/master) |
| `can_be_armed` | bool | R | No | Returns 0 for return and master tracks |
| `implicit_arm` | bool | R/W | Yes | Secondary arm state (Push controller) |
| `mute` | bool | R/W | Yes | Mute state (not on master) |
| `solo` | bool | R/W | Yes | Solo state (not on master) |
| `muted_via_solo` | bool | R | Yes | Muted due to Solo on another track |
| `is_frozen` | bool | R | Yes | Track is currently frozen |
| `can_be_frozen` | bool | R | No | Track supports freezing |
| `performance_impact` | float | R | Yes | Track performance load metric |

## Track Type Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `has_audio_input` | bool | R | No | Returns 1 for audio tracks |
| `has_audio_output` | bool | R | No | Returns 1 for audio/MIDI tracks with instruments |
| `has_midi_input` | bool | R | No | Returns 1 for MIDI tracks |
| `has_midi_output` | bool | R | No | Returns 1 for MIDI tracks with no instruments and no audio effects |

## Routing Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `input_routing_type` | dict | R/W | Yes | Current source type (`display_name`, `identifier`) |
| `input_routing_channel` | dict | R/W | Yes | Current source channel (`display_name`, `identifier`) |
| `output_routing_type` | dict | R/W | Yes | Current target type (`display_name`, `identifier`) |
| `output_routing_channel` | dict | R/W | Yes | Current target channel (`display_name`, `identifier`) |
| `available_input_routing_types` | dict | R | Yes | Available source types for input routing |
| `available_input_routing_channels` | dict | R | Yes | Available source channels for input routing |
| `available_output_routing_types` | dict | R | Yes | Available target types for output routing |
| `available_output_routing_channels` | dict | R | Yes | Available target channels for output routing |

### Routing Example
```python
# Get available input routing types
for routing in track.available_input_routing_types:
    print(routing['display_name'], routing['identifier'])

# Set input routing
track.input_routing_type = track.available_input_routing_types[0]
```

## Meter Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `input_meter_left` | float | R | Yes | Left channel input meter (0.0–1.0) |
| `input_meter_right` | float | R | Yes | Right channel input meter (0.0–1.0) |
| `input_meter_level` | float | R | Yes | Input meter hold peak (0.0–1.0), 1-second hold |
| `output_meter_left` | float | R | Yes | Left channel output meter (0.0–1.0) |
| `output_meter_right` | float | R | Yes | Right channel output meter (0.0–1.0) |
| `output_meter_level` | float | R | Yes | Output meter hold peak (0.0–1.0), 1-second hold |

## Session View Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `fired_slot_index` | int | R | Yes | Blinking clip slot (-1=none, -2=Stop button fired) |
| `playing_slot_index` | int | R | Yes | Current playing slot (-2=Stop fired, -1=Arrangement recording) |
| `back_to_arranger` | bool | R/W | Yes | Single Track Back to Arrangement button state |

## Group Track Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `is_foldable` | bool | R | No | Track can be folded (group tracks only) |
| `fold_state` | int | R/W | No | 0=visible, 1=folded and hidden (group tracks only) |
| `is_grouped` | bool | R | No | Track contained within a Group Track |
| `group_track` | Track | R | No | Parent group track (if grouped) |
| `is_visible` | bool | R | No | 0=hidden in folded Group Track |
| `can_show_chains` | bool | R | No | Track contains Instrument Rack that can show chains |
| `is_showing_chains` | bool | R/W | Yes | Instrument Rack chain visibility in Session View |
| `is_part_of_selection` | bool | R | No | Track selection status |

## Child Collections

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `clip_slots` | list[ClipSlot] | R | Yes | Clip slots in this track |
| `arrangement_clips` | list[Clip] | R | Yes | Arrangement View clips |
| `take_lanes` | list[TakeLane] | R | Yes | Take lanes for this track |
| `devices` | list[Device] | R | Yes | Devices on this track |
| `mixer_device` | MixerDevice | R | No | Track's mixer controls |
| `view` | Track.View | R | No | View aspects of track |

---

## Methods

### `stop_all_clips()`
Stops all playing and fired clips in track.
```python
track.stop_all_clips()
```

### `create_audio_clip(file_path, position)`
Creates audio clip referencing file at specified arrangement position (0–1576800 beats).
```python
track.create_audio_clip("/path/to/audio.wav", 0.0)
```

### `create_midi_clip(start_time, length)`
Creates empty MIDI clip in arrangement (errors on frozen/recording tracks).
```python
track.create_midi_clip(0.0, 4.0)  # 4-beat clip at beginning
```

### `create_take_lane()`
Creates a take lane for the track.
```python
track.create_take_lane()
```

### `delete_clip(clip)`
Removes specified clip.
```python
track.delete_clip(clip)
```

### `delete_device(index)`
Removes device at index.
```python
track.delete_device(0)  # Remove first device
```

### `insert_device(device_name, target_index=None)`
*Available since Live 12.3*

Inserts native Live device at index or end of chain.
```python
track.insert_device("Auto Filter")
track.insert_device("Compressor", 0)  # Insert at beginning
```

### `duplicate_clip_slot(index)`
Works like 'Duplicate' in clip's context menu.
```python
track.duplicate_clip_slot(0)
```

### `duplicate_clip_to_arrangement(clip, destination_time)`
Duplicates clip to arrangement at beat position.
```python
track.duplicate_clip_to_arrangement(clip, 16.0)
```

### `jump_in_running_session_clip(beats)`
Modifies playback position in running Session clip.
```python
track.jump_in_running_session_clip(4.0)  # Jump forward 4 beats
```

---

## MixerDevice Class

The MixerDevice provides access to track mixer controls.

**Canonical Path:** `live_set tracks N mixer_device`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `volume` | DeviceParameter | R | No | Volume control |
| `panning` | DeviceParameter | R | No | Pan control |
| `left_split_stereo` | DeviceParameter | R | No | Left split stereo pan |
| `right_split_stereo` | DeviceParameter | R | No | Right split stereo pan |
| `panning_mode` | int | R/W | Yes | 0=Stereo, 1=Split Stereo |
| `track_activator` | DeviceParameter | R | No | Track on/off control |
| `sends` | list[DeviceParameter] | R | Yes | One send per return track |
| `crossfade_assign` | int | R/W | Yes | 0=A, 1=none, 2=B (not on master) |

### Master Track Only

| Property | Type | Access | Description |
|----------|------|--------|-------------|
| `crossfader` | DeviceParameter | R | Crossfader control |
| `cue_volume` | DeviceParameter | R | Cue volume control |
| `song_tempo` | DeviceParameter | R | Tempo control (as DeviceParameter) |

### Example: Adjust Volume
```python
mixer = track.mixer_device
mixer.volume.value = 0.85  # Set volume (0.0 to 1.0)
print(mixer.volume.str_for_value(mixer.volume.value))  # Print dB value
```

### Example: Set Pan
```python
mixer = track.mixer_device
mixer.panning.value = 0.0  # Center
mixer.panning.value = -1.0  # Full left
mixer.panning.value = 1.0   # Full right
```

### Example: Adjust Sends
```python
mixer = track.mixer_device
for i, send in enumerate(mixer.sends):
    print(f"Send {i}: {send.value}")
    send.value = 0.5  # Set send level
```

---

## Track.View Class

**Canonical Path:** `live_set tracks N view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `selected_device` | Device | R | Yes | The selected device (or first in multi-selection) |
| `device_insert_mode` | int | R/W | Yes | Device insert position (0=end, 1=left, 2=right) |
| `is_collapsed` | bool | R/W | Yes | Arrangement View: 1=collapsed, 0=opened |

### Methods

#### `select_instrument()` → bool
Selects track's instrument or first device, makes it visible and focuses on it. Returns 0 if no devices.
```python
success = track.view.select_instrument()
```

---

## TakeLane Class

**Canonical Path:** `live_set tracks N take_lanes M`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Name shown in take lane header |
| `arrangement_clips` | list[Clip] | R | Yes | Arrangement clips in this take lane |

### Methods

#### `create_audio_clip(file_path, start_time)`
Creates audio clip from file at beat position.

#### `create_midi_clip(start_time, length)`
Creates empty MIDI clip (0–1576800 beats range).
