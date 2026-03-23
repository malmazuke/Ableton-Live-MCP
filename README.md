# Ableton Live MCP

[![CI](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/malmazuke/Ableton-Live-MCP/actions/workflows/ci.yml)

> **🚧 Work in Progress** — This project is in early development and is not yet functional. The communication infrastructure between the MCP server and Ableton is in place, but no tools are available yet. Follow along on the [project board](https://github.com/users/malmazuke/projects/1) to see what's being built.

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

- Python 3.10+
- Ableton Live 12 (any edition)
- macOS or Windows
- [Cursor](https://cursor.com) or [Claude Desktop](https://claude.ai/download)

### 1. Install the MCP server

```bash
pip install mcp-ableton
```

### 2. Install the Remote Script

Copy into Ableton's Remote Scripts folder:

```bash
# macOS
cp -r remote_script/AbletonLiveMCP/ ~/Music/Ableton/User\ Library/Remote\ Scripts/

# Windows
xcopy remote_script\AbletonLiveMCP "%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\AbletonLiveMCP" /E /I
```

### 3. Enable in Ableton

Open Preferences → Link, Tempo & MIDI → set a Control Surface slot to **AbletonLiveMCP** (Input/Output: None).

### 4. Connect your AI assistant

Add the server to your MCP config:

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "mcp-ableton"
    }
  }
}
```

In **Cursor**, add this under Settings → MCP. For **Claude Desktop**, add it to your Claude config file.

## Current status

The communication layer between the MCP server and Ableton's Remote Script is built and tested. What's next is implementing the actual tools — track creation, clip manipulation, device control, mixing, and more.

See the [project board](https://github.com/users/malmazuke/projects/1) for detailed progress and planned work.

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
