"""FastMCP entry point: tools for Neovim discovery, control, and state."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from nvim_mcp.neovim import NeovimManager

mcp = FastMCP("nvim-mcp")
manager = NeovimManager()


@mcp.tool()
async def nvim_connect(
    socket_path: str | None = None,
    terminal_pid: int | None = None,
    index: int | None = None,
) -> str:
    """Connect to a Neovim instance.

    Called with no arguments: auto-connects when exactly one Neovim instance
    is running; lists all instances when multiple are found.

    Optional selection (provide at most one):
    - index: pick from the listed instances (1-based).
    - socket_path: connect directly to a known socket.
    - terminal_pid: find the Neovim instance whose process tree contains
      this PID (useful when Neovim runs inside a specific terminal).

    Other tools auto-connect when a single instance exists.
    """
    return await manager.connect(
        socket_path=socket_path,
        terminal_pid=terminal_pid,
        index=index,
    )


@mcp.tool()
async def nvim_send(
    input: str,
    mode: Literal["command", "eval", "keys"] = "command",
    return_state: bool = True,
) -> str | dict:
    """Send input to Neovim.

    Modes:
    - command (default): ex command, no leading ':'.
      E.g. "e /path/to/file", "w", "42", "wincmd p", "lua vim.print(...)".
    - eval: evaluate a Vimscript expression and return the result.
      E.g. "getcwd()", "line('$')", "expand('%:p')".
    - keys: send keystrokes. Esc is prepended automatically, so the input
      always starts in normal mode. A second call prepends Esc again,
      cancelling any intermediate mode from the previous call. Multi-mode
      sequences must be sent in a single call (e.g. "17GVG", not "17GV"
      then "G"). Ex commands like wincmd do not work in keys mode; use
      command mode for those.

    Returns {"result": ..., "state": {...}} by default, where state is
    the same structure as nvim_state (current at the moment the command
    finished). Set return_state=false to get only the result string.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.send(input=input, mode=mode, return_state=return_state)


@mcp.tool()
async def nvim_state() -> dict:
    """Snapshot of the current Neovim session.

    Top-level fields: mode, cwd, relativenumber, modified_buffers,
    buffer_count, current_tab, tab_count.

    windows — list of visible windows (current tab only). The active
    window is always first. Each entry:
      file, filetype, total_lines, modified, buftype, active, line, col,
      context.
      - buftype: "" for normal file buffers, "terminal" for :terminal,
        "quickfix", "help", etc. for special buffers.
      - context: lines around that window's cursor, each prefixed with its
        absolute line number (e.g. "28:   code here").
      - The active window in visual mode also includes selection
        (start_line, start_col, end_line, end_col).

    Context line counts are controlled by environment variables
    NVIM_MCP_ACTIVE_CONTEXT_LINES (default 20) and
    NVIM_MCP_INACTIVE_CONTEXT_LINES (default 20). Set to 0 to disable.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.get_state()


def main() -> None:
    mcp.run(transport="stdio")
