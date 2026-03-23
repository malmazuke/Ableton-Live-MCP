# AGENTS.md

## Project overview

Ableton Live MCP is a Python MCP server and Ableton Live Remote Script that gives AI assistants direct access to Ableton Live's full API via the Live Object Model.

**Two components, one language (Python):**

- **MCP Server** (`src/mcp_ableton/`) — speaks MCP (JSON-RPC over stdio) with AI clients, forwards commands to Ableton over TCP. Built with the [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) and Pydantic.
- **Remote Script** (`remote_script/AbletonLiveMCP/`) — runs inside Ableton Live's embedded Python runtime as a `_Framework.ControlSurface`. Receives JSON commands over TCP :9877, executes against the Live Object Model, returns results.

**Tech stack:** Python 3.10+, `mcp` SDK (FastMCP), Pydantic, asyncio, `uv` for packaging.

## Project structure

> This is the target layout. Some files/directories may not exist yet — create them as needed following this structure.

```
mcp-ableton/
  pyproject.toml
  src/
    mcp_ableton/
      __init__.py
      server.py              # MCP server setup, tool registration
      connection.py          # async TCP client
      protocol.py            # typed request/response models (Pydantic)
      tools/
        session.py           # transport, tempo, time signature
        track.py             # track CRUD and properties
        clip.py              # arrangement + session clips
        device.py            # devices and parameters
        scene.py             # scene management
        browser.py           # browser navigation and loading
        mixer.py             # volume, pan, sends
  tests/
    test_connection.py
    test_protocol.py
    tools/
  remote_script/
    AbletonLiveMCP/
      __init__.py            # Ableton ControlSurface Remote Script
  docs/
    installation.md
    decisions/               # ADRs numbered sequentially (see 000-template.md)
```

## Commands

```bash
# Dependencies
uv sync                              # install all dependencies
uv add <package>                     # add a new dependency

# Run the MCP server (stdio transport)
uv run mcp-ableton

# Testing
uv run pytest                        # run all tests
uv run pytest tests/test_connection.py  # run a single test file
uv run pytest -x                     # stop on first failure

# Linting and type checking
uv run ruff check .                  # lint
uv run ruff check --fix .            # lint with auto-fix
uv run ruff format .                 # format
uv run mypy src/                     # type check

# MCP development
uv run mcp dev src/mcp_ableton/server.py  # test with MCP Inspector
```

## Code style

- **Python 3.10+** — use modern syntax: `match` statements, `X | Y` union types, `list[str]` not `List[str]`.
- **Formatting:** Ruff, 88-char line length, double quotes, trailing commas.
- **Type hints everywhere.** All function signatures must have parameter and return type annotations. Use Pydantic models for structured data, not raw dicts.
- **Async by default.** The MCP server is async-native. Use `async def` for I/O-bound operations.
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. Match class names to file names (`TrackService` in `track_service.py`).
- **Imports:** absolute imports only (`from mcp_ableton.protocol import ...`, never relative).
- **`__all__` in every `__init__.py`** — define the public API explicitly. Unlisted members are internal.
- **No print statements.** Use `logging` or MCP context logging.
- **File size:** consider splitting files that grow beyond 300-500 lines or handle multiple unrelated responsibilities.

```python
# Good: typed, async, Pydantic model
async def get_track_info(track_index: int) -> TrackInfo:
    response = await connection.send(GetTrackRequest(track_index=track_index))
    return TrackInfo.model_validate(response)

# Bad: untyped, sync, raw dict
def get_track_info(idx):
    resp = connection.send({"type": "get_track", "index": idx})
    return resp
```

## Architecture patterns

- **Registry pattern** for MCP tools — tools are registered declaratively via `@mcp.tool()`, not routed through if/elif chains.
- **Typed protocol** — all messages between MCP server and Remote Script use Pydantic models. No stringly-typed command construction.
- **Layered architecture** — `server.py` (MCP interface) → `tools/` (business logic) → `connection.py` (transport) → `protocol.py` (models). Each layer depends only on layers below it.
- **Single-responsibility tools** — each file in `tools/` owns one domain (tracks, clips, devices, etc.).

## Remote Script constraints

The Remote Script runs inside Ableton Live 12's embedded Python 3 runtime, which is **heavily sandboxed**:

- No `pip install` — only the standard library and Ableton's `_Framework` modules are available.
- Must subclass `_Framework.ControlSurface.ControlSurface`.
- Must use Ableton's threading model — schedule all state changes via `schedule_message(0, callback)` to run on the main thread.
- No async/await — the Remote Script is synchronous.
- Objects are accessed via canonical paths like `live_set tracks 0 devices 1 parameters 2`.
- Use the `ableton-lom` skill (see below) for the full Live Object Model API reference, including reference files by domain (song, track, clip, device, etc.).

## Testing

- Use `pytest` with `pytest-asyncio` for async tests.
- Mock the TCP connection in MCP server tests — never require a running Ableton instance.
- Test Pydantic models with known JSON payloads to verify serialization round-trips.
- Name test files `test_<module>.py` in a parallel `tests/` directory mirroring the source structure.

## Git workflow

- **Commit messages:** imperative mood, lowercase, max 72 chars. Examples: `add track creation tool`, `fix tempo validation in session commands`.
- **Branches:** `feature/<name>`, `fix/<name>`, `docs/<name>`.
- **ADRs:** record significant architectural decisions in `docs/decisions/` using the template in `000-template.md`. Number sequentially.

## Skills

This project includes agent skills in `.agents/skills/`, symlinked to `.cursor/skills/`, `.claude/skills/`, and other agent directories. Skills provide domain-specific knowledge that supplements your general capabilities.

**Installed skills:**

| Skill | Use when |
|-------|----------|
| `python-mcp-server-generator` | Creating MCP tools, configuring FastMCP, implementing resources/prompts |
| `python-project-structure` | Organizing modules, defining `__all__`, structuring packages |
| `ableton-lom` | Working on the Remote Script or any code that interacts with the Live Object Model |
| `find-skills` | The user asks to find or install new skills |

**How to use:** Read the SKILL.md for the relevant skill before starting work in that domain. Skills are in `.agents/skills/<name>/SKILL.md`. Some skills (like `ableton-lom`) include reference files — only read those when you need deeper detail for a specific domain.

**Installing new skills:** `npx skills add <owner/repo@skill> -y`, then symlink into `.cursor/skills/` for Cursor compatibility.

## Boundaries

- **Always:** run tests before suggesting a commit, use type hints, follow the Pydantic protocol pattern, define `__all__` in `__init__.py` files.
- **Ask first:** adding new dependencies, changing the TCP protocol format, modifying the Remote Script's ControlSurface lifecycle.
- **Never:** commit `.env` files or secrets, modify files in `.agents/skills/` directly (use `npx skills update`), use `print()` for logging.
