# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `nvim_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **Use `nvim_buf_edit` for modified buffers.** If `nvim_state` lists
   a file in `modified_buffers`, the disk version is stale — use
   `nvim_buf_edit` and `nvim_buf_read`. For unmodified files, disk
   edits + `:checktime` work fine. No disk edit tools? Use
   `nvim_buf_edit` for everything.
2. **After a disk edit, show the result.** `:checktime` reloads buffers.
   If only one file was edited and it's not the active buffer, switch
   to it so the user can see the changes.
3. **Check diagnostics when fixing code.** `nvim_state` includes a
   `diagnostics_summary` per window. Use `nvim_diagnostics` to get full
   details (file, line, severity, message) when you need them.
4. **The user's question almost always relates to the active file window**
   (buftype ""), not a terminal or special buffer.
5. **Preserve the user's active window.** If the terminal is active and
   you need to act on a file window, switch with `wincmd p`, act, then
   switch back. Disk edits only need `checktime` — no window switch.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
