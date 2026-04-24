# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `get_state_brief` at the START of every turn — before
any nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.
Use the full `get_state` only when you need deep context (folds, marks,
diagnostics, highlights, all windows).**

1. **If a file is in `buffers`, always use buffer tools — not disk.**
   Read with `read_full_buf` (or `read_buf_range` for a slice).
   Edit with `find_and_replace_buf` (or `write_full_buf` for full content).
   This ensures the user sees changes immediately and gets undo.
   Fall back to disk only if the file isn't in `buffers`.
2. **The user's context is the active window.** If the active window
   is a terminal, the user's file context is the alternate window.
   When opening files in that case, use
   `send_command(["wincmd p", "e <file>", "wincmd p"])`.
   If the terminal is the only window, use
   `send_command("vsplit <file>")` to avoid replacing it.
3. **Keep the terminal window in place when splitting.** If a terminal
   window exists, open new splits from a non-terminal window so the
   terminal stays where it is. Switch to a file window first
   (`wincmd p` or target it directly), run the split there, then
   switch back if needed.

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
one — don't guess
