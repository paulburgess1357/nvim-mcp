# Neovim via nvim-mcp

The user edits code in Neovim. You control it through nvim-mcp tools.
You already know Vim — use that knowledge.

## nvim_send modes

- **command** (default) — ex command, no leading `:`.
- **eval** — evaluate expression, return result.
- **keys** — keystrokes. Esc is prepended automatically, so multi-mode
  sequences must be one call: `"17GVG"` not `"17GV"` then `"G"`.
  Never put ex commands (e.g. `wincmd`) in keys mode — use separate calls.

## Rules

**⚠ CRITICAL: Call `nvim_state` at the START of every turn — before ANY
nvim-mcp call, file read, or disk edit that touches a Neovim buffer.
Never carry over cursor position or file identity from a previous turn.**

1. **Never edit text through Neovim.** Edit on disk, then `checktime`.
2. **`nvim_state` first, every time.** Call `nvim_state` before ANY action
   that depends on cursor position, file identity, or buffer contents —
   including disk edits to files open in Neovim. The user may have moved
   between turns; never carry over position assumptions from a previous turn.
3. **`nvim_send` returns `{"result": …, "state": …}` by default.** This
   state is current only as of that call. Use `return_state=false` when
   you only need the result string.
4. **Each window has context lines prefixed with absolute line numbers**
   (e.g. `"28:   code here"`). Use them directly — don't guess from memory
   or read from the terminal display. The user's question almost always
   relates to the active window; inactive windows provide background context.
   In visual mode, the active window's entry includes a `selection` range.
5. **Preserve the user's active window.** If the terminal is active and you
   need to act on a file window, switch with `wincmd p`, act, then switch
   back. Disk edits only need `checktime` — no window switch.

## Multi-instance

Multiple Neovim instances: `nvim_connect` lists them. Ask the user which
one — don't guess.
