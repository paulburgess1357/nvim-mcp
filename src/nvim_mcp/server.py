"""FastMCP entry point: tools for Neovim discovery, control, and state."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from nvim_mcp.neovim import NeovimManager

mcp = FastMCP("nvim-mcp")
manager = NeovimManager()


@mcp.tool()
async def connect(
    socket_path: str | None = None,
    terminal_pid: int | None = None,
    index: int | None = None,
) -> dict:
    """Connect to a Neovim instance.

    Called with no arguments: auto-connects when exactly one instance
    is running; lists all instances when multiple are found.

    Optional selection (provide at most one):
    - index: pick from the listed instances (1-based).
    - socket_path: connect directly to a known socket.
    - terminal_pid: find the Neovim instance whose process tree contains
      this PID (useful when Neovim runs inside a specific terminal).
    """
    return await manager.connect(
        socket_path=socket_path,
        terminal_pid=terminal_pid,
        index=index,
    )


@mcp.tool()
async def send_command(command: str | list[str]) -> dict | list[dict]:
    """Run ex commands in Neovim, no leading ':'.

    Accepts a single command string or a list of commands.
    E.g. "w", "e /path/to/file", "42", "wincmd p",
    "lua vim.print(...)", or ["wincmd p", "checktime", "wincmd p"].
    """
    return await manager.send_command(command)


@mcp.tool()
async def send_keys(keys: str) -> dict:
    """Send keystrokes to Neovim.

    Esc is prepended automatically, so the input always starts in normal
    mode. Multi-mode sequences must be sent in a single call
    (e.g. "17GVG", not "17GV" then "G").
    """
    return await manager.send_keys(keys)


@mcp.tool()
async def get_all_diagnostics() -> list:
    """Get LSP diagnostics from all buffers in Neovim.

    Returns a list of {file, line, col, severity, message, source}.
    """
    return await manager.get_diagnostics()


@mcp.tool()
async def get_buf_diagnostics(file: str) -> list:
    """Get LSP diagnostics for a single Neovim buffer.

    Returns a list of {file, line, col, severity, message, source}.
    """
    return await manager.get_diagnostics(file=file)


@mcp.tool()
async def find_and_replace_buf(
    file: str,
    old_string: str,
    new_string: str,
) -> dict:
    """Find and replace text in a Neovim buffer (in-memory, not disk).

    old_string must match exactly once in the buffer.
    """
    return await manager.edit_buffer(
        file=file, new_string=new_string, old_string=old_string
    )


@mcp.tool()
async def write_full_buf(
    file: str,
    content: str,
) -> dict:
    """Set the entire content of a Neovim buffer (in-memory, not disk).

    Creates the buffer if it doesn't already exist."""
    return await manager.edit_buffer(file=file, new_string=content)


@mcp.tool()
async def read_full_buf(file: str) -> dict:
    """Read an entire Neovim buffer (in-memory, not disk).

    Returns lines prefixed with line numbers. The file must be open
    in Neovim.
    """
    return await manager.read_buffer(file=file)


@mcp.tool()
async def read_buf_range(
    file: str,
    start_line: int,
    end_line: int,
) -> dict:
    """Read a line range from a Neovim buffer (in-memory, not disk).

    Returns lines prefixed with line numbers. Lines are 1-indexed.
    The file must be open in Neovim.
    """
    return await manager.read_buffer(
        file=file, start_line=start_line, end_line=end_line
    )


@mcp.tool()
async def get_state() -> dict:
    """Snapshot of the current Neovim session.

    Returns: mode, cwd, buffers, modified_buffers, current_tab, tab_count.

    windows — list of visible windows (current tab only). The active
    window is always first. Each entry:
      file, filetype, total_lines, modified, buftype, active, line, col.
      Optional per-window fields:
      - context: lines around the cursor with line numbers.
      - selection: {start_line, start_col, end_line, end_col} in visual mode.
      - folds: list of [start, end] closed fold ranges.
      - diagnostics_summary: {error, warning, info, hint} counts.
    """
    return await manager.get_state()


@mcp.tool()
async def highlight_range(
    file: str,
    start_line: int,
    end_line: int,
    color: str = "#3b4048",
) -> dict:
    """Highlight lines in a Neovim buffer with colored annotations.

    Does not modify buffer content. Lines are 1-indexed. color is any
    Neovim color name or hex value (e.g. "DarkGreen", "#334455").
    """
    return await manager.highlight_buffer(
        file=file, start_line=start_line, end_line=end_line, color=color,
    )


@mcp.tool()
async def highlight_ranges(
    highlights: list[dict],
) -> list[dict]:
    """Apply multiple highlights at once.

    Each item in highlights must have: file, start_line, end_line.
    Optional: color (hex or name, defaults to "#3b4048").

    Example: [{"file": "foo.py", "start_line": 1, "end_line": 3, "color": "#5f3a3a"},
              {"file": "foo.py", "start_line": 10, "end_line": 12}]
    """
    results = []
    for h in highlights:
        results.append(await manager.highlight_buffer(
            file=h["file"],
            start_line=h["start_line"],
            end_line=h["end_line"],
            color=h.get("color", "#3b4048"),
        ))
    return results


@mcp.tool()
async def clear_highlights(file: str) -> dict:
    """Remove all MCP highlights from a Neovim buffer."""
    return await manager.clear_highlights(file=file)


def main() -> None:
    mcp.run(transport="stdio")
