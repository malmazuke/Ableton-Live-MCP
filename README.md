# Ableton Live MCP

[![CI](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml)

> **🚧 Work in Progress** — This project is in early development. The MCP server and Remote Script can talk over TCP; **session/transport**, **track management**, **session clip**, **MIDI note**, and **browser** MCP tools are implemented, with more domains coming. Follow along on the [project board](https://github.com/users/malmazuke/projects/1) to see what's being built.

Control Ableton Live with AI. Ask your AI assistant to create tracks, add clips, tweak devices, mix — anything you'd normally do by hand in Ableton.

Ableton Live MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that connects AI assistants like Cursor and Claude directly to Ableton Live 12, giving them access to the full [Live Object Model](https://docs.cycling74.com/apiref/lom).

## What will this look like?

Once complete, you'll be able to open a chat in Cursor or Claude and say things like:

- *"Create a 4-bar MIDI clip with a Cm7 chord progression"*
- *"Add a reverb to track 3 and set the decay to 2.5 seconds"*
- *"Set the tempo to 128 and loop bars 1–8"*
- *"Solo the bass track and raise its volume to -3 dB"*

The AI assistant will execute these directly in your running Ableton Live session — no copy-pasting, no manual clicking.

## How it works

```
AI Assistant ◄── MCP (stdio) ──► MCP Server ◄── TCP :9877 ──► Remote Script inside Ableton Live
```

Two components work together:

- **MCP Server** — a Python process that translates AI assistant requests into commands for Ableton. Built with the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
- **Remote Script** — a Python control surface that runs inside Ableton Live, listens for commands over TCP, and executes them against the Live Object Model.

## Getting started

> These instructions describe the intended setup flow. Since the project is still in early development, they won't produce a working system yet — but they show where things are headed.

### Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Ableton Live 12 (any edition)
- macOS (Windows support coming soon)
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

This keeps the Remote Script in sync with the repository -- any updates you pull will be reflected immediately.

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

If the setup tool doesn't work for your system, copy the Remote Script manually:

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

You should see `AbletonLiveMCP: Listening for commands on port 9877` in the status bar at the bottom of the Ableton window.

### 4. Configure your AI assistant

**Cursor:**

Go to Settings > MCP > Add new MCP server, then enter:

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

Replace `/path/to/Ableton-Live-MCP` with the actual path to your cloned repository.

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

### Uninstalling

Remove the Remote Script from Ableton:

```bash
uv run mcp-ableton-setup --uninstall
```

Then remove the MCP server configuration from your AI assistant's settings.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Remote Script not appearing in Ableton | Restart Ableton after running the setup tool. Check that the symlink/directory exists in your Remote Scripts folder. |
| "Connection refused" errors | Make sure Ableton Live is running and the AbletonLiveMCP control surface is selected in Preferences. |
| Port 9877 already in use | Another instance may be running. Close other Ableton instances or applications using that port. |
| Setup tool can't find Remote Scripts directory | Use `--target /path/to/Remote\ Scripts` to specify the directory manually. |
| Changes not reflected after git pull | If you installed with `--method copy`, re-run `uv run mcp-ableton-setup` to update. Symlink installs update automatically. |

For more detailed instructions, see [docs/installation.md](docs/installation.md).

## Current status

The communication layer between the MCP server and Ableton's Remote Script is built and tested. What's next is implementing the actual tools — track creation, clip manipulation, device control, mixing, and more.

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
| Tracks | Create MIDI/audio tracks, rename, delete, configure routing |
| Arrangement clips | Create, move, and edit clips in arrangement view |
| Session clips | Fire, stop, and manage clips in session view |
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
