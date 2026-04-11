# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that gives AI assistants (Cursor, Claude, and others) full access to a running **Neovim** session. The assistant sees what you see — cursor position, visible code, window layout, visual selections — and can act on it: run any ex command, send keystrokes, evaluate expressions, trigger LSP actions, or anything else Neovim can do.

It talks to Neovim directly over its default **Unix socket** using msgpack-RPC and discovers running instances automatically.

<video src="https://github.com/user-attachments/assets/d4a9267a-9e79-40ce-ac84-50411c84b608"></video>

## Setup

1. **Install [uv](https://docs.astral.sh/uv/)** if you don't have it: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Register the MCP server** with your client — example for Cursor (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "nvim-mcp": {
      "command": "uvx",
      "args": ["nvim-mcp"]
    }
  }
}
```

   See [`config/README.md`](config/README.md) for other clients (Claude CLI, Codex, etc.) or to run from a local clone.

3. **Add agent rules** — registering the server gives the assistant the tools, but a rule file teaches it *when and how* to use them. Copy one from [`config/`](config/) into your project (`cursor.mdc` for Cursor, `AGENTS.md` for Claude Code / Codex / others).
4. **Start Neovim** — it listens on an RPC socket by default.

## Tools

| Tool               | Purpose                                                                                                                                                                                                                                                                            |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`nvim_state`**   | Real-time snapshot of your session: current file, cursor position, mode, modified buffers, cwd, and per-window details (file, cursor, **context lines**, and visual selection for the active window), each prefixed with its absolute line number. This is how the assistant knows what you're looking at. |
| **`nvim_send`**    | Do anything in Neovim. Three modes: `command` (ex commands), `eval` (Vimscript expressions), `keys` (keystrokes). Returns `{"result": ..., "state": {...}}` by default; set `return_state=false` for the result string only.                                                       |
| **`nvim_connect`** | Connect to a Neovim instance. Auto-connects when only one exists; lists all when multiple are found.                                                                                                                                                                               |
| **`nvim_recipes`** | Built-in cheat sheet the assistant consults to know how to drive Neovim. Categories: files, navigation, buffers, windows, marks, registers, folds, LSP.                                                                                                                            |

## Multi-instance

One Neovim instance running? Tools auto-connect. Multiple? `nvim_connect` lists them — pick by `index`, `socket_path`, or `terminal_pid`. Set `NVIM_SOCKET_PATH` to skip discovery entirely.

## Environment

| Variable                          | Default           | Description                                                                    |
| --------------------------------- | ----------------- | ------------------------------------------------------------------------------ |
| `NVIM_SOCKET_PATH`                | _(auto-discover)_ | Skip discovery; connect directly to this socket.                               |
| `NVIM_MCP_ACTIVE_CONTEXT_LINES`   | `20`              | Lines above/below cursor in the active window. Set to `0` to disable.          |
| `NVIM_MCP_INACTIVE_CONTEXT_LINES` | `20`              | Lines above/below cursor in inactive windows. Set to `0` to disable.           |

## Demo

Open a file in Neovim, then paste this into your AI assistant:

```
For each step: explain what you're about to do, then do it, then tell me
what happened. Wait for me to say "next" before moving on.

1. What file am I in and what's around my cursor?
2. Highlight the current function and explain what it does.
3. Add a docstring above it, save, and show me the result.
4. Open a vertical split, write a short test for that function, and save.
```

## Requirements

- Python ≥ 3.10
- Linux
- Neovim ≥ 0.11

## License

MIT — see [LICENSE](LICENSE).
