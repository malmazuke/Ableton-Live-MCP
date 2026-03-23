# Installation Guide

> **Note:** Ableton Live MCP is in early development and is not yet functional. These instructions describe the intended setup flow for when the project is ready.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Ableton Live 12 (any edition)
- macOS or Windows
- Cursor IDE or Claude Desktop

## Steps

### 1. Install the MCP Server

```bash
pip install mcp-ableton
```

Or for development:

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
```

### 2. Install the Remote Script

Copy the Remote Script into Ableton's Remote Scripts folder:

**macOS:**
```bash
cp -r remote_script/AbletonLiveMCP ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

**Windows:**
```bash
xcopy remote_script\AbletonLiveMCP "%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\AbletonLiveMCP" /E /I
```

### 3. Configure Ableton Live

1. Open Ableton Live 12
2. Go to Preferences (Cmd + ,)
3. Navigate to Link, Tempo & MIDI
4. Set an empty Control Surface slot to **AbletonLiveMCP**
5. Set Input and Output to **None**

You should see "AbletonLiveMCP: Listening for commands on port 9877" in the status bar.

### 4. Connect Your AI Assistant

**Cursor IDE:**

Add to your MCP config (Settings > MCP):

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "mcp-ableton"
    }
  }
}
```

**Claude Desktop:**

Edit your Claude config file:

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "mcp-ableton"
    }
  }
}
```

### 5. Verify

Open a new chat and try: "Get information about my current Ableton session"
