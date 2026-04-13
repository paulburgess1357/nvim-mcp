# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `nvim_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **Edit on disk, not through Neovim.** Then `:checktime` to reload.
   If only one file was edited and it's not the active buffer, switch
   to it so the user can see the changes.
2. **Read modified buffers from Neovim, not disk.** If `nvim_state`
   lists a file in `modified_buffers`, use `nvim_buf_read` — the disk
   version is stale.
3. **The user's question almost always relates to the active file window**
   (buftype ""), not a terminal or special buffer.
4. **Preserve the user's active window.** If the terminal is active and
   you need to act on a file window, switch with `wincmd p`, act, then
   switch back. Disk edits only need `checktime` — no window switch.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
