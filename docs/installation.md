# Installation Guide

> Detailed installation instructions coming soon.

## Prerequisites

- macOS 14+ (Sonoma or later)
- Swift 6.0+ (Xcode 16+)
- Ableton Live 12 (any edition)
- Cursor IDE or Claude Desktop

## Steps

### 1. Build the Swift Server

```bash
git clone git@github.com:malmazuke/AbletonMCP.git
cd AbletonMCP
swift build -c release
```

### 2. Install the Remote Script

Copy the Remote Script into Ableton's User Library:

```bash
cp -r RemoteScript/AbletonMCP ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

### 3. Configure Ableton Live

1. Open Ableton Live 12
2. Go to Preferences (Cmd + ,)
3. Navigate to Link, Tempo & MIDI
4. Set an empty Control Surface slot to **AbletonMCP**
5. Set Input and Output to **None**

You should see "AbletonMCP: Listening for commands on port 9877" in the status bar.

### 4. Connect Your AI Assistant

**Cursor IDE:**

Add to your MCP config (Settings > MCP):

```json
{
  "mcpServers": {
    "AbletonMCP": {
      "command": "/path/to/AbletonMCP/.build/release/AbletonMCP"
    }
  }
}
```

**Claude Desktop:**

Edit your Claude config file:

```json
{
  "mcpServers": {
    "AbletonMCP": {
      "command": "/path/to/AbletonMCP/.build/release/AbletonMCP"
    }
  }
}
```

### 5. Verify

Open a new chat and try: "Get information about my current Ableton session"
