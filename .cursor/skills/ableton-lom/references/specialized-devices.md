# Specialized Device Classes Reference

These classes extend the base Device class with additional properties and methods specific to each device type.

## Table of Contents
- [SimplerDevice](#simplerdevice)
- [Sample Class](#sample-class)
- [WavetableDevice](#wavetabledevice)
- [LooperDevice](#looperdevice)
- [CompressorDevice](#compressordevice)
- [Eq8Device](#eq8device)
- [HybridReverbDevice](#hybridreverbdevice)
- [DriftDevice](#driftdevice)
- [MeldDevice](#melddevice)
- [RoarDevice](#roardevice)
- [ShifterDevice](#shifterdevice)
- [SpectralResonatorDevice](#spectralresonatordevice)
- [DrumCellDevice](#drumcelldevice)
- [PluginDevice](#plugindevice)
- [MaxDevice](#maxdevice)

---

## SimplerDevice

**Canonical Path:** `live_set tracks N devices M` (when device is Simpler)

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `playback_mode` | int | R/W | Yes | 0=Classic, 1=One-Shot, 2=Slicing |
| `slicing_playback_mode` | int | R/W | Yes | 0=Mono, 1=Poly, 2=Thru |
| `pad_slicing` | bool | R/W | Yes | Add slices by playing unassigned notes |
| `retrigger` | bool | R/W | Yes | 1 = Retrigger enabled |
| `voices` | int | R/W | Yes | Voice count |
| `multi_sample_mode` | bool | R | No | 1 = Simpler in multisample mode |
| `playing_position` | float | R | No | Playback position (0.0 - 1.0) |
| `playing_position_enabled` | bool | R | No | 1 = Playing and showing position |
| `can_warp_as` | bool | R | No | 1 = warp_as available |
| `can_warp_double` | bool | R | No | 1 = warp_double available |
| `can_warp_half` | bool | R | No | 1 = warp_half available |

### Children

| Property | Type | Description |
|----------|------|-------------|
| `sample` | Sample | The loaded sample |

### Methods

```python
simpler.crop()                    # Crop sample to start/end markers
simpler.reverse()                 # Reverse the sample
simpler.warp_as(beats)            # Warp active region to beat count
simpler.warp_double()             # Double playback tempo
simpler.warp_half()               # Halve playback tempo
simpler.guess_playback_length()   # Returns estimated beat time
```

---

## Sample Class

Represents the sample loaded in Simpler.

**Canonical Path:** `live_set tracks N devices M sample`

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `file_path` | unicode | R | Yes | Sample file path |
| `length` | int | R | No | Sample duration in frames |
| `sample_rate` | int | R | No | Sample rate (since Live 11.0) |
| `start_marker` | int | R/W | Yes | Sample start marker |
| `end_marker` | int | R/W | Yes | Sample end marker |
| `gain` | float | R/W | Yes | Sample gain |
| `warping` | bool | R/W | Yes | Enable/disable warping |
| `warp_mode` | int | R/W | Yes | 0-6 (Beats/Tones/Texture/Re-Pitch/Complex/Complex Pro) |
| `warp_markers` | dict | R | Yes | Warp marker data (since Live 11.0) |
| `slices` | list[int] | R | Yes | Playable slice positions in frames (since Live 11.0) |
| `slicing_style` | int | R/W | Yes | Transient/Beat/Region/Manual |
| `slicing_sensitivity` | float | R/W | Yes | Sensitivity (0.0-1.0) |
| `slicing_beat_division` | int | R/W | Yes | Beat division (0-10) |
| `slicing_region_count` | int | R/W | Yes | Number of regions |

### Warp Mode Properties

| Property | Type | Access | Description |
|----------|------|--------|-------------|
| `beats_granulation_resolution` | int | R/W | Beats Mode divisions (0-6) |
| `beats_transient_envelope` | float | R/W | Volume fade per segment (0-100) |
| `beats_transient_loop_mode` | int | R/W | Off/Forward/Back-and-Forth |
| `tones_grain_size` | float | R/W | Tones Mode grain size |
| `texture_flux` | float | R/W | Texture Mode flux |
| `texture_grain_size` | float | R/W | Texture Mode grain size |
| `complex_pro_envelope` | float | R/W | Complex Pro envelope |
| `complex_pro_formants` | float | R/W | Complex Pro formants |

### Methods

```python
sample.gain_display_string()                    # Returns gain as "X.X dB"
sample.insert_slice(slice_time)                 # Insert slice at time
sample.move_slice(source_time, dest_time)       # Move slice
sample.remove_slice(slice_time)                 # Remove slice
sample.clear_slices()                           # Remove all manual slices
sample.reset_slices()                           # Restore original slices
```

---

## WavetableDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `oscillator_1_wavetable_category` | int | R/W | Yes | Osc 1 category selector |
| `oscillator_2_wavetable_category` | int | R/W | Yes | Osc 2 category selector |
| `oscillator_1_wavetable_index` | int | R/W | Yes | Osc 1 wavetable selector |
| `oscillator_2_wavetable_index` | int | R/W | Yes | Osc 2 wavetable selector |
| `oscillator_1_effect_mode` | int | R/W | Yes | 0=None, 1=FM, 2=Classic, 3=Modern |
| `oscillator_2_effect_mode` | int | R/W | Yes | Same as osc 1 |
| `filter_routing` | int | R/W | Yes | 0=Serial, 1=Parallel, 2=Split |
| `mono_poly` | int | R/W | Yes | 0=Mono, 1=Poly |
| `poly_voices` | int | R/W | Yes | Polyphonic voice count |
| `unison_voice_count` | int | R/W | Yes | Unison voices |
| `unison_mode` | int | R/W | Yes | 0=None, 1=Classic, 2=Shimmer, 3=Noise, 4=Phase Sync, 5=Position Spread, 6=Random Note |
| `oscillator_wavetable_categories` | StringVector | R | Yes | Available categories |
| `oscillator_1_wavetables` | StringVector | R | Yes | Osc 1 available wavetables |
| `oscillator_2_wavetables` | StringVector | R | Yes | Osc 2 available wavetables |
| `visible_modulation_target_names` | StringVector | R | Yes | Visible mod targets |

### Methods

```python
wavetable.add_parameter_to_modulation_matrix(param)
wavetable.get_modulation_target_parameter_name(index)
wavetable.get_modulation_value(target_index, source_index)
wavetable.set_modulation_value(target_index, source_index)
wavetable.is_parameter_modulatable(param)  # Returns bool
```

---

## LooperDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `loop_length` | float | R | Yes | Buffer length |
| `tempo` | float | R | Yes | Buffer tempo |
| `overdub_after_record` | bool | R/W | Yes | Switch to overdub after fixed recording |
| `record_length_index` | int | R/W | Yes | Record Length chooser index |
| `record_length_list` | StringVector | R | No | Record Length options |

### Methods

```python
looper.record()                         # Start recording
looper.overdub()                        # Playback + record layers
looper.play()                           # Playback only
looper.stop()                           # Stop playback
looper.clear()                          # Erase content
looper.undo()                           # Erase since last overdub toggle
looper.double_speed()                   # 2x speed
looper.half_speed()                     # 0.5x speed
looper.double_length()                  # 2x buffer length
looper.half_length()                    # 0.5x buffer length
looper.export_to_clip_slot(clip_slot)   # Export to empty slot
```

---

## CompressorDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `input_routing_type` | dict | R/W | Yes | Sidechain source type |
| `input_routing_channel` | dict | R/W | Yes | Sidechain source channel |
| `available_input_routing_types` | dict | R | Yes | Available source types |
| `available_input_routing_channels` | dict | R | Yes | Available source channels |

---

## Eq8Device

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `global_mode` | int | R/W | Yes | 0=Stereo, 1=L/R, 2=M/S |
| `edit_mode` | bool | R/W | Yes | Channel for editing (L/R or M/S or A/B) |
| `oversample` | bool | R/W | Yes | 0=Off, 1=On |

---

## HybridReverbDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `ir_category_index` | int | R/W | Yes | Selected IR category |
| `ir_category_list` | StringVector | R | No | IR category names |
| `ir_file_index` | int | R/W | Yes | Selected IR file |
| `ir_file_list` | StringVector | R | Yes | IR files in category |
| `ir_attack_time` | float | R/W | Yes | IR envelope attack (seconds) |
| `ir_decay_time` | float | R/W | Yes | IR envelope decay (seconds) |
| `ir_size_factor` | float | R/W | Yes | IR relative size (0.0-1.0) |
| `ir_time_shaping_on` | bool | R/W | Yes | Enable envelope/size transform |

---

## DriftDevice

### Properties (Modulation Matrix)

| Property | Type | Access | Description |
|----------|------|--------|-------------|
| `mod_matrix_filter_source_1_index` | int | R/W | Filter mod source 1 |
| `mod_matrix_filter_source_1_list` | StringVector | R | Available sources |
| `mod_matrix_filter_source_2_index` | int | R/W | Filter mod source 2 |
| `mod_matrix_lfo_source_index` | int | R/W | LFO mod source |
| `mod_matrix_pitch_source_1_index` | int | R/W | Pitch mod source 1 |
| `mod_matrix_pitch_source_2_index` | int | R/W | Pitch mod source 2 |
| `mod_matrix_shape_source_index` | int | R/W | Shape mod source |
| `mod_matrix_source_1/2/3_index` | int | R/W | Custom slot sources |
| `mod_matrix_target_1/2/3_index` | int | R/W | Custom slot targets |
| `pitch_bend_range` | int | R/W | MIDI pitch bend range |
| `voice_count_index` | int | R/W | Voice count |
| `voice_mode_index` | int | R/W | Voice mode |

---

## MeldDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `selected_engine` | int | R/W | Yes | 0=Engine A, 1=Engine B |
| `mono_poly` | int | R/W | Yes | 0=Mono, 1=Poly |
| `poly_voices` | int | R/W | Yes | 2/3/4/5/6/8/12 voices |
| `unison_voices` | int | R/W | Yes | Off/2/3/4 unison voices |

---

## RoarDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `routing_mode_index` | int | R/W | Yes | Routing mode |
| `routing_mode_list` | StringVector | R | No | Available modes |
| `env_listen` | bool | R/W | Yes | Envelope Input Listen |

---

## ShifterDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `pitch_mode_index` | int | R/W | Yes | 0=Internal, 1=MIDI |
| `pitch_bend_range` | int | R/W | Yes | MIDI pitch bend range |

---

## SpectralResonatorDevice

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `frequency_dial_mode` | int | R/W | Yes | 0=Hertz, 1=MIDI note |
| `midi_gate` | int | R/W | Yes | 0=Off, 1=On |
| `mod_mode` | int | R/W | Yes | 0=None, 1=Chorus, 2=Wander, 3=Granular |
| `mono_poly` | int | R/W | Yes | 0=Mono, 1=Poly |
| `pitch_mode` | int | R/W | Yes | 0=Internal, 1=MIDI |
| `pitch_bend_range` | int | R/W | Yes | Pitch bend range |
| `polyphony` | int | R/W | Yes | 0=2, 1=4, 2=8, 3=16 voices |

---

## DrumCellDevice

Represents Drum Sampler within a Drum Rack.

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `gain` | float | R/W | Yes | Sample gain (normalized 0.0-1.0) |

---

## PluginDevice

Represents VST/AU plugins.

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `presets` | StringVector | R | Yes | List of plugin presets |
| `selected_preset_index` | int | R/W | Yes | Current preset index |

```python
# List presets
for i, preset in enumerate(plugin.presets):
    print(f"{i}: {preset}")

# Change preset
plugin.selected_preset_index = 5
```

---

## MaxDevice

Represents Max for Live devices.

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `audio_inputs` | list[DeviceIO] | R | Yes | Audio input list |
| `audio_outputs` | list[DeviceIO] | R | Yes | Audio output list |
| `midi_inputs` | list[DeviceIO] | R | Yes | MIDI input list (since 11.0) |
| `midi_outputs` | list[DeviceIO] | R | Yes | MIDI output list (since 11.0) |

### Methods

```python
max_device.get_bank_count()                  # Returns int
max_device.get_bank_name(bank_index)         # Returns list[symbol]
max_device.get_bank_parameters(bank_index)   # Returns parameter indices (-1 for empty)
```

---

## DeviceIO Class

Represents an input or output bus of a device.

### Properties

| Property | Type | Access | Observable | Description |
|----------|------|--------|------------|-------------|
| `routing_type` | dict | R/W | Yes | Current routing type |
| `routing_channel` | dict | R/W | Yes | Current routing channel |
| `available_routing_types` | dict | R | Yes | Available types |
| `available_routing_channels` | dict | R | Yes | Available channels |
| `default_external_routing_channel_is_none` | bool | R | No | Default is none (since 11.0) |
