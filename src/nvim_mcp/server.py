"""MCP server entry point: tools for Neovim discovery, control, and state."""

from __future__ import annotations

from importlib.metadata import version

from mcp.server.mcpserver import MCPServer

from nvim_mcp.manager import NeovimManager

mcp = MCPServer("nvim-mcp", version=version("nvim-mcp"))
manager = NeovimManager()


@mcp.tool()
async def connect(
    socket_path: str | None = None,
    terminal_pid: int | None = None,
    index: int | None = None,
) -> dict:
    """Connect to a running Neovim instance over its Unix socket or TCP address.

    Call this before any other tool if the agent is not yet connected.
    Connection is persistent for the session; you only need to call it once
    unless you want to switch instances.

    Called with no arguments: auto-connects when exactly one instance
    is running; returns a list of instances when multiple are found.

    Optional selection (provide at most one):
    - index: pick from the listed instances (1-based).
    - socket_path: connect directly to a known Unix socket or host:port.
    - terminal_pid: find the Neovim instance whose process tree contains
      this PID (useful when Neovim runs inside a specific terminal).

    Returns {connected, cwd, file} on success, or {error} with details
    on failure (e.g. no instances found, connection timeout, bad index).
    """
    return await manager.connect(
        socket_path=socket_path,
        terminal_pid=terminal_pid,
        index=index,
    )


@mcp.tool()
async def send_command(command: str | list[str]) -> dict | list[dict]:
    """Run one or more Vim ex commands in Neovim. This is a mutation tool —
    commands can modify buffers, files on disk, windows, and editor state.

    command: a single command string or a list of strings, without the
      leading ':'. E.g. "w", "e src/main.py", "42", "wincmd v",
      "lua vim.print(...)", or ["wincmd p", "e file.py", "wincmd p"].

    Use this for editor operations that don't have a dedicated tool
    (e.g. saving, opening files, splitting windows, setting options).
    Use `send_keys` instead when you need normal-mode motions or
    operator sequences. Use `find_and_replace_buf` or `write_full_buf`
    for buffer text edits — they are safer and provide undo.

    Returns {output} with the command's captured output, or {error}
    if the command failed. When given a list, returns a list of results
    in the same order; execution stops on the first error.
    """
    return await manager.send_command(command)


@mcp.tool()
async def send_keys(keys: str) -> dict:
    """Send raw keystrokes to Neovim as if typed by the user. This is a
    mutation tool — keystrokes can modify buffers, change mode, and
    trigger editor actions.

    keys: a string of Vim keystrokes. Esc is prepended automatically, so
      input always begins in normal mode. Multi-mode sequences must be sent
      in a single call (e.g. "17GVG", not "17GV" then "G"). Use Vim
      notation for special keys (e.g. "<CR>", "<C-w>v", "<Tab>").

    Use this for normal-mode motions, visual selections, or operator
    sequences. Use `send_command` for ex commands, and
    `find_and_replace_buf` or `write_full_buf` for text edits — they
    are safer and provide structured results.

    Returns {sent} confirming the keys that were dispatched. Keystrokes
    are fire-and-forget; errors from the resulting Vim actions are not
    captured in the return value.
    """
    return await manager.send_keys(keys)


@mcp.tool()
async def send_to_terminal(
    text: str,
    terminal: str | int | None = None,
    submit: bool = False,
) -> dict:
    """Type text into a terminal buffer's running program (usually a shell)
    by writing to its job channel. This is a mutation tool — the text
    reaches the program's stdin as if typed, but is not executed unless
    submit is true.

    text: the text to send, raw. In most shells an embedded newline acts
      like pressing Enter, so multi-line text may execute line by line.
      When submit is false, trailing newlines are stripped so nothing
      runs by accident.
    terminal: which terminal to target — a buffer number or buffer name,
      as listed under `terminals` in `get_state` / `get_state_brief`.
      Names match exactly first, then by unique substring. Omit it when
      exactly one terminal exists; with several open, omitting it
      returns an error listing them.
    submit: false (default) leaves the text at the prompt for the user
      to review and press Enter. true appends a carriage return so the
      program executes it immediately. NEVER pass submit=true unless
      the user has explicitly asked for the command to be run — "put",
      "paste", "type", or "prepare" a command always means
      submit=false. Suggesting a command yourself is not permission to
      run it. When in doubt, use submit=false and let the user press
      Enter.

    Use this whenever text needs to go into a terminal. It works
    regardless of focus, mode, or visibility and never moves the user's
    cursor — unlike `send_keys`, which requires focusing the terminal
    and juggling modes. Terminal buffers cannot be edited with the
    buffer tools.

    Returns {sent, terminal, buf, submitted} on success — sent is the
    byte count actually written. On failure returns {error}, including
    a `terminals` list when the target was missing or ambiguous.
    """
    return await manager.send_to_terminal(
        text=text, terminal=terminal, submit=submit
    )


@mcp.tool()
async def get_all_diagnostics() -> list:
    """Get LSP diagnostics from all open buffers in Neovim. Read-only.

    Use this for a project-wide overview of errors and warnings. Use
    `get_buf_diagnostics` instead when you only need diagnostics for a
    specific file — it is more focused and returns less data.

    Returns a list of {file, line, col, severity, message, source}.
    severity is one of "error", "warning", "info", "hint". Returns an
    empty list when there are no diagnostics. Results depend on which
    LSP servers are attached and which buffers are loaded in Neovim.
    """
    return await manager.get_diagnostics()


@mcp.tool()
async def get_buf_diagnostics(file: str) -> list:
    """Get LSP diagnostics for a single Neovim buffer. Read-only.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.

    Use this when you need diagnostics for one specific file. Use
    `get_all_diagnostics` instead for a project-wide overview.

    Returns a list of {file, line, col, severity, message, source}.
    severity is one of "error", "warning", "info", "hint". Returns an
    empty list when the buffer has no diagnostics.
    """
    return await manager.get_diagnostics(file=file)


@mcp.tool()
async def find_and_replace_buf(
    file: str,
    old_string: str,
    new_string: str,
) -> dict:
    """Find and replace text in a Neovim buffer. The edit happens in-memory
    and is fully undoable — nothing is written to disk until the user saves.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
    old_string: the exact text to find. Must match exactly once in the
      buffer; returns an error if not found or if it matches multiple
      locations. Include surrounding lines to disambiguate.
    new_string: the replacement text.

    Creates the buffer if it doesn't already exist. Use this for targeted
    edits. Use `write_full_buf` instead when replacing the entire buffer
    content. Use `read_full_buf` or `read_buf_range` first if you need
    to see the current content before editing.

    Returns {start_line, lines_removed, lines_added, total_lines} on
    success, or {error} with a message on failure.
    """
    return await manager.edit_buffer(
        file=file, new_string=new_string, old_string=old_string
    )


@mcp.tool()
async def write_full_buf(
    file: str,
    content: str,
) -> dict:
    """Replace the entire content of a Neovim buffer. The edit happens
    in-memory and is fully undoable — nothing is written to disk until
    the user saves.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
    content: the full new text for the buffer.

    Creates the buffer if it doesn't already exist. Use this when you
    need to rewrite the whole file. Use `find_and_replace_buf` instead
    for targeted edits that preserve surrounding content.

    Returns {total_lines} with the new line count.
    """
    return await manager.edit_buffer(file=file, new_string=content)


@mcp.tool()
async def read_full_buf(file: str) -> dict:
    """Read the full content of a Neovim buffer. Read-only; reads from
    Neovim's in-memory buffer, which may differ from the file on disk
    if there are unsaved changes.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.

    Use this when you need to see the entire file. Use `read_buf_range`
    instead when you only need a specific section — it returns less data.

    Returns {lines, total_lines}. lines is a list of strings, each
    prefixed with its 1-based line number (e.g. "1: first line").
    """
    return await manager.read_buffer(file=file)


@mcp.tool()
async def read_buf_range(
    file: str,
    start_line: int,
    end_line: int,
) -> dict:
    """Read a specific line range from a Neovim buffer. Read-only; reads
    from Neovim's in-memory buffer, which may differ from the file on
    disk if there are unsaved changes.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.
    start_line: first line to read (1-indexed, inclusive).
    end_line: last line to read (1-indexed, inclusive). Out-of-range
      values are clamped to the buffer bounds. If start_line > end_line
      they are swapped automatically.

    Use this when you only need a section of a file. Use `read_full_buf`
    instead when you need the entire buffer.

    Returns {lines, total_lines}. lines is a list of strings, each
    prefixed with its 1-based line number (e.g. "10: some code").
    """
    return await manager.read_buffer(
        file=file, start_line=start_line, end_line=end_line
    )


@mcp.tool()
async def get_state() -> dict:
    """Full snapshot of the current Neovim session. Read-only — does not
    modify any editor state.

    Use `get_state_brief` for quick orientation at the start of a turn.
    Use this when you need the complete picture: all window details,
    folds, marks, diagnostics summaries, highlights, virtual text, and
    indent settings.

    Returns: mode (normal/insert/visual/etc.), cwd, buffers (relative
    paths of all listed buffers), modified_buffers, current_tab, tab_count,
    and terminals — a list of open terminal buffers as {buf, name,
    visible}, present only when at least one exists (targets for
    `send_to_terminal`).

    windows — list of visible windows (current tab only). The active
    window is always first, the alternate window (previous) is second.
    Each window entry contains:
      file (path relative to cwd), filetype, total_lines, modified,
      buftype ("file" for normal buffers, "terminal", etc.),
      line, col, indent: {expandtab, shiftwidth, tabstop}.
      Optional per-window fields (present when applicable):
      - role: "active" or "alternate".
      - context: numbered lines surrounding the cursor.
      - selection: {start_line, start_col, end_line, end_col} in visual modes.
      - folds: list of [start, end] closed fold ranges.
      - diagnostics_summary: {error, warning, info, hint} counts.
      - marks: list of {mark, line, col} for lowercase (a-z) buffer marks.
      - mcp_highlights: list of {start_line, end_line, color} for active highlights.
      - mcp_virtual_text: list of {line, position, lines, color} for active virtual text.
    """
    return await manager.get_state()


@mcp.tool()
async def get_state_brief() -> dict:
    """Lightweight snapshot of the Neovim session for quick orientation.
    Read-only — does not modify any editor state.

    Use this at the start of each turn to see what the user is working
    on. Use `get_state` instead when you need the full picture: all
    windows, folds, marks, diagnostics summaries, highlights, virtual
    text, and indent settings.

    Returns: mode (normal/insert/visual/etc.), cwd, buffers (relative
    paths of all listed buffers), modified_buffers, and active_window:
    {file, filetype, total_lines, modified, buftype, line, col, context}.
    context is a short list of numbered lines around the cursor.

    If an alternate window exists, also returns alternate_window with
    the same fields. When terminal buffers exist, returns terminals — a
    list of {buf, name, visible} (targets for `send_to_terminal`).
    """
    return await manager.get_state_brief()


@mcp.tool()
async def highlight_range(
    file: str,
    start_line: int,
    end_line: int,
    color: str = "Comment",
) -> dict:
    """Add a colored line highlight to a Neovim buffer. This is a visual
    annotation only — it does not modify buffer content and is not
    persisted to disk. Highlights stack; calling this multiple times adds
    more highlights without removing previous ones.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.
    start_line: first line to highlight (1-indexed, inclusive).
    end_line: last line to highlight (1-indexed, inclusive). Out-of-range
      values are clamped. If start_line > end_line they are swapped.
    color: a hex color (e.g. "#3b4048") or a Neovim highlight group name
      (e.g. "Comment", "DiagnosticError"). For groups, the resolved
      foreground color becomes the line background — so highlights adapt
      to the user's colorscheme. Defaults to "Comment". Unknown names
      (including bare color literals like "Red") return an error.

    Use this for a single highlight. Use `highlight_ranges` to apply
    multiple highlights in one call. Use `clear_highlights` to remove
    all highlights from a buffer.

    Returns {highlighted} with the number of lines highlighted, or
    {error} with a message on failure.
    """
    return await manager.highlight_buffer(
        file=file,
        start_line=start_line,
        end_line=end_line,
        color=color,
    )


@mcp.tool()
async def highlight_ranges(
    highlights: list[dict],
) -> list[dict]:
    """Add colored line highlights to one or more Neovim buffers in a single
    call. This is a visual annotation only — it does not modify buffer
    content and is not persisted to disk. Highlights stack; calling this
    adds more highlights without removing previous ones.

    highlights: a list of dicts. Each dict requires:
      - file: path relative to Neovim's cwd (as shown in `get_state`).
        The buffer must be open in Neovim.
      - start_line: first line (1-indexed, inclusive).
      - end_line: last line (1-indexed, inclusive).
      - color (optional): hex color (e.g. "#5f3a3a") or Neovim highlight
        group name (e.g. "Comment", "DiagnosticError"). For groups, the
        resolved foreground color becomes the line background. Defaults
        to "Comment". Unknown names (including bare color literals like
        "Red") return an error. Out-of-range lines are clamped.

    Use this when you need to highlight several ranges at once (possibly
    across different files). Use `highlight_range` for a single range.
    Use `clear_highlights` to remove all highlights from a buffer.

    Returns a list of {highlighted} results in the same order as the
    input. Raises an error if any item is missing required keys.

    Example: [{"file": "foo.py", "start_line": 1, "end_line": 3,
               "color": "DiagnosticError"},
              {"file": "foo.py", "start_line": 10, "end_line": 12}]
    """
    required_keys = ("file", "start_line", "end_line")
    results = []
    for idx, h in enumerate(highlights):
        missing = [k for k in required_keys if k not in h]
        if missing:
            raise ValueError(
                f"highlights[{idx}] missing required key(s): {', '.join(missing)}"
            )
        results.append(
            await manager.highlight_buffer(
                file=h["file"],
                start_line=h["start_line"],
                end_line=h["end_line"],
                color=h.get("color", "Comment"),
            )
        )
    return results


@mcp.tool()
async def clear_highlights(file: str) -> dict:
    """Remove all MCP highlights from a Neovim buffer. Only removes
    highlights added by `highlight_range` or `highlight_ranges` — does
    not affect syntax highlighting, LSP highlights, or other plugins.
    Does not modify buffer content. Safe to call even if no highlights
    are present (returns {cleared: true} either way).

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.

    Use this to clean up highlights after an annotation workflow.
    Use `highlight_range` or `highlight_ranges` to add highlights.
    """
    return await manager.clear_highlights(file=file)


@mcp.tool()
async def add_virtual_text(
    file: str,
    line: int,
    text: list[str],
    position: str = "eol",
    color: str = "Comment",
) -> dict:
    """Add a virtual text annotation to a Neovim buffer. Visual only —
    the buffer's actual content is unchanged and nothing is written to
    disk. Annotations stack; multiple calls accumulate.

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.
    line: 1-indexed anchor line. Out-of-range values are clamped.
    text: list of strings, one per virtual line. Must be non-empty.
      When position is "eol", exactly one item is allowed.
    position: where the annotation appears relative to the anchor line.
      One of "eol" (after end of line), "above" (between previous and
      anchor lines), or "below" (between anchor and next lines).
      Defaults to "eol".
    color: a Neovim highlight group name (e.g. "Comment",
      "DiagnosticError") or a hex color (e.g. "#7a9ad4"). Defaults to
      "Comment", which adapts to the user's colorscheme. Unknown names
      (including bare color literals like "Red") return an error.

    Use this for a single annotation. Use `add_virtual_texts` for
    multiple annotations in one call. Use `clear_virtual_texts` to
    remove all MCP virtual text from a buffer.

    Returns {added: 1} on success, or {error} with a message on failure.
    """
    return await manager.add_virtual_text(
        file=file, line=line, text=text, position=position, color=color,
    )


@mcp.tool()
async def add_virtual_texts(
    items: list[dict],
) -> list[dict]:
    """Add multiple virtual text annotations to Neovim buffers in a
    single call. Visual only — buffer content is unchanged. Annotations
    stack; calling this adds more without removing previous ones.

    items: a list of dicts. Each dict requires:
      - file: path relative to Neovim's cwd. Buffer must be open.
      - line: 1-indexed anchor line. Out-of-range values are clamped.
      - text: list of strings, one per virtual line. Non-empty.
        EOL position requires exactly one item.
      And optionally:
      - position: "eol" (default), "above", or "below".
      - color: hex color (e.g. "#7a9ad4") or Neovim highlight group
        name (e.g. "Comment", "DiagnosticError"). Defaults to "Comment".
        Unknown names (including bare color literals like "Red") return
        an error.

    Use this when you need to add several annotations at once (possibly
    across different files). Use `add_virtual_text` for a single
    annotation. Use `clear_virtual_texts` to remove all MCP virtual
    text from a buffer.

    Returns a list of {added: 1} results in input order. Raises a
    ValueError if any item is missing a required key. Iteration is
    sequential: if item N fails validation or the manager raises,
    items 0..N-1 have already been applied (call `clear_virtual_texts`
    to roll back).

    Example: [{"file": "foo.py", "line": 10, "text": ["this is the bug"]},
              {"file": "foo.py", "line": 20, "text": ["note one", "note two"],
               "position": "above", "color": "DiagnosticInfo"}]
    """
    required_keys = ("file", "line", "text")
    results = []
    for idx, item in enumerate(items):
        missing = [k for k in required_keys if k not in item]
        if missing:
            raise ValueError(
                f"items[{idx}] missing required key(s): {', '.join(missing)}"
            )
        results.append(
            await manager.add_virtual_text(
                file=item["file"],
                line=item["line"],
                text=item["text"],
                position=item.get("position", "eol"),
                color=item.get("color", "Comment"),
            )
        )
    return results


@mcp.tool()
async def clear_virtual_texts(file: str) -> dict:
    """Remove all MCP virtual text annotations from a Neovim buffer.
    Only removes annotations added by `add_virtual_text` or
    `add_virtual_texts` — does not affect highlights, LSP virtual
    text, inlay hints, or other plugins. Does not modify buffer
    content. Safe to call even if no annotations are present
    (returns {cleared: true} either way).

    file: path relative to Neovim's cwd (as shown in `get_state` buffers).
      The buffer must already be open in Neovim; returns an error otherwise.

    Use this to clean up after an annotation workflow. Use
    `add_virtual_text` or `add_virtual_texts` to add annotations.
    """
    return await manager.clear_virtual_texts(file=file)


def main() -> None:
    mcp.run(transport="stdio")
