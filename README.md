# Ableton Live MCP

[![CI](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml)

> **Shipped and actively maintained** — Ableton Live MCP now provides a broad, tested MCP surface for Ableton Live 12.2.5: **session/transport/recording with undo/redo**, **track management including routing, explicit main/return/master addressing, and group-track folding**, **scene management**, **session clips**, **session, arrangement, and take-lane audio import**, **clip properties, clip automation, and audio clip gain/pitch/warp editing**, **MIDI notes**, **arrangement clips, take lanes, and locators**, **browser navigation including plug-ins**, **device/parameter control**, **groove pool**, and **mixer tools including sends/returns and master control**. Follow the [project board](https://github.com/users/malmazuke/projects/1) for follow-on extensions and runtime-limited gaps.

Control Ableton Live with AI. Ask your AI assistant to create tracks, add clips, tweak devices, mix — anything you'd normally do by hand in Ableton.

Ableton Live MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that connects AI assistants like Cursor and Claude directly to Ableton Live 12, giving them a broad, typed control surface over the [Live Object Model](https://docs.cycling74.com/apiref/lom).

## What can you do with it?

With the current `main` branch you can open a chat in Cursor or Claude and ask for operations like:

- *"Create a 4-bar MIDI clip with a Cm7 chord progression"*
- *"Add a reverb to track 3 and set the decay to 2.5 seconds"*
- *"Set the tempo to 128 and loop bars 1–8"*
- *"Solo the bass track and raise its volume to -3 dB"*

The AI assistant will execute supported commands directly in your running Ableton Live session.

## How it works

```
AI Assistant ◄── MCP (stdio) ──► MCP Server ◄── TCP :9877 ──► Remote Script inside Ableton Live
```

Two components work together:

- **MCP Server** — a Python process that translates AI assistant requests into commands for Ableton. Built with the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
- **Remote Script** — a Python control surface that runs inside Ableton Live, listens for commands over TCP, and executes them against the Live Object Model.

## Getting started

### Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Ableton Live 12 (any edition)
- macOS or Windows
- [Cursor](https://cursor.com) or [Claude Desktop](https://claude.ai/download)

### 1. Clone and install dependencies

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
```

### 2. Install the Remote Script

The setup tool automatically finds your Ableton Remote Scripts directory and creates a symlink:

```bash
uv run mcp-ableton-setup
```

This installs the `AbletonLiveMCP` Remote Script into Ableton's Remote Scripts
directory. The default `symlink` method keeps the installed script in sync with
the repository.

<details>
<summary>Setup options</summary>

```bash
uv run mcp-ableton-setup --dry-run        # preview without making changes
uv run mcp-ableton-setup --method copy     # copy files instead of symlink
uv run mcp-ableton-setup --target /path    # override auto-detected directory
uv run mcp-ableton-setup --uninstall       # remove the Remote Script
```

</details>

<details>
<summary>Manual installation (fallback)</summary>

If the setup tool doesn't work for your system, install the Remote Script
manually:

**macOS:**
```bash
cp -r remote_script/AbletonLiveMCP ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

**Windows:**
```powershell
Copy-Item -Recurse remote_script\AbletonLiveMCP "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts\"
```

</details>

### 3. Configure Ableton Live

1. Open (or restart) Ableton Live 12
2. Go to **Preferences** (Cmd+, on macOS)
3. Navigate to **Link, Tempo & MIDI**
4. In an empty **Control Surface** slot, select **AbletonLiveMCP**
5. Set both **Input** and **Output** to **None**

You should briefly see `AbletonLiveMCP: listening on port 9877` in the status
bar, and Ableton's log should record the TCP server starting on `127.0.0.1:9877`.

### 4. Configure your AI assistant

**Cursor:**

Create `.cursor/mcp.json` in the repo and add:

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

For a global Cursor config, replace `${workspaceFolder}` with the absolute path
to your cloned repository.

**Claude Desktop:**

Edit your config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

### 5. Verify

1. Make sure Ableton Live is running with the Remote Script active (check the status bar)
2. Open a new chat in your AI assistant
3. Try: *"Get information about my current Ableton session"*

For the full install guide, Windows notes, uninstall flow, and troubleshooting,
see [docs/installation.md](docs/installation.md).

### Uninstalling

Remove the Remote Script from Ableton:

```bash
uv run mcp-ableton-setup --uninstall
```

Then remove the MCP server configuration from your AI assistant's settings.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Remote Script not appearing in Ableton | Restart Ableton and confirm `AbletonLiveMCP` exists under your `Remote Scripts` directory. |
| "Connection refused" errors | Make sure Ableton is running, `AbletonLiveMCP` is selected as a control surface, and something is listening on port `9877`. |
| Port 9877 already in use | Find the conflicting process and stop it, then reload the control surface. |
| Setup tool can't find Remote Scripts directory | Create the default `Remote Scripts` directory first or pass `--target`. |
| Changes not reflected after git pull | Re-run the installer for copy installs; restart Ableton and clear `__pycache__` for symlink installs if needed. |

See [docs/installation.md](docs/installation.md) for the canonical install and
troubleshooting guide.

## Current status

Ableton Live MCP now ships a broad, tested control surface on `main` for Ableton Live 12.2.5. The core communication layer, tool surface, tests, and CI are all in place.

| Area | What ships on `main` |
|------|----------------------|
| Transport & session | Session info, playback position, tempo, time signature, playback, recording, overdub, capture MIDI, undo, redo |
| Tracks & mixing | Track CRUD, mute/solo/arm where supported, explicit `main`/`return`/`master` addressing, routing, volume/pan, sends/returns, master control, group-track fold support |
| Session clips | Create, duplicate, delete, fire, stop, rename, inspect, import audio, and edit MIDI notes |
| Arrangement & take lanes | Arrangement clip listing/creation/move, arrangement length/loop, locators, take-lane listing/creation/rename, take-lane MIDI clip creation, take-lane audio import |
| Clip editing | Clip loop/color, clip automation read/write, audio clip gain/pitch/warp editing |
| Devices & browser | Browser tree/items/search, instrument/effect loading, plug-in browser support, device parameter read/write |
| Scenes & grooves | Scene management, groove pool listing, groove application |

The remaining backlog is mostly post-v1 extensions and runtime-limited features rather than core missing domains.

See the [project board](https://github.com/users/malmazuke/projects/1) for detailed progress, follow-on work, and runtime-limited investigations.

## Known limitations

- `set_tempo` style commands can change the current song tempo at runtime.
- Native Arrangement tempo automation on the Main track is **not** currently supported.
- On Ableton Live 12.2.5, Live exposes `song.tempo` for direct tempo changes, but does not expose a supported public runtime API for creating or editing the Main track's tempo automation envelope.
- Because of that limitation, Ableton Live MCP does **not** attempt to patch `.als` files, drive the Live UI, or require extra OS permissions just to emulate tempo automation. If Ableton exposes a supported API for this in a future Live release, the feature can be revisited.
- Live 12.2.5 exposes fold state and grouping metadata for existing group tracks, but not a supported public API for creating new group tracks or regrouping existing tracks.

## Follow-on work

The project board now tracks follow-on extensions, post-v1 experiments, and runtime-limited investigations rather than a missing core MCP surface. That includes areas such as broader return/master mutation coverage and any future Live APIs for true group-track creation or Main-track tempo automation.

## Contributing

The core MCP surface is now shipped and contributions are welcome. Check the [project board](https://github.com/users/malmazuke/projects/1) for follow-on work, extensions, and runtime-limited investigations.

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync          # install dependencies
uv run pytest    # run tests
```

## License

MIT — see [LICENSE](LICENSE).
