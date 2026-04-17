# Configuration

This guide covers everything beyond basic installation: registering the MCP server with your client, adding agent rules, and tuning optional settings.

For a quick overview and getting-started steps, see the [main README](../README.md).

---

## 1. Register the MCP server

Add nvim-mcp to your MCP client so it knows how to launch the server.

<details>
<summary><strong>Cursor</strong></summary>

Add to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

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

From a local clone:

```json
{
  "mcpServers": {
    "nvim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "<path/to/nvim-mcp>", "nvim-mcp"]
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code</strong></summary>

**Global** (available in every project):

```bash
claude mcp add nvim-mcp --scope user -- uvx nvim-mcp
```

**Project only** (current project):

```bash
claude mcp add nvim-mcp --scope project -- uvx nvim-mcp
```

From a local clone:

```bash
claude mcp add nvim-mcp --scope user -- uv run --directory <path/to/nvim-mcp> nvim-mcp
```

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to `claude_desktop_config.json` ([location varies by OS](https://docs.anthropic.com/en/docs/agents-and-tools/mcp/quickstart#configure-claude-for-desktop)):

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

From a local clone:

```json
{
  "mcpServers": {
    "nvim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "<path/to/nvim-mcp>", "nvim-mcp"]
    }
  }
}
```

</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex mcp add nvim-mcp -- uvx nvim-mcp
```

Or add to `~/.codex/config.toml`:

```toml
[mcp_servers.nvim-mcp]
command = "uvx"
args = ["nvim-mcp"]
```

From a local clone:

```bash
codex mcp add nvim-mcp -- uv run --directory <path/to/nvim-mcp> nvim-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.nvim-mcp]
command = "uv"
args = ["run", "--directory", "<path/to/nvim-mcp>", "nvim-mcp"]
```

</details>

<details>
<summary><strong>Other MCP clients</strong></summary>

The command is `uvx`, the argument is `nvim-mcp`. From a local clone, use `uv run --directory <path/to/nvim-mcp> nvim-mcp` instead. Adapt to whatever config format your client expects.

</details>

## 2. Add agent rules

Registering the server gives the agent the tools, but a rule file teaches it **when and how** to use them.

Run the generator and pick your client:

```bash
./config/generate-configs.sh
```

It produces the appropriate rule file and tells you where to place it:

| Client | Default path |
| ------ | ------------ |
| Cursor | `~/.cursor/rules/nvim-mcp.mdc` |
| Claude | `~/.claude/CLAUDE.md` |
| Codex  | `~/.codex/AGENTS.md` |

The source template is [AGENTS-EXAMPLE.md](AGENTS-EXAMPLE.md) — adjust it to match your workflow.

## 3. Environment variables (optional)

These are only needed to override defaults. Most setups work without any of them.

Because the MCP server runs as a separate process spawned by your client, set these in the MCP config's `env` field — your shell environment has no effect.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `NVIM_ADDRESS` | _(auto-discover)_ | Connect directly to a Neovim instance, skipping discovery. Accepts a Unix socket path or `host:port`. |
| `NVIM_MCP_ACTIVE_CONTEXT_LINES` | `20` | Lines of context around the cursor in the active window. |
| `NVIM_MCP_INACTIVE_CONTEXT_LINES` | `20` | Lines of context around the cursor in inactive windows. |

### When do you need `NVIM_ADDRESS`?

Auto-discovery finds Neovim sockets whose filename starts with `nvim` in standard runtime directories (`$XDG_RUNTIME_DIR`, `/run/user/<uid>`, `/tmp`). You need `NVIM_ADDRESS` when:

- Your socket has a **custom name** (e.g. `nvim --listen /tmp/my-editor.sock`)
- You're using a **TCP address** (e.g. `nvim --listen 127.0.0.1:6666`)

Example `env` block for Cursor (`.cursor/mcp.json`) — adapt for your client:

```jsonc
{
  "mcpServers": {
    "nvim-mcp": {
      "command": "uvx",
      "args": ["nvim-mcp"],
      "env": {
        "NVIM_ADDRESS": "/tmp/my-editor.sock"  // or "127.0.0.1:6666"
        // "NVIM_MCP_ACTIVE_CONTEXT_LINES": "30",
        // "NVIM_MCP_INACTIVE_CONTEXT_LINES": "10"
      }
    }
  }
}
```

## 4. Clearing highlights manually

`clear_highlights` removes MCP highlights via the tool, but you can also clear them directly in Neovim. Add this to your Neovim config:

```lua
vim.api.nvim_create_user_command('McpClearHighlights', function()
  local ns = vim.api.nvim_create_namespace('mcp_highlight')
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
  end
end, {})
```

Then `:McpClearHighlights` removes all MCP highlights from every buffer.
