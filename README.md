# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that lets AI assistants (Cursor, Claude, and others) control a running **Neovim** session: open buffers, move the cursor, run LSP actions, inspect layout, and more. It talks to Neovim directly over its default **Unix socket** using msgpack-RPC, discovers instances automatically, and exposes four tools.

**Platforms:** Linux and macOS only.

## Install

```bash
uv tool install nvim-mcp
```

Or run without installing:

```bash
uvx nvim-mcp
```

## Quick start

1. Start Neovim (it listens on an RPC socket by default).
2. Set up your MCP client and agent rules — see [`config/`](config/) for everything you need.
3. The assistant can now control Neovim through 4 tools.

## Tools

| Tool | Purpose |
|------|---------|
| **`nvim_send`** | The universal interface. Send any ex command, Vimscript expression, or key sequence to Neovim. Three modes: `command`, `eval`, `keys`. |
| **`nvim_state`** | Structured snapshot: current file, cursor position, mode, window layout, modified buffers, cwd, and more. |
| **`nvim_connect`** | Connect to a Neovim instance. Auto-connects when only one exists; lists all when multiple are found. |
| **`nvim_recipes`** | Browse operation recipes by category (files, navigation, buffers, windows, marks, registers, folds, LSP). |

## Multi-instance

One Neovim instance running? Tools auto-connect. Multiple? `nvim_connect` lists them — pick by `index`, `socket_path`, or `terminal_pid`. Set `NVIM_SOCKET_PATH` to skip discovery entirely.

## Setup

See [`config/`](config/) for MCP client registration (Cursor, Claude Desktop, Claude CLI) and example agent rule files.

## Manual testing

Open Neovim, then copy-paste the block below into your AI assistant to verify the MCP server end-to-end:

```
Run through these tests one at a time. After each test, tell me what happened
and wait for my OK before moving to the next one.

1. Connect to my Neovim instance and show me the current file, cursor position, and mode.
2. Open ~/.bashrc in Neovim.
3. Go to line 10 in the current buffer.
4. What is the current working directory in Neovim?
5. Jump to the top of the file, then move down 5 lines.
6. Open a vertical split with /tmp/test.txt, then switch back to the original window.
7. Are there any unsaved buffers? List them.
8. Toggle the fold under the cursor.
9. Search for the word "function" in the current buffer.
10. Close the current buffer without saving.
11. Show me the LSP recipes for Neovim.
```

## Requirements

- Python ≥ 3.10
- Linux or macOS
- Neovim with RPC socket enabled (default)

## License

MIT — see [LICENSE](LICENSE).
