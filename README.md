# AbletonMCP

Control Ableton Live programmatically through AI assistants using the [Model Context Protocol](https://modelcontextprotocol.io).

A Python MCP server and Remote Script that give AI assistants like Cursor and Claude direct access to Ableton Live's full API -- arrangement view, session view, tracks, devices, mixing, and more.

## Architecture

```
┌─────────────────┐                    ┌──────────────────────┐
│  AI Assistant    │  stdio (MCP)       │  Python MCP Server   │
│  (Cursor/Claude) │◄──────────────────►│                      │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                          TCP :9877 (JSON)
                                                  │
                                       ┌──────────▼───────────┐
                                       │  Python Remote Script │
                                       │  (inside Ableton)     │
                                       └──────────┬───────────┘
                                                  │
                                          Live Object Model
                                                  │
                                       ┌──────────▼───────────┐
                                       │    Ableton Live 12    │
                                       └──────────────────────┘
```

**Two independent components:**

- **MCP Server** -- a Python process that speaks MCP (JSON-RPC over stdio) with AI clients and communicates with Ableton via TCP. Built with the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).
- **Remote Script** -- runs inside Ableton Live's embedded Python runtime as a ControlSurface. Receives JSON commands over TCP, executes them against the [Live Object Model](https://docs.cycling74.com/apiref/lom), and returns results.

## Features

### Arrangement View (first-class support)
- Create, read, and delete MIDI/audio clips at any position
- Add and retrieve notes from arrangement clips
- Set clip properties (name, color, loop settings)

### Session View
- Create, fire, stop, and manage session clips
- Scene management (create, delete, fire, rename)

### Tracks
- Create and configure MIDI and audio tracks
- Control volume, panning, mute, solo, arm
- Input/output routing

### Devices & Parameters
- List devices on any track
- Read and write device parameters in real-time
- Load instruments and effects from Ableton's browser

### Transport & Session
- Start, stop, record
- Set tempo and time signature
- Loop control, song position

### Mixing
- Track volumes and panning
- Send levels and return tracks

## Requirements

- Python 3.10+
- Ableton Live 12 (any edition)
- macOS or Windows
- Cursor IDE or Claude Desktop

## Project Structure

```
AbletonMCP/
  pyproject.toml                        -- Python package manifest
  src/
    ableton_mcp/
      __init__.py
      server.py                         -- MCP server setup, tool registration
      connection.py                     -- async TCP client
      protocol.py                       -- typed request/response models
      tools/
        session.py                      -- transport, tempo, time signature
        track.py                        -- track CRUD and properties
        clip.py                         -- arrangement + session clips
        device.py                       -- devices and parameters
        scene.py                        -- scene management
        browser.py                      -- browser navigation and loading
        mixer.py                        -- volume, pan, sends
  tests/
    test_connection.py
    test_protocol.py
    tools/
  remote_script/
    AbletonMCP/
      __init__.py                       -- Ableton Remote Script
  docs/
    installation.md
    decisions/
```

## Installation

> Detailed installation guide coming soon. See [docs/installation.md](docs/installation.md).

### Quick Start

1. **Install the MCP server:**
   ```bash
   pip install ableton-mcp
   ```

2. **Install the Remote Script** into Ableton's User Library:
   ```bash
   cp -r remote_script/AbletonMCP/ ~/Music/Ableton/User\ Library/Remote\ Scripts/
   ```

3. **Configure Ableton:** Preferences > Link, Tempo & MIDI > set Control Surface to "AbletonMCP", Input/Output to "None".

4. **Add to Cursor:** Settings > MCP > add server:
   ```json
   {
     "mcpServers": {
       "AbletonMCP": {
         "command": "ableton-mcp"
       }
     }
   }
   ```

5. **Try it:** "Create a MIDI clip in arrangement at bar 1 with a Cm7 chord."

## Design Principles

- **Arrangement-first** -- most producers work in arrangement view. It's a first-class citizen, not an afterthought.
- **Typed protocol** -- the JSON protocol between MCP server and Remote Script uses Pydantic models. No stringly-typed command construction.
- **Registry pattern** -- tools are registered declaratively, not routed through if/elif chains.
- **Async native** -- the MCP server uses asyncio throughout. No blocking I/O.
- **Comprehensive coverage** -- targeting the full Live Object Model, not just the basics.

## Roadmap

See the [AbletonMCP Roadmap](https://github.com/users/malmazuke/projects/1) project board for current status and planned work.

**Phase 1 -- Core:** Communication layer, transport, tracks, arrangement + session clips, devices.
**Phase 2 -- Extended:** Scenes, browser, audio import, mixer, automation.
**Phase 3 -- Advanced:** Routing, group tracks, take lanes, locators, groove pool, undo/redo.

## Tech Stack

- **MCP Server:** Python 3.10+, [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk), Pydantic
- **Remote Script:** Python 3 (Ableton's embedded runtime), `_Framework.ControlSurface`
- **Protocol:** JSON over TCP (port 9877)
- **CI:** GitHub Actions

## License

MIT -- see [LICENSE](LICENSE).
