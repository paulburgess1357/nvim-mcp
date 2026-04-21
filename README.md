# nvim-mcp

[![PyPI](https://img.shields.io/pypi/v/nvim-mcp)](https://pypi.org/project/nvim-mcp/)

An [MCP](https://modelcontextprotocol.io/) server that gives AI agents first-class access to your running Neovim session. It connects through Neovim's native msgpack-RPC socket — no plugins required.

Works with Cursor, Claude Code, Codex, and any MCP-compatible client.

## What agents can do

- **See what you see** — editor mode, working directory, open buffers, window layout, cursor context, folds, selections, marks, and diagnostics.
- **Edit buffers in memory** — find-and-replace or full rewrites with immediate feedback and full undo support. Nothing touches disk until you save.
- **Run any Vim command** — `:w`, `:e`, `:vsplit`, macros, or anything else you could type at the command line.
- **Send keystrokes** — navigate, enter insert mode, trigger mappings.
- **Query LSP diagnostics** — errors, warnings, and hints across one buffer or the whole session.
- **Annotate code with highlights** — colored extmarks to draw your attention to specific lines.
- **Work with multiple instances** — auto-discovers running sessions and connects to the right one. See [multiple instances](docs/MULTIPLE_INSTANCES.md).

Anything you can do in Neovim, the agent can too. See the [full tool reference](docs/TOOLS.md) for details.

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

<details>
<summary>Multiple Neovim instances</summary>

<video src="https://github.com/user-attachments/assets/15fa449e-0296-4815-8bfc-b9c33b5075bb"></video>

</details>

## Quick start

nvim-mcp runs via [uv](https://docs.astral.sh/uv/) (recommended) or [Nix](https://nixos.org/download/).

1. **Install a launcher.**

   <details open>
   <summary><strong>uv</strong></summary>

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   </details>

   <details>
   <summary><strong>Nix</strong></summary>

   Install [Nix](https://nixos.org/download/) — flakes must be enabled.

   </details>

2. **Register the MCP server** with your client. Example for Cursor (`.cursor/mcp.json`):

   <details open>
   <summary><strong>With uv</strong></summary>

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

   </details>

   <details>
   <summary><strong>With Nix</strong></summary>

   ```json
   {
     "mcpServers": {
       "nvim-mcp": {
         "command": "nix",
         "args": ["run", "github:paulburgess1357/nvim-mcp"]
       }
     }
   }
   ```

   </details>

   For Claude Code, Codex, Claude Desktop, and other clients, see the [configuration guide](config/README.md).

3. **Add agent rules — do not skip this.** Without rules, the agent has the tools but doesn't know *when or how* to use them, and behavior will be unreliable. See the [configuration guide](config/README.md#2-add-agent-rules) for setup.

4. **Start Neovim** — on most Linux systems it listens on a Unix socket automatically and is discovered by nvim-mcp. If auto-discovery doesn't work, see [environment variables](config/README.md#3-environment-variables-optional). Running multiple instances? See [multiple instances](docs/MULTIPLE_INSTANCES.md).

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
- Neovim ≥ 0.11 ([older versions](config/README.md#3-environment-variables-optional) work with `--listen` and `NVIM_ADDRESS`)

## License

MIT — see [LICENSE](LICENSE).
