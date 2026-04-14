# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `get_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **If a file is in `buffers`, always use buffer tools — not disk.**
   Read with `read_full_buf` (or `read_buf_range` for a slice).
   Edit with `find_and_replace_buf` (or `write_full_buf` for full content).
   This ensures the user sees changes immediately and gets undo.
   Fall back to disk only if the file isn't in `buffers`.
3. **Check diagnostics when fixing code.** `get_state` includes a
   `diagnostics_summary` per window. Use `get_all_diagnostics` or
   `get_buf_diagnostics` to get full details (file, line, severity,
   message) when you need them.
4. **The user's question almost always relates to the active file window**
   (buftype ""), not a terminal or special buffer.
5. **Preserve the user's active window.** If the terminal is active and
   you need to act on a file window, switch with `wincmd p`, act, then
   switch back.

## Highlight colors

When using `highlight_range`, use these colors:
- Focus (default): `#3b4048`
- Errors / problems: `#5f3a3a`
- Good / additions: `#3a5f3a`
- Info / context: `#2e4a6e`
- Warnings / caution: `#6b5a2a`
- Suggestions / notes: `#4a3a5f`

## Multi-instance

Multiple Neovim instances: `connect` lists them. Ask the user which
one — don't guess.
