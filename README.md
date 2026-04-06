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
2. Create a new file called /tmp/nvim-mcp-test.py and add a few lines of Python to it (a function, a comment, a print statement).
3. Save the file, then tell me the total line count.
4. Go to line 1, then jump to the last line. Tell me the cursor position after each move.
5. What is the current working directory in Neovim?
6. Open a vertical split with /tmp/nvim-mcp-test2.py, write a short function in it, and save it.
7. Switch back to the original window and confirm which file is shown.
8. Add a comment above the first function in the current file and save.
9. Are there any unsaved buffers? List all open buffers.
10. Search for the word "def" in the current buffer. Tell me which lines match.
11. Close the current buffer without saving, then close the remaining buffer.
12. Show me the LSP recipes for Neovim.
```

## Requirements

- Python ≥ 3.10
- Linux or macOS
- Neovim with RPC socket enabled (default)

## License

MIT — see [LICENSE](LICENSE).
