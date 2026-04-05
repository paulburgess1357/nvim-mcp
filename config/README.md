# Configuration

This directory contains everything you need to set up nvim-mcp with your AI
assistant.

## 1. Register the MCP server

Your AI tool needs to know how to start nvim-mcp. Pick the setup that matches
your client.

### From PyPI

#### Cursor

Add to `.cursor/mcp.json` (project or `~/.cursor/mcp.json` for global):

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

#### Claude CLI

```bash
claude mcp add nvim-mcp -- uvx nvim-mcp
```

#### Claude Desktop / other clients

Same pattern — command is `uvx`, args `["nvim-mcp"]`.

### From a local clone (development)

If you're developing nvim-mcp, point at the repo instead:

#### Cursor

```json
{
  "mcpServers": {
    "nvim-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/nvim-mcp", "nvim-mcp"]
    }
  }
}
```

#### Claude CLI

```bash
claude mcp add nvim-mcp -- uv run --directory /path/to/nvim-mcp nvim-mcp
```

## 2. Teach the assistant how to use it

Registering the server gives the assistant access to the tools, but a rule file
teaches it **when and how** to use them effectively. The files in this directory
are examples you can copy and adapt:

- **[cursor.mdc](cursor.mdc)** — Cursor rule. Copy to `.cursor/rules/` in your
  project.
- **[AGENTS.md](AGENTS.md)** — Generic agent rule for Claude Code, Codex, and
  others. Copy to your project root (or wherever your tool reads agent
  instructions).

These are starting points. Adjust them to match your workflow — add
project-specific conventions, change what's always-on vs. manual, etc.

## Optional Environment variables

| Variable | Effect |
|----------|--------|
| `NVIM_SOCKET_PATH` | Skip discovery and connect to this socket only. |
