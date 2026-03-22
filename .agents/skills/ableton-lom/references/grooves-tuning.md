# Grooves & Tuning Systems Reference

This document covers the GroovePool, Groove, and TuningSystem classes.

## Table of Contents
- [GroovePool Class](#groovepool-class)
- [Groove Class](#groove-class)
- [TuningSystem Class](#tuningsystem-class)
- [Common Patterns](#common-patterns)

---

## GroovePool Class

*Available since Live 11.0*

The GroovePool contains all grooves loaded in the current Live Set.

**Canonical Path:** `live_set groove_pool`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `grooves` | list[Groove] | R | Yes | List of grooves from top to bottom |

### Accessing the Groove Pool
```python
groove_pool = self._song.groove_pool
for groove in groove_pool.grooves:
    print(f"Groove: {groove.name}")
```

---

## Groove Class

*Available since Live 11.0*

Represents a groove stored in Live's groove pool.

**Canonical Path:** `live_set groove_pool grooves N`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Groove name |
| `base` | int | R/W | No | Base grid (see values below) |
| `quantization_amount` | float | R/W | Yes | Quantization amount (0.0-1.0) |
| `timing_amount` | float | R/W | Yes | Timing amount (0.0-1.0) |
| `random_amount` | float | R/W | Yes | Random amount (0.0-1.0) |
| `velocity_amount` | float | R/W | Yes | Velocity amount (0.0-1.0) |

### Base Grid Values
```
0 = 1/4
1 = 1/8
2 = 1/16
3 = 1/32
4 = 1/8 Triplet
5 = 1/16 Triplet
```

### Example: Adjust Groove Settings
```python
def set_groove_settings(groove, timing=0.5, velocity=0.3, random=0.1):
    """Configure groove parameters."""
    groove.timing_amount = timing
    groove.velocity_amount = velocity
    groove.random_amount = random
    groove.quantization_amount = 0.0  # No quantization

# Apply to first groove
groove = self._song.groove_pool.grooves[0]
set_groove_settings(groove)
```

### Example: Apply Groove to Clip
```python
def apply_groove_to_clip(clip, groove):
    """Apply a groove to a clip."""
    clip.groove = groove

# Usage
groove = self._song.groove_pool.grooves[0]
clip = track.clip_slots[0].clip
apply_groove_to_clip(clip, groove)

# Check if clip has groove
if clip.has_groove:
    print(f"Clip uses groove: {clip.groove.name}")
```

---

## TuningSystem Class

Represents the active tuning system in Live.

**Canonical Path:** `live_set tuning_system`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Name of active tuning system |
| `pseudo_octave_in_cents` | float | R | No | Pseudo octave size in cents |
| `lowest_note` | dict | R/W | Yes | Lowest note (note index and octave) |
| `highest_note` | dict | R/W | Yes | Highest note (note index and octave) |
| `reference_pitch` | dict | R/W | Yes | Reference pitch settings |
| `note_tunings` | dict | R/W | Yes | Relative note tunings in cents |

### Note Dictionary Format

The `lowest_note`, `highest_note`, and `reference_pitch` properties return dictionaries with:
- `note_index`: Index within the pseudo octave
- `octave`: Octave number

### Note Tunings Format

The `note_tunings` property returns a dictionary containing an array of cent offsets for each note in the pseudo octave.

### Example: Get Tuning Info
```python
def get_tuning_info(song):
    """Get current tuning system information."""
    tuning = song.tuning_system

    return {
        "name": tuning.name,
        "pseudo_octave_cents": tuning.pseudo_octave_in_cents,
        "lowest_note": tuning.lowest_note,
        "highest_note": tuning.highest_note,
        "reference_pitch": tuning.reference_pitch,
        "note_tunings": tuning.note_tunings
    }

info = get_tuning_info(self._song)
print(f"Tuning: {info['name']}")
print(f"Octave size: {info['pseudo_octave_cents']} cents")
```

### Example: Monitor Tuning Changes
```python
def on_tuning_changed():
    tuning = self._song.tuning_system
    self.log_message(f"Tuning changed to: {tuning.name}")

self._song.tuning_system.add_name_listener(on_tuning_changed)
```

---

## Common Patterns

### Manage Groove Pool
```python
class GrooveManager:
    """Helper class for working with grooves."""

    def __init__(self, song):
        self.song = song
        self.pool = song.groove_pool

    def get_groove_by_name(self, name):
        """Find a groove by name."""
        for groove in self.pool.grooves:
            if groove.name == name:
                return groove
        return None

    def get_all_groove_names(self):
        """List all available grooves."""
        return [g.name for g in self.pool.grooves]

    def apply_to_all_clips(self, groove, tracks=None):
        """Apply a groove to all clips in specified tracks."""
        target_tracks = tracks if tracks else self.song.tracks

        for track in target_tracks:
            for slot in track.clip_slots:
                if slot.has_clip:
                    slot.clip.groove = groove

    def remove_grooves_from_all(self):
        """Remove grooves from all clips."""
        for track in self.song.tracks:
            for slot in track.clip_slots:
                if slot.has_clip and slot.clip.has_groove:
                    slot.clip.groove = None

    def randomize_groove_amounts(self, groove, timing_range=(0.3, 0.7),
                                  velocity_range=(0.2, 0.5)):
        """Randomize groove parameters within ranges."""
        import random
        groove.timing_amount = random.uniform(*timing_range)
        groove.velocity_amount = random.uniform(*velocity_range)
        groove.random_amount = random.uniform(0, 0.2)
```

### Song Groove Amount
```python
def set_global_groove(song, amount):
    """Set the global groove pool amount."""
    song.groove_amount = max(0.0, min(1.0, amount))

# Set to 50%
set_global_groove(self._song, 0.5)
```

### Groove Presets
```python
GROOVE_PRESETS = {
    "subtle": {
        "timing_amount": 0.2,
        "velocity_amount": 0.1,
        "random_amount": 0.05,
        "quantization_amount": 0.0
    },
    "medium": {
        "timing_amount": 0.5,
        "velocity_amount": 0.3,
        "random_amount": 0.1,
        "quantization_amount": 0.0
    },
    "heavy": {
        "timing_amount": 0.8,
        "velocity_amount": 0.5,
        "random_amount": 0.2,
        "quantization_amount": 0.0
    },
    "drunk": {
        "timing_amount": 1.0,
        "velocity_amount": 0.4,
        "random_amount": 0.3,
        "quantization_amount": 0.0
    }
}

def apply_groove_preset(groove, preset_name):
    """Apply a preset configuration to a groove."""
    preset = GROOVE_PRESETS.get(preset_name)
    if preset:
        groove.timing_amount = preset["timing_amount"]
        groove.velocity_amount = preset["velocity_amount"]
        groove.random_amount = preset["random_amount"]
        groove.quantization_amount = preset["quantization_amount"]
        return True
    return False
```

### Tuning System Manager
```python
class TuningManager:
    """Helper for working with tuning systems."""

    def __init__(self, song):
        self.song = song
        self.tuning = song.tuning_system

    def get_current_tuning(self):
        """Get current tuning system name."""
        return self.tuning.name

    def get_note_offset(self, note_index):
        """Get the cent offset for a specific note."""
        tunings = self.tuning.note_tunings
        if 'tunings' in tunings and note_index < len(tunings['tunings']):
            return tunings['tunings'][note_index]
        return 0.0

    def is_equal_temperament(self):
        """Check if current tuning is standard equal temperament."""
        tunings = self.tuning.note_tunings
        if 'tunings' in tunings:
            # All notes should be 0 cents offset
            return all(t == 0.0 for t in tunings['tunings'])
        return True

    def get_octave_size(self):
        """Get the octave size in cents (1200 for standard)."""
        return self.tuning.pseudo_octave_in_cents
```

### Scale and Tuning Integration
```python
def get_scale_tuning_info(song):
    """Get combined scale and tuning information."""
    return {
        # Scale info
        "root_note": song.root_note,
        "scale_name": song.scale_name,
        "scale_intervals": list(song.scale_intervals),
        "scale_mode": song.scale_mode,

        # Tuning info
        "tuning_name": song.tuning_system.name,
        "octave_cents": song.tuning_system.pseudo_octave_in_cents,
        "note_tunings": song.tuning_system.note_tunings
    }
```

### Groove Analysis
```python
def analyze_groove(groove):
    """Analyze groove characteristics."""
    # Classify intensity
    total_amount = (groove.timing_amount + groove.velocity_amount +
                    groove.random_amount)

    if total_amount < 0.5:
        intensity = "subtle"
    elif total_amount < 1.0:
        intensity = "moderate"
    elif total_amount < 1.5:
        intensity = "strong"
    else:
        intensity = "extreme"

    # Classify style
    if groove.timing_amount > groove.velocity_amount:
        style = "timing-focused"
    elif groove.velocity_amount > groove.timing_amount:
        style = "dynamics-focused"
    else:
        style = "balanced"

    return {
        "name": groove.name,
        "intensity": intensity,
        "style": style,
        "timing_amount": groove.timing_amount,
        "velocity_amount": groove.velocity_amount,
        "random_amount": groove.random_amount,
        "base_grid": ["1/4", "1/8", "1/16", "1/32", "1/8T", "1/16T"][groove.base]
    }
```
