# nvim-mcp

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that lets AI assistants (Cursor, Claude, and others) control a running **Neovim** session: open buffers, move the cursor, run LSP actions, inspect layout, and more. It is a Python package (stdio transport, **FastMCP**) that talks to Neovim over the default **socket** (RPC) via [pynvim](https://github.com/neovim/pynvim), discovers instances automatically, and exposes four tools.

**Platforms:** Linux and macOS only (Neovim with a listening socket — the usual default).

## Install

```bash
uv tool install nvim-mcp
```

Run without a global install:

```bash
uvx nvim-mcp
```

## Quick start

1. Start Neovim (ensure it is listening on its RPC socket — default behavior).
2. Register the server in your MCP client (see [Client setup](#client-setup)).
3. Use the tools from the assistant: connect if needed, then send commands, read state, or browse recipes.

## Tools

| Tool | Purpose |
|------|--------|
| **`nvim_connect`** | Attach to a Neovim instance. No arguments: if exactly one instance exists, connects; if several, returns a numbered list. You can pass `socket_path`, `terminal_pid`, or `index` (1-based) to choose one. |
| **`nvim_send`** | Send input in one of three modes: `command` (ex command, no leading `:`), `eval` (Vimscript expression, string result), or `keys` (key sequence; `<Esc>` is prefixed automatically). Auto-connects when only one instance exists. |
| **`nvim_state`** | Returns structured state: current file, line, column, mode, modified flags, `filetype`, line count, `cwd`, `relativenumber`, window list, modified buffer names, buffer count. Auto-connects when only one instance exists. |
| **`nvim_recipes`** | Operation cheat sheet from bundled docs. Omit `category` for a short reference plus category names; pass `category` for the full text of that section (names match `recipes.md` headers, case-insensitive). Does not require a Neovim connection. |

### `nvim_send` modes

- **`command`** — Example: `e /path/to/file`, `w`, `42` (jump to line), `lua vim.lsp.buf.definition()`.
- **`eval`** — Example: `getcwd()`, `line('$')`.
- **`keys`** — Example: `gg`, `G`, `za` (normal-mode keys as typed).

## Multi-instance behavior

Discovery walks standard locations for **socket** files whose names start with `nvim`, up to a limited depth, then probes each candidate with pynvim (dead sockets are skipped). Search roots include `$XDG_RUNTIME_DIR`, `/run/user/$UID`, `$TMPDIR`, and `/tmp`, in that order, with deduplication by resolved path.

- **One** matching instance → tools that need a connection auto-connect.
- **None** → an error explains that Neovim is not running or not discoverable.
- **Several** → `nvim_connect` with no arguments lists them with index, socket path, cwd, and current file. Connect with `index=N`, `socket_path="..."`, or `terminal_pid=...` (PID of the terminal where that Neovim runs; descendants are matched to instance PIDs via `pgrep`).

If **`NVIM_SOCKET_PATH`** is set to a valid socket path, discovery uses **only** that socket (see below).

## Client setup

All examples assume `uvx` can resolve the `nvim-mcp` package (PyPI or your configured index).

### Cursor

`.cursor/mcp.json`:

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

### Claude Desktop

Add the same `mcpServers.nvim-mcp` entry to the Claude Desktop MCP configuration file for your OS.

### Claude CLI

```bash
claude mcp add nvim-mcp -- uvx nvim-mcp
```

### Generic (stdio)

Any MCP client that can spawn a process and speak MCP over stdio:

```bash
uvx nvim-mcp
```

---

## Appendix: Cursor rule (`.cursor/rules/*.mdc`)

Copy or adapt the following as a **Cursor rule** so the model uses nvim-mcp consistently.

````markdown
---
description: Use nvim-mcp to inspect and control the user's Neovim session
alwaysApply: false
---

# Neovim via MCP (nvim-mcp)

The user edits in **Neovim**. Use **nvim-mcp** tools instead of guessing buffer contents from chat.

## Ground truth

- Call **`nvim_state`** to see the current file, cursor line/column, windows, cwd, and modified buffers. Prefer this over inferring from conversation alone.
- If the tool reports multiple instances, call **`nvim_connect`** with `index`, `socket_path`, or `terminal_pid` before relying on other tools.

## Actions in Neovim

- Use **`nvim_send`** with `mode="command"` for ex commands (open file, write, LSP via `lua vim.lsp.buf...`, etc.).
- Use `mode="eval"` when you need a Vimscript expression result.
- Use `mode="keys"` for normal-mode motion and toggles (e.g. folds, jumps).

## Discovering operations

- Call **`nvim_recipes`** with no arguments for a quick list and categories; pass `category` for full detail (navigation, LSP, buffers, etc.).

## Files on disk vs. Neovim

- The assistant often **edits files on disk** with its own tools. Neovim does not auto-reload those changes unless asked.
- After you change a file on disk that is open in Neovim, always call **`nvim_send`** with `input="checktime"` and `mode="command"` so Neovim can reload from disk when the buffer is unchanged; if the buffer is modified, coordinate with the user.
````

---

## Environment variables

| Variable | Meaning |
|----------|--------|
| **`NVIM_SOCKET_PATH`** | If set to a **valid socket** path, discovery considers **only** that Neovim instance (full path resolved; must be a socket). If unset or invalid, normal discovery applies. |

## Recipes reference

Bundled operation lists live in the repo: [src/nvim_mcp/recipes.md](src/nvim_mcp/recipes.md).

## Requirements

- **Python** ≥ 3.10
- **OS:** Linux or macOS
- **Neovim** with RPC socket enabled (default)

## License

MIT — see [LICENSE](LICENSE).
