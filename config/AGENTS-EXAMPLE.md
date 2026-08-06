# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## Rules

**⚠ CRITICAL: Call `get_state_brief` at the START of every turn — before
any nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.
Use the full `get_state` only when you need deep context (folds, marks,
diagnostics, highlights, virtual text, all windows).**

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

## Terminals

**To put text into a terminal, use `send_to_terminal` — never
`send_keys`, insert mode, or the buffer edit tools (terminal buffers
are not editable).** It writes to the terminal's job channel, so it
works regardless of focus or mode and never moves the user's cursor.

- Open terminals are listed under `terminals` in `get_state_brief` /
  `get_state`; target one by its `buf` or `name`. With a single
  terminal open, the argument can be omitted.
- Default (`submit=false`): the text sits at the prompt for the user
  to review and press Enter. This is almost always what you want.

**⚠ MANDATORY: never pass `submit=true` unless the user has
explicitly asked for the command to be RUN in that message. "Put",
"paste", "type", or "prepare" a command always means `submit=false`.
Suggesting a command yourself is not permission to run it. When in
doubt, use `submit=false` and let the user press Enter.**

## Colors

Both `highlight_range` and `add_virtual_text` accept the same two
color formats:

- Hex code (e.g. `#3b4048`) — used as-is.
- Highlight group name (e.g. `Comment`, `DiagnosticError`) — adapts
  to the user's colorscheme. For `highlight_range`, the group's
  foreground color is used as the line background. For
  `add_virtual_text`, the group is used directly.

Unknown names (including bare color literals like `Red` or
`darkgreen`) return an error. Use either a hex code or a valid
highlight group.

### Recommended highlight groups

When using `highlight_range` or `add_virtual_text`, prefer these
groups so the visual semantics stay consistent and adapt to the
colorscheme:

- Notes / context (default for both tools): `Comment`
- Errors / problems: `DiagnosticError`
- Warnings / caution: `DiagnosticWarn`
- Info / context: `DiagnosticInfo`
- Hints / suggestions: `DiagnosticHint`
- Good / success: `DiagnosticOk`

Pass the group name as the `color` argument
(e.g. `color="DiagnosticError"`). Both tools default to `Comment`
when no color is provided.

## Virtual text

**⚠ MANDATORY: every `add_virtual_text` / `add_virtual_texts` text item
MUST start with `※ ` (U+203B, "Reference Mark"). No exceptions, every
call, every item. Example: `text=["※ swap if reversed"]`.**

- Keep each annotation **single-line and short**. No `\n`. One item per
  `text` list. If you need more, place several short annotations on
  adjacent lines instead.
- `color`: default `Comment`. Use a `Diagnostic*` group only when
  semantics demand it.
- `position`: default `"eol"`. Use `"above"` / `"below"` only when the
  annotated line is already long.

## Multi-instance

Multiple Neovim instances: `connect` lists them. Ask the user which
one — don't guess
