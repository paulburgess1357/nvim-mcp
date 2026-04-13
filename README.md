# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that gives AI assistants (Cursor, Claude, and others) full access to a running **Neovim** session. The assistant sees what you see — cursor position, visible code, window layout, visual selections — and can send keystrokes, run commands, or read buffer contents.

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

3. **Add agent rules** — registering the server gives the assistant the tools, but a rule file teaches it *when and how* to use them. Copy one from [`config/`](config/) into your project (`AGENTS.md` for Claude Code / Codex / others, or run `./config/generate-mdc.sh` for Cursor).
4. **Start Neovim** — it listens on an RPC socket by default.

## Tools

| Tool               | Purpose                                                                                                                                                                                                                                                                            |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`nvim_state`**   | Snapshot of the session: mode, cwd, and per-window details (file, cursor, filetype, **context lines**, folds, and visual selection), each context line prefixed with its absolute line number. |
| **`nvim_buf_read`**| Read lines from a buffer (in-memory, not disk). Supports optional line range.                                                                                                                |
| **`nvim_command`** | Run ex commands (no leading `:`). Accepts a single string or a list. E.g. `"w"`, `"e /path"`, `"lua vim.print(...)"`, or `["wincmd p", "checktime", "wincmd p"]`.                            |
| **`nvim_keys`**    | Send keystrokes. E.g. `"gg"`, `"17GVG"`, `"za"`. Esc is prepended automatically.                                                                                                            |
| **`nvim_connect`** | Connect to a Neovim instance. Auto-connects when only one exists; lists all when multiple are found.                                                                                         |

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
