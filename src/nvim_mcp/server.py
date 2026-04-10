"""FastMCP entry point: tools for Neovim discovery, control, state, and recipes."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from nvim_mcp.neovim import NeovimManager
from nvim_mcp.recipes import get_recipes

mcp = FastMCP("nvim-mcp")
manager = NeovimManager()


@mcp.tool()
async def nvim_connect(
    socket_path: str | None = None,
    terminal_pid: int | None = None,
    index: int | None = None,
) -> str:
    """Connect to a Neovim instance.

    No args = auto-connect if one instance, list all if multiple.
    With index = pick from list (1-based).
    With socket_path = direct connect.
    With terminal_pid = match via process tree.
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
    - command: Run ex command without leading ':'. E.g. "e /path/to/file", "w", "42"
    - eval: Evaluate expression, return result. E.g. "getcwd()", "line('$')"
    - keys: Send keystrokes for navigation. E.g. "gg", "G", "za"
      Esc is prepended automatically to ensure normal mode. This means
      sequences that depend on an intermediate mode (like visual selection)
      MUST be sent in a single call — a second call prepends Esc and cancels
      the mode. E.g. send "17GVG" in one call, NOT "17GV" then "G".

    Auto-connects if only one Neovim instance exists.

    Returns {"result": ..., "state": {...}} by default.
    Set return_state=false to get only the command result string.
    """
    return await manager.send(input=input, mode=mode, return_state=return_state)


@mcp.tool()
async def nvim_state() -> dict:
    """Get structured Neovim state.

    Returns file, line, col, mode, modified status, filetype, total lines,
    cwd, relativenumber, window layout, modified buffers, buffer count, and
    context (lines around the cursor or selection, each prefixed with its
    absolute line number). In visual mode, also includes selection
    (start_line, start_col, end_line, end_col) identifying which context
    lines are selected. Context span is controlled by NVIM_MCP_CONTEXT_LINES
    (default 20; 0 disables).
    """
    return await manager.get_state()


@mcp.tool()
async def nvim_recipes(category: str | None = None) -> str:
    """Get Neovim operation recipes.

    No args = quick reference + category list.
    With category = full recipes for that section.
    """
    return get_recipes(category=category)


def main() -> None:
    mcp.run(transport="stdio")
