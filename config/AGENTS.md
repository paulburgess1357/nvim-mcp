# Neovim via nvim-mcp

The user edits code in **Neovim**. You have full access to their editor through
the nvim-mcp MCP server (4 tools).

## nvim_send — the universal interface

`nvim_send` is your primary tool. You already know Vim — use that knowledge
directly. Any ex command, Vimscript expression, or key sequence works through
this single tool. The recipes (`nvim_recipes`) are a reference, not a boundary.

**Modes:**

- `command` (default) — ex command without leading `:`.
  Examples: `"e /path/to/file"`, `"42"` (go to line), `"w"`, `"vs other.py"`,
  `"lua vim.lsp.buf.definition()"`, `"checktime"`
- `eval` — evaluate a Vimscript expression, returns the result.
  Examples: `"getcwd()"`, `"line('$')"`, `"expand('%:p')"`
- `keys` — normal-mode keystrokes (Esc is prepended automatically).
  Examples: `"gg"`, `"G"`, `"za"`, `"zR"`

If you know the Vim command for something, use `nvim_send`. The recipes are a
cheat sheet for common operations, not the extent of what's possible.

## Editing boundary

**Never edit text through Neovim.** Use your own file-editing tools to modify
files on disk, then reload Neovim's buffers:

```
nvim_send(input="checktime", mode="command")
```

Always call `checktime` after changing any file that may be open in Neovim.

Neovim is for: navigation, state awareness, LSP operations (definition,
references, rename, diagnostics), and Vim-specific queries (marks, registers,
folds, quickfix). Not for text manipulation.

## nvim_state

Returns structured editor state: current file, line, column, mode, modified
flags, filetype, line count, cwd, relativenumber, window layout, modified
buffer list, buffer count. Call this to understand what the user sees.

**Line numbers:** Use `nvim_state` or read the file directly for accurate line
numbers. Never try to count or parse line numbers from the terminal display —
Neovim typically shows relative numbers in the gutter, which are easy to
misread.

## nvim_recipes

Quick reference for common operations. No arguments returns the top 9
operations plus a list of categories. Pass a category name (case-insensitive)
for full recipes. Categories: files, navigation, buffers, windows & tabs,
marks, registers, folds, LSP & diagnostics.

## nvim_connect

Manages connections to Neovim instances. With one instance running, other tools
auto-connect. With multiple instances, **always ask the user which instance
they mean** before connecting — don't guess. Present the list (cwd and open
file for each) so they can pick. Connect with `index=N`,
`socket_path="..."`, or `terminal_pid=...`.
