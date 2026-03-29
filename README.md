# Ableton Live MCP

[![CI](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml)

> **🚧 Work in Progress** — Ableton Live MCP is usable today for the current shipped tool surface: **session/transport/recording with undo/redo**, **track management including explicit main/return/master addressing and routing**, **scene management**, **session clip**, **session and arrangement audio import**, **clip properties, clip automation, and audio clip gain/pitch/warp editing**, **MIDI note**, **arrangement clip and locator**, **browser**, **device/parameter**, **groove pool**, and **mixer tools including sends/returns and return-track control** are implemented. More domains are still in flight. Follow along on the [project board](https://github.com/users/malmazuke/projects/1) to see what's being built.

Control Ableton Live with AI. Ask your AI assistant to create tracks, add clips, tweak devices, mix — anything you'd normally do by hand in Ableton.

Ableton Live MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that connects AI assistants like Cursor and Claude directly to Ableton Live 12, giving them access to the full [Live Object Model](https://docs.cycling74.com/apiref/lom).

## What can you do with it?

Today you can already open a chat in Cursor or Claude and ask for operations like:

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

The communication layer between the MCP server and Ableton's Remote Script is built and tested. The current implementation now includes transport/session/recording with undo/redo, track management and routing, explicit scoped track addressing for main/return/master info and supported mutations, scene management, session clips, audio file import to session and arrangement, clip loop/color editing, audio clip gain/pitch/warp editing, clip automation read/write, MIDI notes, arrangement clips and locators, browser navigation including plug-ins, device parameters, groove pool access, and mixer control for track volume/pan, sends, return tracks, and master volume. Remaining work focuses on the rest of the roadmap such as broader return/master mutation coverage.

See the [project board](https://github.com/users/malmazuke/projects/1) for detailed progress and planned work.

## Known limitations

- `set_tempo` style commands can change the current song tempo at runtime.
- Native Arrangement tempo automation on the Main track is **not** currently supported.
- On Ableton Live 12.2.5, Live exposes `song.tempo` for direct tempo changes, but does not expose a supported public runtime API for creating or editing the Main track's tempo automation envelope.
- Because of that limitation, Ableton Live MCP does **not** attempt to patch `.als` files, drive the Live UI, or require extra OS permissions just to emulate tempo automation. If Ableton exposes a supported API for this in a future Live release, the feature can be revisited.

**Planned capabilities:**

| Area | Examples |
|------|----------|
| Transport & session | Play, stop, record, set tempo, time signature, loop |
| Tracks | Broader return/master mutation coverage, grouping, and fold operations |
| Arrangement clips | Create, move, import, and edit clips in arrangement view |
| Session clips | Fire, stop, import, and manage clips in session view |
| Devices & parameters | Load instruments/effects, read and tweak parameters |
| Scenes | Create, fire, and manage scenes |
| Mixing | Volume, pan, sends, solo, mute, arm |

## Contributing

This project is in its early stages and contributions are welcome. Check the [project board](https://github.com/users/malmazuke/projects/1) to see what's in progress and what's coming next.

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync          # install dependencies
uv run pytest    # run tests
```

## License

MIT — see [LICENSE](LICENSE).
