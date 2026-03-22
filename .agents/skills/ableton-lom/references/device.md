# Device & DeviceParameter Reference

The Device class represents any device (instrument, effect, or rack) in a track's device chain.

**Canonical Path:** `live_set tracks N devices M`

## Table of Contents
- [Device Properties](#device-properties)
- [Device Methods](#device-methods)
- [DeviceParameter Class](#deviceparameter-class)
- [Device.View Class](#deviceview-class)
- [Common Patterns](#common-patterns)

---

## Device Properties

### Basic Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R/W | Yes | Device title bar name |
| `class_name` | symbol | R | No | Live device type (e.g., "Operator", "MidiChord", "PluginDevice") |
| `class_display_name` | symbol | R | No | Original device name (e.g., "Operator", "Auto Filter") |
| `type` | int | R | No | 0=undefined, 1=instrument, 2=audio_effect, 4=midi_effect |
| `is_active` | bool | R | Yes | 0 if device or enclosing Rack is off |

### Rack & Chain Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `can_have_chains` | bool | R | No | 0 for single device, 1 for Rack |
| `can_have_drum_pads` | bool | R | No | 1 if device is a Drum Rack |

### Latency Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `latency_in_samples` | int | R | Yes | Latency in samples |
| `latency_in_ms` | float | R | Yes | Latency in milliseconds |

### AB Compare Properties (Live 12.3+)

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `can_compare_ab` | bool | R | No | 1 for devices that support AB Compare |
| `is_using_compare_preset_b` | bool | R/W | Yes | Indicates preset B status |

### Children

| Property | Type | Access | Description |
|----------|------|--------|-------------|
| `parameters` | list[DeviceParameter] | R | All device parameters |
| `view` | Device.View | R | View aspects of device |

---

## Device Methods

### `store_chosen_bank(script_index, bank_index)`
Hardware control surface utility for bank selection. Rarely used directly.

### `save_preset_to_compare_ab_slot()` (Live 12.3+)
Save current device state to the other AB compare slot.
```python
if device.can_compare_ab:
    device.save_preset_to_compare_ab_slot()
    device.is_using_compare_preset_b = not device.is_using_compare_preset_b
```

---

## DeviceParameter Class

The DeviceParameter class represents an automatable parameter within a device.

**Canonical Path:** `live_set tracks N devices M parameters L`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `name` | symbol | R | No | Short parameter name (as in automation chooser) |
| `original_name` | symbol | R | No | Name before Macro assignment |
| `value` | float | R/W | Yes | Internal value between min and max |
| `display_value` | float | R | Yes | Value as visible in GUI |
| `min` | float | R | No | Minimum allowed value |
| `max` | float | R | No | Maximum allowed value |
| `default_value` | float | R | No | Default value (non-quantized only) |
| `is_enabled` | bool | R | No | Can be modified by user/automation/MIDI |
| `is_quantized` | bool | R | No | 1 for booleans and enums, 0 for continuous |
| `value_items` | StringVector | R | No | Possible values for quantized parameters |
| `automation_state` | int | R | Yes | 0=no automation, 1=active, 2=overridden |
| `state` | int | R | Yes | 0=active, 1=inactive but changeable, 2=cannot change |

### Methods

#### `str_for_value(value)` → symbol
Returns string representation of a numeric value.
```python
param = device.parameters[0]
display = param.str_for_value(param.value)  # e.g., "1.2 dB"
```

#### `re_enable_automation()`
Restores automation capability for the parameter.
```python
param.re_enable_automation()
```

---

## Device.View Class

**Canonical Path:** `live_set tracks N devices M view`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `is_collapsed` | bool | R/W | Yes | 1 = device shown collapsed in chain |

```python
device.view.is_collapsed = True  # Collapse device
device.view.is_collapsed = False  # Expand device
```

---

## Common Patterns

### Iterate All Parameters
```python
device = track.devices[0]
for param in device.parameters:
    self.log_message(f"{param.name}: {param.value} ({param.min} - {param.max})")
```

### Find Parameter by Name
```python
def find_parameter(device, name):
    for param in device.parameters:
        if param.name.lower() == name.lower():
            return param
    return None

# Usage
cutoff = find_parameter(device, "Frequency")
if cutoff:
    cutoff.value = 5000.0
```

### Set Quantized Parameter
```python
# For on/off or enum parameters
param = device.parameters[0]
if param.is_quantized:
    # Use integer indices
    param.value = 1  # Second option
    # Check available values
    print(list(param.value_items))
```

### Normalize Parameter Value
```python
def set_normalized(param, normalized_value):
    """Set parameter using 0.0-1.0 range."""
    param.value = param.min + (normalized_value * (param.max - param.min))

def get_normalized(param):
    """Get parameter as 0.0-1.0 range."""
    return (param.value - param.min) / (param.max - param.min)

# Usage
set_normalized(volume_param, 0.75)  # 75% of range
```

### Monitor Parameter Changes
```python
def on_param_changed():
    self.log_message(f"Parameter changed: {param.value}")

param.add_value_listener(on_param_changed)

# Remember to remove listener when done
param.remove_value_listener(on_param_changed)
```

### Get All Device Info
```python
def get_device_info(device):
    return {
        "name": device.name,
        "class_name": device.class_name,
        "class_display_name": device.class_display_name,
        "type": ["undefined", "instrument", "audio_effect", None, "midi_effect"][device.type],
        "is_active": device.is_active,
        "can_have_chains": device.can_have_chains,
        "can_have_drum_pads": device.can_have_drum_pads,
        "parameter_count": len(device.parameters),
        "parameters": [
            {
                "name": p.name,
                "value": p.value,
                "min": p.min,
                "max": p.max,
                "is_quantized": p.is_quantized
            }
            for p in device.parameters
        ]
    }
```

### Insert Native Device (Live 12.3+)
```python
# Insert at end of chain
track.insert_device("Compressor")

# Insert at specific position
track.insert_device("Auto Filter", 0)  # At beginning

# Available device names match class_display_name
# Examples: "Compressor", "Auto Filter", "EQ Eight", "Reverb", "Delay"
```

### Working with Plugin Devices
```python
if device.class_name == "PluginDevice":
    # Access plugin-specific properties
    plugin = device
    print(f"Presets: {list(plugin.presets)}")
    print(f"Current preset: {plugin.selected_preset_index}")

    # Change preset
    plugin.selected_preset_index = 2
```

---

## Device Type Constants

```python
DEVICE_TYPE_UNDEFINED = 0
DEVICE_TYPE_INSTRUMENT = 1
DEVICE_TYPE_AUDIO_EFFECT = 2
DEVICE_TYPE_MIDI_EFFECT = 4

def is_instrument(device):
    return device.type == DEVICE_TYPE_INSTRUMENT

def is_audio_effect(device):
    return device.type == DEVICE_TYPE_AUDIO_EFFECT

def is_midi_effect(device):
    return device.type == DEVICE_TYPE_MIDI_EFFECT
```
