"""FastMCP entry point: tools for Neovim discovery, control, state, and recipes."""

from __future__ import annotations

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
    mode: str = "command",
) -> str:
    """Send input to Neovim.

    Modes:
    - command: Run ex command without leading ':'. E.g. "e /path/to/file", "w", "42"
    - eval: Evaluate expression, return result. E.g. "getcwd()", "line('$')"
    - keys: Send keystrokes for navigation. E.g. "gg", "G", "za"

    Auto-connects if only one Neovim instance exists.
    """
    return await manager.send(input=input, mode=mode)


@mcp.tool()
async def nvim_state() -> dict:
    """Get structured Neovim state.

    Returns file, line, col, mode, modified status, filetype, total lines,
    cwd, relativenumber, window layout, modified buffers, and buffer count.
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
