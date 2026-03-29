# Installation Guide

This guide walks you through installing Ableton Live MCP, connecting it to
Ableton Live, and checking that everything works.

If you are setting this up for the first time, follow the sections in order.

## Prerequisites

- Python 3.10 or newer
- `uv`
- Ableton Live 12
- A clone of this repository
- An MCP-capable client such as Cursor or Claude Desktop

Install `uv` from the official docs:
[docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/).

## 1. Clone the repository and install Python dependencies

```bash
git clone https://github.com/malmazuke/Ableton-Live-MCP.git
cd Ableton-Live-MCP
uv sync
```

This installs the project and gives you two commands:

- `mcp-ableton`
- `mcp-ableton-setup`

## 2. Install the Remote Script into Ableton

The easiest way is to use the setup tool:

```bash
uv run mcp-ableton-setup
```

It will:

1. Locate `remote_script/AbletonLiveMCP` inside this repository.
2. Detect existing Ableton Remote Script directories for the current OS.
3. Install `AbletonLiveMCP` there as a symlink by default.
4. Print the next Ableton configuration steps.

### Supported installer options

```bash
uv run mcp-ableton-setup --help
uv run mcp-ableton-setup --dry-run
uv run mcp-ableton-setup --method symlink
uv run mcp-ableton-setup --method copy
uv run mcp-ableton-setup --target "/path/to/Remote Scripts"
uv run mcp-ableton-setup --uninstall
uv run mcp-ableton-setup --uninstall --target "/path/to/Remote Scripts"
```

### Where the installer looks

The installer auto-detects these directories when they already exist.

**macOS**

- User Library: `~/Music/Ableton/User Library/Remote Scripts`
- Per-version fallback: `~/Library/Preferences/Ableton/Live <version>/User Remote Scripts`

**Windows**

- User Library: `C:\Users\<you>\Documents\Ableton\User Library\Remote Scripts`
- Per-version fallback:
  `%APPDATA%\Ableton\Live <version>\Preferences\User Remote Scripts`

If the macOS or Windows User Library path exists, the installer selects it
automatically. If only per-version directories exist, it may prompt you to pick
one. If nothing exists, it exits and tells you which default path it expected.

If the Windows paths on your machine look different, use `--target` to point
the installer at the correct `Remote Scripts` folder.

### Symlink vs copy

`mcp-ableton-setup` defaults to `--method symlink`.

| Method | Use it when | Tradeoffs |
| --- | --- | --- |
| `symlink` | You are actively developing or regularly pulling updates | New repo changes are picked up without reinstalling, but Ableton will see the live repo contents, including any bad local edits or incompatible `__pycache__` files. |
| `copy` | You want an isolated snapshot or symlink creation is blocked | Safer and simpler on restrictive systems, but you must re-run the installer after updates. |

On Windows, prefer `--method copy` if symlink creation is blocked by system
policy or Developer Mode is disabled.

### Manual installation fallback

Use this only if the installer cannot find your Ableton folder or you prefer to
manage the files yourself.

**macOS symlink**

```bash
mkdir -p ~/Music/Ableton/User\ Library/Remote\ Scripts
ln -s "$(pwd)/remote_script/AbletonLiveMCP" \
  ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP
```

**macOS copy**

```bash
mkdir -p ~/Music/Ableton/User\ Library/Remote\ Scripts
cp -R remote_script/AbletonLiveMCP \
  ~/Music/Ableton/User\ Library/Remote\ Scripts/
```

**Windows copy**

```powershell
New-Item -ItemType Directory -Force `
  "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts" | Out-Null
Copy-Item -Recurse remote_script\AbletonLiveMCP `
  "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts\"
```

## 3. Configure Ableton Live

1. Start Ableton Live, or restart it if it was already open.
2. Open `Preferences`.
3. Open the `Link, Tempo & MIDI` tab.
4. In an empty `Control Surface` slot, choose `AbletonLiveMCP`.
5. Set `Input` to `None`.
6. Set `Output` to `None`.

When it works:

- Ableton's status bar briefly shows `AbletonLiveMCP: listening on port 9877`.
- The Ableton log records
  `AbletonLiveMCP TCP server listening on 127.0.0.1:9877`.

If `AbletonLiveMCP` does not appear in the list, go to
[Troubleshooting](#troubleshooting).

## 4. Configure your MCP client

### Cursor

Create `.cursor/mcp.json` in the repository root:

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

If you prefer a global Cursor config instead, use the same JSON and replace
`${workspaceFolder}` with the absolute path to this repository.

After saving the config, reload Cursor if it does not automatically start the
server.

### Claude Desktop

Claude Desktop reads MCP servers from `claude_desktop_config.json`.

- macOS:
  `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows:
  `%APPDATA%\Claude\claude_desktop_config.json`

Add this server entry:

```json
{
  "mcpServers": {
    "AbletonLiveMCP": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/Ableton-Live-MCP",
        "mcp-ableton"
      ]
    }
  }
}
```

Replace `/absolute/path/to/Ableton-Live-MCP` with the real repository path.
Restart Claude Desktop after saving the file.

## 5. Verify the setup

Start with the easiest checks:

1. Run the installer in preview mode.
2. Confirm Ableton loaded the control surface.
3. Ask your MCP client for a simple read-only command.

### Check the installer

Run:

```bash
uv run mcp-ableton-setup --dry-run
```

You should see the Remote Scripts directory the installer wants to use. If the
script is already installed, you should also see whether it is installed as a
symlink or a copied folder.

### Check Ableton

Confirm all three:

1. `AbletonLiveMCP` is selected as a control surface.
2. `Input` and `Output` are both `None`.
3. Ableton is listening on port `9877`.

Helpful commands:

```bash
lsof -nP -iTCP:9877 -sTCP:LISTEN
tail -n 50 "$HOME/Library/Preferences/Ableton/Live 12.2.5/Log.txt"
```

### Check from your MCP client

With Ableton running and the control surface active, ask your MCP client for a
simple read-only action:

- `Get the current Ableton session info`
- `List the current session tempo and track count`

If you want to test the TCP connection directly from the terminal, this should
work while Ableton is running and listening:

```bash
uv run python -c $'import asyncio, json\nfrom mcp_ableton.connection import AbletonConnection\nfrom mcp_ableton.protocol import CommandRequest\n\nasync def main() -> None:\n    conn = AbletonConnection()\n    try:\n        await conn.connect()\n        response = await conn.send_command(CommandRequest(command="session.get_info"))\n        print(json.dumps(response.model_dump(), indent=2))\n    finally:\n        await conn.disconnect()\n\nasyncio.run(main())'
```

If that command fails with `Connect call failed ... 9877`, Ableton is not
listening on the expected port yet. In that case, go back to the Ableton setup
and troubleshooting steps below.

## Uninstall

### Remove the Remote Script

```bash
uv run mcp-ableton-setup --uninstall
```

The uninstall flow prompts before removing the installed `AbletonLiveMCP`
directory or symlink.

If you installed to a non-default location, include `--target`:

```bash
uv run mcp-ableton-setup --uninstall --target "/path/to/Remote Scripts"
```

Manual removal is also fine:

**macOS**

```bash
rm -rf ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP
```

**Windows**

```powershell
Remove-Item -Recurse -Force `
  "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts\AbletonLiveMCP"
```

Restart Ableton Live after removal.

### Remove the MCP server from your client

Delete the `AbletonLiveMCP` server entry from Cursor or Claude Desktop, then
restart the client if needed.

## Troubleshooting

### Remote Script does not appear in Ableton's Control Surface list

- Restart Ableton after installing the script.
- Confirm the installed folder or symlink exists:

  ```bash
  ls -la ~/Music/Ableton/User\ Library/Remote\ Scripts/AbletonLiveMCP
  ```

- Confirm the script contains at least `__init__.py`, `dispatcher.py`,
  `tcp_server.py`, and `handlers/`.
- If you used `--target`, make sure you pointed at the parent `Remote Scripts`
  directory, not at `AbletonLiveMCP` itself.
- Check the Ableton log for import failures or `RemoteScriptError`.

### Connection refused or timeout when the MCP server tries to talk to Ableton

- Make sure Ableton is open.
- Make sure `AbletonLiveMCP` is enabled in `Preferences > Link, Tempo & MIDI`.
- Check whether anything is listening on `9877`:

  ```bash
  lsof -nP -iTCP:9877 -sTCP:LISTEN
  ```

- If nothing is listening, inspect the Ableton log and fix the Remote Script
  load problem before debugging the MCP client.

### Stale TCP connection after restarting Ableton

The Remote Script owns the TCP server. If Live restarts while Cursor or Claude
is still holding an old connection, the MCP server can report broken pipe or
connection-refused errors on the next call.

Fix:

1. Restart Ableton fully.
2. Restart the MCP server process by reloading Cursor's MCP server or
   restarting Claude Desktop.
3. Retry a read-only command such as `get_session_info`.

### Port 9877 is already in use

Another process is bound to the Remote Script port.

**macOS**

```bash
lsof -nP -iTCP:9877 -sTCP:LISTEN
```

**Windows**

```powershell
netstat -ano | findstr :9877
```

Stop the conflicting process, then reload the control surface in Ableton.

### `__pycache__` problems with symlink installs

Ableton Live's embedded Python can choke on bytecode written by your local
Python version into the symlinked `remote_script/` tree.

Clean the cache and restart Ableton:

```bash
find remote_script/AbletonLiveMCP -type d -name __pycache__ -prune -exec rm -rf {} +
```

If the problem keeps coming back and you do not need a live repo link, switch
to a copy install:

```bash
uv run mcp-ableton-setup --method copy
```

### The setup tool cannot find a Remote Scripts directory

This is expected on a fresh system if Ableton has not created the directory yet.

Create the default path yourself, then re-run the installer.

**macOS**

```bash
mkdir -p ~/Music/Ableton/User\ Library/Remote\ Scripts
uv run mcp-ableton-setup
```

**Windows**

```powershell
New-Item -ItemType Directory -Force `
  "$env:USERPROFILE\Documents\Ableton\User Library\Remote Scripts" | Out-Null
uv run mcp-ableton-setup
```

If you intentionally want a different location, pass `--target`.

### Changes are not reflected after `git pull`

If you installed with `--method copy`, the installed Remote Script is a snapshot.
Reinstall it after pulling changes:

```bash
uv run mcp-ableton-setup --method copy
```

If you installed with the default symlink method:

1. Restart Ableton so it reloads the Python files.
2. Clear `__pycache__` if the update changed Python modules significantly.
3. Restart Cursor or Claude Desktop if the tool list or MCP server state looks
   stale.

### Where to find Ableton logs

**Verified macOS example**

- `~/Library/Preferences/Ableton/Live 12.2.5/Log.txt`

**General paths**

- macOS: `~/Library/Preferences/Ableton/Live <version>/Log.txt`
- Windows: `%APPDATA%\Ableton\Live <version>\Preferences\Log.txt`

Search for:

- `AbletonLiveMCP`
- `RemoteScriptError`
- `TCP server listening`
- `Client connected`

Those lines tell you whether the script loaded, whether it bound port `9877`,
and whether the MCP server managed to connect.
