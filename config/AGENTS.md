# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge. `nvim_recipes` is a cheat sheet,
not a limit.

## nvim_send modes

- **command** (default) — ex command, no leading `:`.
- **eval** — evaluate expression, return result.
- **keys** — keystrokes. Esc is prepended automatically, so multi-mode
  sequences must be one call: `"17GVG"` not `"17GV"` then `"G"`.

## Rules

1. **Never edit text through Neovim.** Edit on disk, then `checktime`.
2. **Use `nvim_state` before acting** to see file, cursor, mode, and windows.
3. **Never read line numbers from the terminal display** — use `nvim_state`
   or read the file directly.
4. **Preserve the user's active window.** If the terminal is active and you
   need to act on a file window, switch with `wincmd p`, act, then switch
   back. Disk edits only need `checktime` — no window switch.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
