"""FastMCP entry point: tools for Neovim discovery, control, and state."""

from __future__ import annotations

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
async def nvim_command(command: str | list[str]) -> str | list[str]:
    """Run ex commands in Neovim, no leading ':'.

    Accepts a single command string or a list of commands to run
    sequentially. Returns the output string for each command, or
    "(no output)" when a command produces no output. Errors are
    returned inline as "E: <message>".

    E.g. "w", "e /path/to/file", "42", "wincmd p",
    "lua vim.print(...)", or ["wincmd p", "checktime", "wincmd p"].

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.send_command(command)


@mcp.tool()
async def nvim_keys(keys: str) -> str:
    """Send keystrokes to Neovim.

    Esc is prepended automatically, so the input always starts in normal
    mode. A second call prepends Esc again, cancelling any intermediate
    mode from the previous call. Multi-mode sequences must be sent in a
    single call (e.g. "17GVG", not "17GV" then "G").

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.send_keys(keys)


@mcp.tool()
async def nvim_diagnostics(file: str | None = None) -> list:
    """Get LSP diagnostics from Neovim.

    Returns a list of {file, line, col, severity, message, source}.
    Optional file path to limit to one buffer; omit for all buffers.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.get_diagnostics(file=file)


@mcp.tool()
async def nvim_buf_edit(
    file: str,
    new_string: str,
    old_string: str | None = None,
) -> dict:
    """Edit a Neovim buffer (in-memory, not disk).

    Provide old_string and new_string to find and replace text.
    old_string must match exactly once. Omit old_string to set the
    entire buffer content. Creates the buffer if not already open.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.edit_buffer(
        file=file, new_string=new_string, old_string=old_string
    )


@mcp.tool()
async def nvim_buf_read(
    file: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    """Read lines from a Neovim buffer (in-memory, not disk).

    Returns lines prefixed with line numbers. Optional start_line/end_line
    to read a range. The file must be open in Neovim.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.read_buffer(
        file=file, start_line=start_line, end_line=end_line
    )


@mcp.tool()
async def nvim_state() -> dict:
    """Snapshot of the current Neovim session.

    Top-level fields: mode, cwd, relativenumber, buffers, modified_buffers,
    current_tab, tab_count.
    - buffers: file paths of all open (listed) buffers.
    - modified_buffers: subset of buffers with unsaved changes.

    windows — list of visible windows (current tab only). The active
    window is always first. Each entry:
      file, filetype, total_lines, modified, buftype, active, line, col.
      - buftype: "" for normal file buffers, "terminal" for :terminal,
        "quickfix", "help", etc. for special buffers.
      Optional per-window fields (present when applicable):
      - context: lines around that window's cursor, each prefixed with its
        absolute line number (e.g. "28:   code here").
      - selection: {start_line, start_col, end_line, end_col} in visual mode
        (active window only).
      - folds: list of [start, end] closed fold ranges. Lines inside closed
        folds are hidden from the user.
      - diagnostics_summary: {error, warning, info, hint} counts from LSP.
        Only present when the buffer has diagnostics.

    Context line counts are controlled by environment variables
    NVIM_MCP_ACTIVE_CONTEXT_LINES (default 20) and
    NVIM_MCP_INACTIVE_CONTEXT_LINES (default 20). Set to 0 to disable.

    Auto-connects when exactly one Neovim instance is running.
    """
    return await manager.get_state()


def main() -> None:
    mcp.run(transport="stdio")
