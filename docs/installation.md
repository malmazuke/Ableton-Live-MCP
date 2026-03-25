# Installation Guide

> **Note:** Ableton Live MCP is in early development and is not yet functional. These instructions describe the intended setup flow for when the project is ready.

## Prerequisites

- **Python 3.10+** -- [download](https://www.python.org/downloads/) if not already installed
- **uv** -- install with `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows). See [uv docs](https://docs.astral.sh/uv/getting-started/installation/).
- **Ableton Live 12** (any edition -- Intro, Standard, or Suite)
- **macOS** (Windows support is planned)
- **Cursor IDE** or **Claude Desktop** (or any MCP-compatible AI client)

## Step 1: Clone and install

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
```

This installs all Python dependencies and registers the CLI entry points (`mcp-ableton` and `mcp-ableton-setup`).

## Step 2: Install the Remote Script

### Automated (recommended)

```bash
uv run mcp-ableton-setup
```

The setup tool:

1. Detects your Ableton Remote Scripts directory automatically
2. Creates a **symlink** from the detected directory to the `remote_script/AbletonLiveMCP/` folder in this repository
3. Prints next steps for configuring Ableton

Because it uses a symlink, any changes you pull from the repository are reflected immediately -- no need to re-run the setup.

#### Setup options

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would happen without making changes |
| `--method copy` | Copy files instead of creating a symlink |
| `--method symlink` | Create a symlink (default) |
| `--target /path` | Override auto-detection and install to a specific directory |
| `--uninstall` | Remove a previously installed Remote Script |

#### Where does it install?

The tool searches these locations (in order):

**macOS:**

| Location | Notes |
|----------|-------|
| `~/Music/Ableton/User Library/Remote Scripts/` | User Library (recommended, works with Live 10.1.13+) |
| `~/Library/Preferences/Ableton/Live <version>/User Remote Scripts/` | Per-version user scripts |

**Windows:**

| Location | Notes |
|----------|-------|
| `~\Documents\Ableton\User Library\Remote Scripts\` | User Library |
| `%APPDATA%\Ableton\Live <version>\Preferences\User Remote Scripts\` | Per-version user scripts |

If multiple directories are found, the tool prompts you to choose. If none are found, it tells you the expected path and suggests using `--target`.

### Manual installation (fallback)

If the setup tool doesn't work for your system, create the symlink (or copy the files) yourself.

**macOS (symlink):**

```bash
ln -s "$(pwd)/remote_script/AbletonLiveMCP" \
  ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP
```

**macOS (copy):**

```bash
cp -r remote_script/AbletonLiveMCP \
  ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

**Windows (copy):**

```powershell
Copy-Item -Recurse remote_script\AbletonLiveMCP `
  "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts\"
```

> If the `Remote Scripts` directory doesn't exist yet, create it first.

## Step 3: Configure Ableton Live

1. Open (or restart) Ableton Live 12
2. Go to **Preferences** (Cmd+, on macOS, Ctrl+, on Windows)
3. Navigate to the **Link, Tempo & MIDI** tab
4. Find an empty **Control Surface** slot
5. Select **AbletonLiveMCP** from the dropdown
6. Set both **Input** and **Output** to **None**

**How to verify:** look at the status bar at the bottom of the Ableton window. You should see:

```
AbletonLiveMCP: Listening for commands on port 9877
```

If you don't see this message, check Ableton's log file (see [Troubleshooting](#troubleshooting) below).

## Step 4: Configure your AI assistant

The MCP server communicates with your AI assistant over stdio. You need to tell the assistant how to start it.

### Cursor IDE

Go to **Settings > MCP > Add new MCP server** and enter:

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

Replace `/path/to/Ableton-Live-MCP` with the absolute path to your cloned repository.

### Claude Desktop

Edit the Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the following:

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

> Only run one MCP server instance at a time. If you have both Cursor and Claude Desktop configured, only use one at a time.

## Step 5: Verify the connection

1. Make sure Ableton Live is running with the AbletonLiveMCP control surface active
2. Open a new chat in your AI assistant
3. Ask: *"Get information about my current Ableton session"*

If everything is working, the assistant will return details about your Live set (tempo, track count, etc.).

## Uninstalling

### Remove the Remote Script

```bash
uv run mcp-ableton-setup --uninstall
```

Or manually remove the symlink/directory:

**macOS:**
```bash
rm ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP
```

Then restart Ableton Live.

### Remove the MCP server

Remove the `AbletonLiveMCP` entry from your AI assistant's MCP configuration.

## Troubleshooting

### Remote Script doesn't appear in Ableton's Control Surface dropdown

- Restart Ableton after installing the Remote Script.
- Verify the files are in the right place:
  ```bash
  ls ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP/
  ```
  You should see `__init__.py`, `tcp_server.py`, `dispatcher.py`, and `handlers/`.
- If using a symlink, verify it's not broken: `ls -la ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP`

### "Connection refused" or timeout errors

- Make sure Ableton Live is running and the AbletonLiveMCP control surface is selected.
- Check that nothing else is using port 9877: `lsof -i :9877` (macOS).
- Look at the Ableton log for error messages (see below).

### Stale connection after restarting Ableton

If you restart Ableton while the MCP server is running, the TCP connection goes stale. The MCP server will report "Broken pipe" or "Connection refused" errors.

**Fix:** Restart the MCP server. In Cursor, toggle the AbletonLiveMCP switch off and back on in Settings > MCP. In Claude Desktop, restart the application.

### `__pycache__` errors with symlink install

If you installed via symlink and run tests locally (e.g. `uv run pytest`), your local Python may write `.pyc` bytecode files that are incompatible with Ableton's embedded Python. This can cause crashes or import errors when Ableton loads the Remote Script.

**Fix:** Delete the cached bytecode and restart Ableton:

```bash
find remote_script/AbletonLiveMCP -type d -name __pycache__ -exec rm -rf {} +
```

### Port 9877 already in use

Another process is using the port. Close other Ableton instances or find the process:

```bash
lsof -i :9877    # macOS
```

### Finding Ableton's log file

The log file contains detailed error output from the Remote Script:

- **macOS:** `~/Library/Preferences/Ableton/Live <version>/Log.txt`
- **Windows:** `%APPDATA%\Ableton\Live <version>\Preferences\Log.txt`

Search for `AbletonLiveMCP` or `RemoteScriptError` in the log to find relevant entries.

### Changes not reflected after `git pull`

If you installed with `--method copy`, you need to re-run the setup to copy the updated files:

```bash
uv run mcp-ableton-setup
```

If you installed with the default symlink method, changes are picked up automatically -- just restart Ableton.
