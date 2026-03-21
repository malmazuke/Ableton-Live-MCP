# AbletonMCP

Control Ableton Live programmatically through AI assistants using the [Model Context Protocol](https://modelcontextprotocol.io).

A Swift MCP server and Python Remote Script that give AI assistants like Cursor and Claude direct access to Ableton Live's full API -- arrangement view, session view, tracks, devices, mixing, and more.

## Architecture

```
┌─────────────────┐                    ┌──────────────────────┐
│  AI Assistant    │  stdio (MCP)       │  Swift MCP Server    │
│  (Cursor/Claude) │◄──────────────────►│  (macOS binary)      │
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

- **Swift MCP Server** -- a standalone macOS command-line tool. Speaks MCP (JSON-RPC over stdio) with AI clients and communicates with Ableton via TCP. Built with the official [Swift MCP SDK](https://github.com/modelcontextprotocol/swift-sdk).
- **Python Remote Script** -- runs inside Ableton Live's embedded Python runtime as a ControlSurface. Receives JSON commands over TCP, executes them against the [Live Object Model](https://docs.cycling74.com/apiref/lom), and returns results.

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

- macOS 14+ (Sonoma or later)
- Swift 6.0+ (Xcode 16+)
- Ableton Live 12 (any edition)
- Cursor IDE or Claude Desktop

## Project Structure

```
AbletonMCP/
  Package.swift                         -- Swift package manifest
  Sources/
    AbletonMCP/
      main.swift                        -- entry point
      Server/
        AbletonMCPServer.swift          -- MCP server setup, tool registration
      Connection/
        AbletonConnection.swift         -- async TCP client
        MessageProtocol.swift           -- typed request/response models
      Tools/
        SessionTools.swift              -- transport, tempo, time signature
        TrackTools.swift                -- track CRUD and properties
        ClipTools.swift                 -- arrangement + session clips
        DeviceTools.swift               -- devices and parameters
        SceneTools.swift                -- scene management
        BrowserTools.swift              -- browser navigation and loading
        MixerTools.swift                -- volume, pan, sends
  Tests/
    AbletonMCPTests/
      ConnectionTests.swift
      MessageProtocolTests.swift
      ToolTests/
  RemoteScript/
    AbletonMCP/
      __init__.py                       -- Ableton Remote Script
  docs/
    installation.md
    api-reference.md
```

## Installation

> Detailed installation guide coming soon. See [docs/installation.md](docs/installation.md).

### Quick Start

1. **Build the Swift server:**
   ```bash
   swift build -c release
   ```

2. **Install the Remote Script** into Ableton's User Library:
   ```bash
   cp -r RemoteScript/AbletonMCP ~/Music/Ableton/User\ Library/Remote\ Scripts/
   ```

3. **Configure Ableton:** Preferences > Link, Tempo & MIDI > set Control Surface to "AbletonMCP", Input/Output to "None".

4. **Add to Cursor:** Settings > MCP > add server:
   ```json
   {
     "mcpServers": {
       "AbletonMCP": {
         "command": "/path/to/AbletonMCP/.build/release/AbletonMCP"
       }
     }
   }
   ```

5. **Try it:** "Create a MIDI clip in arrangement at bar 1 with a Cm7 chord."

## Design Principles

- **Arrangement-first** -- most producers work in arrangement view. It's a first-class citizen, not an afterthought.
- **Typed protocol** -- the JSON protocol between Swift server and Python script uses strongly typed models on both sides. No stringly-typed command construction.
- **Registry pattern** -- tools are registered declaratively, not routed through if/elif chains.
- **Async native** -- the Swift server uses Swift concurrency throughout. No blocking I/O.
- **Comprehensive coverage** -- targeting the full Live Object Model, not just the basics.

## Roadmap

### Phase 1 -- Core (current)
- Communication layer (Swift TCP client, Python TCP server)
- Session/transport control
- Track management
- Arrangement + session clip creation with notes
- Device parameter control

### Phase 2 -- Extended
- Scene management
- Browser navigation and instrument loading
- Audio file import
- Mixer (sends, returns, crossfader)
- Automation envelopes

### Phase 3 -- Advanced
- Input/output routing configuration
- Group tracks and folding
- Take lanes
- Cue points / locators
- Groove pool
- Undo/redo

## Tech Stack

- **Server:** Swift 6, [modelcontextprotocol/swift-sdk](https://github.com/modelcontextprotocol/swift-sdk), Swift NIO (TCP)
- **Remote Script:** Python 3 (Ableton's embedded runtime), `_Framework.ControlSurface`
- **Protocol:** JSON over TCP (port 9877)
- **CI:** GitHub Actions (macOS runner)

## License

MIT -- see [LICENSE](LICENSE).
