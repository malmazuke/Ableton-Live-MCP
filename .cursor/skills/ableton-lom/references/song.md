# Song Class Reference

The Song class represents the current Live Set. Access via `self.song()` or `self._song`.

**Canonical Path:** `live_set`

## Table of Contents
- [Transport Properties](#transport-properties)
- [Time & Loop Properties](#time--loop-properties)
- [Recording Properties](#recording-properties)
- [Scale & Tuning Properties](#scale--tuning-properties)
- [Child Collections](#child-collections)
- [Transport Methods](#transport-methods)
- [Track Management Methods](#track-management-methods)
- [Scene Management Methods](#scene-management-methods)
- [Navigation Methods](#navigation-methods)
- [Utility Methods](#utility-methods)

---

## Transport Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `tempo` | float | R/W | Yes | Current tempo in BPM (20.0 - 999.0) |
| `is_playing` | bool | R/W | Yes | Transport running state |
| `metronome` | bool | R/W | Yes | Metronome enabled state |
| `nudge_down` | bool | R/W | Yes | Tempo Nudge Down button pressed state |
| `nudge_up` | bool | R/W | Yes | Tempo Nudge Up button pressed state |
| `current_song_time` | float | R/W | Yes | Playing position in beats |
| `start_time` | float | R/W | Yes | Playback start position in beats |
| `song_length` | float | R | Yes | Total song length in beats |
| `last_event_time` | float | R | No | Beat time of final arrangement event |

## Time & Loop Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `signature_numerator` | int | R/W | Yes | Time signature numerator |
| `signature_denominator` | int | R/W | Yes | Time signature denominator |
| `loop` | bool | R/W | Yes | Arrangement loop enabled state |
| `loop_start` | float | R/W | Yes | Arrangement loop start position in beats |
| `loop_length` | float | R/W | Yes | Arrangement loop length in beats |
| `clip_trigger_quantization` | int | R/W | Yes | Quantization setting (0=None, 1=8 Bars, ..., 13=1/32) |
| `midi_recording_quantization` | int | R/W | Yes | Record quantization value (0-8) |
| `swing_amount` | float | R/W | Yes | Swing amount (0.0 - 1.0) |
| `groove_amount` | float | R/W | Yes | Groove pool amount (0.0 - 1.0) |

### Clip Trigger Quantization Values
```
0 = None        4 = 1 Bar       8 = 1/8
1 = 8 Bars      5 = 1/2         9 = 1/8 Triplet
2 = 4 Bars      6 = 1/2 Triplet 10 = 1/16
3 = 2 Bars      7 = 1/4         11 = 1/16 Triplet
                                12 = 1/32
                                13 = 1/32 Triplet
```

## Recording Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `record_mode` | bool | R/W | Yes | Arrangement Record button state |
| `session_record` | bool | R/W | Yes | Session Overdub button state |
| `session_record_status` | int | R | Yes | Session Record button state |
| `session_automation_record` | bool | R/W | Yes | Automation Arm button state |
| `arrangement_overdub` | bool | R/W | Yes | State of MIDI Arrangement Overdub button |
| `overdub` | bool | R/W | Yes | MIDI Arrangement Overdub enabled state |
| `punch_in` | bool | R/W | Yes | Punch-In button enabled state |
| `punch_out` | bool | R/W | Yes | Punch-Out button enabled state |
| `back_to_arranger` | bool | R/W | Yes | Transport bar button indicating playback differs from arrangement |
| `re_enable_automation_enabled` | bool | R | Yes | Re-Enable Automation button state |
| `can_capture_midi` | bool | R | Yes | Whether recently played MIDI can be captured |
| `count_in_duration` | int | R | Yes | Metronome count-in duration index (0-3) |
| `is_counting_in` | bool | R | Yes | Metronome count-in status |

## Scale & Tuning Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `root_note` | int | R/W | Yes | Scale root note (0=C to 11=B) |
| `scale_name` | unicode | R/W | Yes | Current scale name from chooser |
| `scale_intervals` | list | R | Yes | Integer list representing current scale intervals |
| `scale_mode` | bool | R/W | Yes | Scale Mode highlighting and editing state |

## Other Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R | No | Current Live Set name |
| `file_path` | symbol | R | No | OS-native Live Set file path |
| `exclusive_arm` | bool | R | No | Exclusive Arm preference status |
| `exclusive_solo` | bool | R | No | Exclusive Solo preference status |
| `select_on_launch` | bool | R | No | "Select on Launch" preference status |
| `is_ableton_link_enabled` | bool | R/W | Yes | Ableton Link toggle state |
| `is_ableton_link_start_stop_sync_enabled` | bool | R/W | Yes | Link Start Stop Sync state |
| `can_undo` | bool | R | No | Undo history availability |
| `can_redo` | bool | R | No | Redo history availability |
| `can_jump_to_next_cue` | bool | R | Yes | Whether a cue point exists to the right |
| `can_jump_to_prev_cue` | bool | R | Yes | Whether a cue point exists to the left |
| `tempo_follower_enabled` | bool | R/W | Yes | Tempo Follower control state |
| `appointed_device` | Device | R | Yes | The appointed device for control surfaces |

## Child Collections

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `tracks` | list[Track] | R | Yes | All tracks (audio, MIDI, group) |
| `return_tracks` | list[Track] | R | Yes | Return track collection |
| `visible_tracks` | list[Track] | R | Yes | Non-folded tracks |
| `master_track` | Track | R | No | Master output track |
| `scenes` | list[Scene] | R | Yes | Scene collection |
| `cue_points` | list[CuePoint] | R | Yes | Arrangement markers |
| `groove_pool` | GroovePool | R | No | Live's groove pool (since 11.0) |
| `tuning_system` | TuningSystem | R | Yes | Active tuning system |
| `view` | Song.View | R | No | Song view object |

---

## Transport Methods

### `start_playing()`
Start playback from insert marker.
```python
self._song.start_playing()
```

### `stop_playing()`
Stop playback.
```python
self._song.stop_playing()
```

### `continue_playing()`
Resume playback from current position.
```python
self._song.continue_playing()
```

### `stop_all_clips(quantized=1)`
Stop all clips. Set `quantized=0` for immediate stop.
```python
self._song.stop_all_clips()  # Quantized
self._song.stop_all_clips(0)  # Immediate
```

### `play_selection()`
Play arrangement selection if available.

### `tap_tempo()`
Tap tempo based on call interval.
```python
# Call repeatedly to tap tempo
self._song.tap_tempo()
```

### `trigger_session_record(record_length=None)`
Start session recording with optional duration.
```python
self._song.trigger_session_record()  # Record until stopped
self._song.trigger_session_record(4.0)  # Record for 4 beats
```

## Track Management Methods

### `create_midi_track(index)`
Add MIDI track at specified index (-1 for end).
```python
self._song.create_midi_track(-1)  # Add at end
self._song.create_midi_track(0)   # Add at beginning
```

### `create_audio_track(index)`
Add audio track at specified index (-1 for end).

### `create_return_track()`
Add return track at end.

### `delete_track(index)`
Remove track at index.

### `delete_return_track(index)`
Remove return track at index.

### `duplicate_track(index)`
Copy track at index.

## Scene Management Methods

### `create_scene(index)` → Scene
Create scene at index (-1 for end). Returns the new Scene.
```python
new_scene = self._song.create_scene(-1)
```

### `delete_scene(index)`
Remove scene at index.

### `duplicate_scene(index)`
Copy scene at index.

### `capture_and_insert_scene()`
Capture currently playing clips and insert as new scene.

## Navigation Methods

### `jump_by(beats)`
Jump relative to current position.
```python
self._song.jump_by(4.0)   # Jump forward 4 beats
self._song.jump_by(-4.0)  # Jump back 4 beats
```

### `scrub_by(beats)`
Scrub relative to current position.

### `jump_to_next_cue()`
Jump to next cue point to the right.

### `jump_to_prev_cue()`
Jump to next cue point to the left.

### `set_or_delete_cue()`
Toggle cue point at current position.

### `is_cue_point_selected()` → bool
Check if playhead is at a cue point.

## Utility Methods

### `undo()`
Undo last operation.

### `redo()`
Redo last undone operation.

### `re_enable_automation()`
Re-activate automation for all overridden parameters.

### `capture_midi(destination)`
Capture recent MIDI into a clip.
- `destination=0`: Auto
- `destination=1`: Session
- `destination=2`: Arrangement

### `get_current_beats_song_time()` → symbol
Return current position as "bars.beats.sixteenths.ticks".

### `get_beats_loop_start()` → symbol
Return loop start as "bars.beats.sixteenths.ticks".

### `get_beats_loop_length()` → symbol
Return loop length as "bars.beats.sixteenths.ticks".

### `get_current_smpte_song_time(format)` → symbol
Return position as "hours:min:sec" in specified timecode format (0-5).

### `force_link_beat_time()`
Jump Link timeline to current beat time.

### `move_device(device, target, target_position)` → int
Relocate device in target chain.

### `find_device_position(device, target, target_position)` → int
Find closest insertable device position in target chain.

---

## CuePoint Class

**Canonical Path:** `live_set cue_points N`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Cue point name |
| `time` | float | R | Yes | Arrangement position in beats |

### Methods

#### `jump()`
Set current arrangement playback position to this marker (quantized if playing).
```python
cue_point = self._song.cue_points[0]
cue_point.jump()
```
