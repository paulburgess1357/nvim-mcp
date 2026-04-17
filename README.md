# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

An [MCP](https://modelcontextprotocol.io/) server that gives any AI agent first-class access to your running Neovim session. Agents can see your editor state, read and edit buffers, run commands, send keystrokes, query diagnostics, and annotate code with highlights — all through Neovim's native msgpack-RPC socket.

Works with Cursor, Claude Code, Codex, and any MCP-compatible client.

## Demos

<details open>
<summary>Using nvim-mcp across two terminals</summary>

<video src="https://github.com/user-attachments/assets/6de3f7a4-9c12-4a2f-96d9-d02d21935d37"></video>

</details>

<details>
<summary>Using nvim-mcp with a terminal inside Neovim</summary>

<video src="https://github.com/user-attachments/assets/93fd17a6-0f93-48db-8428-d1cba51e29f2"></video>

</details>

<details>
<summary>Claude and Cursor collaborating in one Neovim instance</summary>

<video src="https://github.com/user-attachments/assets/d92915ec-2108-4166-9911-4d09a5025865"></video>

</details>

<details>
<summary>Using nvim-mcp in Cursor</summary>

<video src="https://github.com/user-attachments/assets/388f5f39-ab4d-4747-9eca-e09c666439ee"></video>

</details>

## Tools

Agents can run any Vim command and send any keystrokes, so anything you can do in Neovim, the agent can too. Dedicated tools handle the most common operations without requiring the agent to construct raw commands:

| Tool | Purpose |
| --- | --- |
| `get_state` | Session snapshot — mode, cwd, buffers, windows, cursor context, folds, selections, marks, diagnostics |
| `send_command` | Run ex commands (`:w`, `:e path`, `:wincmd v`, etc.) |
| `send_keys` | Send keystrokes (Esc is prepended automatically) |
| `read_full_buf` / `read_buf_range` | Read buffer contents with line numbers |
| `find_and_replace_buf` | Exact-match find and replace in a buffer |
| `write_full_buf` | Replace entire buffer contents |
| `get_all_diagnostics` / `get_buf_diagnostics` | LSP diagnostics (errors, warnings, hints) |
| `highlight_range` / `highlight_ranges` | Annotate lines with colored extmarks |
| `clear_highlights` | Remove MCP highlights from a buffer |
| `connect` | Discover and connect to running Neovim instances |

Buffer edits are in-memory — nothing is written to disk until saved. Running instances are auto-discovered; when multiple exist, the agent picks by index, socket path, or terminal PID.

## Setup

1. **Install [uv](https://docs.astral.sh/uv/)** if you don't have it: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Register the MCP server** — example for Cursor (`.cursor/mcp.json`):

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

3. **Add agent rules** — registering the server gives the agent the tools, but a rule file teaches it *when and how* to use them. Run `./config/generate-configs.sh` and pick your client.
4. **Start Neovim** — on most Linux systems it listens on a Unix socket automatically and is discovered by nvim-mcp. If auto-discovery doesn't find your instance (custom socket name, TCP address, etc.), see the [environment variables](config/README.md#3-environment-variables-optional) section.

## Verify it works

Open a file in Neovim and paste this into your AI agent:

```
For each step: explain what you're about to do, then do it, then tell me
what happened. Wait for me to say "next" before moving on.

1. What file am I in? Highlight the function my cursor is in.
2. Are there any diagnostics? Highlight any lines with errors or warnings.
3. Add a docstring above the function, then show me the diff.
4. Open a vertical split, write a short test for that function, and save both files.
```

## Requirements

- Linux
- Python ≥ 3.10
- Neovim ≥ 0.11
- [Older Neovim versions](config/README.md#3-environment-variables-optional) work with `--listen` and `NVIM_ADDRESS`

## License

MIT — see [LICENSE](LICENSE).
