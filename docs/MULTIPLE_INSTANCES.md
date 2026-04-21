# Multiple Neovim instances

nvim-mcp can work with more than one Neovim instance at a time.

## Auto-discovery

When multiple instances are running, the `connect` tool lists all discovered sessions. The [agent rules](../config/README.md#2-add-agent-rules) instruct the agent to ask you which one to use rather than guessing.

<details open>
<summary>Demo — listing multiple Neovim sessions</summary>

<video src="https://github.com/user-attachments/assets/15fa449e-0296-4815-8bfc-b9c33b5075bb"></video>

</details>

## Named sockets

If you want a predictable name you can target directly, start Neovim with `--listen`:

```bash
nvim --listen /tmp/nvim-a.sock
nvim --listen /tmp/nvim-b.sock
```

Then tell the agent which one to use:

```
Connect to the Neovim instance at /tmp/nvim-a.sock
```

You can also set `NVIM_ADDRESS` in your MCP config to always connect to a specific socket without the agent needing to discover it. See the [configuration guide](../config/README.md#3-environment-variables-optional) for details.

<details open>
<summary>Demo — connecting to a named socket</summary>

<video src="https://github.com/user-attachments/assets/4e52570a-585e-4b5a-a430-16fffcce44cc"></video>

</details>
