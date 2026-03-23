# Ableton Live Object Model (LOM) Skill

A comprehensive API reference skill for [Claude Code](https://claude.ai/code) that documents the Ableton Live Object Model for Remote Script development.

Covers **Live 12.3** including all classes, properties, methods, and common patterns.

## Installation

```bash
npx skills add mikecfisher/ableton-lom-skill
```

## What's Included

| Reference | Description |
|-----------|-------------|
| `song.md` | Song, transport, tempo, loops, cue points, time signatures |
| `track.md` | Track, MixerDevice, routing, meters, TakeLane |
| `clip.md` | Clip, MIDI notes, warping, automation, playback |
| `device.md` | Device, DeviceParameter, automation states |
| `specialized-devices.md` | Simpler, Wavetable, Looper, Compressor, EQ8, Drift, Meld, etc. |
| `rack.md` | RackDevice, Chain, DrumPad, DrumChain, macros, variations |
| `session.md` | Scene, ClipSlot, launching, recording |
| `views.md` | Application.View, Song.View, Track.View, Clip.View, Device.View |
| `browser.md` | Browser navigation, loading instruments/effects/samples |
| `grooves-tuning.md` | GroovePool, Groove, TuningSystem |

## Usage

Once installed, Claude Code will automatically use this skill when working with:

- Ableton Live Remote Scripts
- Control surface development
- MCP servers for Ableton
- Any Python code interfacing with Live's internal API

## Example

```python
from _Framework.ControlSurface import ControlSurface

class MyScript(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._song = self.song()

        # Access tempo
        self._song.tempo = 120.0

        # Create a MIDI track
        self._song.create_midi_track(-1)

        # Fire a clip
        track = self._song.tracks[0]
        track.clip_slots[0].fire()
```

## API Coverage

- **45+ classes** fully documented
- **400+ properties** with types, access modes, and observable status
- **150+ methods** with parameters and return types
- Common patterns and code examples throughout

## Sources

Documentation compiled from [Cycling '74's Live Object Model reference](https://docs.cycling74.com/apiref/lom/) for Max for Live, which covers Live 12.3.

## License

MIT
