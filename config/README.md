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

```bash
claude mcp add nvim-mcp -- uvx nvim-mcp
```

Add `--scope user` to make it global, or `--scope project` for the current project only.

From a local clone:

```bash
claude mcp add nvim-mcp -- uv run --directory <path/to/nvim-mcp> nvim-mcp
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
it **when and how** to use them. Copy the one that matches your client into
your project:

- **[AGENTS.md](AGENTS.md)** — Rule file for Claude Code, Codex, and others.
  Copy to your project root (or wherever your tool reads agent instructions).
- **Cursor** — Run `./config/generate-mdc.sh` to create `nvim-mcp.mdc`, then
  copy it to `.cursor/rules/` in your project.

These are starting points. Adjust them to match your workflow.
