# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `nvim_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **Edit through the buffer when it has unsaved changes.** If
   `nvim_state` lists a file in `modified_buffers`, use `nvim_buf_edit`
   and `nvim_buf_read` — the disk version is stale. For unmodified
   files, disk edits + `:checktime` are fine. If only one file was
   edited on disk and it's not the active buffer, switch to it.
2. **If you don't have disk edit tools, use `nvim_buf_edit` for all
   edits.** It works the same way regardless of buffer state.
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
