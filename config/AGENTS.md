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
2. **Use `nvim_state` before acting** to see file, cursor, mode, windows,
   and context lines around the cursor. In visual mode, context expands
   around the selection and a `selection` range marks the highlighted lines.
   After the first call, `nvim_send` returns state automatically — you
   rarely need `nvim_state` again mid-conversation.
3. **`nvim_send` returns `{"result": …, "state": …}` by default.** The `state`
   matches `nvim_state`. Use `return_state=false` for the result string only.
4. **Use context lines from state for line numbers** — don't guess from
   memory or read from the terminal display. The `context.start_line` +
   `context.lines` array tells you exactly which code is on which line.
5. **Preserve the user's active window.** If the terminal is active and you
   need to act on a file window, switch with `wincmd p`, act, then switch
   back. Disk edits only need `checktime` — no window switch.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
