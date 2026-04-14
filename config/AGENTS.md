# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `nvim_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **Read open buffers with `nvim_buf_read`, not disk.** For files
   listed in `buffers`, the buffer is the source of truth.
2. **Edit with `nvim_buf_edit`.** It writes directly to the buffer —
   no `:checktime` needed, undo works, unsaved changes are preserved.
   Fall back to disk only if the file isn't open or the tool fails.
2. **Check diagnostics when fixing code.** `nvim_state` includes a
   `diagnostics_summary` per window. Use `nvim_diagnostics` to get full
   details (file, line, severity, message) when you need them.
3. **The user's question almost always relates to the active file window**
   (buftype ""), not a terminal or special buffer.
4. **Preserve the user's active window.** If the terminal is active and
   you need to act on a file window, switch with `wincmd p`, act, then
   switch back.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
