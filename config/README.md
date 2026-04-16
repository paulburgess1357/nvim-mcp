# Configuration

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

From a local clone, use `uv run` instead:

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

The command is `uvx`, the argument is `nvim-mcp`. From a local clone, use `uv run --directory <path/to/nvim-mcp> nvim-mcp` instead. Use whatever config format your client expects.

</details>

## 2. Add agent rules

Registering the server gives the assistant the tools, but a rule file teaches
it **when and how** to use them.

Run the config generator and pick your tool:

```bash
./config/generate-configs.sh
```

It will generate the appropriate rule file and tell you where to place it:

| Tool   | Global path                          |
|--------|--------------------------------------|
| Cursor | `~/.cursor/rules/nvim-mcp.mdc`      |
| Claude | `~/.claude/CLAUDE.md`                |
| Codex  | `~/.codex/AGENTS.md`                 |

The source template is **[AGENTS-EXAMPLE.md](AGENTS-EXAMPLE.md)** — adjust it
to match your workflow.

## 3. Optional Environment variables

| Variable                          | Default           | Description                                        |
| --------------------------------- | ----------------- | -------------------------------------------------- |
| `NVIM_SOCKET_PATH`                | _(auto-discover)_ | Skip discovery; connect directly to this socket.   |
| `NVIM_MCP_ACTIVE_CONTEXT_LINES`   | `20`              | Lines of context around the cursor in the active window.  |
| `NVIM_MCP_INACTIVE_CONTEXT_LINES` | `20`              | Lines of context around the cursor in inactive windows.   |

## 4. Clearing highlights manually

`clear_highlights` clears via the MCP tool, but you can also clear them directly in Neovim. Add this to your config:

```lua
vim.api.nvim_create_user_command('McpClearHighlights', function()
  local ns = vim.api.nvim_create_namespace('mcp_highlight')
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
  end
end, {})
```

Then `:McpClearHighlights` removes all MCP highlights from every buffer.
