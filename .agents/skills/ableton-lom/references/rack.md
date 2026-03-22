# Rack Device Classes Reference

This document covers Instrument Racks, Audio Effect Racks, MIDI Effect Racks, and Drum Racks.

## Table of Contents
- [RackDevice Class](#rackdevice-class)
- [Chain Class](#chain-class)
- [ChainMixerDevice Class](#chainmixerdevice-class)
- [DrumPad Class](#drumpad-class)
- [DrumChain Class](#drumchain-class)
- [Common Patterns](#common-patterns)

---

## RackDevice Class

The RackDevice class represents any type of Rack device in Live.

**Canonical Path:** `live_set tracks N devices M` (when device is a Rack)

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `can_show_chains` | bool | R | No | Rack contains instrument that can show chains in Session View |
| `is_showing_chains` | bool | R/W | Yes | Whether chains are displayed in Session View |
| `has_drum_pads` | bool | R | Yes | Device is a Drum Rack with pads |
| `has_macro_mappings` | bool | R | Yes | Any macro is mapped to a parameter |
| `visible_macro_count` | int | R | Yes | Count of visible macros |
| `variation_count` | int | R | Yes | Number of stored macro variations (since 11.0) |
| `selected_variation_index` | int | R/W | No | Currently selected variation (since 11.0) |

### Children

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `chains` | list[Chain] | R | Yes | All chains in the Rack |
| `return_chains` | list[Chain] | R | Yes | Return chains |
| `chain_selector` | DeviceParameter | R | No | Chain selector control |
| `drum_pads` | list[DrumPad] | R | Yes | All 128 Drum Pads (Drum Rack only) |
| `visible_drum_pads` | list[DrumPad] | R | Yes | 16 visible pads (Drum Rack only) |

### Methods

#### `copy_pad(source_index, destination_index)`
Copy all content from source to destination drum pad.
```python
rack.copy_pad(36, 48)  # Copy C1 to C2
```

#### `add_macro()` (since 11.0)
Increase visible macro controls.
```python
rack.add_macro()
```

#### `remove_macro()` (since 11.0)
Decrease visible macro controls.
```python
rack.remove_macro()
```

#### `randomize_macros()` (since 11.0)
Randomize eligible macro values.
```python
rack.randomize_macros()
```

#### `store_variation()` (since 11.0)
Store new macro variation snapshot.
```python
rack.store_variation()
```

#### `recall_selected_variation()` (since 11.0)
Recall currently selected variation.
```python
rack.selected_variation_index = 2
rack.recall_selected_variation()
```

#### `recall_last_used_variation()` (since 11.0)
Recall most recently used variation.
```python
rack.recall_last_used_variation()
```

#### `delete_selected_variation()` (since 11.0)
Delete currently selected variation.
```python
rack.delete_selected_variation()
```

#### `insert_chain(index)` (since 12.3)
Insert new chain at specified index or at end.
```python
rack.insert_chain(0)   # Insert at beginning
rack.insert_chain(-1)  # Insert at end
```

---

## Chain Class

Represents a chain within a Rack device.

**Canonical Path:** `live_set tracks N devices M chains L`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | unicode | R/W | Yes | Chain name |
| `color` | int | R/W | Yes | RGB value (0x00rrggbb) |
| `color_index` | long | R/W | Yes | Chain's color index |
| `is_auto_colored` | bool | R/W | Yes | Inherit track/chain color |
| `mute` | bool | R/W | Yes | Muted state (Chain Activator) |
| `solo` | bool | R/W | Yes | Solo state (doesn't auto-disable others) |
| `muted_via_solo` | bool | R | No | Muted due to another chain's solo |
| `has_audio_input` | bool | R | No | Has audio input |
| `has_audio_output` | bool | R | No | Has audio output |
| `has_midi_input` | bool | R | No | Has MIDI input |
| `has_midi_output` | bool | R | No | Has MIDI output |

### Children

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `devices` | list[Device] | R | Yes | Devices in this chain |
| `mixer_device` | ChainMixerDevice | R | No | Chain's mixer controls |

### Methods

#### `delete_device(index)`
Remove device at specified position.
```python
chain.delete_device(0)
```

#### `insert_device(device_name, target_index=None)` (since 12.3)
Insert native Live device at position.
```python
chain.insert_device("Compressor")
chain.insert_device("Auto Filter", 0)
```

---

## ChainMixerDevice Class

Provides access to chain mixer controls.

**Canonical Path:** `live_set tracks N devices M chains L mixer_device`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `volume` | DeviceParameter | R | No | Volume (Audio/Instrument Racks only) |
| `panning` | DeviceParameter | R | No | Pan (Audio/Instrument Racks only) |
| `chain_activator` | DeviceParameter | R | No | Chain on/off |
| `sends` | list[DeviceParameter] | R | Yes | Sends (Audio/Instrument Racks only, empty for Drum Racks) |

### Example
```python
chain = rack.chains[0]
mixer = chain.mixer_device

# Adjust volume
mixer.volume.value = 0.8

# Adjust pan
mixer.panning.value = -0.5  # Slightly left

# Adjust sends
for send in mixer.sends:
    send.value = 0.25
```

---

## DrumPad Class

Represents a pad in a Drum Rack.

**Canonical Path:** `live_set tracks N devices M drum_pads L`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R | Yes | Pad name |
| `note` | int | R | No | MIDI note (0-127) |
| `mute` | bool | R/W | Yes | Muted state |
| `solo` | bool | R/W | Yes | Solo state |

### Children

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `chains` | list[Chain] | R | Yes | Chains within the pad |

### Methods

#### `delete_all_chains()`
Remove all chains from the drum pad.
```python
drum_pad.delete_all_chains()
```

### Example: Iterate Drum Pads
```python
drum_rack = track.devices[0]
if drum_rack.has_drum_pads:
    for pad in drum_rack.drum_pads:
        if pad.chains:  # Pad has content
            print(f"Note {pad.note}: {pad.name}")
```

### Example: Work with Visible Pads
```python
# visible_drum_pads gives the 16 currently visible pads
for pad in drum_rack.visible_drum_pads:
    print(f"Visible pad: {pad.name} (note {pad.note})")
```

---

## DrumChain Class

Represents a chain within a Drum Rack pad. Extends Chain class.

**Canonical Path:** `live_set tracks N devices M drum_pads L chains K`

### Additional Properties (beyond Chain)

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `in_note` | int | R/W | Yes | MIDI note that triggers this chain (-1 = All Notes) (since 12.3) |
| `out_note` | int | R/W | Yes | MIDI note sent to devices in chain |
| `choke_group` | int | R/W | Yes | Chain's choke group |

### Example: Set Choke Group
```python
# Make hi-hats choke each other
for pad in drum_rack.drum_pads:
    if "Hat" in pad.name:
        for chain in pad.chains:
            chain.choke_group = 1
```

---

## Common Patterns

### Create and Configure a Rack
```python
def get_rack_info(rack):
    """Get comprehensive rack information."""
    info = {
        "name": rack.name,
        "is_drum_rack": rack.has_drum_pads,
        "chain_count": len(rack.chains),
        "macro_count": rack.visible_macro_count,
        "has_macro_mappings": rack.has_macro_mappings,
        "chains": []
    }

    for chain in rack.chains:
        chain_info = {
            "name": chain.name,
            "mute": chain.mute,
            "solo": chain.solo,
            "device_count": len(chain.devices),
            "devices": [d.name for d in chain.devices]
        }
        info["chains"].append(chain_info)

    return info
```

### Work with Drum Rack Pads
```python
def find_pad_by_note(drum_rack, note):
    """Find a drum pad by MIDI note number."""
    for pad in drum_rack.drum_pads:
        if pad.note == note:
            return pad
    return None

def get_occupied_pads(drum_rack):
    """Get all pads that have content."""
    return [pad for pad in drum_rack.drum_pads if pad.chains]

# Usage
kick_pad = find_pad_by_note(drum_rack, 36)  # C1
if kick_pad:
    kick_pad.solo = True
```

### Manage Macro Variations
```python
def save_and_recall_macros(rack):
    """Example of working with macro variations."""
    # Store current state
    rack.store_variation()
    print(f"Stored variation. Total: {rack.variation_count}")

    # Randomize macros
    rack.randomize_macros()

    # Store randomized state
    rack.store_variation()

    # Recall first variation
    rack.selected_variation_index = 0
    rack.recall_selected_variation()
```

### Navigate Nested Racks
```python
def find_all_devices_recursive(device, depth=0):
    """Recursively find all devices including those in racks."""
    devices = []
    indent = "  " * depth

    devices.append({
        "depth": depth,
        "name": device.name,
        "class": device.class_display_name
    })

    if device.can_have_chains:
        for chain in device.chains:
            for nested_device in chain.devices:
                devices.extend(find_all_devices_recursive(nested_device, depth + 1))

    return devices

# Usage
for track in song.tracks:
    for device in track.devices:
        all_devices = find_all_devices_recursive(device)
        for d in all_devices:
            print(f"{'  ' * d['depth']}{d['name']} ({d['class']})")
```

### Copy Drum Pad with Sample
```python
def duplicate_drum_sound(rack, source_note, dest_note):
    """Copy a drum pad's content to another pad."""
    # Find source and destination indices
    source_idx = None
    dest_idx = None

    for i, pad in enumerate(rack.drum_pads):
        if pad.note == source_note:
            source_idx = i
        if pad.note == dest_note:
            dest_idx = i

    if source_idx is not None and dest_idx is not None:
        rack.copy_pad(source_idx, dest_idx)
        return True
    return False

# Usage
duplicate_drum_sound(drum_rack, 36, 48)  # Copy C1 to C2
```
