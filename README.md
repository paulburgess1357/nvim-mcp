# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

**nvim-mcp** is an [MCP](https://modelcontextprotocol.io/) server that gives AI assistants (Cursor, Claude, and others) full access to a running **Neovim** session. The assistant sees what you see — cursor position, visible code, window layout, visual selections — and can send keystrokes, run commands, or read buffer contents.

It talks to Neovim directly over its default **Unix socket** using msgpack-RPC and discovers running instances automatically.

## Demos

<details open>
<summary>Using nvim-mcp with a terminal inside Neovim</summary>

<video src="https://github.com/user-attachments/assets/93fd17a6-0f93-48db-8428-d1cba51e29f2"></video>

</details>

<details>
<summary>Using nvim-mcp in Cursor</summary>

<video src="https://github.com/user-attachments/assets/388f5f39-ab4d-4747-9eca-e09c666439ee"></video>

</details>

<details>
<summary>Using nvim-mcp across two terminals</summary>

<video src="https://github.com/user-attachments/assets/6de3f7a4-9c12-4a2f-96d9-d02d21935d37"></video>

</details>

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

| Tool                          | Purpose                                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| **`get_state`**               | Snapshot of the session: mode, cwd, buffers, and per-window file, cursor, context, folds, diagnostics. |
| **`get_all_diagnostics`**     | LSP diagnostics from all buffers.                                                                    |
| **`get_buf_diagnostics`**     | LSP diagnostics for a single buffer.                                                                 |
| **`find_and_replace_buf`**    | Find and replace text in a buffer. `old_string` must match exactly once.                             |
| **`write_full_buf`**          | Set the entire content of a buffer.                                                                  |
| **`read_full_buf`**           | Read an entire buffer.                                                                               |
| **`read_buf_range`**          | Read a line range from a buffer. Takes `start_line` and `end_line` (1-indexed).                      |
| **`send_command`**            | Run ex commands (no leading `:`). Single string or list.                                             |
| **`send_keys`**               | Send keystrokes. Esc is prepended automatically.                                                     |
| **`highlight_range`**         | Highlight lines with colored extmarks. Takes `file`, `start_line`, `end_line`, `color`.              |
| **`highlight_ranges`**        | Highlight multiple ranges at once with different colors.                                             |
| **`clear_highlights`**        | Remove all MCP highlights from a buffer.                                                             |
| **`connect`**                 | Connect to a Neovim instance.                                                                        |

## Multi-instance

One Neovim instance running? Tools auto-connect. Multiple? `connect` lists them — pick by `index`, `socket_path`, or `terminal_pid`. Set `NVIM_SOCKET_PATH` to skip discovery entirely.

## Environment

| Variable                          | Default           | Description                                                                    |
| --------------------------------- | ----------------- | ------------------------------------------------------------------------------ |
| `NVIM_SOCKET_PATH`                | _(auto-discover)_ | Skip discovery; connect directly to this socket.                               |
| `NVIM_MCP_ACTIVE_CONTEXT_LINES`   | `20`              | Lines above/below cursor in the active window. Set to `0` to disable.          |
| `NVIM_MCP_INACTIVE_CONTEXT_LINES` | `20`              | Lines above/below cursor in inactive windows. Set to `0` to disable.           |

## Clearing highlights

`clear_highlights` clears a buffer via the MCP tool, but you can also clear them directly in Neovim. Add this to your config:

```lua
vim.api.nvim_create_user_command('McpClearHighlights', function()
  local ns = vim.api.nvim_create_namespace('mcp_highlight')
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
  end
end, {})
```

Then `:McpClearHighlights` removes all MCP highlights from every buffer.

## Setup Test

Open a file in Neovim, then paste this into your AI assistant:

```
For each step: explain what you're about to do, then do it, then tell me
what happened. Wait for me to say "next" before moving on.

1. What file am I in? Highlight the function my cursor is in.
2. Are there any diagnostics? Highlight any lines with errors or warnings.
3. Add a docstring above the function, then show me the diff.
4. Open a vertical split, write a short test for that function, and save both files.
```

## Requirements

- Python ≥ 3.10
- Linux
- Neovim ≥ 0.11

## License

MIT — see [LICENSE](LICENSE).
