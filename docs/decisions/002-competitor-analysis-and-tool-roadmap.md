# ADR-002: Competitor Analysis and Definitive Tool Roadmap

**Status:** Accepted
**Date:** 2026-03-22

## Context

Before implementing our MCP server, we need to understand what existing Ableton MCP servers offer, what patterns work, and what our tool surface should look like. This ADR captures a deep investigation of four competing projects and defines the implementation-ready tool list for Ableton Live MCP.

## Projects Analyzed

| Project | Stars | Tools | Architecture | Active |
|---------|-------|-------|-------------|--------|
| ahujasid/ableton-mcp | 2,334 | 16 | Monolithic single-file | No |
| uisato/ableton-mcp-extended | 140 | 16 (+ stubs) | Fork of above + UDP | Barely |
| jpoindexter/ableton-mcp | 7 | 128 | AI-generated bulk | No |
| ptaczek/daw-mcp | 4 | 11+8 opt-in | Modular TypeScript | No |

---

## Part 1: Competitor Tool Catalog

### ahujasid/ableton-mcp (16 tools)

The original and most popular. Every tool follows the same pattern: `@mcp.tool()` function → `send_command(type, params)` → return string.

| Tool | Parameters | Notes |
|------|-----------|-------|
| `get_session_info` | — | Tempo, time sig, track count, master vol/pan |
| `get_track_info` | `track_index: int` | Name, mute/solo/arm, vol/pan, clip slots, devices |
| `create_midi_track` | `index: int = -1` | At position or end |
| `set_track_name` | `track_index, name` | |
| `create_clip` | `track_index, clip_index, length=4.0` | Session clips only |
| `add_notes_to_clip` | `track_index, clip_index, notes: List[Dict]` | pitch/start_time/duration/velocity/mute |
| `set_clip_name` | `track_index, clip_index, name` | |
| `set_tempo` | `tempo: float` | |
| `load_instrument_or_effect` | `track_index, uri` | Brute-force browser search, depth 10 |
| `fire_clip` | `track_index, clip_index` | |
| `stop_clip` | `track_index, clip_index` | |
| `start_playback` | — | |
| `stop_playback` | — | |
| `get_browser_tree` | `category_type="all"` | Always-flat tree (children never populated) |
| `get_browser_items_at_path` | `path: str` | `"instruments/synths/..."` |
| `load_drum_kit` | `track_index, rack_uri, kit_path` | Multi-step composite |

**Bugs found:**
- `get_browser_categories` and `get_browser_items` dispatched in the if/elif but handlers are never defined (would crash).
- `load_instrument_or_effect` command handler (`_load_instrument_or_effect`) doesn't exist — dead code.
- `set_device_parameter` and `create_audio_track` listed as modifying commands but have no tool or handler.
- `get_browser_tree` builds children list but never populates it (always flat).

**Missing:** audio track creation, device parameters, arrangement view, scene management, note reading, mixer control, clip deletion, track deletion.

### uisato/ableton-mcp-extended (16 tools + hybrid stubs)

Fork of the original with identical MCP tools. The "extended" part is a separate hybrid TCP/UDP Remote Script with additional commands, most of which are **stubs** (return placeholder responses).

**Actually implemented additions (hybrid script only):**
- `get_device_parameters` — returns all param details with normalized values, min/max, is_quantized
- `set_device_parameter` — normalized 0.0-1.0 value input
- `batch_set_device_parameters` — set multiple params atomically
- UDP server (port 9878) for fire-and-forget parameter updates

**Stub-only commands (routed but return placeholder):** `get_notes_from_clip`, `get_scenes_info`, `create_scene`, `set_scene_name`, `delete_scene`, `fire_scene`, `batch_edit_notes_in_clip`, `delete_notes_from_clip`, `transpose_notes_in_clip`, `quantize_notes_in_clip`, `randomize_note_timing`, `set_note_probability`, `create_audio_track`, `set_clip_loop_parameters`, `set_clip_follow_action`, `import_audio_file`, `set_track_level`, `set_track_pan`, `add_clip_envelope_point`, `clear_clip_envelope`, `get_clip_envelope`.

**Separate ElevenLabs MCP server** (19 tools) — TTS, STT, voice cloning, SFX generation, conversational AI. Not relevant to our scope but shows creative integration potential.

### jpoindexter/ableton-mcp (128 MCP tools)

Claims "200+ tools" — actual count is 128 MCP tools plus ~196 REST API whitelist entries. The code is AI-generated bulk with extreme repetition: every tool is a copy-paste template with only names changed. The Remote Script is a 7,032-line single file.

**Tools by domain (128 total):**

| Domain | Count | Tools |
|--------|-------|-------|
| Transport & Session | 11 | health_check, get/set_session_info, start/stop_playback, set_tempo, undo, redo, get/set_metronome, get_cpu_load |
| Track Management | 20 | get_track_info, get/set_track_color, create_midi/audio_track, delete/duplicate_track, set_track_name/mute/solo/arm/volume/pan/color/monitoring, select_track, unarm_all, create_group_track, freeze/flatten_track |
| Clip Operations | 19 | create/delete/fire/stop/duplicate_clip, get_clip_notes, set_clip_name, get/set_clip_color, get/set_clip_loop, select_clip, get/set_clip_gain, get/set_clip_pitch, get_clip_warp_info, set_clip_warp_mode, fold/unfold_track |
| Note Editing | 5 | add_notes_to_clip, remove_notes, remove_all_notes, transpose_notes |
| Scene Management | 8 | get_all_scenes, create/delete/fire/stop/duplicate_scene, set_scene_name/color |
| Devices | 11 | get/set_device_parameters, toggle/delete_device, load_instrument_or_effect, move_device_left/right, get_device_by_name, get_rack_chains, select_rack_chain, load_drum_kit |
| Sends/Returns/Master | 10 | get_return_tracks, get_return_track_info, get/set_send_level, set_return_volume/pan, get_master_info, set_master_volume/pan, load_item_to_return |
| Browser | 6 | get_browser_tree, get_browser_items_at_path, browse_path, search_browser, load_item_to_track, get_scene_color |
| Recording | 6 | start/stop_recording, toggle_session/arrangement_record, set_overdub, capture_midi |
| Arrangement | 5 | get_arrangement_length, set_arrangement_loop, jump_to_time, get_locators, create/delete_locator |
| Routing | 6 | get/set_track_input/output_routing, get_available_inputs/outputs |
| View & Selection | 5 | get_current_view, focus_view, select_track/scene/clip |
| Warp Markers | 3 | get/add/delete_warp_marker |
| Clip Automation | 3 | get/set/clear_clip_automation |
| Groove Pool | 3 | get_groove_pool, apply/commit_groove |
| AI Helpers | 6 | get_scale_notes, quantize_clip_notes, humanize_clip_timing/velocity, generate_drum_pattern/bassline |

**Quality assessment:** Of 128 tools, roughly 50-60 are genuinely useful for AI music production, 30-40 are useful in niche workflows, and 30-40 are filler that pad the count (separate get/set pairs, color tools, fold/unfold split into two tools, etc.).

**Also includes:** FastAPI REST server (2,131 lines) with rate limiting, API key auth, and command whitelisting for Ollama/OpenAI integration. Max for Live chat device.

### ptaczek/daw-mcp (11 default + 8 opt-in tools)

The most architecturally sophisticated project despite being the smallest. Cross-DAW (Bitwig + Ableton) with a focus exclusively on MIDI clip editing in session view.

**Default tools:**

| Tool | Parameters | Notes |
|------|-----------|-------|
| `get_daws` | — | Probe connections, report status |
| `get_project_info` | `daw?` | BPM, time sig, play/record state |
| `list_tracks` | `daw?` | 1-based indexing |
| `batch_list_clips` | `daw?, trackIndex?, trackIndices?` | Only clips WITH content |
| `batch_create_clips` | `daw?, clips?, overwrite?` | Mode A (auto-find empty) / Mode B (targeted) |
| `batch_delete_clips` | `daw?, clips?` | Per-item error collection |
| `set_clip_length` | `daw?, trackIndex?, slotIndex?, lengthInBeats` | |
| `batch_get_notes` | `daw?, trackIndex?, slotIndex?, clips?, verbose?` | Lean `[x,y,vel,dur]` arrays by default |
| `batch_set_notes` | `daw?, trackIndex?, slotIndex?, notes` | Auto-detects lean vs object format |
| `batch_clear_notes` | `daw?, trackIndex?, slotIndex?, notes?` | Specific notes or all |
| `get_clip_stats` | `daw?, trackIndex?, slotIndex?` | Tonal.js analysis: chords, scales, key, grid detection |
| `batch_create_euclid_pattern` | `daw?, tracks` | Euclidean rhythm generation across tracks |

**Opt-in tools:** `batch_move_notes`, `batch_set_note_properties` (MPE), `transpose_clip`, `transpose_range`, `batch_create/delete_tracks`, `batch_set_track_properties`, `transport_set_position`.

---

## Part 1b: Community Demand Analysis

Systematic review of GitHub issues and unmerged PRs across competitor repos reveals clear demand signals. These represent real users trying (and failing) to get features added to abandoned projects.

### ahujasid/ableton-mcp: 28 open issues, 14 open PRs

**Feature requests (issues):**

| Issue | Title | Signal |
|-------|-------|--------|
| #13 | Arrangement view | Most requested feature. User describes the exact pain: clips created in session but no way to move to arrangement. Open since Mar 2025. |
| #35 | Read MIDI notes from existing clips | Detailed proposal with use cases: musical continuity, style analysis, intelligent variations. Open since Jun 2025. |
| #7 | Modify instrument/effect/VST parameters | "Adds the instrument but can't change its parameters." Community confirms it's doable via LOM. Open since Mar 2025. |
| #59 | Create Export method | Export functionality. Open since Feb 2026. |
| #19 | Ollama Integration | Local LLM support. Multiple users discuss workarounds (Open WebUI, mcpo adapter, OpenRouter). Open since Apr 2025. |
| #31 | "Hope to see new updates and new functions!" | User frustration with abandonment. Open since May 2025. |
| #14 | Claude hasn't access to samples through the browser | Browser navigation doesn't find samples/user content. Open since Apr 2025. |
| #79 | VST3 third-party plugins fail to load | URI-based loading doesn't work for third-party VST3s. Open since Mar 2026. |
| #58 | set_clip_follow_actions returns success but doesn't persist | Follow action writes silently fail. Open since Feb 2026. |
| #27 | Problems creating beats or melodies | General reliability complaints. Open since May 2025. |

**Unmerged PRs with real feature work:**

| PR | Title | What it adds | Status |
|----|-------|-------------|--------|
| #82 | Arrangement View: full timeline workflow | `switch_to_arrangement_view`, `set_arrangement_time`, `get_arrangement_clips`, `duplicate_to_arrangement`. Uses `duplicate_clip_to_arrangement` (Live 11+ API). | Open, Mar 2026 |
| #73 | Read MIDI notes from existing clips | `get_notes_from_clip` returning pitch/start_time/duration/velocity/mute | Open, Feb 2026 |
| #54 | Read MIDI notes from clips | Same feature, different contributor | Open, Jan 2026 |
| #55 | ASCII grid notation for MIDI patterns | `clip_to_grid`, `grid_to_clip` — human-readable drum pattern format (`KK\|o---o---\|`) | Open, Jan 2026 |
| #67 | Rack device introspection | `get_rack_device_info` with chain summaries, nested rack serialization | Open, Feb 2026 |
| #63 | Refactor: split into handlers/ and tools/ | Modular architecture matching our planned structure. 43 tools across 10 domain modules. | Open, Feb 2026 |
| #52 | Comprehensive controls for tracks, clips, scenes, devices | 60+ new methods, recording, arrangement, audio analysis | Open, Dec 2025 |
| #50 | Rack chain tools and type safety | Audio Effect Rack, chain creation, load effect to chain, master track effects | Open, Nov 2025 |
| #41 | Device parameter control | `get_device_parameters`, `set_device_parameter`, scene management, automation, sends/returns | Open, Aug 2025 |

**Key insight:** Two separate contributors independently submitted "read MIDI notes" PRs (#54 and #73). Combined with the detailed feature request (#35), this is the single most wanted missing feature after arrangement view.

### uisato/ableton-mcp-extended: 3 issues, 4 PRs

Smaller community but same pain points:

| PR | Title | What it adds | Status |
|----|-------|-------------|--------|
| #9 | Audio track import (WAV → Session + Arrangement) | `create_audio_track`, `load_audio_clip`, `place_clip_in_arrangement`. Discovered Ableton 12 API signature change for `create_audio_clip`. | Closed unmerged |
| #10 | Mixer control and device parameter automation | `set_track_volume/panning`, `get/set_device_parameters`, `get_master_meter` | Closed unmerged |
| #6 | Advanced Clip Management & Device Parameter Control | `clear_clip`, `delete_clip`, `remove_notes_from_clip`, `get/set_device_parameters` | Open |
| #8 | Fix macOS installation + docs | 5,258 additions — comprehensive documentation overhaul | Open |

Issues are mostly setup/installation problems (#1, #2) and a ClyphX Pro integration question (#3).

### jpoindexter/ableton-mcp and ptaczek/daw-mcp

Zero issues, zero PRs on both. No community engagement means no demand signals, but also no users to learn from.

### Demand signal summary (ranked by frequency and intensity)

| Rank | Feature | Evidence | Our Phase |
|------|---------|----------|-----------|
| 1 | **Arrangement view** | Issue #13, PR #82, PR #52 (ahujasid); PR #9 (uisato) | **Phase 1** |
| 2 | **Read MIDI notes from clips** | Issue #35, PR #54, PR #73 (ahujasid) — 3 independent efforts | **Phase 1** |
| 3 | **Device parameter control** | Issue #7, PR #41, PR #52 (ahujasid); PR #6, PR #10 (uisato) | **Phase 1** |
| 4 | **Modular architecture / refactoring** | PR #63 (ahujasid) — exact same structure we're planning | Phase 1 (built in) |
| 5 | **Audio track creation + import** | PR #52 (ahujasid); PR #9 (uisato) | Phase 2 |
| 6 | **Rack device introspection** | PR #67, PR #50 (ahujasid) | Phase 2 |
| 7 | **Scene management** | PR #41, PR #52 (ahujasid) | Phase 2 |
| 8 | **Mixer (volume, pan, sends, returns)** | PR #10 (uisato); PR #52 (ahujasid) | Phase 1 (basic), Phase 2 (sends/returns) |
| 9 | **Clip management (delete, clear)** | PR #6 (uisato) | Phase 1 |
| 10 | **Automation / envelopes** | PR #41 (ahujasid) | Phase 2 |
| 11 | **Ollama / local LLM support** | Issue #19 (ahujasid) — 4 commenters with workarounds | Out of scope (MCP is LLM-agnostic) |
| 12 | **VST3 plugin loading** | Issue #79 (ahujasid) | Phase 1 (browser/load tools) |
| 13 | **Export** | Issue #59 (ahujasid) | Phase 3 |
| 14 | **ASCII grid notation** | PR #55 (ahujasid) — creative but niche | Consider post-v1 |

**Validation:** Our Phase 1 tool list (37 tools) covers the top 4 community requests plus basic mixer. The top 3 requests — arrangement view, read MIDI notes, device parameters — are all Phase 1 features that no competitor has shipped. This confirms our prioritization.

---

## Part 2: Architectural Patterns

### What to adopt

**1. Batch-first API design (from ptaczek)**
Every operation accepts single or batch inputs. Reduces round-trips between AI and MCP server. Per-item error collection means one failure doesn't abort the batch.

```python
# Our approach: single AND batch via the same tool
async def add_notes_to_clip(
    track_index: int,
    clip_index: int,
    notes: list[NoteInput],
) -> AddNotesResult: ...
```

**2. Lean note format with auto-detection (from ptaczek)**
Notes as `[pitch, start_time, duration, velocity]` arrays are 10-15x smaller than verbose objects. Critical for LLM context windows. Accept both formats on input.

**3. Newline-delimited JSON framing (from ptaczek)**
All competitors except ptaczek rely on `json.loads()` succeeding on accumulated TCP buffers — fragile. Newline-delimited JSON (`\n` terminators) is simple, robust, and trivial to implement.

**4. Dynamic dispatch via method naming convention (from ptaczek)**
The `handle_{action}` pattern with `getattr` is clean. We should use a similar approach in our Remote Script dispatcher, mapping `category.action` strings to handler methods.

**5. Input validation at the MCP tool layer**
None of the competitors validate inputs properly before sending to Ableton. We should validate track indices, tempo ranges, note values, etc. using Pydantic models with field constraints.

**6. 1-based indexing for user-facing tools (from ptaczek)**
Convert at the boundary with internal `to_internal()`/`to_user()` helpers. Users and LLMs think in 1-based terms.

**7. Typed response models (none of them do this)**
All competitors return raw strings or dicts. We return Pydantic models for every response. This is our key architectural differentiator.

### What to avoid

**1. if/elif command dispatch (ahujasid, uisato, jpoindexter)**
Monolithic dispatch chains are unmaintainable and error-prone. Use a dispatch registry or handler class pattern.

**2. Synchronous sockets in an async MCP server (all three Python projects)**
All competitors use blocking `socket.socket` calls inside their async MCP servers, defeating the purpose of async. We use `asyncio` streams.

**3. Single-file architecture (all projects)**
Every competitor is 1-3 files total. Our `tools/` module pattern with one file per domain is essential for maintainability.

**4. AI-generated bulk code (jpoindexter)**
128 copy-paste tool functions with zero abstraction. Our tools should be concise and share common patterns via helper functions.

**5. Stub commands that never get implemented (uisato)**
Ship tools that work or don't ship them. No placeholders.

**6. No tests (all projects)**
Every competitor has zero tests. Our test suite is a first-class deliverable.

**7. Fire-and-forget UDP without acknowledgment (uisato)**
The UDP server is clever for real-time parameter control, but silent failures make debugging impossible. We'll consider this for Phase 3 if needed.

### TCP protocol design

Based on competitor analysis, our protocol should:

| Aspect | Competitors | Our Approach |
|--------|------------|-------------|
| Port | 9877 (all Python), 8182 (ptaczek) | 9877 (match ecosystem) |
| Framing | Raw JSON accumulation (fragile) | Newline-delimited JSON |
| Request format | `{"type": "...", "params": {...}}` | `{"command": "category.action", "params": {...}, "id": "uuid"}` |
| Response format | `{"status": "...", "result": {...}}` | `{"status": "ok"/"error", "result": {...}, "id": "uuid", "error": {...}}` |
| Threading | Main-thread schedule for writes | Same: `schedule_message(0, callback)` + `queue.Queue` |
| Buffer | 8192 bytes | 65536 bytes (handle large note payloads) |
| Timeout | 10-15s | 30s with configurable override |

---

## Part 3: Definitive Tool List

### Naming conventions

- `get_*` — read-only queries
- `set_*` — property mutations
- `create_*` — object creation
- `delete_*` — object deletion
- Verb-first for actions: `fire_clip`, `start_playback`
- Domain prefix where needed: `clip_*`, `track_*`, `device_*`

### Phase 1: Core (target: first release)

These tools match or exceed the original ahujasid feature set, add arrangement view as our differentiator, and cover the essential production workflow.

#### Session & Transport (6 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `get_session_info` | — | `SessionInfo` (tempo, time sig, track count, is_playing, is_recording, song_length) | `song.tempo`, `.signature_*`, `.is_playing`, `.record_mode`, `.song_length` |
| `set_tempo` | `tempo: float` (20-999) | `TempoResult` | `song.tempo = tempo` |
| `set_time_signature` | `numerator: int, denominator: int` | `TimeSignatureResult` | `song.signature_numerator`, `song.signature_denominator` |
| `start_playback` | — | `TransportResult` | `song.start_playing()` or `song.continue_playing()` |
| `stop_playback` | — | `TransportResult` | `song.stop_playing()` |
| `get_playback_position` | — | `PlaybackPosition` (beats, bars, time) | `song.current_song_time`, `.is_playing` |

#### Track Management (9 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `get_track_info` | `track_index: int` | `TrackInfo` (name, type, mute, solo, arm, volume, pan, devices, clip_slots) | `song.tracks[i].*` |
| `create_midi_track` | `index: int = -1, name: str = None` | `TrackCreatedResult` | `song.create_midi_track(index)` |
| `create_audio_track` | `index: int = -1, name: str = None` | `TrackCreatedResult` | `song.create_audio_track(index)` |
| `delete_track` | `track_index: int` | `TrackDeletedResult` | `song.delete_track(index)` |
| `duplicate_track` | `track_index: int` | `TrackDuplicatedResult` | `song.duplicate_track(index)` |
| `set_track_name` | `track_index: int, name: str` | `TrackUpdatedResult` | `track.name = name` |
| `set_track_mute` | `track_index: int, mute: bool` | `TrackUpdatedResult` | `track.mute = mute` |
| `set_track_solo` | `track_index: int, solo: bool` | `TrackUpdatedResult` | `track.solo = solo` |
| `set_track_arm` | `track_index: int, arm: bool` | `TrackUpdatedResult` | `track.arm = arm` |

#### Clip Operations (7 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `create_clip` | `track_index, clip_index, length: float = 4.0, name: str = None` | `ClipCreatedResult` | `slot.create_clip(length)` |
| `delete_clip` | `track_index, clip_index` | `ClipDeletedResult` | `slot.delete_clip()` |
| `duplicate_clip` | `track_index, clip_index` | `ClipDuplicatedResult` | `slot.duplicate_clip_to(...)` |
| `set_clip_name` | `track_index, clip_index, name` | `ClipUpdatedResult` | `clip.name = name` |
| `fire_clip` | `track_index, clip_index` | `ClipFiredResult` | `slot.fire()` |
| `stop_clip` | `track_index, clip_index` | `ClipStoppedResult` | `slot.stop()` |
| `get_clip_info` | `track_index, clip_index` | `ClipInfo` (name, length, is_playing, is_midi, loop settings) | `clip.*` |

#### MIDI Note Editing (4 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `get_clip_notes` | `track_index, clip_index` | `ClipNotes` (list of note objects) | `clip.get_notes_extended(0, 128, 0.0, clip.length)` |
| `add_notes_to_clip` | `track_index, clip_index, notes: list[NoteInput]` | `NotesAddedResult` | `clip.add_new_notes(tuple(specs))` |
| `remove_notes` | `track_index, clip_index, from_pitch: int = 0, pitch_span: int = 128, from_time: float = 0.0, time_span: float = None` | `NotesRemovedResult` | `clip.remove_notes_extended(...)` |
| `set_clip_notes` | `track_index, clip_index, notes: list[NoteInput]` | `NotesSetResult` | `clip.remove_notes_extended(...)` then `clip.add_new_notes(...)` (replace all) |

`NoteInput` accepts both lean format `[pitch, start_time, duration, velocity]` and object format `{pitch, start_time, duration, velocity, mute?, velocity_deviation?, probability?}`.

#### Device Management (4 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `get_device_parameters` | `track_index, device_index` | `DeviceParameters` (list of param objects with name, value, min, max, is_quantized) | `device.parameters[*].*` |
| `set_device_parameter` | `track_index, device_index, parameter_index, value: float` | `ParameterSetResult` | `param.value = value` |
| `load_instrument` | `track_index, uri: str` | `InstrumentLoadedResult` | `browser.load_item(item)` |
| `load_effect` | `track_index, uri: str, position: int = -1` | `EffectLoadedResult` | `browser.load_item(item)` |

#### Browser (3 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `get_browser_tree` | `category: str = "all"` | `BrowserTree` (hierarchical categories) | `browser.instruments/sounds/drums/audio_effects/midi_effects` |
| `get_browser_items` | `path: str` | `BrowserItems` (list of items with name, uri, is_loadable) | `browser.{category}.children` navigation |
| `search_browser` | `query: str, category: str = "all"` | `BrowserSearchResult` | Recursive name matching |

#### Mixer (4 tools)

| Tool | Parameters | Returns | LOM Calls |
|------|-----------|---------|-----------|
| `set_track_volume` | `track_index, volume: float` (0.0-1.0) | `MixerUpdatedResult` | `track.mixer_device.volume.value = volume` |
| `set_track_pan` | `track_index, pan: float` (-1.0 to 1.0) | `MixerUpdatedResult` | `track.mixer_device.panning.value = pan` |
| `get_master_info` | — | `MasterTrackInfo` | `song.master_track.*` |
| `set_master_volume` | `volume: float` | `MixerUpdatedResult` | `song.master_track.mixer_device.volume.value = volume` |

**Phase 1 total: 37 tools** — covers transport, tracks, clips, notes, devices, browser, and basic mixing.

### Phase 2: Extended Capabilities

These tools add scene management, arrangement view (our key differentiator), sends/returns, recording, and clip properties.

#### Scene Management (5 tools)
- `get_scenes` — list all scenes with names and indices
- `create_scene` — create at index
- `delete_scene` — delete by index
- `fire_scene` — launch scene
- `set_scene_name` — rename scene

#### Arrangement View (5 tools)
- `get_arrangement_clips` — list arrangement clips for a track or all tracks
- `create_arrangement_clip` — create clip at time position
- `move_arrangement_clip` — move clip to new position/track
- `get_arrangement_length` — total arrangement length
- `set_arrangement_loop` — loop start, end, enabled

#### Sends & Returns (4 tools)
- `get_return_tracks` — list return tracks
- `set_send_level` — track_index, send_index, level
- `set_return_volume` — return_index, volume
- `set_return_pan` — return_index, pan

#### Recording (4 tools)
- `start_recording` — begin recording
- `stop_recording` — stop recording
- `capture_midi` — capture recently played MIDI
- `set_overdub` — toggle overdub mode

#### Clip Properties (4 tools)
- `set_clip_loop` — loop_start, loop_end, looping
- `set_clip_color` — clip color index
- `get_clip_automation` — read clip envelope
- `set_clip_automation` — write clip envelope points

#### Undo (2 tools)
- `undo` — undo last action
- `redo` — redo last undone action

**Phase 2 total: 24 tools** (cumulative: 61 tools)

### Phase 3: Advanced

These tools cover niche but valuable capabilities. Prioritized based on community requests across competitor repos.

#### Routing (4 tools)
- `get_track_routing` — input/output routing info
- `set_track_input_routing` — routing type and channel
- `set_track_output_routing` — routing type and channel
- `get_available_routing` — available inputs/outputs for a track

#### Audio Clip Operations (3 tools)
- `set_clip_gain` — audio clip gain in dB
- `set_clip_pitch` — audio clip pitch in semitones
- `set_clip_warp_mode` — warp mode selection

#### Markers & Navigation (3 tools)
- `get_locators` — list cue points
- `create_locator` — add a cue point at time
- `jump_to_time` — move playhead

#### Track Grouping (2 tools)
- `create_group_track` — group multiple tracks
- `fold_group` — fold/unfold group track

#### Groove Pool (2 tools)
- `get_groove_pool` — list available grooves
- `apply_groove` — apply groove to clip

**Phase 3 total: 14 tools** (cumulative: 75 tools)

### Explicitly excluded

These features are either impractical, out of scope, or better solved differently:

| Feature | Reason |
|---------|--------|
| AI music helpers (scale notes, drum pattern generation) | The AI can compute these directly; no need to round-trip to Ableton |
| ElevenLabs / TTS integration | Out of scope; separate MCP server if needed |
| REST API server | We're MCP-focused; REST can be a separate project |
| Max for Live device | Nice-to-have but not core; consider post-v1 |
| UDP real-time parameter server | Premature optimization; TCP is sufficient for v1 |
| Cross-DAW support | Ableton-focused; different DAWs have fundamentally different APIs |
| Per-note MPE properties | Niche; few Ableton instruments support full MPE |
| View/selection management | Cosmetic; the producer manages their own UI |
| Cosmetic tools (colors, fold/unfold) | Low value for AI interaction |

---

## Part 4: Remote Script Command Mapping

Each MCP tool maps to exactly one Remote Script command. The Remote Script organizes handlers by domain.

### Handler structure

```
remote_script/AbletonLiveMCP/
├── __init__.py          # ControlSurface, TCP server, main-thread scheduling
├── dispatcher.py        # Routes "category.action" → handler method
├── handlers/
│   ├── __init__.py
│   ├── base.py          # BaseHandler with schedule_message helpers
│   ├── session.py       # SessionHandler: get_info, set_tempo, transport
│   ├── track.py         # TrackHandler: CRUD, properties, mixer
│   ├── clip.py          # ClipHandler: CRUD, notes, properties
│   ├── device.py        # DeviceHandler: parameters, loading
│   ├── browser.py       # BrowserHandler: tree, search, navigation
│   ├── scene.py         # SceneHandler: Phase 2
│   ├── arrangement.py   # ArrangementHandler: Phase 2
│   └── mixer.py         # MixerHandler: sends, returns, master
```

### Command naming

Commands use `category.action` dot notation (adopted from ptaczek):

| MCP Tool | Remote Script Command |
|----------|---------------------|
| `get_session_info` | `session.get_info` |
| `set_tempo` | `session.set_tempo` |
| `start_playback` | `session.start_playback` |
| `get_track_info` | `track.get_info` |
| `create_midi_track` | `track.create_midi` |
| `create_audio_track` | `track.create_audio` |
| `delete_track` | `track.delete` |
| `duplicate_track` | `track.duplicate` |
| `set_track_name` | `track.set_name` |
| `set_track_mute` | `track.set_mute` |
| `set_track_solo` | `track.set_solo` |
| `set_track_arm` | `track.set_arm` |
| `create_clip` | `clip.create` |
| `add_notes_to_clip` | `clip.add_notes` |
| `get_clip_notes` | `clip.get_notes` |
| `get_device_parameters` | `device.get_parameters` |
| `set_device_parameter` | `device.set_parameter` |
| `load_instrument` | `browser.load_instrument` |
| `get_browser_tree` | `browser.get_tree` |

### Threading model (same as competitors, proven pattern)

- TCP server runs in a daemon thread
- Each client gets its own daemon thread
- Read-only commands (`get_*`) execute on the client thread
- Write commands are scheduled on the main thread via `schedule_message(0, callback)` with `queue.Queue` for response synchronization (30s timeout)

---

## Part 5: Competitive Positioning Summary

### Why we will win

| Dimension | Competitors | Ableton Live MCP |
|-----------|------------|------------|
| Architecture | 1-3 monolithic files, if/elif dispatch | Modular packages, typed registry |
| Protocol | Raw dict construction, string command types | Pydantic models, typed commands |
| Testing | Zero tests across all 4 projects | pytest + pytest-asyncio from day one |
| CI | None | GitHub Actions on every push |
| Error handling | Catch-all try/except returning strings | Typed error responses with codes |
| Async | Synchronous sockets in async servers | Native asyncio TCP client |
| Arrangement view | Not implemented by anyone | Phase 1 core feature |
| Maintenance | All abandoned or barely maintained | Active, responsive |
| Documentation | Setup READMEs only | API reference, architecture docs, ADRs |

### Our unique contributions
1. **Arrangement-first**: no competitor has working arrangement view support
2. **Quality engineering**: typed protocol, tests, CI — unprecedented in this space
3. **Lean note format**: adopted from ptaczek, reduces token usage 10-15x
4. **Batch operations**: adopted from ptaczek, reduces round-trips
5. **Newline-delimited JSON framing**: robust protocol, not fragile JSON accumulation
6. **Active maintenance**: the bar is zero — just showing up is a differentiator

## Decision

Implement the phased tool roadmap defined in Part 3. Phase 1 (37 tools) covers transport, tracks, clips, notes, devices, browser, and mixing — matching the original's scope while adding arrangement view, device parameters, and audio tracks. Adopt batch-first API, lean note format, newline-delimited JSON, and typed protocol as architectural foundations.

## Consequences

**Positive:**
- Clear implementation target: 37 tools for Phase 1 with exact parameters and LOM calls defined
- Architectural patterns validated by analyzing 4 competitor implementations
- No competitor has arrangement view, device parameters, AND tests — we'll be the first
- Phased approach allows shipping quickly while planning ahead

**Negative:**
- 37 tools is still significant implementation effort
- Lean note format adds complexity (auto-detection, dual format support)
- Newline-delimited JSON is a different protocol than what existing users might expect from ahujasid
- 1-based indexing adds conversion overhead at protocol boundary

**Risks:**
- jpoindexter could gain traction if users don't care about code quality
- New competitors (dawpilot-mcp, nicholasbien/ableton-mcp-pro) could emerge with similar ideas
- Arrangement view API may have undocumented limitations in the LOM
