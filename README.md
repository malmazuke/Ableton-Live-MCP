# Ableton Live MCP

[![CI](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml)

Control Ableton Live from Claude, Cursor, or any other MCP client.

Ableton Live MCP lets an AI assistant operate a real Live set directly: create
and edit clips, work with MIDI notes, load instruments and effects, adjust the
mix, browse Live's content tree, manage scenes and tracks, and automate common
production tasks without relying on screen automation.

If you want an assistant that can act on the set instead of just telling you
what to click, this is the bridge.

Tested against Ableton Live 12.2.5.

## Example prompts

- "Create a 4-bar MIDI clip with a Cm7 chord progression on track 2."
- "Load Analog on the selected synth track and turn the filter cutoff down."
- "Import this drum loop into slot 1 on track 5."
- "Set the tempo to 128, loop bars 1 through 8, and start playback."
- "Solo the bass, pull the vocal send down 3 dB, and add a reverb to the return."

## Quick start

### Requirements

- Python 3.10+
- `uv`
- Ableton Live 12
- Cursor, Claude Desktop, or another MCP client

### 1. Clone the repo and install dependencies

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
```

### 2. Install the Remote Script

```bash
uv run mcp-ableton-setup
```

By default this installs `remote_script/AbletonLiveMCP` into Ableton's Remote
Scripts directory as a symlink. For copy installs, manual installation,
platform-specific paths, uninstall steps, and troubleshooting, see the
[installation guide](docs/installation.md).

### 3. Enable it in Ableton Live

1. Open Ableton Live.
2. Go to `Preferences > Link, Tempo & MIDI`.
3. In an empty `Control Surface` slot, choose `AbletonLiveMCP`.
4. Set both `Input` and `Output` to `None`.

When it loads correctly, Ableton should start listening on `127.0.0.1:9877`.

### 4. Add the MCP server to your client

Cursor:

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "uv",
      "args": ["run", "--directory", "${workspaceFolder}", "mcp-ableton"]
    }
  }
}
```

Claude Desktop:

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/Ableton-Live-MCP", "mcp-ableton"]
    }
  }
}
```

### 5. Verify the connection

Open a chat in your MCP client and ask for something simple, such as:

- "Get the current Ableton session info."
- "List my tracks and current tempo."

## Feature overview

- **Session and transport**: session info, playback position, playback
  control, tempo, time signature, recording, overdub, capture MIDI, undo, redo
- **Tracks and mixer**: track creation and deletion, rename, mute, solo, arm
  where supported, routing, volume, pan, sends, returns, and master control
- **Scenes**: list, create, duplicate, rename, fire, stop, and delete scenes
- **Clips and notes**: session clip creation, duplication, deletion, launch,
  stop, rename, audio import, note read/write, clip loop and color editing,
  clip automation, and audio clip gain/pitch/warp controls
- **Arrangement**: arrangement clip listing, creation, movement, loop control,
  locator management, arrangement audio import, and take-lane support
- **Devices and browser**: browser tree/items/search, plug-in browser support,
  instrument/effect loading, and device parameter read/write
- **Grooves**: groove pool listing and groove application

## Limitations

- Main-track Arrangement tempo automation is not currently supported by a
  public runtime API in Live 12.2.5.
- Live 12.2.5 exposes fold state and grouping metadata for existing group
  tracks, but not a supported public API for creating new group tracks or
  regrouping existing tracks.

## Documentation

- [Installation guide](docs/installation.md)

## Contributing

Contributions are welcome. If you want to extend the tool surface or report a
runtime limitation, open an issue or PR.

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
