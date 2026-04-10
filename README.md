# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that lets AI assistants (Cursor, Claude, and others) control a running **Neovim** session: open buffers, move the cursor, run LSP actions, inspect layout, and more. It talks to Neovim directly over its default **Unix socket** using msgpack-RPC, discovers instances automatically, and exposes four tools.

**Platforms:** Linux and macOS only.

https://github.com/user-attachments/assets/a546b3d5-082e-4f3d-aaaf-e94d997d506a

## Install

```bash
uv tool install nvim-mcp
```

Or run without installing:

```bash
uvx nvim-mcp
```

## Quick start

1. Start Neovim (it listens on an RPC socket by default) — this works in any terminal, including the integrated terminal in Cursor, VS Code, or similar editors.
2. Set up your MCP client and agent rules — see [`config/`](config/) for everything you need.
3. The assistant can now control Neovim through 4 tools.

## Tools

| Tool               | Purpose                                                                                                                                                                                                                                                                            |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`nvim_send`**    | The universal interface. Send any ex command, Vimscript expression, or key sequence to Neovim. Three modes: `command`, `eval`, `keys`. Returns `{"result": ..., "state": {...}}` by default (`state` matches `nvim_state`); set `return_state=false` for the result string only.   |
| **`nvim_state`**   | Structured snapshot: current file, cursor, mode, windows, modified buffers, cwd, and more — plus **context** lines around the cursor or selection (`start_line`, `lines`). In visual mode, also includes a **selection** range (`start_line`, `start_col`, `end_line`, `end_col`). |
| **`nvim_connect`** | Connect to a Neovim instance. Auto-connects when only one exists; lists all when multiple are found.                                                                                                                                                                               |
| **`nvim_recipes`** | Browse operation recipes by category (files, navigation, buffers, windows, marks, registers, folds, LSP).                                                                                                                                                                          |

## Multi-instance

One Neovim instance running? Tools auto-connect. Multiple? `nvim_connect` lists them — pick by `index`, `socket_path`, or `terminal_pid`. Set `NVIM_SOCKET_PATH` to skip discovery entirely.

## Environment

| Variable                 | Default           | Description                                                        |
| ------------------------ | ----------------- | ------------------------------------------------------------------ |
| `NVIM_SOCKET_PATH`       | _(auto-discover)_ | Skip discovery; connect directly to this socket.                   |
| `NVIM_MCP_CONTEXT_LINES` | `20`              | Lines above/below cursor included in state. Set to `0` to disable. |

## Setup

See [`config/`](config/) for MCP client registration (Cursor, Claude Desktop, Claude CLI) and example agent rule files.

## Demo

Open a file in Neovim, then paste this into your AI assistant:

```
Run through these one at a time. After each step, tell me what happened
and wait for my OK before moving on.

1. What file am I in and what code is around my cursor?
2. I'm going to highlight some lines — tell me what I selected and what it does.
3. Add a docstring or comment above the function my cursor is in, save, and show me the result.
4. Open a vertical split with a new file, write a short helper function in it, and save.
5. Switch back to the original window — what's on screen now?
6. Rename a variable in the current function (edit on disk, reload) and confirm the change.
7. Jump to the last function in the file and explain what it does.
8. Show me the LSP recipes.
```

## Requirements

- Python ≥ 3.10
- Linux or macOS
- Neovim with RPC socket enabled (default)

## License

MIT — see [LICENSE](LICENSE).
